package com.drama.app.ui.screens.dramalist

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.drama.app.domain.model.Drama
import com.drama.app.domain.repository.DramaRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class DramaListUiState(
    val dramas: List<Drama> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null,
)

sealed class DramaListEvent {
    data class ShowSnackbar(val message: String) : DramaListEvent()
}

@HiltViewModel
class DramaListViewModel @Inject constructor(
    private val dramaRepository: DramaRepository,
) : ViewModel() {
    private val _uiState = MutableStateFlow(DramaListUiState())
    val uiState: StateFlow<DramaListUiState> = _uiState.asStateFlow()

    private val _events = MutableSharedFlow<DramaListEvent>()
    val events: SharedFlow<DramaListEvent> = _events.asSharedFlow()

    init { loadDramas() }

    fun loadDramas() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true) }
            dramaRepository.listDramas()
                .onSuccess { dramas -> _uiState.update { it.copy(dramas = dramas, isLoading = false) } }
                .onFailure { e -> _uiState.update { it.copy(error = e.message, isLoading = false) } }
        }
    }

    fun deleteDrama(folder: String) {
        viewModelScope.launch {
            dramaRepository.deleteDrama(folder)
                .onSuccess {
                    _uiState.update { it.copy(dramas = it.dramas.filter { d -> d.folder != folder }) }
                    _events.emit(DramaListEvent.ShowSnackbar("已删除：$folder"))
                }
                .onFailure { e -> _events.emit(DramaListEvent.ShowSnackbar("删除失败：${e.message}")) }
        }
    }

    fun loadDrama(folder: String) {
        viewModelScope.launch {
            dramaRepository.loadDrama(folder)
                .onSuccess { _events.emit(DramaListEvent.ShowSnackbar("已加载：$folder")) }
                .onFailure { e -> _events.emit(DramaListEvent.ShowSnackbar("加载失败：${e.message}")) }
        }
    }
}
