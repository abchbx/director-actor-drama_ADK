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

    // Search & Filter
    val searchQuery: String = "",
    val selectedStatusFilter: String? = null, // null = "全部"

    // Batch Selection Mode
    val isSelectionMode: Boolean = false,
    val selectedFolders: Set<String> = emptySet(),
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

    // === Data Operations ===

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
                    _uiState.update { state ->
                        state.copy(
                            dramas = state.dramas.filter { d -> d.folder != folder },
                            selectedFolders = state.selectedFolders - folder,
                        )
                    }
                    _events.emit(DramaListEvent.ShowSnackbar("已删除：$folder"))
                }
                .onFailure { e -> _events.emit(DramaListEvent.ShowSnackbar("删除失败：${e.message}")) }
        }
    }

    /** 批量删除选中的剧本 */
    fun batchDelete(folders: Set<String>) {
        viewModelScope.launch {
            var successCount = 0
            folders.forEach { folder ->
                dramaRepository.deleteDrama(folder)
                    .onSuccess { successCount++ }
            }
            exitSelectionMode()
            if (successCount > 0) {
                loadDramas()
                _events.emit(DramaListEvent.ShowSnackbar("已删除 $successCount 个剧本"))
            }
        }
    }

    /** 修改选中剧本的状态 */
    fun batchUpdateStatus(folders: Set<String>, newStatus: String) {
        viewModelScope.launch {
            var updated = 0
            // 后端暂无批量状态修改 API，此处仅更新本地 UI 状态以展示效果
            // 实际项目中需对接后端 PATCH 接口
            folders.forEach { folder ->
                _uiState.update { state ->
                    state.copy(
                        dramas = state.dramas.map { d ->
                            if (d.folder == folder) d.copy(status = newStatus) else d
                        },
                    )
                }
                updated++
            }
            exitSelectionMode()
            _events.emit(DramaListEvent.ShowSnackbar("已更新 $updated 个剧本状态"))
        }
    }

    fun loadDrama(folder: String) {
        viewModelScope.launch {
            dramaRepository.loadDrama(folder)
                .onSuccess { _events.emit(DramaListEvent.ShowSnackbar("已加载：$folder")) }
                .onFailure { e -> _events.emit(DramaListEvent.ShowSnackbar("加载失败：${e.message}")) }
        }
    }

    // === Search & Filter ===

    fun onSearchQueryChanged(query: String) {
        _uiState.update { it.copy(searchQuery = query) }
    }

    fun onStatusFilterChanged(filter: String?) {
        _uiState.update { it.copy(selectedStatusFilter = filter) }
    }

    /** 根据搜索词和状态筛选过滤后的列表 */
    fun getFilteredDramas(state: DramaListUiState): List<Drama> {
        return state.dramas.filter { drama ->
            val matchesSearch =
                state.searchQuery.isBlank() ||
                drama.theme.contains(state.searchQuery, ignoreCase = true)
            val matchesStatus =
                state.selectedStatusFilter == null ||
                drama.status == state.selectedStatusFilter
            matchesSearch && matchesStatus
        }
    }

    // === Selection Mode ===

    fun enterSelectionMode() {
        _uiState.update { it.copy(isSelectionMode = true, selectedFolders = emptySet()) }
    }

    fun exitSelectionMode() {
        _uiState.update { it.copy(isSelectionMode = false, selectedFolders = emptySet()) }
    }

    fun toggleSelection(folder: String) {
        _uiState.update { state ->
            val newSet = if (state.selectedFolders.contains(folder))
                state.selectedFolders - folder
            else
                state.selectedFolders + folder
            state.copy(selectedFolders = newSet)
        }
    }

    fun selectAll(availableFolders: List<String>) {
        _uiState.update { it.copy(selectedFolders = availableFolders.toSet()) }
    }

    fun clearSelection() {
        _uiState.update { it.copy(selectedFolders = emptySet()) }
    }

    val statusFilters = listOf(
        "全部" to null,
        "筹备中" to "setup",
        "演出中" to "acting",
        "已落幕" to "ended",
    )

    companion object {
        const val STATUS_SETUP = "setup"
        const val STATUS_ACTING = "acting"
        const val STATUS_ENDED = "ended"
    }
}
