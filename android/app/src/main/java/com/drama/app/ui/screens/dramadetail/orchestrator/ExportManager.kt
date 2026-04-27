package com.drama.app.ui.screens.dramadetail.orchestrator

import android.content.Context
import android.content.Intent
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import javax.inject.Inject

/**
 * 导出/Share Intent 管理子组件（per D-23-01, D-23-02）。
 * 封装导出逻辑，通过 SharedFlow 上报事件给主 VM。
 */
class ExportManager @Inject constructor() {
    sealed class ExportEvent {
        data class ShareIntentReady(val intent: Intent) : ExportEvent()
        data class Exported(val path: String) : ExportEvent()
        data class Error(val message: String) : ExportEvent()
    }

    private val _events = MutableSharedFlow<ExportEvent>(extraBufferCapacity = 8)
    val events: SharedFlow<ExportEvent> = _events

    /** 导出为文本并通过 Share Intent 分享 */
    fun exportAndShare(context: Context, dramaTitle: String, content: String) {
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_SUBJECT, dramaTitle)
            putExtra(Intent.EXTRA_TEXT, content)
        }
        _events.tryEmit(ExportEvent.ShareIntentReady(Intent.createChooser(intent, "分享剧情")))
    }

    /** D-23-04: 主 VM onCleared 时调用 */
    fun cleanup() {
        // 无持久状态需要清理
    }
}
