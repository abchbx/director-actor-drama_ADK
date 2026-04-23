package com.drama.app.ui.screens.dramadetail.components

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowForward
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.drama.app.domain.model.InteractionType
import com.drama.app.domain.model.SceneBubble
import com.drama.app.ui.theme.ActorPalette

/**
 * 角色间互动对话气泡 — AGENT ↔ AGENT 交互可视化
 */
@Composable
fun ActorInteractionBubble(bubble: SceneBubble.ActorInteraction) {
    val fromColor = interactionActorColor(bubble.fromActor)
    val toColor = interactionActorColor(bubble.toActor)

    val typeInfo = interactionTypeInfo(bubble.interactionType)

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 8.dp, vertical = 6.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        // 类型标签
        if (typeInfo.showLabel) {
            Surface(
                shape = RoundedCornerShape(10.dp),
                color = typeInfo.labelColor.copy(alpha = 0.12f),
            ) {
                Text(
                    text = typeInfo.labelText,
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Medium,
                    fontStyle = FontStyle.Italic,
                    color = typeInfo.labelColor,
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 3.dp),
                )
            }
            Spacer(modifier = Modifier.height(6.dp))
        }

        // 核心交互卡片
        Surface(
            shape = RoundedCornerShape(18.dp),
            color = MaterialTheme.colorScheme.surfaceContainerLowest,
            shadowElevation = 2.dp,
            tonalElevation = 3.dp,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Column(
                modifier = Modifier.padding(horizontal = 14.dp, vertical = 12.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                // 第一行：头像 A → 箭头 → 头像 B
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    InteractionActorAvatar(
                        name = bubble.fromActor,
                        color = fromColor,
                        isFrom = true,
                        label = bubble.fromActor,
                    )

                    Spacer(modifier = Modifier.weight(1f))

                    Icon(
                        imageVector = Icons.Default.ArrowForward,
                        contentDescription = "${bubble.fromActor} 对 ${bubble.toActor} 说",
                        modifier = Modifier.size(20.dp),
                        tint = typeInfo.arrowColor.copy(alpha = 0.7f),
                    )

                    Spacer(modifier = Modifier.weight(1f))

                    InteractionActorAvatar(
                        name = bubble.toActor,
                        color = toColor,
                        isFrom = false,
                        label = bubble.toActor,
                    )
                }

                Spacer(modifier = Modifier.height(10.dp))

                // 第二行：情绪标签 + 消息内容
                Row(verticalAlignment = Alignment.Top) {
                    Box(
                        modifier = Modifier
                            .width(3.dp)
                            .height(24.dp)
                            .clip(RoundedCornerShape(2.dp))
                            .background(fromColor.copy(alpha = 0.5f)),
                    )
                    Spacer(modifier = Modifier.width(10.dp))

                    Column(modifier = Modifier.weight(1f)) {
                        if (bubble.emotion.isNotBlank()) {
                            Text(
                                text = bubble.emotion,
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = FontWeight.SemiBold,
                                color = fromColor.copy(alpha = 0.75f),
                                fontStyle = FontStyle.Italic,
                            )
                            Spacer(modifier = Modifier.height(3.dp))
                        }

                        Surface(
                            shape = RoundedCornerShape(12.dp),
                            color = fromColor.copy(alpha = 0.06f),
                        ) {
                            // ★ 支持 \n 换行
                            val bubbleTextStyle = MaterialTheme.typography.bodyLarge.copy(
                                lineHeight = 21.sp,
                                color = MaterialTheme.colorScheme.onSurface,
                            )
                            Text(
                                text = buildAnnotatedString {
                                    bubble.text.split("\n").forEachIndexed { idx, line ->
                                        if (idx > 0) append("\n")
                                        withStyle(bubbleTextStyle.toSpanStyle()) { append(line) }
                                    }
                                },
                                modifier = Modifier.padding(horizontal = 14.dp, vertical = 9.dp),
                            )
                        }

                        bubble.replyToText?.let { replyText ->
                            if (replyText.isNotBlank()) {
                                Spacer(modifier = Modifier.height(6.dp))
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    modifier = Modifier.padding(start = 4.dp),
                                ) {
                                    Box(
                                        modifier = Modifier
                                            .width(2.dp)
                                            .height(12.dp)
                                            .clip(RoundedCornerShape(1.dp))
                                            .background(MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f)),
                                    )
                                    Spacer(modifier = Modifier.width(6.dp))
                                    Text(
                                        text = "\"${replyText.take(40)}${if (replyText.length > 40) "..." else ""}\"",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.55f),
                                        fontStyle = FontStyle.Italic,
                                        maxLines = 1,
                                    )
                                }
                            }
                        }
                    }

                    Spacer(modifier = Modifier.width(10.dp))
                    Box(
                        modifier = Modifier
                            .width(3.dp)
                            .height(24.dp)
                            .clip(RoundedCornerShape(2.dp))
                            .background(toColor.copy(alpha = 0.35f)),
                    )
                }
            }
        }
    }
}

/** 单个演员头像（互动卡片专用） */
@Composable
private fun InteractionActorAvatar(
    name: String,
    color: Color,
    isFrom: Boolean,
    label: String,
) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Box(
            modifier = Modifier
                .size(36.dp)
                .clip(CircleShape)
                .background(Brush.linearGradient(colors = listOf(color, color.copy(alpha = 0.7f)))),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                text = name.firstOrNull()?.uppercase() ?: "?",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
                color = Color.White,
            )
        }
        Spacer(modifier = Modifier.height(3.dp))
        Text(
            text = if (label.length > 5) label.take(4) + "." else label,
            style = MaterialTheme.typography.labelSmall,
            fontWeight = if (isFrom) FontWeight.Bold else FontWeight.Normal,
            color = color.copy(alpha = 0.85f),
            maxLines = 1,
        )
    }
}

/** 获取角色对应色 — 避免与 DialogueBubble.actorColor 冲突 */
private fun interactionActorColor(name: String): Color {
    val idx = Math.abs(name.hashCode()) % ActorPalette.size
    return ActorPalette[idx]
}

/** 互动类型视觉配置 */
private data class InteractionTypeInfo(
    val labelText: String,
    val labelColor: Color,
    val arrowColor: Color,
    val showLabel: Boolean = true,
)

@Composable
private fun interactionTypeInfo(type: InteractionType): InteractionTypeInfo {
    return when (type) {
        InteractionType.REPLY -> InteractionTypeInfo(
            labelText = "回复",
            labelColor = MaterialTheme.colorScheme.primary,
            arrowColor = MaterialTheme.colorScheme.primary,
        )
        InteractionType.CHIME_IN -> InteractionTypeInfo(
            labelText = "插话",
            labelColor = MaterialTheme.colorScheme.tertiary,
            arrowColor = MaterialTheme.colorScheme.tertiary,
        )
        InteractionType.COUNTER -> InteractionTypeInfo(
            labelText = "反驳",
            labelColor = MaterialTheme.colorScheme.error,
            arrowColor = MaterialTheme.colorScheme.error,
        )
        InteractionType.PROPOSE -> InteractionTypeInfo(
            labelText = "建议",
            labelColor = MaterialTheme.colorScheme.secondary,
            arrowColor = MaterialTheme.colorScheme.secondary,
        )
        InteractionType.EMOTIONAL -> InteractionTypeInfo(
            labelText = "",
            labelColor = Color.Transparent,
            arrowColor = MaterialTheme.colorScheme.outline,
            showLabel = false,
        )
    }
}
