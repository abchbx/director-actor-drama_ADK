package com.drama.app.ui.screens.dramalist

import com.drama.app.ui.mvi.MviEffect

/** DramaListScreen 一次性副作用（per MVI-06） */
sealed class DramaListEffect : MviEffect {
    data class ShowSnackbar(val message: String) : DramaListEffect()
    data class NavigateToDetail(val dramaId: String) : DramaListEffect()
}
