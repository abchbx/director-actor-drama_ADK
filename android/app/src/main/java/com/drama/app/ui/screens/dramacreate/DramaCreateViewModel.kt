package com.drama.app.ui.screens.dramacreate

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.drama.app.data.local.ServerPreferences
import com.drama.app.data.remote.dto.DramaStatusResponseDto
import com.drama.app.data.remote.dto.WsEventDto
import com.drama.app.data.remote.ws.WebSocketManager
import com.drama.app.domain.repository.DramaRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.contentOrNull
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import javax.inject.Inject

/** 单条导演日志 */
data class DirectorLogEntry(
    val elapsedSeconds: Int,
    val message: String,
)

data class DramaCreateUiState(
    val theme: String = "",
    val isCreating: Boolean = false,
    val stormPhase: String? = null,
    val error: String? = null,
    /** 已用时间秒数（无限增长，无上限） */
    val elapsedSeconds: Int = 0,
    /** 导演日志列表（最新在前，最多保留 50 条） */
    val directorLog: List<DirectorLogEntry> = emptyList(),
)

sealed class DramaCreateEvent {
    data class NavigateToDetail(val dramaId: String) : DramaCreateEvent()
}

@HiltViewModel
class DramaCreateViewModel @Inject constructor(
    private val dramaRepository: DramaRepository,
    private val webSocketManager: WebSocketManager,
    private val serverPreferences: ServerPreferences,
) : ViewModel() {

    companion object {
        // 轮询间隔：2 秒一次
        private const val POLL_INTERVAL_MS = 2_000L
        // 最大连续错误数（纯连接问题才终止）
        private const val MAX_CONSECUTIVE_ERRORS = 8
        // 导演日志最大条数
        private const val MAX_LOG_ENTRIES = 50
        // 创建完成的状态值
        private const val STATUS_SETUP = "setup"
        private const val STATUS_ACTING = "acting"
        private const val STATUS_ENDED = "ended"
        // ★ 新增：绝对超时（秒）— 超时后强制导航，避免永久卡在创建页
        private const val FORCE_NAVIGATE_TIMEOUT_SECONDS = 120  // 2分钟（与后端超时一致）

        /** 格式化已用时间为 [Xm Xs] 或 [Xs] */
        fun formatElapsed(seconds: Int): String {
            return if (seconds >= 60) {
                val m = seconds / 60
                val s = seconds % 60
                "${m}m ${s}s"
            } else {
                "${seconds}s"
            }
        }
    }

    private val _uiState = MutableStateFlow(DramaCreateUiState())
    val uiState: StateFlow<DramaCreateUiState> = _uiState.asStateFlow()

    private val _events = MutableSharedFlow<DramaCreateEvent>()
    val events: SharedFlow<DramaCreateEvent> = _events.asSharedFlow()

    private var wsJob: Job? = null
    private var createJob: Job? = null
    private var pollingJob: Job? = null
    private var timerJob: Job? = null
    @Volatile private var navigated = false
    @Volatile private var startTimeMs = 0L
    /** 用户请求创建的主题名，用于导航时作为 dramaId */
    @Volatile private var creatingTheme: String = ""
    /** 是否已通过轮询确认后端主题与 creatingTheme 匹配 */
    @Volatile private var hasConfirmedThemeMatch = false
    /** WS 是否已连接且收到至少一个事件 — 收到后停止轮询以避免风暴 */
    @Volatile private var wsActive = false

    fun createDrama(theme: String) {
        if (theme.isBlank()) return
        startTimeMs = System.currentTimeMillis()
        navigated = false
        hasConfirmedThemeMatch = false
        creatingTheme = theme.trim()  // ★ 记录用户输入的主题，用于后续验证
        _uiState.update {
            it.copy(
                isCreating = true,
                error = null,
                stormPhase = "正在连接服务器...",
                elapsedSeconds = 0,
                directorLog = listOf(DirectorLogEntry(0, "导演开始创作「$theme」")),
            )
        }

        // ── 1. WebSocket 连接：接收 STORM 进度事件 ──
        wsJob?.cancel()
        wsJob = viewModelScope.launch {
            val config = serverPreferences.serverConfig.first() ?: run {
                addLog("未配置服务器地址")
                _uiState.update { it.copy(error = "未配置服务器地址", isCreating = false) }
                return@launch
            }
            webSocketManager.connect(config.ip, config.port, config.token, config.baseUrl)
                .catch { e ->
                    addLog("⚠️ WebSocket 连接失败: ${e.message}，降级为纯轮询模式")
                    wsActive = false
                    // ★ 修复：WS 断连后不阻塞，轮询仍然可以触发导航
                }
                .collect { event ->
                    wsActive = true
                    handleStormEvent(event)
                }
        }

        // ── 2. REST API 调用：触发后端创建剧本（非阻塞） ──
        // 关键优化：立即启动轮询，不等 /start 返回。
        // 后端的 /start 是阻塞式的（run_command_and_collect 要等整个STORM流程完成才返回），
        // 可能持续数分钟。如果等它返回才轮询，用户会长时间卡在"连接中"。
        startPolling()

        createJob?.cancel()
        createJob = viewModelScope.launch {
            dramaRepository.startDrama(theme)
                .onSuccess {
                    addLog("后端已接收创建请求")
                    _uiState.update { it.copy(stormPhase = "导演正在构思世界观...") }
                    // 轮询已在上面启动，此处无需重复调用
                }
                .onFailure { e ->
                    addLog("创建请求失败：${e.message}")
                    // ★ 关键：请求失败后必须停止所有后台任务，防止轮询/超时泄漏
                    navigated = true
                    cancelJobsOnly()
                    _uiState.update {
                        it.copy(
                            isCreating = false,
                            error = "创建请求失败: ${e.message}",
                            stormPhase = null,
                        )
                    }
                }
        }

        // ── 3. 计时器（无上限，仅记录已用时间）+ 超时强制导航 ──
        startTimer()
        startForceNavigateTimeout()
    }

    /**
     * ★ 新增：绝对超时保护 — 超过 FORCE_NAVIGATE_TIMEOUT_SECONDS 后强制导航
     *
     * 场景：后端 /start 返回 OK 但 /drama/status 一直不满足 isComplete 条件
     * （例如 status 卡在中间态、theme 匹配逻辑误判等）
     * 此时用户已等待太久，应该强制跳转到详情页（详情页有自己的状态恢复能力）
     */
    private fun startForceNavigateTimeout() {
        viewModelScope.launch {
            delay(FORCE_NAVIGATE_TIMEOUT_SECONDS.toLong() * 1000L)
            if (!navigated) {
                val elapsed = getElapsedSeconds()
                // ★ 防护：如果从未确认主题匹配，说明后端可能仍未创建新会话，不允许强制导航
                if (!hasConfirmedThemeMatch) {
                    addLog("⏰ 已等待 ${formatElapsed(elapsed)}，但后端尚未确认新剧本主题")
                    _uiState.update {
                        it.copy(
                            isCreating = false,
                            error = "创建超时：后端未能在 ${FORCE_NAVIGATE_TIMEOUT_SECONDS} 秒内初始化新剧本，请检查后端日志后重试",
                            stormPhase = null,
                        )
                    }
                    cancelJobsOnly()
                    return@launch
                }
                addLog("⏰ 已等待 ${formatElapsed(elapsed)}，强制进入详情页...")
                _uiState.update { it.copy(stormPhase = "正在进入剧本...") }
                // 使用 creatingTheme 作为导航 ID，与 navigateToDetail 一致
                val navTarget = creatingTheme.ifBlank { "current" }
                navigateToDetail(navTarget)
            }
        }
    }

    /** 仅取消后台任务，不设置 navigated（用于超时失败场景） */
    private fun cancelJobsOnly() {
        wsJob?.cancel()
        createJob?.cancel()
        pollingJob?.cancel()
        timerJob?.cancel()
        wsActive = false
        webSocketManager.disconnect()
    }

    /**
     * 核心：轮询 /drama/status 检测创建完成。
     * 无超时限制——只要 Agent 还在跑就继续等待。
     * 仅在连续网络连接失败达到阈值时才提示用户。
     */
    private fun startPolling() {
        pollingJob?.cancel()
        pollingJob = viewModelScope.launch {
            var consecutiveErrors = 0
            var firstPoll = true

            while (isActive && !navigated) {
                // ★ 修复轮询风暴：WS 已连接并收到事件时，大幅降低轮询频率（10秒）
                // WS 断连或未收到事件时，保持原有2秒快速轮询
                if (wsActive) {
                    delay(10_000L)  // WS 活跃时 10 秒轮询一次（仅作为兜底确认）
                } else if (firstPoll) {
                    firstPoll = false
                    delay(500L)  // 首次快速探测（500ms），因为轮询已提前启动
                } else {
                    delay(POLL_INTERVAL_MS)
                }

                dramaRepository.getDramaStatus()
                    .onSuccess { status ->
                        consecutiveErrors = 0
                        handlePollResponse(status)
                    }
                    .onFailure { e ->
                        consecutiveErrors++
                        val isConnectionError = e.message?.contains("Unable to resolve host", true) == true ||
                            e.message?.contains("Failed to connect", true) == true ||
                            e.message?.contains("timeout", ignoreCase = true) == true ||
                            e.message?.contains("SocketException", true) == true ||
                            e.message?.contains("UnknownHost", true) == true

                        when {
                            consecutiveErrors >= MAX_CONSECUTIVE_ERRORS && isConnectionError -> {
                                addLog("连接中断（已重试 $MAX_CONSECUTIVE_ERRORS 次），请检查网络")
                                _uiState.update {
                                    it.copy(
                                        error = "无法连接服务器（已重试 $MAX_CONSECUTIVE_ERRORS 次）",
                                        stormPhase = "网络异常，尝试重新连接...",
                                    )
                                }
                                // 不停止轮询——用户可手动取消，或网络恢复后自动恢复
                            }
                            consecutiveErrors >= MAX_CONSECUTIVE_ERRORS && !isConnectionError -> {
                                addLog("服务响应异常：${e.message}")
                                _uiState.update {
                                    it.copy(
                                        error = "服务器响应异常（已重试 $MAX_CONSECUTIVE_ERRORS 次）：${e.message}",
                                        stormPhase = "等待服务器恢复...",
                                    )
                                }
                            }
                            consecutiveErrors <= 2 -> { /* 静默 */ }
                            else -> _uiState.update {
                                it.copy(stormPhase = "等待服务器响应... (${consecutiveErrors}/$MAX_CONSECUTIVE_ERRORS)")
                            }
                        }
                    }
            }
        }
    }

    /**
     * 解析每次轮询返回的状态，决定是否导航 + 更新导演日志。
     *
     * 核心逻辑：
     *   /drama/start 是阻塞式的（LLM 要执行完整 STORM 流程才返回）。
     *   在此期间轮询 GET /drama/status 会返回：
     *     - 前几秒：旧剧本数据（如上次的"南阳三子"）— 这是正常的
     *     - 几秒后：{theme:"新三国", status:"setup", num_actors:0} — init_drama_state() 已执行
     *     - 之后：num_actors 逐步增加、status 切换到 acting
     *
     *   ★ 关键防护：必须验证轮询返回的 theme 与用户请求的 creatingTheme 匹配，
     *   否则旧剧本数据满足 isComplete 条件时会导致错误导航到旧会话。
     */
    private fun handlePollResponse(status: DramaStatusResponseDto) {
        val ds = status.drama_status.lowercase()
        val currentElapsed = getElapsedSeconds()

        // ★ 主题匹配检查：轮询返回的 theme 必须与用户创建请求的 creatingTheme 匹配
        // 后端 /start 是阻塞式的，在 LLM 完成之前 /drama/status 仍返回旧剧本数据。
        // 如果旧剧本恰好满足 isComplete 条件，不加此检查就会错误导航到旧会话。
        val isThemeMatch = if (creatingTheme.isNotBlank() && status.theme.isNotBlank()) {
            // ★ 严格匹配：只允许精确匹配或后端 theme 以 creatingTheme 开头（带后缀）
            // 禁止使用双向 contains，避免 "南阳三子" 与 "南阳三子外传" 误判
            val ct = creatingTheme.trim()
            val st = status.theme.trim()
            st == ct || st.startsWith(ct)
        } else {
            // 如果 creatingTheme 或 status.theme 为空，无法判断，保守放行
            // （空 theme 说明后端还在初始化，不会有 isComplete 的问题）
            true
        }

        // ── 更新阶段文字 & 日志（始终更新，让用户看到进度） ──
        val phaseInfo = when {
            // 后端还没开始处理（theme 为空说明 LLM 还没调用 start_drama 工具）
            status.theme.isBlank() -> "连接服务器..." to "导演已收到创作指令..."
            !isThemeMatch -> "等待新剧本初始化..." to "检测到旧剧本数据，等待新剧本就绪..."
            // ★ 新增：大纲已就绪但演员未创建时，提示用户确认
            ds == STATUS_SETUP && status.has_outline && status.num_actors == 0 ->
                "大纲已就绪，等待确认..." to "故事大纲已生成，等待用户确认方向..."
            ds == STATUS_SETUP -> when {
                status.num_actors == 0 -> "导演正在构思世界观..." to "正在构建世界观设定..."
                else -> "正在生成角色..." to "正在生成演员阵容（${status.num_actors} 人）..."
            }
            ds == STATUS_ACTING -> when {
                status.current_scene == 0 -> "角色就绪，准备开演..." to "演员就绪，准备第一场演出..."
                else -> "第 ${status.current_scene} 场进行中..." to "正在推进第 ${status.current_scene} 场剧情..."
            }
            ds == STATUS_ENDED -> "戏剧已落幕" to "戏剧已完美落幕！"
            else -> "创作中..." to "创作进行中..."
        }

        _uiState.update { it.copy(stormPhase = phaseInfo.first) }

        // 仅在阶段变化时记录日志（避免刷屏）
        val lastLog = _uiState.value.directorLog.firstOrNull()?.message
        if (lastLog != phaseInfo.second) {
            addLog(phaseInfo.second)
        }

        // ★ 主题不匹配时，绝对不允许导航（旧剧本数据不是我们要找的）
        if (!isThemeMatch) {
            return
        }

        // 标记已通过轮询确认主题匹配（scene_start 导航需要此标志）
        hasConfirmedThemeMatch = true

        // ── 判定是否完成 ──
        // 条件说明（从严格到宽松）：
        //   A) 已有至少一场戏（无论什么状态）→ 可进入聊天
        //   B) acting 状态且演员已就绪 → 可进入聊天
        //   C) setup 状态但演员已创建完成（STORM cast 完成，等待 /next 推进首场）→ 允许进入
        //   D) 已落幕 → 进入查看结局
        //   E) ★ 大纲已就绪（无论有无演员）→ 进入详情页（improv_director 会在用户确认后创建演员）
        //   F) ★ 兜底：已等待超过60秒 且 状态非空(后端有响应) 且 有演员 → 说明STORM基本完成
        val isComplete = when {
            status.current_scene >= 1 -> true
            ds == STATUS_ACTING && status.num_actors > 0 -> true
            ds == STATUS_SETUP && status.num_actors > 0 -> true
            ds == STATUS_ENDED -> true
            // ★ 核心修复：大纲已就绪（has_outline=true）时，即使无演员也允许进入详情页
            // setup_agent 生成大纲后状态切换为 acting，但不创建演员（等待用户确认）
            // 前端进入 DramaDetailScreen 后，用户发送确认消息，improv_director 会创建演员
            status.has_outline -> {
                addLog("📋 大纲已就绪，进入确认页面")
                true
            }
            // ★ 兜底条件：长时间等待 + 后端有数据 + 有演员 → 强制认为可进入
            currentElapsed >= 60 && status.num_actors > 0 && ds.isNotBlank() -> {
                addLog("⚡ 兜底导航: 已等待${currentElapsed}s, actors=${status.num_actors}, status=$ds")
                true
            }
            else -> false
        }

        if (isComplete) {
            // ★★★ 关键修复：优先使用 theme 作为导航 ID ★★★
            // 原因：drama_folder 是文件系统路径（如 "drams/红楼梦"），
            // 而 POST /drama/load 需要的是 save_name（即 theme 本身）。
            // 用文件路径去 load 会找不到存档文件导致静默失败，
            // 最终 loadInitialStatus 拿到旧数据。
            val navTarget = status.theme.ifBlank {
                status.drama_folder.ifBlank { creatingTheme.ifBlank { "current" } }
            }.let {
                // 如果 folder 包含路径分隔符，只取最后一部分作为名称
                it.split("/").last().split("\\").last()
            }
            addLog("创作完成！准备进入详情... [navId=$navTarget]")
            navigateToDetail(navTarget)
        }
    }

    /** 已用时间计时器（无上限） */
    private fun startTimer() {
        timerJob?.cancel()
        timerJob = viewModelScope.launch {
            while (isActive && _uiState.value.isCreating && !navigated) {
                delay(1_000L)
                _uiState.update { it.copy(elapsedSeconds = getElapsedSeconds()) }
            }
        }
    }

    fun cancelCreation() {
        wsJob?.cancel()
        createJob?.cancel()
        pollingJob?.cancel()
        timerJob?.cancel()
        wsActive = false
        webSocketManager.disconnect()
        navigated = true
        addLog("用户取消创作")
        _uiState.update { it.copy(isCreating = false, stormPhase = null) }
    }

    private fun navigateToDetail(dramaId: String) {
        if (navigated) return
        navigated = true
        _uiState.update { it.copy(isCreating = false) }

        // ★★★ 核心修复：只取消本 VM 的事件收集 job，不断开 WS 物理连接 ★★★
        // 原因：WebSocketManager 是全局单例，disconnect() 会关闭底层 TCP 连接。
        // DramaDetailVM 初始化时再 connect() 需要重新握手，产生 1-3 秒的断连窗口，
        // 导致 ConnectionBanner 闪烁"WebSocket 连接失败，已降级到 REST 轮询模式"。
        //
        // 新策略：
        // 1. 只取消本 VM 的 collect job（wsJob），停止消费事件
        // 2. 不断开 WS 物理连接，DramaDetailVM 可直接复用
        // 3. DramaDetailVM.connectWebSocket() 会检测连接状态，已连接则直接开始 collect
        wsJob?.cancel()
        wsJob = null
        createJob?.cancel()
        createJob = null
        pollingJob?.cancel()
        pollingJob = null
        timerJob?.cancel()
        timerJob = null
        wsActive = false
        // ★ 不再调用 webSocketManager.disconnect()！

        viewModelScope.launch {
            _events.emit(DramaCreateEvent.NavigateToDetail(dramaId))
        }
    }

    /** 处理 WebSocket 事件，追加到导演日志 */
    private fun handleStormEvent(event: WsEventDto) {
        // ★ 新增：director_log 事件 — 后端推送的结构化详细日志
        if (event.type == "director_log") {
            val msg = event.data["message"]?.jsonPrimitive?.contentOrNull
            val tool = event.data["tool"]?.jsonPrimitive?.contentOrNull
            val phase = event.data["phase"]?.jsonPrimitive?.contentOrNull
            val ts = event.data["timestamp"]?.jsonPrimitive?.contentOrNull

            // 优先使用后端构造的消息（含emoji和详细信息）
            val logMsg = when {
                !msg.isNullOrBlank() -> {
                    // 加上时间戳前缀便于阅读
                    val timePrefix = if (!ts.isNullOrBlank()) "[$ts] " else ""
                    "$timePrefix$msg"
                }
                else -> "[director_log:$tool/$phase]"
            }

            addLog(logMsg)
            // 更新状态文字为最新的 director_log 消息
            _uiState.update { it.copy(stormPhase = (msg ?: logMsg)) }
            return  // director_log 不走下面的通用逻辑
        }

        val logMsg = when (event.type) {
            "storm_discover" -> "发现新叙事视角..."
            "storm_research" -> "深入研究背景资料..."
            "storm_outline" -> "综合构思故事大纲..."
            "storm_cast" -> "分配演员角色..."
            "scene_start" -> null  // scene_start 直接导航，不再额外记录
            "error" -> {
                val errMsg = event.data["message"]?.jsonPrimitive?.contentOrNull ?: "未知错误"
                "导演遇到问题：$errMsg"
            }
            else -> null  // ★ 改为null — 未识别的事件类型不再显示原始type名
        }
        if (logMsg != null) {
            addLog(logMsg)
            // 同时更新当前状态文字
            _uiState.update { it.copy(stormPhase = logMsg) }
        }
        // ★ 新增：storm_outline 事件表示大纲已生成，仅记录日志，不自动导航
        // 导航由轮询的 isComplete 条件决定（需要演员已创建后才导航）
        if (event.type == "storm_outline") {
            addLog("📋 收到大纲完成信号，等待演员创建...")
            return
        }

        // scene_start 直接触发导航 — 使用记录的 theme 作为 navTarget
        // ★ 防护：仅当后端状态已确认匹配当前创建主题时才导航，防止旧剧本事件误触发
        if (event.type == "scene_start") {
            addLog("收到首场演出信号")
            // 强制等待一次状态确认：如果 creatingTheme 非空，则必须确认后端已切换到新主题
            if (creatingTheme.isNotBlank() && !hasConfirmedThemeMatch) {
                addLog("⚠️ 收到 scene_start 但尚未确认主题匹配，等待轮询验证...")
                return
            }
            val navTarget = creatingTheme.ifBlank { "current" }
            navigateToDetail(navTarget)
        }
    }

    /** 追加一条导演日志（最新在前） */
    private fun addLog(message: String) {
        _uiState.update { state ->
            val entry = DirectorLogEntry(getElapsedSeconds(), message)
            val updated = listOf(entry) + state.directorLog.take(MAX_LOG_ENTRIES - 1)
            state.copy(directorLog = updated)
        }
    }

    /** 获取从开始到现在的已用秒数 */
    private fun getElapsedSeconds(): Int {
        if (startTimeMs <= 0L) return 0
        return ((System.currentTimeMillis() - startTimeMs) / 1000).toInt().coerceAtLeast(0)
    }

    override fun onCleared() {
        super.onCleared()
        // ★ 核心修复：如果已导航到详情页，不断开 WS（DetailVM 正在复用该连接）
        // 只取消本 VM 的 collect job，WS 物理连接由 DetailVM 管理
        if (navigated) {
            wsJob?.cancel()
            createJob?.cancel()
            pollingJob?.cancel()
            timerJob?.cancel()
            wsActive = false
            // ★ 不调用 webSocketManager.disconnect()！
        } else {
            // 用户手动退出或非导航场景，完整清理
            cancelCreation()
        }
    }
}
