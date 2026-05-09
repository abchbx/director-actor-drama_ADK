package com.drama.app.ui.screens.dramacreate

import com.drama.app.ui.mvi.MviEffect

/** DramaCreateScreen 一次性副作用（per MVI-06） */
sealed class DramaCreateEffect : MviEffect {
    data class NavigateToDetail(val dramaId: String) : DramaCreateEffect()
    data class ShowSnackbar(val message: String) : DramaCreateEffect()
}
