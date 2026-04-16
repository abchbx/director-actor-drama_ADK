package com.drama.app.ui.screens.dramadetail

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.drama.app.data.local.ServerPreferences
import com.drama.app.data.remote.dto.SceneSummaryDto
import com.drama.app.data.remote.dto.WsEventDto
import com.drama.app.data.remote.ws.WebSocketManager
import com.drama.app.domain.model.CommandType
import com.drama.app.domain.model.SceneBubble
import com.drama.app.domain.repository.DramaRepository
import dagger.hilt.android.lifecycle.HiltViewModel
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
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import javax.inject.Inject

data class DramaDetailUiState(
    val theme: String = "",
    val currentScene: Int = 0,
    val tensionScore: Int = 0,
    val bubbles: List<SceneBubble> = emptyList(),
    val isTyping: Boolean = false,
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
            // replay 消息由 ReplayMessageDto 处理，此处忽略
            return
        }
        when (event.type) {
            // D-15: WS 事件驱动 UI 更新
            "narration" -> {
                // narration 事件的 data 可能不含 text，文本内容在 end_narration 中
                // 但我们仍然监听，因为 narration 事件指示旁白开始
                _uiState.update { it.copy(isTyping = false) }
            }
            "dialogue" -> {
                val actorName = event.data["actor_name"]?.jsonPrimitive?.contentOrNull ?: ""
                _uiState.update { it.copy(isTyping = false) }
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
            // D-14: Typing 指示器基础版
            "typing" -> {
                _uiState.update { it.copy(isTyping = true) }
            }
            "error" -> {
                val msg = event.data["message"]?.jsonPrimitive?.contentOrNull ?: "Unknown error"
                _uiState.update { it.copy(isTyping = false, error = msg) }
                viewModelScope.launch { _events.emit(DramaDetailEvent.ShowSnackbar(msg)) }
            }
            // STORM 进度（创建后可能在 Detail 屏幕收到）
            "storm_discover" -> _uiState.update { it.copy(stormPhase = "发现新视角...") }
            "storm_research" -> _uiState.update { it.copy(stormPhase = "深入研究...") }
            "storm_outline" -> _uiState.update { it.copy(stormPhase = "综合构思大纲...") }
            "scene_start" -> _uiState.update { it.copy(stormPhase = null, isTyping = false) }
            // D-22: 保存/加载确认
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
                        historyBubbles.add(
                            SceneBubble.Dialogue(
                                id = "hist_${sceneNumber}_d$idx",
                                actorName = actorName,
                                text = text,
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
        // 重新连接 WS 以获取当前场景
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
            // 成功时不立即清除 isProcessing — WS typing 事件会控制状态
        }
    }

    override fun onCleared() {
        super.onCleared()
        wsJob?.cancel()
        webSocketManager.disconnect()
    }
}
