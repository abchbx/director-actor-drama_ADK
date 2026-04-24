package com.drama.app.ui.screens.dramadetail

import android.util.Log
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.drama.app.data.local.ServerPreferences
import com.drama.app.data.remote.dto.ArcProgressDto
import com.drama.app.data.remote.dto.CommandResponseDto
import com.drama.app.data.remote.dto.SceneSummaryDto
import com.drama.app.data.remote.dto.WsEventDto
import com.drama.app.data.remote.ws.WebSocketManager
import com.drama.app.domain.model.ActorInfo
import com.drama.app.domain.model.CommandType
import com.drama.app.domain.model.SceneBubble
import com.drama.app.domain.repository.DramaRepository
import com.drama.app.domain.usecase.DetectActorInteractionUseCase
import dagger.hilt.android.lifecycle.HiltViewModel
import com.drama.app.ui.screens.dramadetail.components.getTypingText
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.contentOrNull
import javax.inject.Inject

/**
 * 剧本详情页 UI 状态
 *
 * 关键：包含 [activeDramaId] 用于数据隔离，确保切换剧本时不会串台。
 */
data class DramaDetailUiState(
    // === 剧本标识 — 数据隔离核心 ===
    val activeDramaId: String = "",

    // === 初始化同步状态 — 防止竞态 ===
    val initialSyncing: Boolean = true,
    val initError: String? = null,

    // === 剧本内容 ===
    val theme: String = "",
    val currentScene: Int = 0,
    val tensionScore: Int = 0,
    val bubbles: List<SceneBubble> = emptyList(),
    val isTyping: Boolean = false,
    val typingText: String = "AI 正在思考...",
    val isProcessing: Boolean = false,
    val stormPhase: String? = null,

    // === 连接状态 ===
    val isWsConnected: Boolean = false,
    val isReconnecting: Boolean = false,  // ★ 区分"正在重连"和"已降级到 REST"
    val error: String? = null,

    // === 场景历史 D-18~D-20 ===
    val viewingHistoryScene: Int? = null,
    val historyScenes: List<SceneSummaryDto> = emptyList(),
    val showHistorySheet: Boolean = false,

    // === 保存操作 D-23 ===
    val showSaveDialog: Boolean = false,

    // === 大纲确认 ===
    val outlineSummary: String = "",

    // === 演员面板 D-01~D-04 ===
    val actors: List<ActorInfo> = emptyList(),
    val showActorDrawer: Boolean = false,
    val isActorLoading: Boolean = false,

    // === 状态概览 D-07 ===
    val arcProgress: List<ArcProgressDto> = emptyList(),
    val timePeriod: String = "",
)

sealed class DramaDetailEvent {
    data class ShowSnackbar(val message: String) : DramaDetailEvent()
}

