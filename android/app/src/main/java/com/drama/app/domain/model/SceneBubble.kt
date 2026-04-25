package com.drama.app.domain.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * 场景气泡密封类 — 聊天界面中的所有消息类型
 *
 * 类型说明：
 * - [Narration]: 旁白/导演叙述（系统文本）
 * - [Dialogue]: 角色发言（单个角色的台词）
 * - [UserMessage]: 用户发送的消息（右对齐）— 用户以"主角"身份参与
 * - [ActorInteraction]: ★ 角色间互动对话（A 对 B 说...）— 清晰呈现角色互动过程
 * - [SceneDivider]: 场景分隔线
 *
 * 头像类型 [AvatarType]：
 * - Director: 导演/旁白专属头像（特殊图标）
 * - Actor: 演员头像（根据名称生成颜色一致的占位头像）
 *
 * ★ 三方消息体系 — 每条消息带有 senderType 和 senderName：
 * - director: 导演/旁白 → 居中灰色斜体卡片，带"旁白"标签
 * - actor: 演员 → 左对齐，演员头像+名称，气泡对应阵营色
 * - user: 用户/主角 → 右对齐，Primary 颜色气泡
 *
 * ★ 去重机制 — 每个子类通过 [contentFingerprint] 提供基于内容的唯一指纹，
 * 用于断网重连后的气泡合并去重：两气泡 fingerprint 相同视为同一消息。
 * ★ equals/hashCode 基于内容指纹重写，确保 Set/Map 操作正确去重，
 * 同一内容的气泡即使 id 不同（本地 vs 后端生成）也视为相等。
 */
@Serializable
sealed class SceneBubble {
    abstract val id: String

    /**
     * ★ 基于内容的唯一指纹，用于断网重连后与后端数据合并去重。
     * 格式："{类型简写}|{关键内容字段}"，如 "D|张三|你好" 或 "N|旁白文本前40字"。
     * 只取内容核心字段，忽略 UI 状态（avatarType/senderType 等），确保断网前后的
     * 同一条消息指纹一致。
     *
     * ★ 注意：此指纹也作为 equals/hashCode 的依据，使得 Set<SceneBubble>、
     * distinctBy 等集合操作能基于内容而非 id 去重。
     */
    abstract val contentFingerprint: String

    /** 发送者类型枚举 — 三方消息体系 */
    @Serializable
    enum class SenderType {
        DIRECTOR,   // 导演/旁白
        ACTOR,      // 演员
        USER,       // 用户/主角
        SYSTEM,     // 系统消息
    }

    /** 头像类型枚举 */
    @Serializable
    enum class AvatarType {
        DIRECTOR,   // 导演/旁白
        ACTOR,      // 演员
        USER,       // 用户
        SYSTEM,     // 系统消息
    }

    /** 旁白 — 系统或导演的叙述文本，居中或特殊样式显示 */
    @Serializable
    @SerialName("narration")
    data class Narration(
        override val id: String,
        val text: String,
        val avatarType: AvatarType = AvatarType.DIRECTOR,
        val avatarUrl: String? = null,
        val senderType: SenderType = SenderType.DIRECTOR,
        val senderName: String = "旁白",
    ) : SceneBubble() {
        override val contentFingerprint: String = "N|${text.take(80)}"

        /** ★ 基于 contentFingerprint 重写，支持跨 id 去重 */
        override fun equals(other: Any?): Boolean {
            if (this === other) return true
            if (other !is Narration) return false
            return contentFingerprint == other.contentFingerprint
        }

        override fun hashCode(): Int = contentFingerprint.hashCode()
    }

    /** 单个角色发言 — 左对齐气泡，带头像和情绪标签 */
    @Serializable
    @SerialName("dialogue")
    data class Dialogue(
        override val id: String,
        val actorName: String,
        val text: String,
        val emotion: String = "",
        val avatarType: AvatarType = AvatarType.ACTOR,
        val avatarUrl: String? = null,
        val senderType: SenderType = SenderType.ACTOR,
        val senderName: String = "",
    ) : SceneBubble() {
        override val contentFingerprint: String = "D|$actorName|${text.take(60)}"

        /** ★ 基于 contentFingerprint 重写，支持跨 id 去重 */
        override fun equals(other: Any?): Boolean {
            if (this === other) return true
            if (other !is Dialogue) return false
            return contentFingerprint == other.contentFingerprint
        }

        override fun hashCode(): Int = contentFingerprint.hashCode()
    }

