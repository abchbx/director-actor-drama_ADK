package com.drama.app.ui.screens.dramadetail

import com.drama.app.data.remote.dto.WsEventDto
import com.drama.app.domain.model.ActorInfo
import com.drama.app.domain.model.SceneBubble
import com.drama.app.ui.mvi.MviIntent

/** DramaDetailScreen 所有用户操作 / 系统事件 / WS 事件（per MVI-01, MVI-04） */
sealed class DramaDetailIntent : MviIntent {

    // === 生命周期 ===
    data object Init : DramaDetailIntent()
    data object RetryInit : DramaDetailIntent()
    data object OnCleared : DramaDetailIntent()

    // === 连接管理 ===
    data object ConnectWebSocket : DramaDetailIntent()
    data object DisconnectWebSocket : DramaDetailIntent()
    data class WsEventReceived(val event: WsEventDto) : DramaDetailIntent()
    data class ConnectionStateChanged(val connectionState: com.drama.app.data.remote.ws.ConnectionState) : DramaDetailIntent()

    // === 聊天/命令 ===
    data class SendCommand(val text: String) : DramaDetailIntent()
    data class SendChatMessage(val text: String, val mention: String? = null) : DramaDetailIntent()
    data class SendFreeChatMessage(val text: String, val mention: String? = null) : DramaDetailIntent()

    // === 模式切换 ===
    data object ToggleChatMode : DramaDetailIntent()

    // === 场景历史 ===
    data object LoadSceneHistory : DramaDetailIntent()
    data class ViewSceneHistory(val sceneNumber: Int) : DramaDetailIntent()
    data object DismissSceneHistory : DramaDetailIntent()
    data object ReturnToCurrentScene : DramaDetailIntent()

    // === 保存/加载 ===
    data object ShowSaveDialog : DramaDetailIntent()
    data object DismissSaveDialog : DramaDetailIntent()
    data class SaveDrama(val name: String) : DramaDetailIntent()
    data class LoadSave(val name: String) : DramaDetailIntent()

    // === 导出 ===
    data object ExportDrama : DramaDetailIntent()

    // === 演员面板 ===
    data object ToggleActorDrawer : DramaDetailIntent()
    data object LoadActors : DramaDetailIntent()
    data class ToggleActorOnStage(val actorName: String) : DramaDetailIntent()

    // === 打字超时兜底 ===
    data object TypingTimeout : DramaDetailIntent()

    // === 打断 ===
    data object InterruptProcessing : DramaDetailIntent()

    // === 重试连接 ===
    data object RetryConnection : DramaDetailIntent()

    // === 前后台切换 ===
    data class SetWebSocketForeground(val isForeground: Boolean) : DramaDetailIntent()

    // === 状态刷新 ===
    data object RefreshStatus : DramaDetailIntent()

    // === 本地存档 ===
    data class SaveState(val name: String) : DramaDetailIntent()
    data class LoadState(val name: String) : DramaDetailIntent()
    data object ListSaves : DramaDetailIntent()
    data class DeleteSave(val name: String) : DramaDetailIntent()

    // === 流式更新 ===
    data class StreamingUpdate(val actorName: String, val text: String) : DramaDetailIntent()
    data object StreamingComplete : DramaDetailIntent()

    // === 内部异步结果（不暴露给 UI） ===
    sealed class Internal : DramaDetailIntent() {
        data class InitSyncComplete(val success: Boolean, val error: String? = null) : Internal()
        data class StatusLoaded(
            val bubbles: List<SceneBubble>,
            val scene: Int,
            val tension: Int,
            val theme: String = "",
            val arcProgress: List<com.drama.app.data.remote.dto.ArcProgressDto> = emptyList(),
            val timePeriod: String = "",
            val outlineSummary: String = "",
        ) : Internal()
        data class CommandResult(val success: Boolean, val error: String? = null) : Internal()
        data class ExportResult(val title: String, val content: String) : Internal()
        data class ExportError(val message: String) : Internal()
        data class ActorsLoaded(val actors: List<ActorInfo>) : Internal()
        data class SceneHistoryLoaded(val scenes: List<com.drama.app.data.remote.dto.SceneSummaryDto>) : Internal()
        data class SaveComplete(val name: String) : Internal()
        data class LoadComplete(val name: String) : Internal()
        data class BubblesLoaded(val bubbles: List<SceneBubble>, val prefix: String = "") : Internal()
        data class BubblesMerged(val bubbles: List<SceneBubble>) : Internal()
        data class ErrorBubbleAdded(val message: String) : Internal()
        data class TypingReset(val nonce: String) : Internal()
        data class ConnectionError(val message: String?) : Internal()
        data class PollingStatusUpdated(
            val scene: Int,
            val arcProgress: List<com.drama.app.data.remote.dto.ArcProgressDto>,
            val timePeriod: String,
            val outlineSummary: String,
        ) : Internal()
    }
}
