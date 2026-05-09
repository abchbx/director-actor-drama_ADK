package com.drama.app.ui.screens.dramadetail

import com.drama.app.ui.mvi.MviEffect

/** DramaDetailScreen 一次性副作用（per MVI-06） */
sealed class DramaDetailEffect : MviEffect {
    data class ShowSnackbar(val message: String) : DramaDetailEffect()
    data object HapticFeedback : DramaDetailEffect()
    data class ShareExport(val title: String, val content: String) : DramaDetailEffect()
    data class NavigateToHistory(val sceneNumber: Int) : DramaDetailEffect()
}