    /**
     * 用户在群聊中发送的消息 — 右对齐显示，用户以"主角"身份参与
     *
     * ★ 交互语义区分：
     * - isAction = false（默认）: 直接对话，渲染为右侧聊天气泡 + 主角头像
     * - isAction = true: 动作行为（如 /action 拔剑），渲染为居中斜体无气泡，强调行为的发生
     */
    @Serializable
    @SerialName("user_message")
    data class UserMessage(
        override val id: String,
        val text: String,
        val mention: String? = null,
        val avatarType: AvatarType = AvatarType.USER,
        val avatarUrl: String? = null,
        val senderType: SenderType = SenderType.USER,
        val senderName: String = "主角",
        /** ★ 是否为动作行为 — true 时渲染为居中斜体（旁白式），false 时渲染为右侧聊天气泡 */
        val isAction: Boolean = false,
    ) : SceneBubble() {
        override val contentFingerprint: String = "U|${if (isAction) "A|" else ""}${text.take(60)}"

        /** ★ 基于 contentFingerprint 重写，支持跨 id 去重 */
        override fun equals(other: Any?): Boolean {
            if (this === other) return true
            if (other !is UserMessage) return false
            return contentFingerprint == other.contentFingerprint
        }

        override fun hashCode(): Int = contentFingerprint.hashCode()
    }

    /**
     * ★ 角色间互动对话 — 展示 AGENT 之间的交流过程
     */
    @Serializable
    @SerialName("actor_interaction")
    data class ActorInteraction(
        override val id: String,
        val fromActor: String,
        val toActor: String,
        val text: String,
        val emotion: String = "",
        val interactionType: InteractionType = InteractionType.REPLY,
        val replyToText: String? = null,
        val avatarType: AvatarType = AvatarType.ACTOR,
        val senderType: SenderType = SenderType.ACTOR,
        val senderName: String = "",
    ) : SceneBubble() {
        override val contentFingerprint: String = "AI|$fromActor|$toActor|${text.take(50)}"

        /** ★ 基于 contentFingerprint 重写，支持跨 id 去重 */
        override fun equals(other: Any?): Boolean {
            if (this === other) return true
            if (other !is ActorInteraction) return false
            return contentFingerprint == other.contentFingerprint
        }

        override fun hashCode(): Int = contentFingerprint.hashCode()
    }

    /** 场景分隔线 — 显示"第 N 场 · 标题" */
    @Serializable
    @SerialName("scene_divider")
    data class SceneDivider(
        override val id: String,
        val sceneNumber: Int,
        val sceneTitle: String = "",
    ) : SceneBubble() {
        override val contentFingerprint: String = "SD|$sceneNumber"

        /** ★ 基于 contentFingerprint 重写，支持跨 id 去重 */
        override fun equals(other: Any?): Boolean {
            if (this === other) return true
            if (other !is SceneDivider) return false
            return contentFingerprint == other.contentFingerprint
        }

        override fun hashCode(): Int = contentFingerprint.hashCode()
    }

    /** 系统错误消息 — 服务端错误内联展示，红色样式区别于普通消息 */
    @Serializable
    @SerialName("system_error")
    data class SystemError(
        override val id: String,
        val text: String,
        val avatarType: AvatarType = AvatarType.SYSTEM,
        val senderType: SenderType = SenderType.SYSTEM,
    ) : SceneBubble() {
        override val contentFingerprint: String = "SE|${text.take(40)}"

        /** ★ 基于 contentFingerprint 重写，支持跨 id 去重 */
        override fun equals(other: Any?): Boolean {
            if (this === other) return true
            if (other !is SystemError) return false
            return contentFingerprint == other.contentFingerprint
        }

        override fun hashCode(): Int = contentFingerprint.hashCode()
    }

    /** ★ 剧情引导反馈 — 用户指令改变剧情后的确认提示，短暂动画展示 */
    @Serializable
    @SerialName("plot_guidance")
    data class PlotGuidance(
        override val id: String,
        val text: String,
        val direction: String = "",
        val avatarType: AvatarType = AvatarType.DIRECTOR,
        val senderType: SenderType = SenderType.DIRECTOR,
    ) : SceneBubble() {
        override val contentFingerprint: String = "PG|$direction|${text.take(40)}"

        /** ★ 基于 contentFingerprint 重写，支持跨 id 去重 */
        override fun equals(other: Any?): Boolean {
            if (this === other) return true
            if (other !is PlotGuidance) return false
            return contentFingerprint == other.contentFingerprint
        }

        override fun hashCode(): Int = contentFingerprint.hashCode()
    }
}

/**
 * 角色互动类型枚举
 */
@Serializable
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
