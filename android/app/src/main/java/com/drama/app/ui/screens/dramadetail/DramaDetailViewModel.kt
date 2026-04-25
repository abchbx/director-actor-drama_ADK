package com.drama.app.ui.screens.dramadetail

import android.util.Log
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.drama.app.data.local.DramaSaveRepository
import com.drama.app.data.local.ServerPreferences
import com.drama.app.data.remote.dto.ArcProgressDto
import com.drama.app.data.remote.dto.CommandResponseDto
import com.drama.app.data.remote.dto.SceneSummaryDto
import com.drama.app.data.remote.dto.WsEventDto
import com.drama.app.data.remote.ws.ConnectionState
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

    // === ★ 主角模式 ===
    val protagonistName: String = "主角",
    val showPlotGuidance: Boolean = false,
    val plotGuidanceText: String = "",

    // === 连接状态（密封类，替代 isWsConnected + isReconnecting） ===
    val connectionState: ConnectionState = ConnectionState.Disconnected,
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

    // === 本地存档 ===
    val availableSaves: List<String> = emptyList(),
) {
    // 向后兼容便捷属性（类体中的计算属性，不参与 copy()）
    val isWsConnected: Boolean get() = connectionState == ConnectionState.Connected
    val isReconnecting: Boolean get() = connectionState is ConnectionState.Reconnecting
}

sealed class DramaDetailEvent {
    data class ShowSnackbar(val message: String) : DramaDetailEvent()
    /** ★ 触觉反馈事件 — AI 回合开始时触发，提示用户后端已开始响应 */
    data object HapticFeedback : DramaDetailEvent()
}

