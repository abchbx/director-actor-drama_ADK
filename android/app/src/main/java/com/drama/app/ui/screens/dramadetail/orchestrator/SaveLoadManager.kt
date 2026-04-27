package com.drama.app.ui.screens.dramadetail.orchestrator

import com.drama.app.data.local.DramaSaveRepository
import com.drama.app.domain.model.SceneBubble
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import javax.inject.Inject

/**
 * 保存/加载/列表管理子组件（per D-23-01, D-23-02）。
 * 封装本地存档操作，通过 SharedFlow 上报事件给主 VM。
 */
class SaveLoadManager @Inject constructor(
    private val dramaSaveRepository: DramaSaveRepository,
) {
    sealed class SaveLoadEvent {
        data class Saved(val name: String) : SaveLoadEvent()
        data class Loaded(val name: String, val bubbles: List<SceneBubble>, val currentScene: Int, val theme: String, val tensionScore: Int) : SaveLoadEvent()
        data class Listed(val saves: List<String>) : SaveLoadEvent()
        data class Deleted(val name: String) : SaveLoadEvent()
        data class ListAsBubble(val bubble: SceneBubble) : SaveLoadEvent()
        data class Error(val message: String) : SaveLoadEvent()
    }

    private val _events = MutableSharedFlow<SaveLoadEvent>(extraBufferCapacity = 16)
    val events: SharedFlow<SaveLoadEvent> = _events

    /** 保存当前状态到本地 DataStore */
    suspend fun save(name: String, dramaId: String, currentScene: Int, theme: String, tensionScore: Int, bubbles: List<SceneBubble>) {
        try {
            dramaSaveRepository.saveState(
                name = name,
                dramaId = dramaId,
                currentScene = currentScene,
                theme = theme,
                tensionScore = tensionScore,
                bubbles = bubbles,
            )
            _events.tryEmit(SaveLoadEvent.Saved(name))
        } catch (e: Exception) {
            _events.tryEmit(SaveLoadEvent.Error("保存失败：${e.message}"))
        }
    }

    /** 加载存档 */
    suspend fun load(name: String, dramaId: String) {
        try {
            val save = dramaSaveRepository.loadState(name, dramaId)
            if (save == null) {
                _events.tryEmit(SaveLoadEvent.Error("存档 $name 不存在"))
                return
            }
            val restoredBubbles = dramaSaveRepository.decodeBubbles(save.bubblesJson)
            _events.tryEmit(SaveLoadEvent.Loaded(
                name = name,
                bubbles = restoredBubbles,
                currentScene = save.currentScene,
                theme = save.theme,
                tensionScore = save.tensionScore,
            ))
        } catch (e: Exception) {
            _events.tryEmit(SaveLoadEvent.Error("加载失败：${e.message}"))
        }
    }

    /** 删除存档 */
    suspend fun delete(name: String, dramaId: String) {
        try {
            dramaSaveRepository.deleteSave(name, dramaId)
            _events.tryEmit(SaveLoadEvent.Deleted(name))
        } catch (e: Exception) {
            _events.tryEmit(SaveLoadEvent.Error("删除失败：${e.message}"))
        }
    }

    /** D-23-04: 主 VM onCleared 时调用 */
    fun cleanup() {
        // 无持久状态需要清理
    }
}
