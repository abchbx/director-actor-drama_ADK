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

data class DramaDetailUiState(
    val theme: String = "",
    val currentScene: Int = 0,
    val tensionScore: Int = 0,
    val bubbles: List<SceneBubble> = emptyList(),
    val isTyping: Boolean = false,
    val typingText: String = "处理中...",
    val isProcessing: Boolean = false,
    val stormPhase: String? = null,
    val isWsConnected: Boolean = false,
    val error: String? = null,
    // D-18~D-20: 场景历史
    val viewingHistoryScene: Int? = null,
    val historyScenes: List<SceneSummaryDto> = emptyList(),
    val showHistorySheet: Boolean = false,
    // D-23: 保存操作
    val showSaveDialog: Boolean = false,
    // D-01~D-04: 演员面板
    val actors: List<ActorInfo> = emptyList(),
    val showActorDrawer: Boolean = false,
    // D-07: 状态概览
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
    private val dramaId: String = savedStateHandle["dramaId"] ?: ""

    private val _uiState = MutableStateFlow(DramaDetailUiState())
    val uiState: StateFlow<DramaDetailUiState> = _uiState.asStateFlow()

    private val _events = MutableSharedFlow<DramaDetailEvent>()
    val events: SharedFlow<DramaDetailEvent> = _events.asSharedFlow()

    private var wsJob: Job? = null
    private var bubbleCounter = 0

    init {
        loadInitialStatus()
        connectWebSocket()
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
                }
        }
    }

    fun connectWebSocket() {
        wsJob?.cancel()
        wsJob = viewModelScope.launch {
            val config = serverPreferences.serverConfig.first() ?: return@launch
            webSocketManager.connect(config.ip, config.port, config.token)
                .catch { e ->
                    _uiState.update { it.copy(isWsConnected = false, error = e.message) }
                }
                .collect { event -> handleWsEvent(event) }
        }
    }

    private fun handleWsEvent(event: WsEventDto) {
        // 处理 replay 消息（Pitfall 6）
        if (event.type == "replay") {
            return
        }
        when (event.type) {
            "narration" -> {
                _uiState.update { it.copy(isTyping = false) }
            }
            "dialogue" -> {
                val actorName = event.data["actor_name"]?.jsonPrimitive?.contentOrNull ?: ""
                val emotion = event.data["emotion"]?.jsonPrimitive?.contentOrNull ?: ""
                _uiState.update { it.copy(isTyping = false) }
                val bubble = SceneBubble.Dialogue(
                    id = "b_${bubbleCounter++}",
                    actorName = actorName,
                    text = event.data["text"]?.jsonPrimitive?.contentOrNull ?: "",
                    emotion = emotion,
                )
                _uiState.update { it.copy(bubbles = it.bubbles + bubble) }
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

    // D-18/D-19: 场景历史
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

    // D-20: 查看历史场景
    fun viewHistoryScene(sceneNumber: Int) {
        viewModelScope.launch {
            dramaRepository.getSceneDetail(sceneNumber)
                .onSuccess { detail ->
                    val historyBubbles = mutableListOf<SceneBubble>()
                    if (detail.narration.isNotBlank()) {
                        historyBubbles.add(
                            SceneBubble.Narration(
                                id = "hist_${sceneNumber}_n",
                                text = detail.narration,
                            ),
                        )
                    }
                    for ((idx, d) in detail.dialogue.withIndex()) {
                        val actorName = d["actor_name"]?.jsonPrimitive?.contentOrNull ?: ""
                        val text = d["text"]?.jsonPrimitive?.contentOrNull ?: ""
                        val emotion = d["emotion"]?.jsonPrimitive?.contentOrNull ?: ""
                        historyBubbles.add(
                            SceneBubble.Dialogue(
                                id = "hist_${sceneNumber}_d$idx",
                                actorName = actorName,
                                text = text,
                                emotion = emotion,
                            ),
                        )
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
        _uiState.update { it.copy(viewingHistoryScene = null) }
        connectWebSocket()
    }

    // D-23: 保存操作
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
                    _events.emit(
                        DramaDetailEvent.ShowSnackbar("已保存：${saveName.ifBlank { response.theme }}"),
                    )
                }
                .onFailure { e ->
                    _events.emit(DramaDetailEvent.ShowSnackbar("保存失败：${e.message}"))
                }
            _uiState.update { it.copy(showSaveDialog = false) }
        }
    }

    // D-01~D-04: 演员面板
    fun showActorDrawer() {
        loadActorPanel()
        _uiState.update { it.copy(showActorDrawer = true) }
    }

    fun hideActorDrawer() {
        _uiState.update { it.copy(showActorDrawer = false) }
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

                    mergedActors.add(
                        ActorInfo(
                            name = name,
                            role = role,
                            personality = personality,
                            background = background,
                            emotions = emotions,
                            memorySummary = memorySummary,
                            isA2ARunning = isRunning,
                            a2aPort = port,
                        ),
                    )
                }
            }

            _uiState.update { it.copy(actors = mergedActors) }
        }
    }

    private fun buildMemorySummary(actorObj: JsonObject): String {
        val memoryArray = actorObj["memory"]?.jsonArray ?: return ""
        return memoryArray.mapNotNull { it.jsonPrimitive.contentOrNull }.joinToString(" ").take(500)
    }

    // D-07: refresh status for overview card
    fun refreshStatus() {
        viewModelScope.launch {
            dramaRepository.getDramaStatus()
                .onSuccess { status ->
                    _uiState.update { it.copy(
                        currentScene = status.current_scene,
                        arcProgress = status.arc_progress,
                        timePeriod = status.time_period,
                    ) }
                }
        }
    }

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
            result.onFailure { e ->
                _uiState.update { it.copy(isProcessing = false, error = e.message) }
                _events.emit(DramaDetailEvent.ShowSnackbar("命令失败：${e.message}"))
            }
        }
    }

    override fun onCleared() {
        super.onCleared()
        wsJob?.cancel()
        webSocketManager.disconnect()
    }
}
