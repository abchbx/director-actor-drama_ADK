package com.drama.app.ui.screens.dramadetail.components

import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.spring
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
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
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.drama.app.domain.model.ActorInfo

/**
 * Apple Style 演员卡片 — 磨砂玻璃质感 (Glassmorphism)
 *
 * 包含: 圆形头像 | 角色名称 | 性格标签 | 心理状态反馈 | A2A 运行状态
 */
@Composable
fun ActorCard(
    actor: ActorInfo,
    onClick: ((ActorInfo) -> Unit)? = null,
    modifier: Modifier = Modifier,
) {
    val interactionSource = remember { MutableInteractionSource() }

    Surface(
        modifier = modifier
            .fillMaxWidth()
            .then(
                if (onClick != null) {
                    Modifier.clickable(
                        interactionSource = interactionSource,
                        indication = null,
                        onClick = { onClick(actor) },
                    )
                } else {
                    Modifier
                }
            ),
        shape = RoundedCornerShape(20.dp),
        color = MaterialTheme.colorScheme.surface.copy(alpha = 0.6f),
        shadowElevation = 1.dp,
        tonalElevation = 0.dp,
    ) {
        // 磨砂玻璃背景层
        Box(
            modifier = Modifier
                .clip(RoundedCornerShape(20.dp))
                .background(
                    Brush.verticalGradient(
                        colors = listOf(
                            MaterialTheme.colorScheme.surface.copy(alpha = 0.5f),
                            MaterialTheme.colorScheme.surfaceContainerHighest.copy(alpha = 0.4f),
                        ),
                    ),
                )
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(14.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                // ── 头像（圆形，带渐变边框） ──
                AvatarCircle(name = actor.name)

                Spacer(modifier = Modifier.width(12.dp))

                // ── 右侧信息列 ──
                Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    // 角色名称 + A2A 状态指示点
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(
                            text = actor.name,
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                            color = MaterialTheme.colorScheme.onSurface,
                        )
                        // A2A 运行状态指示灯
                        Box(
                            modifier = Modifier
                                .size(8.dp)
                                .clip(CircleShape)
                                .background(
                                    if (actor.isA2ARunning) Color(0xFF34C759) else Color(0xFFFF3B30)
                                ),
                        )
                    }

                    // 角色描述
                    if (actor.role.isNotBlank()) {
                        Text(
                            text = actor.role,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }

                    // 性格标签行
                    if (actor.personality.isNotBlank()) {
                        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                            PersonalityTag(text = actor.personality)
                            EmotionBadge(emotion = actor.emotions)
                        }
                    } else {
                        EmotionBadge(emotion = actor.emotions)
                    }

                    // 心理状态反馈
                    Spacer(modifier = Modifier.height(2.dp))
                    Text(
                        text = buildStatusText(actor),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.7f),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }
    }
}

@Composable
private fun AvatarCircle(name: String) {
    val avatarColors = rememberAvatarColors(name)

    Box(
        modifier = Modifier
            .size(48.dp)
            .clip(CircleShape)
            .background(Brush.radialGradient(colors = avatarColors)),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = name.firstOrNull()?.uppercase() ?: "?",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold,
            color = Color.White,
        )
    }
}

@Composable
private fun PersonalityTag(text: String) {
    Surface(
        shape = RoundedCornerShape(6.dp),
        color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.5f),
    ) {
        Text(
            text = text.take(8),
            style = MaterialTheme.typography.labelSmall,
            modifier = Modifier.padding(horizontal = 7.dp, vertical = 1.dp),
            color = MaterialTheme.colorScheme.primary,
        )
    }
}

@Composable
private fun EmotionBadge(emotion: String) {
    val (bgColor, textColor) = when (emotion.lowercase()) {
        "happy", "joy" -> Pair(Color(0xFFFFF0E0), Color(0xFFE65100))
        "sad", "sorrow" -> Pair(Color(0xFFE3F2FD), Color(0xFF1565C0))
        "angry", "rage" -> Pair(Color(0xFFFFEBEE), Color(0xFFC62828))
        "neutral", "calm" -> Pair(Color(0xFFF3E5F5), Color(0xFF6A1B9A))
        else -> Pair(MaterialTheme.colorScheme.surfaceContainerHighest, MaterialTheme.colorScheme.onSurfaceVariant)
    }

    Surface(shape = RoundedCornerShape(6.dp), color = bgColor) {
        Text(
            text = emotion,
            style = MaterialTheme.typography.labelSmall,
            modifier = Modifier.padding(horizontal = 7.dp, vertical = 1.dp),
            color = textColor,
        )
    }
}

private fun buildStatusText(actor: ActorInfo): String {
    return buildString {
        if (actor.isA2ARunning) {
            if (actor.a2aPort > 0) append("思考中... :${actor.a2aPort} ") else append("思考中... ")
        } else {
            append("待命 ")
        }
        if (actor.memorySummary.isNotBlank()) {
            append("· ${actor.memorySummary.take(20)}")
        }
    }.trim()
}

@Composable
private fun rememberAvatarColors(name: String): List<Color> {
    return remember(name) {
        val hash = name.hashCode()
        val hue = ((hash % 360).coerceIn(0, 359)).toFloat() / 360f
        listOf(
            Color.hsv(hue * 360f, 0.65f, 0.75f),
            Color.hsv((hue + 0.15f) * 360f % 360f, 0.55f, 0.60f),
        )
    }
}
