package com.drama.app.ui.screens.dramadetail

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.drama.app.data.local.ServerPreferences
import com.drama.app.data.remote.dto.ArcProgressDto
import com.drama.app.data.remote.dto.SceneSummaryDto
import com.drama.app.data.remote.dto.WsEventDto
import com.drama.app.data.remote.ws.WebSocketManager
import com.drama.app.domain.model.ActorInfo
import com.drama.app.domain.model.CommandType
import com.drama.app.domain.model.InteractionType
import com.drama.app.domain.model.SceneBubble
import com.drama.app.domain.repository.DramaRepository
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
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
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
    val activeDramaId: String = "",          // 当前正在查看的剧本 ID（folder name）

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
    val error: String? = null,

    // === 场景历史 D-18~D-20 ===
    val viewingHistoryScene: Int? = null,
    val historyScenes: List<SceneSummaryDto> = emptyList(),
    val showHistorySheet: Boolean = false,

    // === 保存操作 D-23 ===
    val showSaveDialog: Boolean = false,

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
    savedStateHandle: SavedStateHandle,
) : ViewModel() {
    /**
     * 当前活跃的剧本标识符。
     * 来自导航参数，用于：
     * 1. 数据隔离判断（防止不同剧本事件串台）
     * 2. 日志追踪
     * 3. 未来可扩展为请求参数
     */
    private val activeDramaId: String = savedStateHandle["dramaId"] ?: ""

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

    init {
        // ★ 核心：初始化时完全重置状态 + 设置 dramaId
        resetAllState(activeDramaId)

        // ★★★ 关键修复：先调 POST /drama/load 切换服务端上下文到当前剧本 ★★★
        // 后端所有 API（status/cast/scenes/chat）都是基于"当前活跃剧本"返回数据的。
        // 如果不等 loadDrama 完成就去 loadInitialStatus，服务端仍返回上一个操作的剧本数据（如"南阳三子"），
        // 导致：创建新剧本后跳转看到旧剧本的内容和演员。
        if (activeDramaId.isNotBlank()) {
            viewModelScope.launch {
                switchToDramaAndWait(activeDramaId)
                // loadDrama 完成后，再依次初始化其他模块（严格顺序）
                loadInitialStatus()
                connectWebSocket()
                startPolling()
            }
        } else {
            // 无 dramaId 时降级处理（理论上不会走到这里）
            loadInitialStatus()
            connectWebSocket()
            startPolling()
        }
    }

    /**
     * 切换服务端活跃剧本上下文 — 同步等待版本（带超时）
     *
     * 调用 POST /drama/load 告诉后端"我们要操作哪个剧本了"，并**等待其完成**。
     * 这是解决"创建新剧本跳转到旧剧本数据"的核心方法。
     *
     * @return true 表示成功（或可忽略的失败），false 表示需要降级处理
     */
    private suspend fun switchToDramaAndWait(dramaId: String): Boolean {
        return try {
            dramaRepository.loadDrama(dramaId)
                .onSuccess {
                    // loadDrama 成功，服务端已切换到目标剧本
                }
                .onFailure { e ->
                    // 即使 loadDrama 失败也继续（可能新剧本尚未有存档）
                    // 后续 getDramaStatus 会获取当前状态作为降级
                }
            true
        } catch (e: Exception) {
            false
        }
    }

    /**
     * 切换服务端活跃剧本上下文（异步版本，供 returnToCurrentScene 等场景使用）
     */
    private fun switchToDrama(dramaId: String) {
        viewModelScope.launch {
            switchToDramaAndWait(dramaId)
        }
    }

    /**
     * 完全重置所有状态为初始值，并设置新的 dramaId。
     * 此方法是数据隔离的核心——每次进入新剧本时调用，
     * 确保不会看到上一个剧本的气泡、演员、场景历史等。
     */
    private fun resetAllState(dramaId: String) {
        bubbleCounter = 0
        lastKnownScene = 0
        replyPollJob?.cancel()
        replyPollJob = null

        _uiState.value = DramaDetailUiState(
            activeDramaId = dramaId,
        )
    }

    private fun loadInitialStatus() {
        viewModelScope.launch {
            dramaRepository.getDramaStatus()
                .onSuccess { status ->
                    _uiState.update { it.copy(
                        theme = status.theme,
                        currentScene = status.current_scene,
                        isWsConnected = true,
                        arcProgress = status.arc_progress,
                        timePeriod = status.time_period,
                    ) }
                    // 加载完基础状态后，加载当前场景的已有对话内容
                    if (status.current_scene > 0) {
                        lastKnownScene = status.current_scene
                        loadExistingBubbles(status.current_scene)
                    }
                    // ★ 自动预加载演员面板数据
                    // 这样用户点击演员按钮时无需等待网络请求
                    if (status.num_actors > 0) {
                        preloadActorPanel()
                    }
                }
        }
    }

    /**
     * 加载已存在的对话气泡（用于剧本恢复或首次加载）
     */
    private fun loadExistingBubbles(sceneNumber: Int) {
        viewModelScope.launch {
            dramaRepository.getSceneDetail(sceneNumber)
                .onSuccess { detail ->
                    val existingBubbles = mutableListOf<SceneBubble>()

                    // 添加场景分隔线
                    existingBubbles.add(SceneBubble.SceneDivider(
                        id = "init_div_$sceneNumber",
                        sceneNumber = sceneNumber,
                        sceneTitle = detail.title,
                    ))

                    // 添加旁白
                    if (detail.narration.isNotBlank()) {
                        existingBubbles.add(SceneBubble.Narration(
                            id = "init_${sceneNumber}_n",
                            text = detail.narration,
                        ))
                    }

                    // 添加所有已有对话
                    for ((idx, d) in detail.dialogue.withIndex()) {
                        val actorName = d["actor_name"]?.jsonPrimitive?.contentOrNull ?: ""
                        val text = d["text"]?.jsonPrimitive?.contentOrNull ?: ""
                        val emotion = d["emotion"]?.jsonPrimitive?.contentOrNull ?: ""
                        if (actorName.isNotBlank() && text.isNotBlank()) {
                            existingBubbles.add(SceneBubble.Dialogue(
                                id = "init_${sceneNumber}_d$idx",
                                actorName = actorName,
                                text = text,
                                emotion = emotion,
                            ))
                        }
                    }

                    if (existingBubbles.size > 1) { // 超过分隔线本身
                        _uiState.update { it.copy(bubbles = existingBubbles) }
                    }
                }
        }
    }

    // ============================================================
    // WebSocket 管理
    // ============================================================

    fun connectWebSocket() {
        // 先断开旧连接（防止多剧本同时监听同一 WS 导致事件串台）
        disconnectWebSocketSafely()

        wsJob?.cancel()
        connectionStateJob?.cancel()

        wsJob = viewModelScope.launch {
            val config = serverPreferences.serverConfig.first() ?: return@launch
            webSocketManager.onReconnected = {
                refreshStatus()
            }
            webSocketManager.connect(config.ip, config.port, config.token, config.baseUrl)
                .catch { e ->
                    _uiState.update { it.copy(isWsConnected = false, error = e.message) }
                }
                .collect { event -> handleWsEvent(event) }
        }

        connectionStateJob = viewModelScope.launch {
            webSocketManager.connectionState.collect { connected ->
                _uiState.update { it.copy(isWsConnected = connected) }
            }
        }
    }

    /**
     * 安全断开 WS 连接（仅断开监听，不关闭全局单例连接）
     * 用于切换剧本时停止接收旧事件
     */
    private fun disconnectWebSocketSafely() {
        wsJob?.cancel()
        wsJob = null
        webSocketManager.onReconnected = null
    }

    // ============================================================
    // REST 轮询降级
    // ============================================================

    private fun startPolling() {
        pollingJob?.cancel()
        pollingJob = viewModelScope.launch {
            while (true) {
                kotlinx.coroutines.delay(3000)
                if (!_uiState.value.isWsConnected) {
                    pollStatus()
                }
            }
        }
    }

    private fun pollStatus() {
        viewModelScope.launch {
            dramaRepository.getDramaStatus()
                .onSuccess { status ->
                    _uiState.update { it.copy(
                        theme = status.theme,
                        currentScene = status.current_scene,
                        arcProgress = status.arc_progress,
                        timePeriod = status.time_period,
                    ) }
                    if (status.current_scene > lastKnownScene) {
                        lastKnownScene = status.current_scene
                        loadNewSceneBubbles(status.current_scene)
                    }
                }
        }
    }

    private fun loadNewSceneBubbles(sceneNumber: Int) {
        viewModelScope.launch {
            dramaRepository.getSceneDetail(sceneNumber)
                .onSuccess { detail ->
                    val newBubbles = mutableListOf<SceneBubble>()
                    if (detail.narration.isNotBlank()) {
                        newBubbles.add(SceneBubble.Narration(
                            id = "poll_${sceneNumber}_n",
                            text = detail.narration,
                        ))
                    }
                    for ((idx, d) in detail.dialogue.withIndex()) {
                        val actorName = d["actor_name"]?.jsonPrimitive?.contentOrNull ?: ""
                        val text = d["text"]?.jsonPrimitive?.contentOrNull ?: ""
                        val emotion = d["emotion"]?.jsonPrimitive?.contentOrNull ?: ""
                        newBubbles.add(SceneBubble.Dialogue(
                            id = "poll_${sceneNumber}_d$idx",
                            actorName = actorName,
                            text = text,
                            emotion = emotion,
                        ))
                    }
                    if (newBubbles.isNotEmpty()) {
                        val divider = SceneBubble.SceneDivider(
                            id = "poll_div_$sceneNumber",
                            sceneNumber = sceneNumber,
                        )
                        _uiState.update { it.copy(
                            bubbles = it.bubbles + divider + newBubbles,
                            isTyping = false,
                            isProcessing = false,
                            stormPhase = null,
                        ) }
                    }
                }
        }
    }

    // ============================================================
    // WS 事件处理（含 dramaId 隐式隔离）
    // ============================================================

    private fun handleWsEvent(event: WsEventDto) {
        // 过滤 replay 消息
        if (event.type == "replay") return

        // 数据隔离防护：
        // 由于后端 WS 事件不携带 dramaId，我们通过以下方式隐式隔离：
        // 1. 每个 DramaDetailViewModel 有独立的状态流
        // 2. 当用户离开此屏幕时，wsJob 被取消，不再接收任何事件
        // 3. 进入新屏幕时 resetAllState() 清空旧数据
        //
        // 因此只要用户不在两个剧本间快速切换（backStack 中保留多个实例），
        // 就不会出现串台。如果确实需要严格隔离，后端需在 WS 事件中加入 drama_id 字段。

        when (event.type) {
            "narration" -> {
                _uiState.update { it.copy(isTyping = false) }
            }
            "dialogue" -> {
                val actorName = event.data["actor_name"]?.jsonPrimitive?.contentOrNull ?: ""
                val emotion = event.data["emotion"]?.jsonPrimitive?.contentOrNull ?: ""
                _uiState.update { it.copy(isTyping = false) }

                // ★ 智能互动检测：判断此发言是否为对其他角色的回复
                // 检查前一个气泡是否为不同角色的对话
                val lastBubble = _uiState.value.bubbles.lastOrNull()
                val interactionBubble = tryDetectActorInteraction(
                    currentActor = actorName,
                    text = event.data["text"]?.jsonPrimitive?.contentOrNull ?: "",
                    emotion = emotion,
                    lastBubble = lastBubble,
                    eventType = "dialogue",
                )

                if (interactionBubble != null) {
                    _uiState.update { it.copy(bubbles = it.bubbles + interactionBubble) }
                } else {
                    val bubble = SceneBubble.Dialogue(
                        id = "b_${bubbleCounter++}",
                        actorName = actorName,
                        text = event.data["text"]?.jsonPrimitive?.contentOrNull ?: "",
                        emotion = emotion,
                    )
                    _uiState.update { it.copy(bubbles = it.bubbles + bubble) }
                }
            }
            "end_narration" -> {
                val text = event.data["text"]?.jsonPrimitive?.contentOrNull ?: ""
                if (text.isNotBlank()) {
                    val bubble = SceneBubble.Narration(id = "b_${bubbleCounter++}", text = text)
                    _uiState.update { it.copy(bubbles = it.bubbles + bubble) }
                }
            }
            "scene_end" -> {
                val sceneNum = event.data["scene_number"]?.jsonPrimitive?.intOrNull ?: 0
                val sceneTitle = event.data["scene_title"]?.jsonPrimitive?.contentOrNull ?: ""
                val divider = SceneBubble.SceneDivider(id = "b_${bubbleCounter++}", sceneNumber = sceneNum, sceneTitle = sceneTitle)
                _uiState.update { it.copy(
                    bubbles = it.bubbles + divider,
                    currentScene = sceneNum,
                ) }
            }
            "tension_update" -> {
                val score = event.data["tension_score"]?.jsonPrimitive?.intOrNull ?: 0
                _uiState.update { it.copy(tensionScore = score) }
            }
            "typing" -> {
                val toolName = event.data["tool"]?.jsonPrimitive?.contentOrNull
                val text = getTypingText(toolName)
                _uiState.update { it.copy(isTyping = true, typingText = text) }
            }
            "error" -> {
                val msg = event.data["message"]?.jsonPrimitive?.contentOrNull ?: "Unknown error"
                _uiState.update { it.copy(isTyping = false, error = msg) }
                viewModelScope.launch { _events.emit(DramaDetailEvent.ShowSnackbar(msg)) }
            }
            "storm_discover" -> _uiState.update { it.copy(stormPhase = "发现新视角...") }
            "storm_research" -> _uiState.update { it.copy(stormPhase = "深入研究...") }
            "storm_outline" -> _uiState.update { it.copy(stormPhase = "综合构思大纲...") }
            "scene_start" -> _uiState.update { it.copy(stormPhase = null, isTyping = false) }
            "actor_chime_in" -> {
                // CHAT-07: 角色主动插话 — 优先渲染为互动气泡
                val actorName = event.data["actor_name"]?.jsonPrimitive?.contentOrNull ?: ""
                _uiState.update { it.copy(isTyping = false) }
                val text = event.data["text"]?.jsonPrimitive?.contentOrNull
                if (text != null && text.isNotBlank()) {
                    val lastBubble = _uiState.value.bubbles.lastOrNull()
                    val interactionBubble = tryDetectActorInteraction(
                        currentActor = actorName,
                        text = text,
                        emotion = "",
                        lastBubble = lastBubble,
                        eventType = "chime_in",
                    )
                    if (interactionBubble != null) {
                        _uiState.update { it.copy(bubbles = it.bubbles + interactionBubble) }
                    } else {
                        val bubble = SceneBubble.Dialogue(
                            id = "chime_${bubbleCounter++}",
                            actorName = actorName,
                            text = text,
                        )
                        _uiState.update { it.copy(bubbles = it.bubbles + bubble) }
                    }
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
    // ★ 角色互动智能检测
    // ============================================================

    /**
     * 智能检测角色间互动：判断当前发言是否应渲染为 ActorInteraction 气泡
     *
     * 判定规则：
     * 1. 前一个气泡是不同角色的 Dialogue → 可能是回复（REPLY）
     * 2. 事件类型为 actor_chime_in → 插话（CHIME_IN）
     * 3. 文本包含引用性词汇（"你说的对"、"我不这么认为"等）→ 反驳或回复
     * 4. 有明确的 target_actor 数据 → 直接使用
     *
     * @return 如果判定为互动则返回 ActorInteraction，否则返回 null
     */
    private fun tryDetectActorInteraction(
        currentActor: String,
        text: String,
        emotion: String,
        lastBubble: SceneBubble?,
        eventType: String,  // "dialogue" | "chime_in"
    ): SceneBubble.ActorInteraction? {
        if (currentActor.isBlank() || text.isBlank()) return null

        // 规则1：从 WS 事件数据中获取目标角色（如果后端提供了）
        val explicitTarget = "" // 后续可扩展：event.data["target_actor"]?.contentOrNull

        // 规则2：基于前一个气泡推断
        var inferredTarget: String? = null
        var interactionType: InteractionType? = null

        when {
            eventType == "chime_in" -> {
                interactionType = InteractionType.CHIME_IN
                // 插话时找最近发言的其他角色作为隐式目标
                if (lastBubble is SceneBubble.Dialogue && lastBubble.actorName != currentActor) {
                    inferredTarget = lastBubble.actorName
                }
            }
            lastBubble is SceneBubble.Dialogue && lastBubble.actorName != currentActor -> {
                interactionType = InteractionType.REPLY
                inferredTarget = lastBubble.actorName
            }
            lastBubble is SceneBubble.UserMessage && lastBubble.mention != null -> {
                interactionType = InteractionType.REPLY
                inferredTarget = lastBubble.mention
            }
            lastBubble is SceneBubble.ActorInteraction && lastBubble.fromActor != currentActor -> {
                interactionType = InteractionType.REPLY
                inferredTarget = lastBubble.fromActor
            }
        }

        // 规则3：文本语义分析 — 检测反驳/协商关键词
        if (interactionType == InteractionType.REPLY) {
            val counterKeywords = listOf("不对", "不是", "我不同意", "错了", "荒谬", "胡说",
                "不认同", "反对", "但是", "然而", "可是")
            val proposeKeywords = listOf("不如", "建议", "我们可以", "要不要", "也许应该",
                "不如我们", "或许可以", "要不")
            
            if (counterKeywords.any { text.contains(it) }) {
                interactionType = InteractionType.COUNTER
            } else if (proposeKeywords.any { text.contains(it) }) {
                interactionType = InteractionType.PROPOSE
            }
        }

        // 综合确定目标角色
        val finalTarget = explicitTarget ?: inferredTarget ?: return null

        return SceneBubble.ActorInteraction(
            id = "interaction_${bubbleCounter++}",
            fromActor = currentActor,
            toActor = finalTarget,
            text = text,
            emotion = emotion,
            interactionType = interactionType ?: InteractionType.REPLY,
            replyToText = (lastBubble as? SceneBubble.Dialogue)?.text?.take(50),
        )
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
            dramaRepository.getSceneDetail(sceneNumber)
                .onSuccess { detail ->
                    val historyBubbles = mutableListOf<SceneBubble>()
                    if (detail.narration.isNotBlank()) {
                        historyBubbles.add(SceneBubble.Narration(id = "hist_${sceneNumber}_n", text = detail.narration))
                    }
                    for ((idx, d) in detail.dialogue.withIndex()) {
                        val actorName = d["actor_name"]?.jsonPrimitive?.contentOrNull ?: ""
                        val text = d["text"]?.jsonPrimitive?.contentOrNull ?: ""
                        val emotion = d["emotion"]?.jsonPrimitive?.contentOrNull ?: ""
                        historyBubbles.add(SceneBubble.Dialogue(
                            id = "hist_${sceneNumber}_d$idx",
                            actorName = actorName,
                            text = text,
                            emotion = emotion,
                        ))
                    }
                    _uiState.update { it.copy(
                        viewingHistoryScene = sceneNumber,
                        bubbles = historyBubbles,
                        showHistorySheet = false,
                    ) }
                }
        }
    }

    fun returnToCurrentScene() {
        // 返回当前场景时重置为实时气泡列表
        _uiState.update { it.copy(viewingHistoryScene = null) }
        // 重新确认服务端上下文 + 重新连接 WS 以继续接收实时更新
        switchToDrama(activeDramaId)
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
    // 演员面板 D-01~D-04
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
            val castResult = dramaRepository.getCast()
            val statusResult = dramaRepository.getCastStatus()

            val mergedActors = mutableListOf<ActorInfo>()

            castResult.onSuccess { cast ->
                val statusMap = statusResult.getOrNull()?.actors ?: emptyMap()

                for ((name, actorElement) in cast.actors) {
                    val actorObj = (actorElement as? JsonObject)?.jsonObject ?: continue
                    val role = actorObj["role"]?.jsonPrimitive?.contentOrNull ?: ""
                    val personality = actorObj["personality"]?.jsonPrimitive?.contentOrNull ?: ""
                    val background = actorObj["background"]?.jsonPrimitive?.contentOrNull ?: ""
                    val emotions = actorObj["emotions"]?.jsonPrimitive?.contentOrNull ?: "neutral"
                    val memorySummary = buildMemorySummary(actorObj)

                    val a2aData = statusMap[name]
                    val isRunning = (a2aData as? JsonObject)?.get("running")?.jsonPrimitive?.booleanOrNull ?: false
                    val port = (a2aData as? JsonObject)?.get("port")?.jsonPrimitive?.intOrNull ?: 0

                    mergedActors.add(ActorInfo(
                        name = name,
                        role = role,
                        personality = personality,
                        background = background,
                        emotions = emotions,
                        memorySummary = memorySummary,
                        isA2ARunning = isRunning,
                        a2aPort = port,
                    ))
                }
            }

            _uiState.update { it.copy(actors = mergedActors, isActorLoading = false) }
        }
    }

    /**
     * ★ 预加载演员面板数据 — 在剧本切换成功后自动调用
     * 与 loadActorPanel() 逻辑相同，但不修改 showActorDrawer/isActorLoading 状态。
     * 这样用户打开抽屉时数据已就绪，无需等待网络请求。
     */
    private fun preloadActorPanel() {
        viewModelScope.launch {
            val castResult = dramaRepository.getCast()
            val statusResult = dramaRepository.getCastStatus()

            val mergedActors = mutableListOf<ActorInfo>()

            castResult.onSuccess { cast ->
                val statusMap = statusResult.getOrNull()?.actors ?: emptyMap()

                for ((name, actorElement) in cast.actors) {
                    val actorObj = (actorElement as? JsonObject)?.jsonObject ?: continue
                    val role = actorObj["role"]?.jsonPrimitive?.contentOrNull ?: ""
                    val personality = actorObj["personality"]?.jsonPrimitive?.contentOrNull ?: ""
                    val background = actorObj["background"]?.jsonPrimitive?.contentOrNull ?: ""
                    val emotions = actorObj["emotions"]?.jsonPrimitive?.contentOrNull ?: "neutral"
                    val memorySummary = buildMemorySummary(actorObj)

                    val a2aData = statusMap[name]
                    val isRunning = (a2aData as? JsonObject)?.get("running")?.jsonPrimitive?.booleanOrNull ?: false
                    val port = (a2aData as? JsonObject)?.get("port")?.jsonPrimitive?.intOrNull ?: 0

                    mergedActors.add(ActorInfo(
                        name = name,
                        role = role,
                        personality = personality,
                        background = background,
                        emotions = emotions,
                        memorySummary = memorySummary,
                        isA2ARunning = isRunning,
                        a2aPort = port,
                    ))
                }
            }

            // 仅更新 actors 数据，不改变 drawer 显示状态
            _uiState.update { it.copy(actors = mergedActors) }
        }
    }

    private fun buildMemorySummary(actorObj: JsonObject): String {
        val memoryArray = actorObj["memory"]?.jsonArray ?: return ""
        return memoryArray.mapNotNull { it.jsonPrimitive.contentOrNull }.joinToString(" ").take(500)
    }

    // ============================================================
    // 状态刷新 D-07/D-16
    // ============================================================

    fun refreshStatus() {
        viewModelScope.launch {
            dramaRepository.getDramaStatus()
                .onSuccess { status ->
                    _uiState.update { it.copy(
                        currentScene = status.current_scene,
                        arcProgress = status.arc_progress,
                        timePeriod = status.time_period,
                        isWsConnected = true,
                    ) }
                }
        }
    }

    // ============================================================
    // 命令发送
    // ============================================================

    fun sendCommand(text: String) {
        val commandType = CommandType.fromInput(text)
        _uiState.update { it.copy(isProcessing = true) }
        viewModelScope.launch {
            val result = when (commandType) {
                CommandType.NEXT -> dramaRepository.nextScene()
                CommandType.END -> dramaRepository.endDrama()
                CommandType.ACTION -> {
                    val desc = text.removePrefix("/action").trim()
                    if (desc.isBlank()) {
                        _uiState.update { it.copy(isProcessing = false) }
                        return@launch
                    }
                    dramaRepository.userAction(desc)
                }
                CommandType.SPEAK -> {
                    val parts = text.removePrefix("/speak").trim().split(" ", limit = 2)
                    if (parts.size < 2 || parts[0].isBlank()) {
                        _uiState.update { it.copy(isProcessing = false) }
                        return@launch
                    }
                    dramaRepository.actorSpeak(parts[0], parts[1])
                }
                CommandType.FREE_TEXT -> dramaRepository.userAction(text.trim())
            }
            _uiState.update { it.copy(isProcessing = false) }
            result.onFailure { e ->
                _uiState.update { it.copy(error = e.message) }
                _events.emit(DramaDetailEvent.ShowSnackbar("命令失败：${e.message}"))
            }
        }
    }

    // ============================================================
    // 群聊消息发送 — 核心入口
    // ============================================================

    fun sendChatMessage(text: String, mention: String?) {
        if (text.isBlank()) return

        // 立即进入思考状态
        _uiState.update { it.copy(isProcessing = true, isTyping = true, typingText = "思考中...") }

        // 即时显示用户消息气泡
        val userBubble = SceneBubble.UserMessage(
            id = "user_${bubbleCounter++}",
            text = text,
            mention = mention,
        )
        _uiState.update { it.copy(bubbles = it.bubbles + userBubble) }

        // 调用 /drama/chat API
        viewModelScope.launch {
            val result = dramaRepository.sendChatMessage(text, mention)

            result.onSuccess { cmdResp ->
                val respBubbles = extractBubblesFromCommandResponse(cmdResp)
                if (respBubbles.isNotEmpty()) {
                    _uiState.update { it.copy(
                        bubbles = it.bubbles + respBubbles,
                        isTyping = false,
                        isProcessing = false,
                    ) }
                } else {
                    if (!_uiState.value.isWsConnected) {
                        startReplyPolling()
                    }
                    _uiState.update { it.copy(isProcessing = false) }
                }
            }.onFailure { e ->
                _uiState.update {
                    it.copy(isTyping = false, isProcessing = false, error = e.message)
                }
                _events.emit(DramaDetailEvent.ShowSnackbar("发送失败：${e.message}"))
            }
        }
    }

    /**
     * 从 CommandResponseDto 提取可渲染的气泡
     */
    private fun extractBubblesFromCommandResponse(
        resp: com.drama.app.data.remote.dto.CommandResponseDto,
    ): List<SceneBubble> {
        val bubbles = mutableListOf<SceneBubble>()

        if (resp.final_response.isNotBlank() && resp.final_response.length > 5) {
            bubbles.add(SceneBubble.Narration(
                id = "api_resp_n_${bubbleCounter++}",
                text = resp.final_response.trim(),
            ))
        }

        for (result in resp.tool_results) {
            val actorName = result["actor_name"]?.toString()?.removeSurrounding("\"")
            val narrationText = result["narration"]?.toString()?.removeSurrounding("\"")
                ?: result["formatted_narration"]?.toString()?.removeSurrounding("\"")
            val dialogueText = result["text"]?.toString()?.removeSurrounding("\"")
            val emotion = result["emotion"]?.toString()?.removeSurrounding("\"") ?: ""

            if (!actorName.isNullOrBlank() && !dialogueText.isNullOrBlank()) {
                bubbles.add(SceneBubble.Dialogue(
                    id = "api_resp_d_${bubbleCounter++}",
                    actorName = actorName,
                    text = dialogueText,
                    emotion = emotion,
                ))
            } else if (!narrationText.isNullOrBlank() && narrationText.length > 3) {
                bubbles.add(SceneBubble.Narration(
                    id = "api_resp_tool_n_${bubbleCounter++}",
                    text = narrationText,
                ))
            }
        }

        return bubbles
    }

    /**
     * WS 断连降级轮询
     */
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
                            loadNewSceneBubbles(status.current_scene)
                            return@launch
                        }
                    }

                val currentScene = _uiState.value.currentScene
                if (currentScene > 0) {
                    dramaRepository.getSceneDetail(currentScene)
                        .onSuccess { detail ->
                            val lastDialogueIdx = _uiState.value.bubbles.indexOfLast {
                                it is SceneBubble.Dialogue || it is SceneBubble.Narration
                            }
                            val existingCount = if (lastDialogueIdx >= 0) lastDialogueIdx + 1 else 0
                            val totalExpected = 1 + (detail.dialogue.size) +
                                (if (detail.narration.isNotBlank()) 1 else 0)

                            if (totalExpected > existingCount) {
                                loadNewSceneBubbles(currentScene)
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
        disconnectWebSocketSafely()
        // 注意：不调用 webSocketManager.disconnect()，因为它是全局单例，
        // 其他屏幕可能仍在使用。只取消当前 ViewModel 的订阅即可。
    }
}
