package com.drama.app.ui.screens.dramacreate

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.drama.app.data.local.ServerPreferences
import com.drama.app.data.remote.dto.WsEventDto
import com.drama.app.data.remote.ws.WebSocketManager
import com.drama.app.domain.repository.DramaRepository
import dagger.hilt.android.lifecycle.HiltViewModel
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
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.contentOrNull
import javax.inject.Inject

data class DramaCreateUiState(
    val theme: String = "",
    val isCreating: Boolean = false,
    val stormPhase: String? = null,
    val error: String? = null,
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
    private val _uiState = MutableStateFlow(DramaCreateUiState())
    val uiState: StateFlow<DramaCreateUiState> = _uiState.asStateFlow()

    private val _events = MutableSharedFlow<DramaCreateEvent>()
    val events: SharedFlow<DramaCreateEvent> = _events.asSharedFlow()

    fun createDrama(theme: String) {
        if (theme.isBlank()) return
        viewModelScope.launch {
            _uiState.update { it.copy(isCreating = true, error = null) }
            // D-02: 调用 POST /drama/start 后进入加载态
            dramaRepository.startDrama(theme)
                .onSuccess {
                    // D-04: 不在此处导航，等 WS scene_start 事件
                    connectWebSocketForStormProgress()
                }
                .onFailure { e ->
                    _uiState.update { it.copy(isCreating = false, error = e.message) }
                }
        }
    }

    private fun connectWebSocketForStormProgress() {
        viewModelScope.launch {
            val config = serverPreferences.serverConfig.first() ?: return@launch
            webSocketManager.connect(config.ip, config.port, config.token)
                .catch { e -> _uiState.update { it.copy(error = e.message) } }
                .collect { event -> handleStormEvent(event) }
        }
    }

    private fun handleStormEvent(event: WsEventDto) {
        when (event.type) {
            // D-03: STORM 进度实时展示
            "storm_discover" -> _uiState.update { it.copy(stormPhase = "发现新视角...") }
            "storm_research" -> _uiState.update { it.copy(stormPhase = "深入研究...") }
            "storm_outline" -> _uiState.update { it.copy(stormPhase = "综合构思大纲...") }
            // D-04: 创建完成自动跳转
            "scene_start" -> {
                _uiState.update { it.copy(isCreating = false) }
                viewModelScope.launch {
                    _events.emit(DramaCreateEvent.NavigateToDetail("current"))
                }
            }
            "error" -> {
                val msg = event.data["message"]?.jsonPrimitive?.contentOrNull ?: "Unknown error"
                _uiState.update { it.copy(isCreating = false, error = msg) }
            }
        }
    }

    override fun onCleared() {
        super.onCleared()
        webSocketManager.disconnect()
    }
}