@HiltViewModel
class DramaDetailViewModel @Inject constructor(
    private val dramaRepository: DramaRepository,
    private val dramaSaveRepository: DramaSaveRepository,
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
    // ★ 追踪已添加的错误气泡 id，避免重复
    private val addedErrorIds = mutableSetOf<String>()

    init {
        resetAllState(activeDramaId)
        performInitSync()
        observeAvailableSaves()
    }

    /**
     * 监听本地存档名称列表，自动更新 UiState.availableSaves。
     * DataStore 的 `data` 是 Flow，不阻塞主线程。
     */
    private fun observeAvailableSaves() {
        viewModelScope.launch {
            dramaSaveRepository.getSaveNames(activeDramaId).collect { names ->
                _uiState.update { it.copy(availableSaves = names) }
            }
        }
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
        addedErrorIds.clear()
        _uiState.value = DramaDetailUiState(activeDramaId = dramaId)
    }

    /**
     * ★ 将错误消息作为 SystemError 气泡追加到消息列表中。
     * 使用 [addedErrorIds] 去重，防止同一错误重复添加。
     */
    private fun addErrorBubble(errorMessage: String) {
        val errorId = "sys_err_${bubbleCounter}"
        if (addedErrorIds.contains(errorMessage)) return
        addedErrorIds.add(errorMessage)
        _uiState.update { it.copy(
            bubbles = it.bubbles + SceneBubble.SystemError(
                id = errorId,
                text = errorMessage,
            )
        ) }
        bubbleCounter++
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
        val isAlreadyConnected = webSocketManager.connectionState.value == ConnectionState.Connected

        // 设置回调（无论是否复用连接都需要）
        webSocketManager.onReconnected = {
            onWsReconnected()
        }
        webSocketManager.onPermanentFailure = {
            Log.w(TAG, "WS permanent failure, degrading to REST mode")
            val msg = "WebSocket 连接失败，已降级到 REST 轮询"
            _uiState.update { it.copy(error = msg) }
            addErrorBubble("[错误] $msg")
        }

        if (isAlreadyConnected) {
            // ★ 复用已有连接：直接开始 collect 事件，无需重新 connect()
            Log.i(TAG, "WS already connected, reusing existing connection")
            wsJob = viewModelScope.launch {
                webSocketManager.events
                    .catch { e ->
                        _uiState.update { it.copy(error = e.message) }
                        addErrorBubble("[错误] ${e.message ?: "WebSocket 连接异常"}")
                    }
                    .collect { event -> handleWsEvent(event) }
            }
        } else {
            // 正常流程：建立新的 WS 连接
            wsJob = viewModelScope.launch {
                val config = serverPreferences.serverConfig.first() ?: return@launch
                webSocketManager.connect(config.ip, config.port, config.token, config.baseUrl)
                    .catch { e ->
                        _uiState.update { it.copy(error = e.message) }
                        addErrorBubble("[错误] ${e.message ?: "WebSocket 连接异常"}")
                    }
                    .collect { event -> handleWsEvent(event) }
            }
        }

        // 收集 ConnectionState 密封类，统一驱动 UI 连接状态
        connectionStateJob = viewModelScope.launch {
            webSocketManager.connectionState.collect { state ->
                _uiState.update { it.copy(connectionState = state) }
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

    /**
     * 供 UI DisposableEffect 调用：离开屏幕时主动断开 WebSocket 连接。
     * 与 disconnectWebSocketSafely 不同，此方法还会调用 webSocketManager.disconnect()
     * 确保物理连接也被关闭，避免泄露。
     */
    fun disconnectWebSocket() {
        disconnectWebSocketSafely()
        webSocketManager.disconnect()
    }

    // ============================================================
    // REST 轮询降级
    // ============================================================

    private fun startPolling() {
        pollingJob?.cancel()
        pollingJob = viewModelScope.launch {
            while (true) {
                kotlinx.coroutines.delay(3000)
                // ★ 修复：轮询不仅用于 WS 断连降级，也用于同步 outlineSummary 等状态
                // WS 事件只推送增量变化，outlineSummary 需要通过 REST 获取
                pollStatus()
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
        // ★ 增强：同步更新 typingText，让 TypingIndicator 实时反映后端进度
        if (event.type == "director_log") {
            val msg = event.data["message"]?.jsonPrimitive?.contentOrNull
            val tool = event.data["tool"]?.jsonPrimitive?.contentOrNull
            if (!msg.isNullOrBlank()) {
                // 用 director_log 的消息覆盖 typingText，消除黑盒卡顿感
                val updatedTypingText = msg
                _uiState.update { it.copy(
                    stormPhase = msg,
                    typingText = updatedTypingText,
                    isTyping = true,
                ) }
            } else if (!tool.isNullOrBlank()) {
                // 如果只有 tool 没有 message，用 getTypingText 映射
                _uiState.update { it.copy(
                    typingText = getTypingText(tool),
                    isTyping = true,
                ) }
            }
            return
        }

        when (event.type) {
            // ★ 修复：narration 事件 — 仅在 response 阶段（text 非空）创建气泡
            "narration" -> {
                val text = event.data["text"]?.jsonPrimitive?.contentOrNull ?: ""
                val senderName = event.data["sender_name"]?.jsonPrimitive?.contentOrNull ?: "旁白"

                if (text.isBlank()) {
                    // call 阶段：只更新 typing 指示
                    _uiState.update { it.copy(isTyping = true, typingText = "旁白正在讲述...") }
                    return
                }

                // ★ 防御性去重：跳过与上一个旁白气泡完全相同的重复推送
                val lastBubble = _uiState.value.bubbles.lastOrNull()
                if (lastBubble is SceneBubble.Narration && lastBubble.text == normalizeLineBreaks(text)) {
                    return
                }

                _uiState.update { it.copy(isTyping = false, stormPhase = null) }
                val normalizedText = normalizeLineBreaks(text)
                if (normalizedText.isNotBlank()) {
                    val bubble = SceneBubble.Narration(
                        id = "b_${bubbleCounter++}",
                        text = normalizedText,
                        avatarType = SceneBubble.AvatarType.DIRECTOR,
                        senderType = SceneBubble.SenderType.DIRECTOR,
                        senderName = senderName,
                    )
                    _uiState.update { it.copy(bubbles = it.bubbles + bubble, typingText = "AI 正在思考...") }
                }
            }

            "dialogue" -> {
                val actorName = event.data["actor_name"]?.jsonPrimitive?.contentOrNull ?: ""
                val text = event.data["text"]?.jsonPrimitive?.contentOrNull ?: ""
                val emotion = event.data["emotion"]?.jsonPrimitive?.contentOrNull ?: ""
                val senderName = event.data["sender_name"]?.jsonPrimitive?.contentOrNull ?: actorName

                // ★ 核心修复：仅当 text 非空时才创建气泡
                if (text.isBlank()) {
                    // call 阶段：只更新 typing 指示，不创建气泡
                    _uiState.update { it.copy(isTyping = true, typingText = "${actorName}正在说话...") }
                    return
                }

                // ★ 防御性去重：跳过与上一个对话气泡完全相同的重复推送
                val normalizedText = normalizeLineBreaks(text)
                val lastBubble = _uiState.value.bubbles.lastOrNull()
                if (lastBubble is SceneBubble.Dialogue
                    && lastBubble.actorName == actorName
                    && lastBubble.text == normalizedText
                ) {
                    return
                }

                _uiState.update { it.copy(isTyping = false, stormPhase = null) }

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
                        senderType = SceneBubble.SenderType.ACTOR,
                        senderName = senderName,
                    )
                    _uiState.update { it.copy(bubbles = it.bubbles + bubble) }
                }
            }

            "end_narration" -> {
                val text = event.data["text"]?.jsonPrimitive?.contentOrNull ?: ""
                val senderName = event.data["sender_name"]?.jsonPrimitive?.contentOrNull ?: "旁白"
                val normalizedText = normalizeLineBreaks(text)
                if (normalizedText.isNotBlank()) {
                    val bubble = SceneBubble.Narration(
                        id = "b_${bubbleCounter++}",
                        text = normalizedText,
                        avatarType = SceneBubble.AvatarType.DIRECTOR,
                        senderType = SceneBubble.SenderType.DIRECTOR,
                        senderName = senderName,
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
                // ★ AI 回合正式开始，触发触觉反馈提示用户
                viewModelScope.launch { _events.emit(DramaDetailEvent.HapticFeedback) }
            }

            "error" -> {
                val msg = event.data["message"]?.jsonPrimitive?.contentOrNull ?: "Unknown error"
                _uiState.update { it.copy(isTyping = false, isProcessing = false, stormPhase = null, error = msg) }
                addErrorBubble("[错误] $msg")
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
                val senderName = event.data["sender_name"]?.jsonPrimitive?.contentOrNull ?: actorName

                // ★ 修复：仅当 text 非空时才创建气泡（同 dialogue 逻辑）
                if (text.isBlank()) {
                    _uiState.update { it.copy(isTyping = true, typingText = "${actorName}想要发言...") }
                    return
                }

                _uiState.update { it.copy(isTyping = false, stormPhase = null) }
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
                        senderType = SceneBubble.SenderType.ACTOR,
                        senderName = senderName,
                    )
                    _uiState.update { it.copy(bubbles = it.bubbles + bubble) }
                }
            }

            "save_confirm" -> {
                val msg = event.data["message"]?.jsonPrimitive?.contentOrNull ?: "已保存"
                _uiState.update { it.copy(isTyping = false, stormPhase = null) }
                viewModelScope.launch { _events.emit(DramaDetailEvent.ShowSnackbar(msg)) }
            }

            "load_confirm" -> {
                val msg = event.data["message"]?.jsonPrimitive?.contentOrNull ?: "已加载"
                _uiState.update { it.copy(isTyping = false, stormPhase = null) }
                viewModelScope.launch { _events.emit(DramaDetailEvent.ShowSnackbar(msg)) }
            }

            // ★ user_message 事件 — 后端推送的用户主角消息（备用通道）
            // 目前用户气泡由 ViewModel 本地创建，此事件作为去重安全网：
            // 仅当本地尚未为该文本创建气泡时才添加
            "user_message" -> {
                val text = event.data["text"]?.jsonPrimitive?.contentOrNull ?: ""
                val mention = event.data["mention"]?.jsonPrimitive?.contentOrNull
                val senderName = event.data["sender_name"]?.jsonPrimitive?.contentOrNull ?: "主角"

                if (text.isNotBlank()) {
                    // ★ 去重：检查本地是否已存在同文本的用户气泡
                    val alreadyExists = _uiState.value.bubbles.any {
                        it is SceneBubble.UserMessage && it.text == text
                    }
                    if (!alreadyExists) {
                        val bubble = SceneBubble.UserMessage(
                            id = "user_msg_${bubbleCounter++}",
                            text = text,
                            mention = mention,
                            avatarType = SceneBubble.AvatarType.USER,
                            senderType = SceneBubble.SenderType.USER,
                            senderName = senderName,
                        )
                        _uiState.update { it.copy(bubbles = it.bubbles + bubble) }
                    }
                }
            }
        }
    }

    /**
     * ★ REST 降级发送消息后的主动 Scene 刷新：
     *
     * 在 WS 断连、降级到 REST 发送消息后，必须立即触发一次 Scene 数据刷新：
     * 1. 通过 REST 获取最新状态，检查场景号是否已变化
     * 2. 场景号已变化 → 加载新场景的完整气泡列表
     * 3. 场景号未变 → 对当前场景做一次气泡合并对齐，补齐 REST 响应可能遗漏的数据
     *
     * ★ 关键：REST 响应可能只包含部分结果（如 CommandResponseDto），
     * 而后端的完整状态（如后继的 actor 回复）只有通过主动 Scene 刷新才能获取。
     * 此方法确保即使在 REST 降级模式下，用户也能看到后端的最新完整数据。
     */
    private fun refreshSceneAfterRestFallback() {
        viewModelScope.launch {
            Log.d(TAG, "REST fallback: 开始主动 Scene 刷新")
            dramaRepository.getDramaStatus()
                .onSuccess { status ->
                    _uiState.update { it.copy(
                        currentScene = status.current_scene,
                        arcProgress = status.arc_progress,
                        timePeriod = status.time_period,
                        outlineSummary = status.outline_summary,
                    ) }
                    if (status.current_scene > lastKnownScene) {
                        // 场景号已变化，加载新场景的完整气泡
                        lastKnownScene = status.current_scene
                        Log.d(TAG, "REST fallback: 场景号变化 → $lastKnownScene，加载新场景气泡")
                        dramaRepository.getSceneBubbles(status.current_scene, "rest_refresh_", includeDivider = true)
                            .onSuccess { serverBubbles ->
                                val localBubbles = _uiState.value.bubbles
                                val merged = mergeBubblesAfterReconnect(localBubbles, serverBubbles)
                                if (merged.size > localBubbles.size) {
                                    _uiState.update { it.copy(bubbles = merged) }
                                    Log.d(TAG, "REST fallback: 合并完成，新增 ${merged.size - localBubbles.size} 个气泡")
                                }
                            }
                    } else if (status.current_scene > 0) {
                        // 场景号未变，对当前场景做合并对齐
                        Log.d(TAG, "REST fallback: 场景号未变，执行气泡合并对齐")
                        dramaRepository.getSceneBubbles(status.current_scene, "rest_sync_", includeDivider = false)
                            .onSuccess { serverBubbles ->
                                val localBubbles = _uiState.value.bubbles
                                val merged = mergeBubblesAfterReconnect(localBubbles, serverBubbles)
                                if (merged.size > localBubbles.size) {
                                    _uiState.update { it.copy(bubbles = merged) }
                                    Log.d(TAG, "REST fallback: 对齐完成，新增 ${merged.size - localBubbles.size} 个气泡")
                                }
                            }
                    }
                }
                .onFailure { e ->
                    Log.w(TAG, "REST fallback: Scene 刷新失败: ${e.message}")
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
    // 本地存档（/save、/load、/list、/delete）
    // ============================================================

    /**
     * 保存当前状态到本地 DataStore。
     * 在协程中执行，不阻塞主线程。
     */
    fun saveState(name: String) {
        val state = _uiState.value
        viewModelScope.launch {
            try {
                dramaSaveRepository.saveState(
                    name = name,
                    dramaId = activeDramaId,
                    currentScene = state.currentScene,
                    theme = state.theme,
                    tensionScore = state.tensionScore,
                    bubbles = state.bubbles,
                )
                _events.emit(DramaDetailEvent.ShowSnackbar("存档 $name 已保存"))
            } catch (e: Exception) {
                _events.emit(DramaDetailEvent.ShowSnackbar("保存失败：${e.message}"))
            }
        }
    }

    /**
     * 从本地 DataStore 加载存档，恢复 ViewModel 状态。
     * UI 会自动刷新（因 bubbles 等字段由 StateFlow 驱动）。
     */
    fun loadState(name: String) {
        viewModelScope.launch {
            try {
                val save = dramaSaveRepository.loadState(name, activeDramaId)
                if (save == null) {
                    _events.emit(DramaDetailEvent.ShowSnackbar("存档 $name 不存在"))
                    return@launch
                }

                // 解析气泡列表
                val restoredBubbles = dramaSaveRepository.decodeBubbles(save.bubblesJson)

                // 恢复 ViewModel 状态
                bubbleCounter = 0
                lastKnownScene = save.currentScene
                _uiState.update { it.copy(
                    currentScene = save.currentScene,
                    theme = save.theme,
                    tensionScore = save.tensionScore,
                    bubbles = restoredBubbles,
                    isTyping = false,
                    isProcessing = false,
                ) }

                _events.emit(DramaDetailEvent.ShowSnackbar("已加载存档：$name"))
            } catch (e: Exception) {
                _events.emit(DramaDetailEvent.ShowSnackbar("加载失败：${e.message}"))
            }
        }
    }

    /**
     * 列出当前剧本的所有存档名称，作为系统消息显示在聊天中。
     */
    fun listSaves() {
        viewModelScope.launch {
            val saves = _uiState.value.availableSaves
            val message = if (saves.isEmpty()) {
                "当前没有存档"
            } else {
                "可用的存档: [${saves.joinToString(", ")}]"
            }
            // 添加系统气泡
            val systemBubble = SceneBubble.Narration(
                id = "sys_${bubbleCounter++}",
                text = message,
                avatarType = SceneBubble.AvatarType.SYSTEM,
            )
            _uiState.update { it.copy(bubbles = it.bubbles + systemBubble) }
        }
    }

    /**
     * 删除指定本地存档。
     */
    fun deleteSave(name: String) {
        viewModelScope.launch {
            try {
                dramaSaveRepository.deleteSave(name, activeDramaId)
                _events.emit(DramaDetailEvent.ShowSnackbar("已删除存档：$name"))
            } catch (e: Exception) {
                _events.emit(DramaDetailEvent.ShowSnackbar("删除失败：${e.message}"))
            }
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
     * ★ WS 重连成功后状态强制对齐（虎贲攻坚版）：
     *
     * 断网重连后的完整对齐流程：
     * 1. 重新 switchToDrama 确保服务端 session 一致
     * 2. 刷新全量状态（主题、场次、弧线等）
     * 3. 获取后端当前场景的完整气泡列表（权威来源）
     * 4. 与 UI 现有气泡合并去重：保留旧气泡的 UI 状态，追加断网期间丢失的新气泡
     * 5. 同步 lastKnownScene 和 currentScene，防止后续轮询重复加载
     *
     * ★ 关键：此方法由 webSocketManager.onReconnected 回调触发，
     * 在 WebSocket 重新建立连接后立即执行，确保断网期间的状态漂移被修正。
     */
    private fun onWsReconnected() {
        viewModelScope.launch {
            Log.i(TAG, "WS reconnected: ★ 开始强制状态对齐")

            // 1. 重新切换到当前剧本，确保服务端 session 一致
            if (activeDramaId.isNotBlank() && !skipLoad) {
                val switchOk = switchToDramaAndWait(activeDramaId)
                if (!switchOk) {
                    Log.e(TAG, "WS reconnected: switchToDrama 失败，对齐中止！")
                    addErrorBubble("[重连] 切换剧本失败，状态可能不一致")
                    return@launch
                }
                Log.d(TAG, "WS reconnected: switchToDrama 成功")
            }

            // 2. 刷新全量状态
            val statusResult = dramaRepository.getDramaStatus()
            val currentScene = statusResult.getOrNull()?.current_scene ?: _uiState.value.currentScene

            statusResult.onSuccess { status ->
                _uiState.update { it.copy(
                    theme = status.theme,
                    currentScene = status.current_scene,
                    arcProgress = status.arc_progress,
                    timePeriod = status.time_period,
                    outlineSummary = status.outline_summary,
                ) }
                if (status.current_scene > lastKnownScene) {
                    lastKnownScene = status.current_scene
                    Log.d(TAG, "WS reconnected: lastKnownScene 更新为 ${status.current_scene}")
                }
            }.onFailure { e ->
                Log.w(TAG, "WS reconnected: getDramaStatus 失败: ${e.message}")
            }

            // 3. 获取后端最新完整气泡列表（权威来源）
            if (currentScene <= 0) {
                Log.d(TAG, "WS reconnected: 无当前场景，跳过气泡对齐")
                return@launch
            }

            dramaRepository.getSceneBubbles(currentScene, "sync_", includeDivider = true)
                .onSuccess { serverBubbles ->
                    val existingBubbles = _uiState.value.bubbles
                    val existingSize = existingBubbles.size

                    // 4. 合并去重：保留旧气泡 UI 状态，追加断网期间丢失的新气泡
                    val merged = mergeBubblesAfterReconnect(existingBubbles, serverBubbles)

                    // ★ 只有真正有变化时才更新，避免不必要的 recomposition
                    val newSize = merged.size
                    if (merged != existingBubbles) {
                        _uiState.update { it.copy(bubbles = merged) }
                        Log.i(TAG, "WS reconnected: ★ 气泡对齐完成！local=$existingSize, server=${serverBubbles.size}, merged=$newSize, 新增=${newSize - existingSize}")
                    } else {
                        Log.i(TAG, "WS reconnected: 气泡无变化，无需更新")
                    }
                }
                .onFailure { e ->
                    Log.w(TAG, "WS reconnected: 获取场景气泡失败: ${e.message}")
                    addErrorBubble("[重连] 同步气泡失败，数据可能不完整")
                }
        }
    }

    /**
     * ★ 断网重连后气泡合并去重策略（基于后端权威顺序的智能合并）：
     *
     * 核心原则：
     * - 后端列表为权威顺序来源，新气泡按后端时序插入
     * - 本地气泡保留 UI 状态（如动画、展开等），不丢弃
     * - 通过 contentFingerprint（已重写 equals/hashCode）判断同一消息
     *
     * 合并算法：
     * 1. 构建本地指纹集合，用于快速去重判断
     * 2. 遍历后端列表，维护已合并集合防止重复
     * 3. 后端有 & 本地没有 → 插入（断网期间丢失的新消息）
     * 4. 后端有 & 本地也有 → 保留本地的（保留 UI 状态）
     * 5. 本地有 & 后端没有 → 保留（用户消息、本地即时气泡等）
     * 6. 将仅存在于本地的气泡追加到末尾
     *
     * ★ 改进：不再简单追加，而是按后端顺序穿插插入新气泡，
     * 保证消息时序的正确性。
     */
    private fun mergeBubblesAfterReconnect(
        localBubbles: List<SceneBubble>,
        serverBubbles: List<SceneBubble>,
    ): List<SceneBubble> {
        if (serverBubbles.isEmpty()) return localBubbles
        if (localBubbles.isEmpty()) return serverBubbles

        // ★ 利用重写后的 equals/hashCode，构建本地指纹集合
        val localFingerprintSet = localBubbles.map { it.contentFingerprint }.toMutableSet()
        // ★ 本地气泡指纹 → 本地气泡实例（保留 UI 状态）
        val localByFingerprint = localBubbles.associateBy { it.contentFingerprint }

        val merged = mutableListOf<SceneBubble>()
        val mergedFingerprints = mutableSetOf<String>()

        // 1. 按后端权威顺序遍历，确保时序正确
        for (serverBubble in serverBubbles) {
            val fp = serverBubble.contentFingerprint
            if (fp in mergedFingerprints) continue  // 防重复

            if (fp in localFingerprintSet) {
                // 本地也有 → 保留本地版本（保留 UI 状态）
                val localBubble = localByFingerprint[fp] ?: serverBubble
                merged.add(localBubble)
            } else {
                // 仅后端有 → 断网期间丢失的新消息，按后端顺序插入
                merged.add(serverBubble)
            }
            mergedFingerprints.add(fp)
        }

        // 2. 追加仅存在于本地的气泡（用户消息、本地即时气泡等后端不知道的）
        for (localBubble in localBubbles) {
            val fp = localBubble.contentFingerprint
            if (fp !in mergedFingerprints) {
                merged.add(localBubble)
                mergedFingerprints.add(fp)
            }
        }

        return merged
    }

    /**
     * 用户主动重试连接（点击"重试"按钮时调用）。
     * 重置失败计数，重新发起 WebSocket 连接。
     */
    fun retryConnection() {
        disconnectWebSocketSafely()
        hasCalledConnectWebSocket = true
        connectWebSocket()
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

        // ★ 本地存档命令：不走 REST API，直接在本地处理
        when (commandType) {
            CommandType.SAVE -> {
                val name = text.removePrefix("/save").trim().ifBlank { "autosave" }
                saveState(name)
                return
            }
            CommandType.LOAD -> {
                val name = text.removePrefix("/load").trim()
                if (name.isBlank()) {
                    viewModelScope.launch {
                        _events.emit(DramaDetailEvent.ShowSnackbar("请指定存档名称，如 /load my_progress"))
                    }
                    return
                }
                loadState(name)
                return
            }
            CommandType.LIST -> {
                listSaves()
                return
            }
            CommandType.DELETE -> {
                val name = text.removePrefix("/delete").trim()
                if (name.isBlank()) {
                    viewModelScope.launch {
                        _events.emit(DramaDetailEvent.ShowSnackbar("请指定存档名称，如 /delete my_progress"))
                    }
                    return
                }
                deleteSave(name)
                return
            }
            CommandType.CAST -> {
                // ★ /cast 命令：查询当前活跃演员阵容
                viewModelScope.launch {
                    dramaRepository.getMergedCast()
                        .onSuccess { actors ->
                            if (actors.isEmpty()) {
                                val bubble = SceneBubble.Narration(
                                    id = "cast_${bubbleCounter++}",
                                    text = "当前没有活跃的演员",
                                    avatarType = SceneBubble.AvatarType.SYSTEM,
                                    senderType = SceneBubble.SenderType.SYSTEM,
                                    senderName = "系统",
                                )
                                _uiState.update { it.copy(bubbles = it.bubbles + bubble) }
                            } else {
                                val castText = buildString {
                                    append("🎭 当前演员阵容\n")
                                    actors.forEach { actor ->
                                        append("• ${actor.name}（${actor.role}）— ${actor.emotions}\n")
                                    }
                                }
                                val bubble = SceneBubble.Narration(
                                    id = "cast_${bubbleCounter++}",
                                    text = castText.trimEnd(),
                                    avatarType = SceneBubble.AvatarType.DIRECTOR,
                                    senderType = SceneBubble.SenderType.DIRECTOR,
                                    senderName = "旁白",
                                )
                                _uiState.update { it.copy(bubbles = it.bubbles + bubble) }
                            }
                        }
                        .onFailure { e ->
                            addErrorBubble("[错误] 查询演员阵容失败：${e.message}")
                        }
                }
                return
            }
            else -> { /* 继续走原有逻辑 */ }
        }

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
            CommandType.SAVE, CommandType.LOAD, CommandType.LIST, CommandType.DELETE, CommandType.CAST ->
                ""  // 本地存档命令已在上方处理，/cast 不显示用户气泡
            CommandType.FREE_TEXT -> text.trim()
        }

        // ★ 交互语义区分：ACTION/NEXT 是动作行为，渲染为居中斜体；其他是对话，渲染为右侧气泡
        val isActionCommand = commandType in listOf(CommandType.ACTION, CommandType.NEXT)

        val userBubble = SceneBubble.UserMessage(
            id = "cmd_${bubbleCounter++}",
            text = displayText,
            mention = if (commandType == CommandType.SPEAK) {
                text.removePrefix("/speak").trim().split(" ", limit = 2).getOrNull(0)
            } else null,
            avatarType = SceneBubble.AvatarType.USER,
            senderType = SceneBubble.SenderType.USER,
            senderName = _uiState.value.protagonistName,
            isAction = isActionCommand,
        )

        // ★ 剧情引导反馈：用户指令改变剧情时，显示确认提示
        val isPlotChanging = commandType in listOf(
            CommandType.NEXT, CommandType.ACTION, CommandType.SPEAK, CommandType.FREE_TEXT
        )
        val plotGuidance = if (isPlotChanging) {
            SceneBubble.PlotGuidance(
                id = "pg_${bubbleCounter++}",
                text = when (commandType) {
                    CommandType.NEXT -> "剧情正在转向下一场..."
                    CommandType.ACTION -> "剧情已转向：${text.removePrefix("/action").trim().take(20)}..."
                    CommandType.SPEAK -> "角色正在回应你的指令..."
                    CommandType.FREE_TEXT -> "剧情正在因你而改变..."
                    else -> "剧情已转向..."
                },
                direction = when (commandType) {
                    CommandType.NEXT -> "next_scene"
                    CommandType.ACTION -> "user_action"
                    CommandType.SPEAK -> "actor_speak"
                    else -> "free_text"
                },
            )
        } else null
        _uiState.update { it.copy(
            isProcessing = true,
            isTyping = true,
            typingText = "思考中...",
            bubbles = it.bubbles + userBubble + listOfNotNull(plotGuidance),
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
                CommandType.SAVE, CommandType.LOAD, CommandType.LIST, CommandType.DELETE, CommandType.CAST ->
                    Result.success(CommandResponseDto())  // 不会到达此处
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
                // ★ REST 降级发送后，立即触发一次 Scene 数据刷新
                // 确保断网期间可能被后端处理的状态变化被同步回来
                refreshSceneAfterRestFallback()
            }

            result.onFailure { e ->
                _uiState.update { it.copy(isTyping = false, isProcessing = false, error = e.message) }
                addErrorBubble("[错误] 命令失败：${e.message}")
                _events.emit(DramaDetailEvent.ShowSnackbar("命令失败：${e.message}"))
            }
        }
    }

    /**
     * ★ 新增：从 CommandResponse 提取可渲染的 SceneBubble 列表（WS 断连降级用）
     * ★ 增强：识别响应中针对主角的反应
     */
    private fun extractBubblesFromCommandResponse(resp: CommandResponseDto): List<SceneBubble> {
        val bubbles = mutableListOf<SceneBubble>()
        val protagonistName = _uiState.value.protagonistName

        if (resp.final_response.isNotBlank() && resp.final_response.length > 5) {
            // ★ 增强识别：若 final_response 提及主角，标记 senderName
            val narrationText = normalizeLineBreaks(resp.final_response.trim())
            val mentionsProtagonist = narrationText.contains(protagonistName) || narrationText.contains("@主角")
            bubbles.add(SceneBubble.Narration(
                id = "resp_n_${bubbleCounter++}",
                text = narrationText,
                avatarType = SceneBubble.AvatarType.DIRECTOR,
                senderType = SceneBubble.SenderType.DIRECTOR,
                senderName = if (mentionsProtagonist) "旁白 →主角" else "旁白",
            ))
        }

        for (result in resp.tool_results) {
            val actorName = result["actor_name"]?.jsonPrimitive?.contentOrNull ?: ""
            val dialogueText = result["text"]?.jsonPrimitive?.contentOrNull ?: ""
            val narrationText = result["narration"]?.jsonPrimitive?.contentOrNull
                ?: result["formatted_narration"]?.jsonPrimitive?.contentOrNull
            val emotion = result["emotion"]?.jsonPrimitive?.contentOrNull ?: ""
            // ★ 增强识别：检测 tool_results 中的 target/sender_name 字段
            val targetUser = result["target"]?.jsonPrimitive?.contentOrNull ?: ""
            val senderName = result["sender_name"]?.jsonPrimitive?.contentOrNull ?: actorName

            if (actorName.isNotBlank() && dialogueText.isNotBlank()) {
                // ★ 增强：若对话提及主角名或 target 为 user，标记 emotion
                val mentionsProtagonist = dialogueText.contains(protagonistName)
                        || dialogueText.contains("@主角")
                        || targetUser.equals("user", ignoreCase = true)
                        || targetUser.equals(protagonistName, ignoreCase = true)
                val enhancedEmotion = if (mentionsProtagonist && !emotion.contains("→主角")) {
                    emotion.ifBlank { "" } + " →主角"
                } else emotion

                bubbles.add(SceneBubble.Dialogue(
                    id = "resp_d_${bubbleCounter++}",
                    actorName = actorName,
                    text = normalizeLineBreaks(dialogueText),
                    emotion = enhancedEmotion,
                    avatarType = SceneBubble.AvatarType.ACTOR,
                    senderType = SceneBubble.SenderType.ACTOR,
                    senderName = senderName,
                ))
            } else if (!narrationText.isNullOrBlank() && narrationText.length > 3) {
                bubbles.add(SceneBubble.Narration(
                    id = "resp_n_${bubbleCounter++}",
                    text = normalizeLineBreaks(narrationText),
                    avatarType = SceneBubble.AvatarType.DIRECTOR,
                    senderType = SceneBubble.SenderType.DIRECTOR,
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
     * ★ 主角模式：附带角色身份标识（senderType + senderName），供后端识别。
     *
     * 策略：
     * - WS 已连接：仅通过 WS 事件接收回复气泡，REST 响应仅用于确认请求成功
     * - WS 未连接：使用 REST 响应中的 respBubbles 作为降级方案，辅以轮询
     */
    fun sendChatMessage(text: String, mention: String?) {
        if (text.isBlank()) return

        _uiState.update { it.copy(isProcessing = true, isTyping = true, typingText = "思考中...") }

        val protagonistName = _uiState.value.protagonistName
        val userBubble = SceneBubble.UserMessage(
            id = "user_${bubbleCounter++}",
            text = text,
            mention = mention,
            avatarType = SceneBubble.AvatarType.USER,
            senderType = SceneBubble.SenderType.USER,
            senderName = protagonistName,
        )
        _uiState.update { it.copy(bubbles = it.bubbles + userBubble) }

        viewModelScope.launch {
            val isWsConnected = _uiState.value.isWsConnected
            dramaRepository.sendChatMessageAsBubbles(text, mention, protagonistName)
                .onSuccess { respBubbles ->
                    if (isWsConnected) {
                        // ★ WS 已连接：REST 响应气泡丢弃，由 WS 事件驱动 UI
                        // REST 仅用于确认请求已被后端接收，回复内容由 WS 推送
                        _uiState.update { it.copy(isProcessing = false) }
                    } else {
                        // ★ WS 未连接：降级使用 REST 响应气泡
                        // ★ 增强：识别响应中针对主角的反应
                        val enhancedBubbles = enhanceBubblesWithProtagonistContext(respBubbles, text)
                        if (enhancedBubbles.isNotEmpty()) {
                            _uiState.update { it.copy(
                                bubbles = it.bubbles + enhancedBubbles,
                                isTyping = false,
                                isProcessing = false,
                            ) }
                        } else {
                            startReplyPolling()
                            _uiState.update { it.copy(isProcessing = false) }
                        }
                        // ★ REST 降级发送后，立即触发一次 Scene 数据刷新
                        refreshSceneAfterRestFallback()
                    }
                }
                .onFailure { e ->
                    _uiState.update { it.copy(isTyping = false, isProcessing = false, error = e.message) }
                    addErrorBubble("[错误] 发送失败：${e.message}")
                    _events.emit(DramaDetailEvent.ShowSnackbar("发送失败：${e.message}"))
                }
        }
    }

    /**
     * ★ 增强气泡列表：识别响应中哪些是针对主角的反应。
     * 
     * 策略：
     * - 若 dialogue 提及主角名或含"@主角"标记，标记为针对主角的反应
     * - 若 narration 含"你"或主角名，标记为针对主角的旁白
     */
    private fun enhanceBubblesWithProtagonistContext(
        bubbles: List<SceneBubble>,
        userMessage: String,
    ): List<SceneBubble> {
        val protagonistName = _uiState.value.protagonistName
        return bubbles.map { bubble ->
            when (bubble) {
                is SceneBubble.Dialogue -> {
                    val mentionsProtagonist = bubble.text.contains(protagonistName)
                            || bubble.text.contains("@${protagonistName}")
                            || bubble.text.contains("@主角")
                    bubble.copy(
                        senderName = if (bubble.senderName.isBlank()) bubble.actorName else bubble.senderName,
                    )
                    // ★ 对话提及主角时，通过 emotion 字段附加标记（不改模型，复用现有字段）
                    if (mentionsProtagonist && !bubble.emotion.contains("→主角")) {
                        bubble.copy(emotion = bubble.emotion.ifBlank { "" } + " →主角")
                    } else bubble
                }
                else -> bubble
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
