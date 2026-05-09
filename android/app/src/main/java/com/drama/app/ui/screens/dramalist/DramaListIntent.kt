package com.drama.app.ui.screens.dramalist

import com.drama.app.domain.model.Drama
import com.drama.app.ui.mvi.MviIntent

/** DramaListScreen 所有用户操作 / 系统事件（per MVI-01） */
sealed class DramaListIntent : MviIntent {
    // === 数据操作 ===
    data object LoadDramas : DramaListIntent()
    data class DeleteDrama(val folder: String) : DramaListIntent()
    data class BatchDelete(val folders: Set<String>) : DramaListIntent()
    data class BatchUpdateStatus(val folders: Set<String>, val newStatus: String) : DramaListIntent()
    data class LoadDrama(val folder: String) : DramaListIntent()

    // === 搜索过滤 ===
    data class OnSearchQueryChanged(val query: String) : DramaListIntent()
    data class OnStatusFilterChanged(val filter: String?) : DramaListIntent()

    // === 选择模式 ===
    data object EnterSelectionMode : DramaListIntent()
    data object ExitSelectionMode : DramaListIntent()
    data class ToggleSelection(val folder: String) : DramaListIntent()
    data class SelectAll(val folders: List<String>) : DramaListIntent()
    data object ClearSelection : DramaListIntent()

    // === 内部异步结果（不暴露给 UI） ===
    sealed class Internal : DramaListIntent() {
        data class DramasLoaded(val dramas: List<Drama>) : Internal()
        data class LoadError(val message: String?) : Internal()
        data class DeleteComplete(val folder: String, val success: Boolean, val error: String? = null) : Internal()
        data class BatchDeleteComplete(val successCount: Int) : Internal()
        data class BatchUpdateComplete(val updatedCount: Int) : Internal()
        data class LoadDramaComplete(val folder: String, val success: Boolean, val error: String? = null) : Internal()
    }
}
