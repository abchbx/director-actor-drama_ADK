package com.drama.app.ui.screens.connection

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.drama.app.domain.model.AuthMode
import com.drama.app.domain.model.ConnectionStatus
import com.drama.app.domain.model.ErrorType
import com.drama.app.domain.model.ServerConfig
import com.drama.app.domain.repository.AuthRepository
import com.drama.app.domain.repository.ServerRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ConnectionUiState(
    val ip: String = "",
    val port: String = "8000",
    val baseUrl: String = "",  // Cloud URL (e.g. https://xxx.cloudstudio.club/)
    val useCloudUrl: Boolean = false,  // Toggle between IP:port and full URL
    val token: String = "",
    val showTokenInput: Boolean = false,  // D-02: 需要 token 时弹出
    val status: ConnectionStatus = ConnectionStatus.Idle,
)

@HiltViewModel
class ConnectionViewModel @Inject constructor(
    private val authRepository: AuthRepository,
    private val serverRepository: ServerRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(ConnectionUiState())
    val uiState: StateFlow<ConnectionUiState> = _uiState.asStateFlow()

    // 已保存的服务器配置（历史记录下拉用）
    val savedServerConfig = serverRepository.serverConfig.stateIn(
        viewModelScope, SharingStarted.Lazily, null,
    )

    fun updateIp(ip: String) {
        _uiState.value = _uiState.value.copy(ip = ip)
    }

    fun updatePort(port: String) {
        _uiState.value = _uiState.value.copy(port = port)
    }

    fun updateToken(token: String) {
        _uiState.value = _uiState.value.copy(token = token)
    }

    fun updateBaseUrl(url: String) {
        _uiState.value = _uiState.value.copy(baseUrl = url)
    }

    fun setUseCloudUrl(use: Boolean) {
        _uiState.value = _uiState.value.copy(useCloudUrl = use)
    }

    fun connect() {
        val state = _uiState.value
        viewModelScope.launch {
            _uiState.value = state.copy(status = ConnectionStatus.Connecting)

            val result = if (state.useCloudUrl && state.baseUrl.isNotBlank()) {
                authRepository.verifyServer("", "", state.baseUrl.trimEnd('/'))
            } else {
                authRepository.verifyServer(state.ip, state.port)
            }
            result.onSuccess { authMode ->
                when (authMode) {
                    is AuthMode.Bypass -> {
                        // D-02: 无需 token，直接保存配置并进入
                        saveConfigAndConnect(state.ip, state.port, null)
                    }
                    is AuthMode.RequireToken -> {
                        // D-02: 弹出 token 输入
                        _uiState.value = _uiState.value.copy(showTokenInput = true, status = ConnectionStatus.Idle)
                    }
                }
            }.onFailure { error ->
                // D-03: 区分错误类型
                val errorType = when {
                    error.message == "TIMEOUT" || error.message?.startsWith("TIMEOUT") == true -> ErrorType.TIMEOUT
                    error.message == "NETWORK_UNREACHABLE" || error.message?.startsWith("DNS_ERROR") == true -> ErrorType.NETWORK_UNREACHABLE
                    error.message == "AUTH_FAILED" -> ErrorType.AUTH_FAILED
                    error.message?.startsWith("SSL_ERROR") == true -> ErrorType.NETWORK_UNREACHABLE
                    else -> ErrorType.UNKNOWN
                }
                _uiState.value = _uiState.value.copy(
                    status = ConnectionStatus.Error(error.message ?: "连接失败", errorType),
                )
            }
        }
    }

    fun submitToken() {
        val state = _uiState.value
        viewModelScope.launch {
            saveConfigAndConnect(state.ip, state.port, state.token.ifBlank { null })
        }
    }

    private suspend fun saveConfigAndConnect(ip: String, port: String, token: String?) {
        val baseUrl = if (_uiState.value.useCloudUrl && _uiState.value.baseUrl.isNotBlank()) {
            _uiState.value.baseUrl.trimEnd('/')
        } else null
        serverRepository.saveServerConfig(ServerConfig(ip = ip, port = port, token = token, baseUrl = baseUrl))
        _uiState.value = _uiState.value.copy(status = ConnectionStatus.Connected, showTokenInput = false)
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(status = ConnectionStatus.Idle)
    }
}
