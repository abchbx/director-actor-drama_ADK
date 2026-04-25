package com.drama.app.data.local

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import com.drama.app.domain.model.SceneBubble
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import javax.inject.Inject

/**
 * 本地存档仓库 — 使用 Preferences DataStore 持久化存档数据
 *
 * 存储结构：
 * - `save_names_<dramaId>`: JSON 数组，存储该剧本下所有存档名称
 * - `save_<dramaId>_<saveName>`: JSON 字符串，存储单个存档的完整数据
 *
 * 所有 DataStore 操作均在协程中执行（`data` 是 Flow，写入用 `edit`），
 * 不阻塞主线程。
 */
class DramaSaveRepository @Inject constructor(
    private val dataStore: DataStore<Preferences>,
) {
    private val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
        classDiscriminator = "type"
    }

    // ============================================================
    // Key 构造
    // ============================================================

    private fun saveNamesKey(dramaId: String) =
        stringPreferencesKey("save_names_$dramaId")

    private fun saveDataKey(dramaId: String, saveName: String) =
        stringPreferencesKey("save_${dramaId}_${saveName}")

    // ============================================================
    // 公共 API
    // ============================================================

    /**
     * 获取指定剧本的所有存档名称列表（Flow）
     */
    fun getSaveNames(dramaId: String): Flow<List<String>> =
        dataStore.data.map { prefs ->
            val jsonStr = prefs[saveNamesKey(dramaId)] ?: "[]"
            try {
                json.decodeFromString<List<String>>(jsonStr)
            } catch (_: Exception) {
                emptyList()
            }
        }

    /**
     * 获取指定剧本的所有完整存档数据（Flow）
     */
    fun getSaves(dramaId: String): Flow<List<DramaSave>> =
        dataStore.data.map { prefs ->
            val namesJson = prefs[saveNamesKey(dramaId)] ?: "[]"
            val names = try {
                json.decodeFromString<List<String>>(namesJson)
            } catch (_: Exception) {
                emptyList()
            }
            names.mapNotNull { name ->
                val saveJson = prefs[saveDataKey(dramaId, name)] ?: return@mapNotNull null
                try {
                    json.decodeFromString<DramaSave>(saveJson)
                } catch (_: Exception) {
                    null
                }
            }
        }

    /**
     * 保存存档。若同名存档已存在则覆盖。
     *
     * @param name 存档名称
     * @param dramaId 剧本 ID
     * @param currentScene 当前场景编号
     * @param theme 剧本主题
     * @param tensionScore 紧张度分数
     * @param bubbles 当前气泡列表
     */
    suspend fun saveState(
        name: String,
        dramaId: String,
        currentScene: Int,
        theme: String,
        tensionScore: Int,
        bubbles: List<SceneBubble>,
    ) {
        val now = System.currentTimeMillis()
        val bubblesJson = json.encodeToString(bubbles)
        val messageSummary = buildMessageSummary(bubbles)

        val save = DramaSave(
            name = name,
            dramaId = dramaId,
            timestamp = now,
            currentScene = currentScene,
            theme = theme,
            tensionScore = tensionScore,
            bubblesJson = bubblesJson,
            messageSummary = messageSummary,
        )

        dataStore.edit { prefs ->
            // 更新存档名称列表
            val namesJson = prefs[saveNamesKey(dramaId)] ?: "[]"
            val names = try {
                json.decodeFromString<MutableList<String>>(namesJson)
            } catch (_: Exception) {
                mutableListOf()
            }
            if (name !in names) {
                names.add(name)
            }
            prefs[saveNamesKey(dramaId)] = json.encodeToString(names)

            // 写入存档数据
            prefs[saveDataKey(dramaId, name)] = json.encodeToString(save)
        }
    }

    /**
     * 加载存档，恢复完整的气泡列表
     *
     * @return DramaSave 或 null（存档不存在时）
     */
    suspend fun loadState(name: String, dramaId: String): DramaSave? {
        val prefs = dataStore.data.first()
        val saveJson = prefs[saveDataKey(dramaId, name)] ?: return null
        return try {
            json.decodeFromString<DramaSave>(saveJson)
        } catch (_: Exception) {
            null
        }
    }

    /**
     * 解析存档中的气泡列表
     */
    fun decodeBubbles(bubblesJson: String): List<SceneBubble> {
        return try {
            json.decodeFromString<List<SceneBubble>>(bubblesJson)
        } catch (_: Exception) {
            emptyList()
        }
    }

    /**
     * 删除指定存档
     */
    suspend fun deleteSave(name: String, dramaId: String) {
        dataStore.edit { prefs ->
            // 从名称列表中移除
            val namesJson = prefs[saveNamesKey(dramaId)] ?: "[]"
            val names = try {
                json.decodeFromString<MutableList<String>>(namesJson)
            } catch (_: Exception) {
                mutableListOf()
            }
            names.remove(name)
            prefs[saveNamesKey(dramaId)] = json.encodeToString(names)

            // 移除存档数据
            prefs.remove(saveDataKey(dramaId, name))
        }
    }

    // ============================================================
    // 私有工具方法
    // ============================================================

    /**
     * 从气泡列表构建消息摘要（取最近几条消息的文本）
     */
    private fun buildMessageSummary(bubbles: List<SceneBubble>): String {
        val recentBubbles = bubbles.takeLast(10)
        return recentBubbles.joinToString("\n") { bubble ->
            when (bubble) {
                is SceneBubble.Narration -> "[旁白] ${bubble.text.take(80)}"
                is SceneBubble.Dialogue -> "[${bubble.actorName}] ${bubble.text.take(80)}"
                is SceneBubble.UserMessage -> "[你] ${bubble.text.take(80)}"
                is SceneBubble.ActorInteraction -> "[${bubble.fromActor}→${bubble.toActor}] ${bubble.text.take(80)}"
                is SceneBubble.SceneDivider -> "── 第${bubble.sceneNumber}场 ──"
                is SceneBubble.SystemError -> "[系统错误] ${bubble.text.take(80)}"
                is SceneBubble.PlotGuidance -> "[剧情引导] ${bubble.text.take(80)}"
            }
        }
    }
}
