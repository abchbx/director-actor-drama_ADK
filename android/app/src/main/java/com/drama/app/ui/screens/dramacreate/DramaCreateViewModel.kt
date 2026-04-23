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

    fun createDrama(theme: String) {
        if (theme.isBlank()) return
        startTimeMs = System.currentTimeMillis()
        navigated = false
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
                    // ★ 修复：WS 断连后不阻塞，轮询仍然可以触发导航
                }
                .collect { event -> handleStormEvent(event) }
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
                addLog("⏰ 已等待 ${formatElapsed(elapsed)}，强制进入详情页...")
                _uiState.update { it.copy(stormPhase = "正在进入剧本...") }
                // 使用 creatingTheme 作为导航 ID，与 navigateToDetail 一致
                val navTarget = creatingTheme.ifBlank { "current" }
                navigateToDetail(navTarget)
            }
        }
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
                if (firstPoll) {
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
            // 精确匹配或包含匹配（后端可能对 theme 做了格式调整）
            status.theme.trim() == creatingTheme.trim() ||
                status.theme.contains(creatingTheme.trim()) ||
                creatingTheme.contains(status.theme.trim())
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

        // ── 判定是否完成 ──
        // 条件说明（从严格到宽松）：
        //   A) 已有至少一场戏（无论什么状态）→ 可进入聊天
        //   B) acting 状态且演员已就绪 → 可进入聊天
        //   C) setup 状态但演员已创建完成（STORM cast 完成，等待 /next 推进首场）→ 允许进入
        //   D) 已落幕 → 进入查看结局
        //   E) ★ 兜底：已等待超过60秒 且 状态非空(后端有响应) 且 有演员 → 说明STORM基本完成
        val isComplete = when {
            status.current_scene >= 1 -> true
            ds == STATUS_ACTING && status.num_actors > 0 -> true
            ds == STATUS_SETUP && status.num_actors > 0 -> true
            ds == STATUS_ENDED -> true
            // ★ 新增兜底条件：长时间等待 + 后端有数据 + 有演员 → 强制认为可进入
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
        webSocketManager.disconnect()
        navigated = true
        addLog("用户取消创作")
        _uiState.update { it.copy(isCreating = false, stormPhase = null) }
    }

    private fun navigateToDetail(dramaId: String) {
        if (navigated) return
        navigated = true
        _uiState.update { it.copy(isCreating = false) }

        // ★★★ 关键修复：导航到详情页之前，必须清理创建阶段的所有资源 ★★★
        // 原因：
        // 1. WebSocketManager 是全局单例，如果不断开，创建页的WS监听会继续运行
        //    导致 STORM/scene_start 等事件泄漏到新的 DramaDetailViewModel
        // 2. 轮询 job 不取消会持续消耗资源
        // 3. DramaDetailScreen 会重新建立自己的 WS 连接和轮询
        wsJob?.cancel()
        wsJob = null
        createJob?.cancel()
        createJob = null
        pollingJob?.cancel()
        pollingJob = null
        timerJob?.cancel()
        timerJob = null

        // 断开 WebSocket 全局单例（DramaDetail 会重新 connect）
        webSocketManager.disconnect()

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
        // scene_start 直接触发导航 — 使用记录的 theme 作为 navTarget
        if (event.type == "scene_start") {
            addLog("收到首场演出信号")
            // ★★★ 优先使用 creatingTheme，避免 "current" 导致 loadDrama 失败
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
        cancelCreation()
    }
}