@HiltViewModel
class DramaDetailViewModel @Inject constructor(
    private val dramaRepository: DramaRepository,
    private val webSocketManager: WebSocketManager,
    private val serverPreferences: ServerPreferences,
    private val detectActorInteraction: DetectActorInteractionUseCase,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {
    companion object {
        private const val TAG = "DramaDetailViewModel"
    }

    private val activeDramaId: String = savedStateHandle["dramaId"] ?: ""
    /** 从创建页进入时为 true，跳过 loadDrama（后端已是当前活跃剧本） */
    private val skipLoad: Boolean = savedStateHandle["skipLoad"] ?: false

    private val _uiState = MutableStateFlow(DramaDetailUiState())
    val uiState: StateFlow<DramaDetailUiState> = _uiState.asStateFlow()

    private val _events = MutableSharedFlow<DramaDetailEvent>()
    val events: SharedFlow<DramaDetailEvent> = _events.asSharedFlow()

    private var wsJob: Job? = null
    private var connectionStateJob: Job? = null
    private var bubbleCounter = 0
    private var pollingJob: Job? = null
    private var replyPollJob: Job? = null
    private var lastKnownScene: Int = 0
    // ★ 修复：防止重组导致的连接抖动
    private var hasCalledConnectWebSocket = false

    init {
        resetAllState(activeDramaId)
        performInitSync()
    }

    /**
     * 执行初始化同步。
     *
     * - 从列表进入（skipLoad=false）：需要 loadDrama 切换后端活跃剧本
     * - 从创建页进入（skipLoad=true）：后端已是当前活跃剧本，直接加载状态即可
     *
     * 失败时设置 initError，阻止后续流程，UI 显示重试按钮。
     */
    private fun performInitSync() {
        viewModelScope.launch {
            if (activeDramaId.isNotBlank() && !skipLoad) {
                val success = switchToDramaAndWait(activeDramaId)
                if (!success) {
                    _uiState.update { it.copy(
                        initialSyncing = false,
                        initError = "切换剧本失败，请检查网络后重试",
                    ) }
                    return@launch
                }
            }
            _uiState.update { it.copy(initialSyncing = false, initError = null) }

            // ★ 核心优化：loadInitialStatus 和 connectWebSocket 并行启动
            // 之前是串行：先等 REST 状态加载完，再连接 WS → 浪费 0.5-2 秒
            // 现在并行：两者同时启动，WS 复用连接时几乎瞬时完成
            loadInitialStatus()
            if (!hasCalledConnectWebSocket) {
                hasCalledConnectWebSocket = true
                connectWebSocket()
            }
            startPolling()
        }
    }

    /** 重试初始化同步（用户点击重试按钮时调用） */
    fun retryInit() {
        _uiState.update { it.copy(initialSyncing = true, initError = null) }
        performInitSync()
    }

    // ============================================================
    // 初始化与状态管理
    // ============================================================

    private suspend fun switchToDramaAndWait(dramaId: String): Boolean {
        return try {
            dramaRepository.loadDrama(dramaId)
            true
        } catch (e: Exception) {
            false
        }
    }

    private fun switchToDrama(dramaId: String) {
        viewModelScope.launch { switchToDramaAndWait(dramaId) }
    }

    private fun resetAllState(dramaId: String) {
        bubbleCounter = 0
        lastKnownScene = 0
        replyPollJob?.cancel()
        replyPollJob = null
        _uiState.value = DramaDetailUiState(activeDramaId = dramaId)
    }

    private fun loadInitialStatus() {
        viewModelScope.launch {
            dramaRepository.getDramaStatus()
                .onSuccess { status ->
                    // ★ 修复：当 skipLoad=true 但后端返回的 theme 与 activeDramaId 不匹配时，
                    // 说明热重载或竞态导致后端状态漂移到旧剧本，需要主动 switchToDrama 修正
                    if (activeDramaId.isNotBlank() && status.theme.isNotBlank()
                        && status.theme.trim() != activeDramaId.trim()
                        && !status.theme.contains(activeDramaId)
                        && !activeDramaId.contains(status.theme)
                    ) {
                        val corrected = switchToDramaAndWait(activeDramaId)
                        if (corrected) {
                            // 重新获取状态
                            dramaRepository.getDramaStatus()
                                .onSuccess { correctedStatus ->
                                // ★ isWsConnected 由 connectionState Flow 驱动，不在此处设置
                                _uiState.update { it.copy(
                                    theme = correctedStatus.theme,
                                    currentScene = correctedStatus.current_scene,
                                    arcProgress = correctedStatus.arc_progress,
                                    timePeriod = correctedStatus.time_period,
                                    outlineSummary = correctedStatus.outline_summary,
                                ) }
                                    if (correctedStatus.current_scene > 0) {
                                        lastKnownScene = correctedStatus.current_scene
                                        loadSceneBubbles(correctedStatus.current_scene, "init_")
                                    }
                                    // ★ 修复：无论 num_actors 是否为 0，都尝试预加载演员面板
                                    // 创建后进入时后端可能短暂返回 0，但演员数据实际已存在
                                    preloadActorPanel()
                                }
                            return@launch
                        }
                        // ★ 修复：switchToDrama 失败时不可静默使用旧状态，必须报错
                        _uiState.update { it.copy(
                            initialSyncing = false,
                            initError = "后端当前为「${status.theme}」而非「$activeDramaId」，且切换失败。请返回列表重新进入。",
                        ) }
                        return@launch
                    }

                    // ★ isWsConnected 由 connectionState Flow 驱动，不在此处设置
                    // REST 轮询成功不代表 WS 已连接，避免 ConnectionBanner 闪烁
                    _uiState.update { it.copy(
                        theme = status.theme,
                        currentScene = status.current_scene,
                        arcProgress = status.arc_progress,
                        timePeriod = status.time_period,
                        outlineSummary = status.outline_summary,
                    ) }
                    if (status.current_scene > 0) {
                        lastKnownScene = status.current_scene
                        loadSceneBubbles(status.current_scene, "init_")
                    }
                    // ★ 修复：无论 num_actors 是否为 0，都尝试预加载演员面板
                    // 从创建页进入时后端可能短暂返回 0，但演员数据实际已存在
                    preloadActorPanel()
                }
        }
    }

    // ============================================================
    // WebSocket 管理
    // ============================================================

    fun connectWebSocket() {
        disconnectWebSocketSafely()
        wsJob?.cancel()
        connectionStateJob?.cancel()

        // ★ 核心修复：检测 WS 是否已连接（从创建页复用），避免断连闪烁
        val isAlreadyConnected = webSocketManager.connectionState.value

        // 设置回调（无论是否复用连接都需要）
        webSocketManager.onReconnected = {
            onWsReconnected()
        }
        webSocketManager.onPermanentFailure = {
            Log.w(TAG, "WS permanent failure, degrading to REST mode")
            _uiState.update { it.copy(isWsConnected = false) }
        }

        if (isAlreadyConnected) {
            // ★ 复用已有连接：直接开始 collect 事件，无需重新 connect()
            // 这是从创建页导航过来的场景，WS 物理连接仍然活跃
            Log.i(TAG, "WS already connected, reusing existing connection")
            wsJob = viewModelScope.launch {
                webSocketManager.events
                    .catch { e -> _uiState.update { it.copy(isWsConnected = false, error = e.message) } }
                    .collect { event -> handleWsEvent(event) }
            }
        } else {
            // 正常流程：建立新的 WS 连接
            wsJob = viewModelScope.launch {
                val config = serverPreferences.serverConfig.first() ?: return@launch
                webSocketManager.connect(config.ip, config.port, config.token, config.baseUrl)
                    .catch { e -> _uiState.update { it.copy(isWsConnected = false, error = e.message) } }
                    .collect { event -> handleWsEvent(event) }
            }
        }

        connectionStateJob = viewModelScope.launch {
            webSocketManager.connectionState.collect { connected ->
                _uiState.update { it.copy(isWsConnected = connected) }
            }
        }

        // 收集 isReconnecting 状态，让 UI 可以区分"正在重连"和"已降级到 REST"
        viewModelScope.launch {
            webSocketManager.isReconnecting.collect { reconnecting ->
                _uiState.update { it.copy(isReconnecting = reconnecting) }
            }
        }
    }

    private fun disconnectWebSocketSafely() {
        wsJob?.cancel()
        wsJob = null
        connectionStateJob?.cancel()
        connectionStateJob = null
        webSocketManager.onReconnected = null
        // ★ 修复：断开时重置标志，允许后续重新连接
        hasCalledConnectWebSocket = false
    }

    // ============================================================
    // REST 轮询降级
    // ============================================================

    private fun startPolling() {
        pollingJob?.cancel()
        pollingJob = viewModelScope.launch {
            while (true) {
                kotlinx.coroutines.delay(3000)
                if (!_uiState.value.isWsConnected) pollStatus()
            }
        }
    }

    private fun pollStatus() {
        viewModelScope.launch {
                dramaRepository.getDramaStatus()
                    .onSuccess { status ->
                        // ★ isWsConnected 由 connectionState Flow 驱动，不在此处设置
                        _uiState.update { it.copy(
                            theme = status.theme,
                            currentScene = status.current_scene,
                            arcProgress = status.arc_progress,
                            timePeriod = status.time_period,
                            outlineSummary = status.outline_summary,
                        ) }
                    if (status.current_scene > lastKnownScene) {
                        lastKnownScene = status.current_scene
                        loadSceneBubbles(status.current_scene, "poll_")
                    }
                }
        }
    }

    // ============================================================
    // WS 事件处理
    // ============================================================

    /**
     * 将换行符转换为 Markdown 支持的格式
     * 单个 \n 转换为双 \n\n，以支持 Markdown 段落分隔
     */
    private fun normalizeLineBreaks(text: String): String {
        return text.replace("\\n", "\n\n")
    }

    private fun handleWsEvent(event: WsEventDto) {
        if (event.type == "replay") return

        // 历史查看模式下，不处理实时 WS 事件，防止干扰历史数据展示
        if (_uiState.value.viewingHistoryScene != null) return

        // ★ 新增：director_log 事件 — 显示后端详细进度（创建演员等）
        if (event.type == "director_log") {
            val msg = event.data["message"]?.jsonPrimitive?.contentOrNull
            if (!msg.isNullOrBlank()) {
                // 更新 stormPhase 显示进度，不添加到 bubbles
                _uiState.update { it.copy(stormPhase = msg) }
            }
            return
        }

        when (event.type) {
            // ★ 修复：narration 事件 — 仅在 response 阶段（text 非空）创建气泡
            "narration" -> {
                val text = event.data["text"]?.jsonPrimitive?.contentOrNull ?: ""

                if (text.isBlank()) {
                    // call 阶段：只更新 typing 指示
                    _uiState.update { it.copy(isTyping = true, typingText = "旁白正在讲述...") }
                    return
                }

                _uiState.update { it.copy(isTyping = false) }
                val normalizedText = normalizeLineBreaks(text)
                if (normalizedText.isNotBlank()) {
                    val bubble = SceneBubble.Narration(
                        id = "b_${bubbleCounter++}",
                        text = normalizedText,
                        avatarType = SceneBubble.AvatarType.DIRECTOR,
                    )
                    _uiState.update { it.copy(bubbles = it.bubbles + bubble, typingText = "AI 正在思考...") }
                }
            }

            "dialogue" -> {
                val actorName = event.data["actor_name"]?.jsonPrimitive?.contentOrNull ?: ""
                val text = event.data["text"]?.jsonPrimitive?.contentOrNull ?: ""
                val emotion = event.data["emotion"]?.jsonPrimitive?.contentOrNull ?: ""

                // ★ 核心修复：仅当 text 非空时才创建气泡
                // 后端 event_mapper 对同一个 tool 会发出两次 dialogue 事件：
                //   1. function_call 阶段：text=""（仅标记 actor_name，typing 指示）
                //   2. function_response 阶段：text=完整对话内容（此时才创建气泡）
                if (text.isBlank()) {
                    // call 阶段：只更新 typing 指示，不创建气泡
                    _uiState.update { it.copy(isTyping = true, typingText = "${actorName}正在说话...") }
                    return
                }

                _uiState.update { it.copy(isTyping = false) }
                val normalizedText = normalizeLineBreaks(text)

                val lastBubble = _uiState.value.bubbles.lastOrNull()
                val interactionBubble = detectActorInteraction(
                    currentActor = actorName,
                    text = normalizedText,
                    emotion = emotion,
                    lastBubble = lastBubble,
                    eventType = "dialogue",
                    bubbleCounter = bubbleCounter++,
                )

                if (interactionBubble != null) {
                    _uiState.update { it.copy(bubbles = it.bubbles + interactionBubble) }
                } else {
                    val bubble = SceneBubble.Dialogue(
                        id = "b_${bubbleCounter++}",
                        actorName = actorName,
                        text = normalizedText,
                        emotion = emotion,
                        avatarType = SceneBubble.AvatarType.ACTOR,
                    )
                    _uiState.update { it.copy(bubbles = it.bubbles + bubble) }
                }
            }

            "end_narration" -> {
                val text = event.data["text"]?.jsonPrimitive?.contentOrNull ?: ""
                val normalizedText = normalizeLineBreaks(text)
                if (normalizedText.isNotBlank()) {
                    val bubble = SceneBubble.Narration(
                        id = "b_${bubbleCounter++}",
                        text = normalizedText,
                        avatarType = SceneBubble.AvatarType.DIRECTOR,
                    )
                    _uiState.update { it.copy(bubbles = it.bubbles + bubble) }
                }
            }

            "scene_end" -> {
                val sceneNum = event.data["scene_number"]?.jsonPrimitive?.intOrNull ?: 0
                val sceneTitle = event.data["scene_title"]?.jsonPrimitive?.contentOrNull ?: ""
                val divider = SceneBubble.SceneDivider(id = "b_${bubbleCounter++}", sceneNumber = sceneNum, sceneTitle = sceneTitle)
                _uiState.update { it.copy(bubbles = it.bubbles + divider, currentScene = sceneNum) }
            }

            "tension_update" -> {
                val score = event.data["tension_score"]?.jsonPrimitive?.intOrNull ?: 0
                _uiState.update { it.copy(tensionScore = score) }
            }

            "typing" -> {
                val toolName = event.data["tool"]?.jsonPrimitive?.contentOrNull
                val typingText = getTypingText(toolName)
                _uiState.update { it.copy(isTyping = true, typingText = typingText) }
            }

            "error" -> {
                val msg = event.data["message"]?.jsonPrimitive?.contentOrNull ?: "Unknown error"
                _uiState.update { it.copy(isTyping = false, error = msg) }
                viewModelScope.launch { _events.emit(DramaDetailEvent.ShowSnackbar(msg)) }
            }

            "storm_discover" -> _uiState.update { it.copy(stormPhase = "发现新视角...") }
            "storm_research" -> _uiState.update { it.copy(stormPhase = "深入研究...") }
            "storm_outline" -> {
                // ★ 修复：解析大纲事件数据，显示大纲摘要
                val msg = event.data["message"]?.jsonPrimitive?.contentOrNull ?: ""
                val numActs = event.data["num_acts"]?.jsonPrimitive?.intOrNull ?: 0
                _uiState.update { it.copy(
                    stormPhase = if (msg.isNotBlank()) msg else "大纲已完成（${numActs}幕），等待确认...",
                ) }
            }
            "scene_start" -> {
                _uiState.update { it.copy(stormPhase = null, isTyping = false) }
                preloadActorPanel()
            }

            // ★ 新增：command_echo 事件 — 后端回显用户指令
            // 前端在 sendCommand/sendChatMessage 中已自行添加用户气泡，
            // 此事件仅作为确认（避免重复添加气泡），更新 stormPhase 显示当前操作
            "command_echo" -> {
                val command = event.data["command"]?.jsonPrimitive?.contentOrNull ?: ""
                if (command.isNotBlank()) {
                    _uiState.update { it.copy(stormPhase = "执行: $command") }
                }
            }

            "actor_created" -> {
                // 演员创建事件 — 清除 stormPhase，重新加载演员面板
                val actorName = event.data["actor_name"]?.jsonPrimitive?.contentOrNull ?: ""
                _uiState.update { it.copy(stormPhase = null) }
                preloadActorPanel()
            }

            "cast_update" -> {
                // 演员阵容更新 — 重新加载演员面板
                preloadActorPanel()
            }

            "actor_chime_in" -> {
                val actorName = event.data["actor_name"]?.jsonPrimitive?.contentOrNull ?: ""
                val text = event.data["text"]?.jsonPrimitive?.contentOrNull ?: ""

                // ★ 修复：仅当 text 非空时才创建气泡（同 dialogue 逻辑）
                if (text.isBlank()) {
                    _uiState.update { it.copy(isTyping = true, typingText = "${actorName}想要发言...") }
                    return
                }

                _uiState.update { it.copy(isTyping = false) }
                val normalizedText = normalizeLineBreaks(text)
                val lastBubble = _uiState.value.bubbles.lastOrNull()
                val interactionBubble = detectActorInteraction(
                    currentActor = actorName,
                    text = normalizedText,
                    emotion = "",
                    lastBubble = lastBubble,
                    eventType = "chime_in",
                    bubbleCounter = bubbleCounter++,
                )
                if (interactionBubble != null) {
                    _uiState.update { it.copy(bubbles = it.bubbles + interactionBubble) }
                } else {
                    val bubble = SceneBubble.Dialogue(
                        id = "chime_${bubbleCounter++}",
                        actorName = actorName,
                        text = normalizedText,
                        avatarType = SceneBubble.AvatarType.ACTOR,
                    )
                    _uiState.update { it.copy(bubbles = it.bubbles + bubble) }
                }
            }

            "save_confirm" -> {
                val msg = event.data["message"]?.jsonPrimitive?.contentOrNull ?: "已保存"
                _uiState.update { it.copy(isTyping = false) }
                viewModelScope.launch { _events.emit(DramaDetailEvent.ShowSnackbar(msg)) }
            }

            "load_confirm" -> {
                val msg = event.data["message"]?.jsonPrimitive?.contentOrNull ?: "已加载"
                _uiState.update { it.copy(isTyping = false) }
                viewModelScope.launch { _events.emit(DramaDetailEvent.ShowSnackbar(msg)) }
            }
        }
    }

    // ============================================================
    // 场景气泡加载（委托 Repository 层映射）
    // ============================================================

    private fun loadSceneBubbles(sceneNumber: Int, prefix: String, includeDivider: Boolean = true) {
        viewModelScope.launch {
            dramaRepository.getSceneBubbles(sceneNumber, prefix, includeDivider)
                .onSuccess { bubbles ->
                    if (bubbles.isNotEmpty()) {
                        _uiState.update { it.copy(bubbles = it.bubbles + bubbles) }
                    }
                }
        }
    }

    // ============================================================
    // 场景历史 D-18/D-20
    // ============================================================

    fun loadScenes() {
        viewModelScope.launch {
            dramaRepository.getScenes()
                .onSuccess { response ->
                    _uiState.update { it.copy(historyScenes = response.scenes) }
                }
        }
    }

    fun showHistorySheet() {
        loadScenes()
        _uiState.update { it.copy(showHistorySheet = true) }
    }

    fun hideHistorySheet() {
        _uiState.update { it.copy(showHistorySheet = false) }
    }

    fun viewHistoryScene(sceneNumber: Int) {
        viewModelScope.launch {
            dramaRepository.getSceneBubbles(sceneNumber, "hist_", includeDivider = false)
                .onSuccess { bubbles ->
                    _uiState.update { it.copy(
                        viewingHistoryScene = sceneNumber,
                        bubbles = bubbles,
                        showHistorySheet = false,
                    ) }
                }
        }
    }

    fun returnToCurrentScene() {
        _uiState.update { it.copy(viewingHistoryScene = null) }
        switchToDrama(activeDramaId)
        // ★ 修复：从历史场景返回时，重新连接 WebSocket
        // hasCalledConnectWebSocket 已在 disconnectWebSocketSafely 中重置
        disconnectWebSocketSafely()
        connectWebSocket()
    }

    // ============================================================
    // 保存操作 D-23
    // ============================================================

    fun showSaveDialog() {
        _uiState.update { it.copy(showSaveDialog = true) }
    }

    fun hideSaveDialog() {
        _uiState.update { it.copy(showSaveDialog = false) }
    }

    fun saveDrama(saveName: String = "") {
        viewModelScope.launch {
            dramaRepository.saveDrama(saveName)
                .onSuccess { response ->
                    _events.emit(DramaDetailEvent.ShowSnackbar("已保存：${saveName.ifBlank { response.theme }}"))
                }
                .onFailure { e ->
                    _events.emit(DramaDetailEvent.ShowSnackbar("保存失败：${e.message}"))
                }
            _uiState.update { it.copy(showSaveDialog = false) }
        }
    }

    // ============================================================
    // 演员面板 D-01~D-04（委托 Repository 层合并）
    // ============================================================

    fun showActorDrawer() {
        _uiState.update { it.copy(isActorLoading = true, showActorDrawer = true) }
        loadActorPanel()
    }

    fun hideActorDrawer() {
        _uiState.update { it.copy(showActorDrawer = false, isActorLoading = false) }
    }

    private fun loadActorPanel() {
        viewModelScope.launch {
            dramaRepository.getMergedCast()
                .onSuccess { actors ->
                    _uiState.update { it.copy(actors = actors, isActorLoading = false) }
                }
                .onFailure {
                    _uiState.update { it.copy(isActorLoading = false) }
                }
        }
    }

    private fun preloadActorPanel() {
        viewModelScope.launch {
            dramaRepository.getMergedCast()
                .onSuccess { actors ->
                    _uiState.update { it.copy(actors = actors) }
                }
        }
    }

    // ============================================================
    // 状态刷新 D-07/D-16
    // ============================================================

    fun refreshStatus() {
        viewModelScope.launch {
            dramaRepository.getDramaStatus()
                .onSuccess { status ->
                    // ★ isWsConnected 由 connectionState Flow 驱动，不在此处设置
                    _uiState.update { it.copy(
                        currentScene = status.current_scene,
                        arcProgress = status.arc_progress,
                        timePeriod = status.time_period,
                    ) }
                }
        }
    }

    /**
     * WS 重连成功后自动同步：重新 switchToDrama 确保服务端状态一致，
     * 然后刷新状态与气泡数据。
     */
    private fun onWsReconnected() {
        viewModelScope.launch {
            // 重新切换到当前剧本，确保服务端 session 一致
            // 但从创建页进入时后端已是当前活跃剧本，无需 loadDrama
            if (activeDramaId.isNotBlank() && !skipLoad) {
                switchToDramaAndWait(activeDramaId)
            }
            // 刷新全量状态（主题、场次、弧线等）
            loadInitialStatus()
        }
    }

    // ============================================================
    // 命令发送
    // ============================================================

    /**
     * 发送命令。
     *
     * ★ 核心修复：所有命令都在会话中显示用户指令气泡，确保消息可追溯。
     * WS 已连接时，回复由 WS 事件驱动；WS 断连时，通过 REST 轮询降级。
     */
    fun sendCommand(text: String) {
        val commandType = CommandType.fromInput(text)

        // ★ 显示用户指令气泡（除 /next 和 /end 外，这些是控制命令）
        val displayText = when (commandType) {
            CommandType.NEXT -> "/next — 推进下一场"
            CommandType.END -> "/end — 落幕"
            CommandType.ACTION -> {
                val desc = text.removePrefix("/action").trim()
                if (desc.isBlank()) return
                desc  // 只显示描述部分，不显示 /action 前缀
            }
            CommandType.SPEAK -> {
                val parts = text.removePrefix("/speak").trim().split(" ", limit = 2)
                if (parts.size < 2 || parts[0].isBlank()) return
                "@${parts[0]} ${parts[1]}"  // 显示为 @角色 情境 格式
            }
            CommandType.FREE_TEXT -> text.trim()
        }

        val userBubble = SceneBubble.UserMessage(
            id = "cmd_${bubbleCounter++}",
            text = displayText,
            mention = if (commandType == CommandType.SPEAK) {
                text.removePrefix("/speak").trim().split(" ", limit = 2).getOrNull(0)
            } else null,
        )
        _uiState.update { it.copy(
            isProcessing = true,
            isTyping = true,
            typingText = "思考中...",
            bubbles = it.bubbles + userBubble,
        ) }

        viewModelScope.launch {
            val result = when (commandType) {
                CommandType.NEXT -> dramaRepository.nextScene()
                CommandType.END -> dramaRepository.endDrama()
                CommandType.ACTION -> dramaRepository.userAction(text.removePrefix("/action").trim())
                CommandType.SPEAK -> {
                    val parts = text.removePrefix("/speak").trim().split(" ", limit = 2)
                    dramaRepository.actorSpeak(parts[0], parts[1])
                }
                CommandType.FREE_TEXT -> dramaRepository.userAction(text.trim())
            }

            if (_uiState.value.isWsConnected) {
                // WS 已连接：回复由 WS 事件驱动，REST 仅确认请求成功
                _uiState.update { it.copy(isProcessing = false) }
            } else {
                // WS 断连：尝试从 REST 响应提取气泡作为降级
                result.onSuccess { resp ->
                    val respBubbles = extractBubblesFromCommandResponse(resp)
                    if (respBubbles.isNotEmpty()) {
                        _uiState.update { it.copy(
                            bubbles = it.bubbles + respBubbles,
                            isTyping = false,
                            isProcessing = false,
                        ) }
                    } else {
                        startReplyPolling()
                        _uiState.update { it.copy(isProcessing = false) }
                    }
                }
            }

            result.onFailure { e ->
                _uiState.update { it.copy(isTyping = false, isProcessing = false, error = e.message) }
                _events.emit(DramaDetailEvent.ShowSnackbar("命令失败：${e.message}"))
            }
        }
    }

    /**
     * ★ 新增：从 CommandResponse 提取可渲染的 SceneBubble 列表（WS 断连降级用）
     */
    private fun extractBubblesFromCommandResponse(resp: CommandResponseDto): List<SceneBubble> {
        val bubbles = mutableListOf<SceneBubble>()

        if (resp.final_response.isNotBlank() && resp.final_response.length > 5) {
            bubbles.add(SceneBubble.Narration(
                id = "resp_n_${bubbleCounter++}",
                text = normalizeLineBreaks(resp.final_response.trim()),
                avatarType = SceneBubble.AvatarType.DIRECTOR,
            ))
        }

        for (result in resp.tool_results) {
            val actorName = result["actor_name"]?.jsonPrimitive?.contentOrNull ?: ""
            val dialogueText = result["text"]?.jsonPrimitive?.contentOrNull ?: ""
            val narrationText = result["narration"]?.jsonPrimitive?.contentOrNull
                ?: result["formatted_narration"]?.jsonPrimitive?.contentOrNull
            val emotion = result["emotion"]?.jsonPrimitive?.contentOrNull ?: ""

            if (actorName.isNotBlank() && dialogueText.isNotBlank()) {
                bubbles.add(SceneBubble.Dialogue(
                    id = "resp_d_${bubbleCounter++}",
                    actorName = actorName,
                    text = normalizeLineBreaks(dialogueText),
                    emotion = emotion,
                    avatarType = SceneBubble.AvatarType.ACTOR,
                ))
            } else if (!narrationText.isNullOrBlank() && narrationText.length > 3) {
                bubbles.add(SceneBubble.Narration(
                    id = "resp_n_${bubbleCounter++}",
                    text = normalizeLineBreaks(narrationText),
                    avatarType = SceneBubble.AvatarType.DIRECTOR,
                ))
            }
        }

        return bubbles
    }

    // ============================================================
    // 群聊消息发送（委托 Repository 返回 SceneBubble 列表）
    // ============================================================

    /**
     * 发送群聊消息。
     *
     * ★ 核心修复：消息源唯一化，避免 WS + REST 双重来源导致重复气泡。
     *
     * 策略：
     * - WS 已连接：仅通过 WS 事件接收回复气泡，REST 响应仅用于确认请求成功
     * - WS 未连接：使用 REST 响应中的 respBubbles 作为降级方案，辅以轮询
     */
    fun sendChatMessage(text: String, mention: String?) {
        if (text.isBlank()) return

        _uiState.update { it.copy(isProcessing = true, isTyping = true, typingText = "思考中...") }

        val userBubble = SceneBubble.UserMessage(
            id = "user_${bubbleCounter++}",
            text = text,
            mention = mention,
        )
        _uiState.update { it.copy(bubbles = it.bubbles + userBubble) }

        viewModelScope.launch {
            val isWsConnected = _uiState.value.isWsConnected
            dramaRepository.sendChatMessageAsBubbles(text, mention)
                .onSuccess { respBubbles ->
                    if (isWsConnected) {
                        // ★ WS 已连接：REST 响应气泡丢弃，由 WS 事件驱动 UI
                        // REST 仅用于确认请求已被后端接收，回复内容由 WS 推送
                        _uiState.update { it.copy(isProcessing = false) }
                    } else {
                        // ★ WS 未连接：降级使用 REST 响应气泡
                        if (respBubbles.isNotEmpty()) {
                            _uiState.update { it.copy(
                                bubbles = it.bubbles + respBubbles,
                                isTyping = false,
                                isProcessing = false,
                            ) }
                        } else {
                            startReplyPolling()
                            _uiState.update { it.copy(isProcessing = false) }
                        }
                    }
                }
                .onFailure { e ->
                    _uiState.update { it.copy(isTyping = false, isProcessing = false, error = e.message) }
                    _events.emit(DramaDetailEvent.ShowSnackbar("发送失败：${e.message}"))
                }
        }
    }

    // ============================================================
    // WS 断连降级轮询
    // ============================================================

    private fun startReplyPolling() {
        replyPollJob?.cancel()
        replyPollJob = viewModelScope.launch {
            var attempts = 0
            val maxAttempts = 20
            while (attempts < maxAttempts && _uiState.value.isTyping) {
                kotlinx.coroutines.delay(1000)
                attempts++

                dramaRepository.getDramaStatus()
                    .onSuccess { status ->
                        if (status.current_scene > lastKnownScene) {
                            lastKnownScene = status.current_scene
                            loadSceneBubbles(status.current_scene, "poll_")
                            return@launch
                        }
                    }

                val currentScene = _uiState.value.currentScene
                if (currentScene > 0) {
                    dramaRepository.getSceneBubbles(currentScene, "poll_reply_", includeDivider = false)
                        .onSuccess { sceneBubbles ->
                            val lastDialogueIdx = _uiState.value.bubbles.indexOfLast {
                                it is SceneBubble.Dialogue || it is SceneBubble.Narration
                            }
                            val existingCount = if (lastDialogueIdx >= 0) lastDialogueIdx + 1 else 0

                            if (sceneBubbles.size > existingCount) {
                                loadSceneBubbles(currentScene, "poll_")
                                return@launch
                            }
                        }
                }
            }
            if (_uiState.value.isTyping) {
                _uiState.update { it.copy(isTyping = false, isProcessing = false) }
            }
        }
    }

    override fun onCleared() {
        super.onCleared()
        wsJob?.cancel()
        connectionStateJob?.cancel()
        pollingJob?.cancel()
        replyPollJob?.cancel()
        // ★ 修复：onCleared 时必须完整断开 WS，否则单例 WebSocketManager 会保留断开的连接
        webSocketManager.disconnect()
    }
}
