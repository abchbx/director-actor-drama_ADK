package com.drama.app.ui.screens.dramadetail.components

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
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
import androidx.compose.material.icons.filled.Psychology
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.drama.app.domain.model.ActorInfo
import com.drama.app.ui.theme.ActorPalette

/**
 * Material3 演员卡片
 *
 * 布局：[圆形头像] | [名称 + 称号 + 性格FlowRow] | [状态标签 + 思考进度]
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ActorCard(
    actor: ActorInfo,
    onClick: ((ActorInfo) -> Unit)? = null,
    modifier: Modifier = Modifier,
) {
    val interactionSource = remember { MutableInteractionSource() }

    ElevatedCard(
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
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.elevatedCardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainerLow,
        ),
        elevation = CardDefaults.elevatedCardElevation(
            defaultElevation = 2.dp,
        ),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            // ── 左侧：圆形头像 ──
            AvatarCircle(name = actor.name)

            Spacer(modifier = Modifier.width(14.dp))

            // ── 中间区域：名称 + 称号 + 性格标签 ──
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(3.dp),
            ) {
                // 第一行：演员名称
                Text(
                    text = actor.name,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    color = MaterialTheme.colorScheme.onSurface,
                )

                // 第二行：称号
                if (actor.role.isNotBlank()) {
                    Text(
                        text = actor.role,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }

                // 第三行：性格关键词 FlowRow
                if (actor.personality.isNotBlank()) {
                    val keywords = actor.personality.split("[、,，\\s]+".toRegex())
                        .filter { it.isNotBlank() }
                        .take(6)
                    if (keywords.isNotEmpty()) {
                        FlowRow(
                            horizontalArrangement = Arrangement.spacedBy(4.dp),
                            verticalArrangement = Arrangement.spacedBy(4.dp),
                        ) {
                            keywords.forEach { keyword ->
                                PersonalityChip(text = keyword)
                            }
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.width(8.dp))

            // ── 右侧：状态标签 + 思考进度 ──
            Column(
                horizontalAlignment = Alignment.End,
                verticalArrangement = Arrangement.Center,
            ) {
                // 状态标签
                if (actor.isA2ARunning) {
                    ThinkingStatusChip()
                } else {
                    EmotionStatusChip(emotion = actor.emotions)
                }

                Spacer(modifier = Modifier.height(4.dp))

                // 思考进度数字
                if (actor.isA2ARunning && actor.thinkingProgress > 0) {
                    Text(
                        text = "${actor.thinkingProgress}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f),
                    )
                } else if (actor.isA2ARunning && actor.a2aPort > 0) {
                    Text(
                        text = ":${actor.a2aPort}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f),
                    )
                }
            }
        }
    }
}

// ═══════════════════════════════════════════════════════════
// 圆形头像 — 根据名称匹配阵营/固定色
// ═══════════════════════════════════════════════════════════

/** 知名角色固定色映射 */
private val FactionColors = mapOf(
    "曹操" to Color(0xFFB71C1C),     // 深红
    "刘备" to Color(0xFF42A5F5),     // 浅蓝
    "孙权" to Color(0xFF2E7D32),     // 深绿
    "诸葛亮" to Color(0xFFFFB300),   // 金色
    "关羽" to Color(0xFFD32F2F),     // 正红
    "张飞" to Color(0xFF5D4037),     // 棕黑
    "周瑜" to Color(0xFFE65100),     // 橙红
    "赵云" to Color(0xFF1565C0),     // 靛蓝
    "吕布" to Color(0xFF6A1B9A),     // 深紫
    "司马懿" to Color(0xFF37474F),   // 暗灰蓝
    "黄忠" to Color(0xFFF57F17),     // 暗金
    "马超" to Color(0xFFAD1457),     // 玫红
)

@Composable
private fun AvatarCircle(name: String) {
    val bgColor = remember(name) {
        FactionColors[name] ?: ActorPalette[name.hashCode().let { Math.abs(it) } % ActorPalette.size]
    }

    Box(
        modifier = Modifier
            .size(48.dp)
            .clip(CircleShape)
            .background(bgColor),
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

// ═══════════════════════════════════════════════════════════
// 性格关键词 Chip
// ═══════════════════════════════════════════════════════════

@Composable
private fun PersonalityChip(text: String) {
    Surface(
        shape = RoundedCornerShape(8.dp),
        color = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.7f),
    ) {
        Text(
            text = text.take(6),
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
            color = MaterialTheme.colorScheme.onSecondaryContainer,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

// ═══════════════════════════════════════════════════════════
// 状态标签
// ═══════════════════════════════════════════════════════════

/** 思考中状态 — 带旋转动画的 AssistChip */
@Composable
private fun ThinkingStatusChip() {
    val infiniteTransition = rememberInfiniteTransition(label = "thinking-pulse")
    val pulseAlpha by infiniteTransition.animateFloat(
        initialValue = 0.4f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(800, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "pulse",
    )

    AssistChip(
        onClick = {},
        label = {
            Text(
                text = "思考中…",
                style = MaterialTheme.typography.labelSmall,
                modifier = Modifier.alpha(pulseAlpha),
            )
        },
        leadingIcon = {
            CircularProgressIndicator(
                modifier = Modifier.size(AssistChipDefaults.IconSize),
                strokeWidth = 2.dp,
                strokeCap = StrokeCap.Round,
                color = MaterialTheme.colorScheme.primary,
                trackColor = Color.Transparent,
            )
        },
        modifier = Modifier.height(28.dp),
        shape = RoundedCornerShape(8.dp),
        colors = AssistChipDefaults.assistChipColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.3f),
            labelColor = MaterialTheme.colorScheme.primary,
        ),
        border = null,
    )
}

/** 情绪/待机状态标签 */
@Composable
private fun EmotionStatusChip(emotion: String) {
    val (bgColor, textColor) = when (emotion.lowercase()) {
        "happy", "joy" -> Color(0xFFFFF0E0) to Color(0xFFE65100)
        "sad", "sorrow" -> Color(0xFFE3F2FD) to Color(0xFF1565C0)
        "angry", "rage" -> Color(0xFFFFEBEE) to Color(0xFFC62828)
        "neutral", "calm" -> Color(0xFFF3E5F5) to Color(0xFF6A1B9A)
        else -> MaterialTheme.colorScheme.surfaceContainerHighest to MaterialTheme.colorScheme.onSurfaceVariant
    }

    Surface(
        shape = RoundedCornerShape(8.dp),
        color = bgColor,
    ) {
        Text(
            text = emotion,
            style = MaterialTheme.typography.labelSmall,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
            color = textColor,
            maxLines = 1,
        )
    }
}
