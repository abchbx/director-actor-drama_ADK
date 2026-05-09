package com.drama.app.ui.screens.dramalist

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.drama.app.domain.model.Drama
import com.drama.app.domain.repository.DramaRepository
import com.drama.app.ui.mvi.MviState
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.channels.consumeEach
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
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
) : MviState

@HiltViewModel
class DramaListViewModel @Inject constructor(
    private val dramaRepository: DramaRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(DramaListUiState())
    val state: StateFlow<DramaListUiState> = _state.asStateFlow()

    private val _effect = MutableSharedFlow<DramaListEffect>(extraBufferCapacity = 64)
    val effect: SharedFlow<DramaListEffect> = _effect.asSharedFlow()

    /** Intent 顺序队列 — D-26-01: UNLIMITED 防止 WS 消息突发阻塞 */
    private val intentQueue = Channel<DramaListIntent>(Channel.UNLIMITED)

    init {
        viewModelScope.launch {
            intentQueue.consumeEach { intent ->
                val currentState = _state.value
                val newState = reduce(currentState, intent)
                _state.compareAndSet(currentState, newState)
            }
        }
        processIntent(DramaListIntent.LoadDramas)
    }

    /** 唯一公共入口 — 所有操作必须经此入队 */
    fun processIntent(intent: DramaListIntent) {
        intentQueue.trySend(intent)
    }

    /** Reducer 纯函数 — (State, Intent) -> State */
    private fun reduce(state: DramaListUiState, intent: DramaListIntent): DramaListUiState {
        return when (intent) {
            // === 数据操作 ===
            is DramaListIntent.LoadDramas -> {
                loadDramasAsync()
                state.copy(isLoading = true, error = null)
            }
            is DramaListIntent.DeleteDrama -> {
                deleteDramaAsync(intent.folder)
                state
            }
            is DramaListIntent.BatchDelete -> {
                batchDeleteAsync(intent.folders)
                state.copy(isSelectionMode = false, selectedFolders = emptySet())
            }
            is DramaListIntent.BatchUpdateStatus -> {
                val updatedDramas = state.dramas.map { d ->
                    if (d.folder in intent.folders) d.copy(status = intent.newStatus) else d
                }
                emitEffect(DramaListEffect.ShowSnackbar("已更新 ${intent.folders.size} 个剧本状态"))
                state.copy(
                    dramas = updatedDramas,
                    isSelectionMode = false,
                    selectedFolders = emptySet(),
                )
            }
            is DramaListIntent.LoadDrama -> {
                loadDramaAsync(intent.folder)
                state
            }

            // === 搜索过滤 ===
            is DramaListIntent.OnSearchQueryChanged -> state.copy(searchQuery = intent.query)
            is DramaListIntent.OnStatusFilterChanged -> state.copy(selectedStatusFilter = intent.filter)

            // === 选择模式 ===
            is DramaListIntent.EnterSelectionMode ->
                state.copy(isSelectionMode = true, selectedFolders = emptySet())
            is DramaListIntent.ExitSelectionMode ->
                state.copy(isSelectionMode = false, selectedFolders = emptySet())
            is DramaListIntent.ToggleSelection -> {
                val newSet = if (state.selectedFolders.contains(intent.folder))
                    state.selectedFolders - intent.folder
                else
                    state.selectedFolders + intent.folder
                state.copy(selectedFolders = newSet)
            }
            is DramaListIntent.SelectAll ->
                state.copy(selectedFolders = intent.folders.toSet())
            is DramaListIntent.ClearSelection ->
                state.copy(selectedFolders = emptySet())

            // === 内部异步结果 ===
            is DramaListIntent.Internal.DramasLoaded ->
                state.copy(dramas = intent.dramas, isLoading = false)
            is DramaListIntent.Internal.LoadError ->
                state.copy(error = intent.message, isLoading = false)
            is DramaListIntent.Internal.DeleteComplete -> {
                if (intent.success) {
                    emitEffect(DramaListEffect.ShowSnackbar("已删除：${intent.folder}"))
                    processIntent(DramaListIntent.LoadDramas)
                } else {
                    emitEffect(DramaListEffect.ShowSnackbar("删除失败：${intent.error}"))
                }
                state
            }
            is DramaListIntent.Internal.BatchDeleteComplete -> {
                if (intent.successCount > 0) {
                    emitEffect(DramaListEffect.ShowSnackbar("已删除 ${intent.successCount} 个剧本"))
                    processIntent(DramaListIntent.LoadDramas)
                }
                state
            }
            is DramaListIntent.Internal.BatchUpdateComplete -> {
                emitEffect(DramaListEffect.ShowSnackbar("已更新 ${intent.updatedCount} 个剧本状态"))
                state
            }
            is DramaListIntent.Internal.LoadDramaComplete -> {
                if (intent.success) {
                    emitEffect(DramaListEffect.ShowSnackbar("已加载：${intent.folder}"))
                } else {
                    emitEffect(DramaListEffect.ShowSnackbar("加载失败：${intent.error}"))
                }
                state
            }
        }
    }

    private fun emitEffect(effect: DramaListEffect) {
        _effect.tryEmit(effect)
    }

    private fun loadDramasAsync() {
        viewModelScope.launch {
            dramaRepository.listDramas()
                .onSuccess { dramas ->
                    processIntent(DramaListIntent.Internal.DramasLoaded(dramas))
                }
                .onFailure { e ->
                    processIntent(DramaListIntent.Internal.LoadError(e.message))
                }
        }
    }

    private fun deleteDramaAsync(folder: String) {
        viewModelScope.launch {
            dramaRepository.deleteDrama(folder)
                .onSuccess {
                    processIntent(DramaListIntent.Internal.DeleteComplete(folder, success = true))
                }
                .onFailure { e ->
                    processIntent(DramaListIntent.Internal.DeleteComplete(folder, success = false, error = e.message))
                }
        }
    }

    private fun batchDeleteAsync(folders: Set<String>) {
        viewModelScope.launch {
            var successCount = 0
            folders.forEach { folder ->
                dramaRepository.deleteDrama(folder)
                    .onSuccess { successCount++ }
            }
            processIntent(DramaListIntent.Internal.BatchDeleteComplete(successCount))
        }
    }

    private fun loadDramaAsync(folder: String) {
        viewModelScope.launch {
            dramaRepository.loadDrama(folder)
                .onSuccess {
                    processIntent(DramaListIntent.Internal.LoadDramaComplete(folder, success = true))
                }
                .onFailure { e ->
                    processIntent(DramaListIntent.Internal.LoadDramaComplete(folder, success = false, error = e.message))
                }
        }
    }

    override fun onCleared() {
        super.onCleared()
        intentQueue.close()
    }
}
