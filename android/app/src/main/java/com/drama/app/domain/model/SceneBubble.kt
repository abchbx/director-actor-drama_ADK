package com.drama.app.domain.model

/**
 * 场景气泡密封类 — 聊天界面中的所有消息类型
 *
 * 类型说明：
 * - [Narration]: 旁白/导演叙述（系统文本）
 * - [Dialogue]: 角色发言（单个角色的台词）
 * - [UserMessage]: 用户发送的消息（右对齐）
 * - [ActorInteraction]: ★ 角色间互动对话（A 对 B 说...）— 清晰呈现角色互动过程
 * - [SceneDivider]: 场景分隔线
 */
sealed class SceneBubble {
    abstract val id: String

    /** 旁白 — 系统或导演的叙述文本，居中或特殊样式显示 */
    data class Narration(
        override val id: String,
        val text: String,
    ) : SceneBubble()

    /** 单个角色发言 — 左对齐气泡，带头像和情绪标签 */
    data class Dialogue(
        override val id: String,
        val actorName: String,
        val text: String,
        val emotion: String = "",       // D-10: 情绪标签
    ) : SceneBubble()

    /** 用户在群聊中发送的消息 — 右对齐显示 */
    data class UserMessage(
        override val id: String,
        val text: String,
        val mention: String? = null,    // @提及的角色名（可为null）
    ) : SceneBubble()

    /**
     * ★ 角色间互动对话 — 展示 AGENT 之间的交流过程
     *
     * 使用场景：
     * - A2A (Agent-to-Agent) 直接通信时展示
     * - 角色之间互相回应、争论、协作
     * - 需要清晰表达"谁对谁说了什么"
     *
     * 与 Dialogue 的区别：
     * - Dialogue: 角色对用户/观众发言（单向）
     * - ActorInteraction: 角色 A → 角色 B 的定向交互（双向上下文）
     *
     * 示例：
     * ```
     * ┌─ 张三 ──────────────→ 李四 ─┐
     * │  "你这个计划太冒险了！      │
     * │   我们应该先稳住阵脚。"     │
     * └───────────────────────────┘
     * ```
     */
    data class ActorInteraction(
        override val id: String,
        val fromActor: String,           // 发言者名称
        val toActor: String,             // 接收者名称（目标角色）
        val text: String,                // 对话内容
        val emotion: String = "",        // 发言者的情绪
        val interactionType: InteractionType = InteractionType.REPLY,
        /** 附加的回复引用文本（可选，用于展示"回复了某句话"） */
        val replyToText: String? = null,
    ) : SceneBubble()

    /** 场景分隔线 — 显示"第 N 场 · 标题" */
    data class SceneDivider(
        override val id: String,
        val sceneNumber: Int,
        val sceneTitle: String = "",
    ) : SceneBubble()
}

/**
 * 角色互动类型枚举
 */
enum class InteractionType {
    /** 回复 — 回应对方的言论 */
    REPLY,
    /** 插话 — 主动加入对话（actor_chime_in 场景） */
    CHIME_IN,
    /** 反驳 — 不同意对方观点 */
    COUNTER,
    /** 协商 — 提出建议或妥协 */
    PROPOSE,
    /** 情感表达 — 表达情绪而非信息 */
    EMOTIONAL,
}
