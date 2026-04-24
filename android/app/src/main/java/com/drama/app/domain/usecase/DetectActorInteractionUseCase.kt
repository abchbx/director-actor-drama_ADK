package com.drama.app.domain.usecase

import com.drama.app.domain.model.InteractionType
import com.drama.app.domain.model.SceneBubble
import javax.inject.Inject

/**
 * 角色互动智能检测 UseCase
 *
 * 判断当前发言是否应渲染为 ActorInteraction 气泡。
 * 判定规则：
 * 1. 前一个气泡是不同角色的 Dialogue → 可能是回复（REPLY）
 * 2. 事件类型为 actor_chime_in → 插话（CHIME_IN）
 * 3. 文本包含引用性词汇（"你说的对"、"我不这么认为"等）→ 反驳或回复
 * 4. 有明确的 target_actor 数据 → 直接使用
 */
class DetectActorInteractionUseCase @Inject constructor() {

    /** 反驳关键词 */
    private val counterKeywords = listOf(
        "不对", "不是", "我不同意", "错了", "荒谬", "胡说",
        "不认同", "反对", "但是", "然而", "可是",
    )

    /** 协商关键词 */
    private val proposeKeywords = listOf(
        "不如", "建议", "我们可以", "要不要", "也许应该",
        "不如我们", "或许可以", "要不",
    )

    /**
     * @param currentActor  当前发言者
     * @param text          发言内容
     * @param emotion       情绪标签
     * @param lastBubble    前一个气泡（用于推断目标角色）
     * @param eventType     事件类型 ("dialogue" | "chime_in")
     * @param bubbleCounter 用于生成 id 的计数器值
     * @return 如果判定为互动则返回 ActorInteraction，否则返回 null
     */
    operator fun invoke(
        currentActor: String,
        text: String,
        emotion: String,
        lastBubble: SceneBubble?,
        eventType: String,
        bubbleCounter: Int,
    ): SceneBubble.ActorInteraction? {
        if (currentActor.isBlank() || text.isBlank()) return null

        // 规则1：从事件数据中获取目标角色（预留扩展点）
        val explicitTarget: String? = null

        // 规则2：基于前一个气泡推断
        var inferredTarget: String? = null
        var interactionType: InteractionType? = null

        when {
            eventType == "chime_in" -> {
                interactionType = InteractionType.CHIME_IN
                if (lastBubble is SceneBubble.Dialogue && lastBubble.actorName != currentActor) {
                    inferredTarget = lastBubble.actorName
                }
            }
            lastBubble is SceneBubble.Dialogue && lastBubble.actorName != currentActor -> {
                interactionType = InteractionType.REPLY
                inferredTarget = lastBubble.actorName
            }
            lastBubble is SceneBubble.UserMessage && lastBubble.mention != null -> {
                interactionType = InteractionType.REPLY
                inferredTarget = lastBubble.mention
            }
            lastBubble is SceneBubble.ActorInteraction && lastBubble.fromActor != currentActor -> {
                interactionType = InteractionType.REPLY
                inferredTarget = lastBubble.fromActor
            }
        }

        // 规则3：文本语义分析 — 检测反驳/协商关键词
        if (interactionType == InteractionType.REPLY) {
            if (counterKeywords.any { text.contains(it) }) {
                interactionType = InteractionType.COUNTER
            } else if (proposeKeywords.any { text.contains(it) }) {
                interactionType = InteractionType.PROPOSE
            }
        }

        val finalTarget = explicitTarget ?: inferredTarget ?: return null

        return SceneBubble.ActorInteraction(
            id = "interaction_$bubbleCounter",
            fromActor = currentActor,
            toActor = finalTarget,
            text = text,
            emotion = emotion,
            interactionType = interactionType ?: InteractionType.REPLY,
            replyToText = (lastBubble as? SceneBubble.Dialogue)?.text?.take(50),
        )
    }
}
