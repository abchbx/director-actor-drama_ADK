package com.drama.app.data.local

import kotlinx.serialization.Serializable

/**
 * 本地存档数据模型
 *
 * 包含剧本快照信息，用于 /save、/load、/list 命令。
 * 通过 Preferences DataStore 持久化，JSON 序列化存储。
 */
@Serializable
data class DramaSave(
    /** 用户指定的存档唯一名称 */
    val name: String,
    /** 所属剧本 ID（theme） */
    val dramaId: String,
    /** 创建时间戳（毫秒） */
    val timestamp: Long,
    /** 当前场景编号 */
    val currentScene: Int,
    /** 剧本主题名称 */
    val theme: String,
    /** 紧张度分数 */
    val tensionScore: Int = 0,
    /** 序列化的气泡列表 JSON（完整消息历史快照） */
    val bubblesJson: String = "[]",
    /** 最近消息摘要（纯文本，便于快速预览） */
    val messageSummary: String = "",
)
