package com.drama.app.ui.screens.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.drama.app.domain.model.ServerConfig
import com.drama.app.domain.repository.ServerRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class SettingsUiState(
    val serverConfig: ServerConfig? = null,
    val isConnected: Boolean = false,
)

@HiltViewModel  // APP-13, APP-14
class SettingsViewModel @Inject constructor(
    private val serverRepository: ServerRepository,
) : ViewModel() {
    private val _uiState = MutableStateFlow(SettingsUiState())
    val uiState: StateFlow<SettingsUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            serverRepository.serverConfig.collect { config ->
                _uiState.value = _uiState.value.copy(
                    serverConfig = config,
                    isConnected = config != null,
                )
            }
        }
    }
}
