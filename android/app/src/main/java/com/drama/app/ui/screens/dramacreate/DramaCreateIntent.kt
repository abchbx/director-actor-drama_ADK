package com.drama.app.ui.screens.dramacreate

import com.drama.app.data.remote.dto.WsEventDto
import com.drama.app.ui.mvi.MviIntent

/** DramaCreateScreen 所有用户操作 / 系统事件（per MVI-01） */
sealed class DramaCreateIntent : MviIntent {
    data class UpdateTheme(val text: String) : DramaCreateIntent()
    data class SelectDirectorStyle(val style: String) : DramaCreateIntent()
    data class CreateDrama(val theme: String) : DramaCreateIntent()
    data object CancelCreation : DramaCreateIntent()
    data class WsEventReceived(val event: WsEventDto) : DramaCreateIntent()

    // === 内部异步结果 ===
    sealed class Internal : DramaCreateIntent() {
        data class DirectorLogReceived(val entry: DirectorLogEntry) : Internal()
        data class CreateComplete(val dramaId: String) : Internal()
        data class CreateError(val message: String) : Internal()
        data class PollingPhaseUpdated(val phase: String, val log: String?) : Internal()
        data class PollingError(val message: String) : Internal()
        data class ElapsedUpdated(val seconds: Int) : Internal()
        data class ForceNavigateTimeout(val dramaId: String) : Internal()
    }
}
