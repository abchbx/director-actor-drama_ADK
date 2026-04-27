package com.drama.app.ui.screens.dramadetail.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.TheaterComedy
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.drama.app.domain.model.SceneBubble
import com.drama.app.ui.components.ActorEmphasizeColor
import com.drama.app.ui.components.MarkdownConfig
import com.drama.app.ui.components.MarkdownText
import com.drama.app.ui.components.ParagraphSpacing
import com.drama.app.ui.components.QuoteStyle
import com.drama.app.ui.components.TypewriterMarkdownText
import com.drama.app.ui.theme.MarkdownColors

/** 导演头像颜色 - 专属配色 */
private val DirectorAvatarColor = Color(0xFF6A5ACD)  // 紫色系

/**
 * ★ 导演（旁白）气泡 — 居中/透明背景风格
 * 
 * 设计要点：
 * - 居中显示，半透明背景卡片，区别于左侧角色气泡
 * - 导演专属头像（戏剧面具）+ 名称
 * - 斜体风格 Markdown 渲染
 * - 比演员气泡更宽，营造"叙述感"
 */
@Composable
fun NarrationBubble(bubble: SceneBubble.Narration) {
    val displayName = bubble.senderName.ifBlank { "旁白" }
    // ★ 增强：若 senderName 包含"→主角"标记，显示特殊的"对你的叙述"标签
    val isDirectedAtProtagonist = displayName.contains("→主角")
    val cleanDisplayName = displayName.replace("→主角", "").trim().ifBlank { "旁白" }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        // ★ 导演标签行 — 头像 + 名称 + 旁白标签
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(bottom = 4.dp),
        ) {
            // ★ 导演专属头像（小尺寸，24dp）
            Box(
                modifier = Modifier
                    .size(24.dp)
                    .clip(CircleShape)
                    .background(
                        brush = Brush.linearGradient(
                            colors = listOf(
                                DirectorAvatarColor,
                                DirectorAvatarColor.copy(alpha = 0.7f)
                            )
                        )
                    ),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    imageVector = Icons.Filled.TheaterComedy,
                    contentDescription = cleanDisplayName,
                    tint = Color.White,
                    modifier = Modifier.size(14.dp),
                )
            }

            Spacer(modifier = Modifier.width(6.dp))

            Text(
                text = cleanDisplayName,
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Medium,
                color = DirectorAvatarColor,
            )

            // ★ "旁白"标签
            Surface(
                shape = RoundedCornerShape(6.dp),
                color = DirectorAvatarColor.copy(alpha = 0.1f),
            ) {
                Text(
                    text = "旁白",
                    style = MaterialTheme.typography.labelSmall,
                    color = DirectorAvatarColor.copy(alpha = 0.7f),
                    modifier = Modifier.padding(horizontal = 5.dp, vertical = 1.dp),
                )
            }

            // ★ 若针对主角，显示特殊标记
            if (isDirectedAtProtagonist) {
                Spacer(modifier = Modifier.width(4.dp))
                Surface(
                    shape = RoundedCornerShape(6.dp),
                    color = Color(0xFFB71C1C).copy(alpha = 0.1f),
                ) {
                    Text(
                        text = "→ 主角",
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Medium,
                        color = Color(0xFFB71C1C).copy(alpha = 0.7f),
                        modifier = Modifier.padding(horizontal = 5.dp, vertical = 1.dp),
                    )
                }
            }
        }

        // ★ 叙述气泡 — 群聊样式：居中，自适应宽度，小圆角，更紧凑
        Surface(
            shape = RoundedCornerShape(12.dp),
            color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.45f),
            shadowElevation = 0.dp,
            modifier = Modifier.padding(horizontal = 32.dp),
        ) {
            // ★ Markdown 渲染：支持 **加粗**、*斜体*、`代码`、[链接](url) 等
            // 旁白专用配置：斜体风格 + 更大的段落间距 + 淡雅配色
            val narrationConfig = MarkdownConfig(
                actorColor = ActorEmphasizeColor(
                    primary = DirectorAvatarColor.copy(alpha = 0.9f),
                    secondary = MarkdownColors.Quote.LightText,
                    tertiary = DirectorAvatarColor.copy(alpha = 0.8f),
                ),
                useActorColorForEmphasis = false,  // 旁白不加粗强调色
                quoteStyle = QuoteStyle(
                    enabled = true,
                    cornerRadius = 10,
                    backgroundColor = DirectorAvatarColor.copy(alpha = 0.05f),
                    leftBorderWidth = 2,
                    padding = 8,
                    showQuoteBar = true,
                ),
                paragraphSpacing = ParagraphSpacing(
                    enabled = true,
                    paragraphTopSpacing = 8,  // 更大的段落间距
                    paragraphBottomSpacing = 6,
                    listItemSpacing = 6,
                    headingBottomMargin = 10,
                ),
                mixedLanguage = com.drama.app.ui.components.MixedLanguageConfig(
                    enabled = true,
                    letterSpacing = 0.3f,
                    chineseLetterSpacing = 0.8f,
                    lineHeightMultiplier = 1.6f,  // 更大的行高
                ),
            )

            TypewriterMarkdownText(
                id = bubble.id,
                markdown = bubble.text,
                style = MaterialTheme.typography.bodyMedium.copy(
                    fontStyle = FontStyle.Italic,
                    lineHeight = 20.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                ),
                config = narrationConfig,
                modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                typingSpeedMs = 22L,
            )
        }
    }
}

/**
 * 实时旁白气泡 - 用于 typing 状态下的实时旁白显示
 * 样式略有不同，带有"正在输入"动画效果
 */
@Composable
fun RealtimeNarrationBubble(text: String) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 6.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        // 导演标签行
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(bottom = 6.dp),
        ) {
            Box(
                modifier = Modifier
                    .size(28.dp)
                    .clip(CircleShape)
                    .background(
                        brush = Brush.linearGradient(
                            colors = listOf(
                                DirectorAvatarColor,
                                DirectorAvatarColor.copy(alpha = 0.7f)
                            )
                        )
                    ),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    imageVector = Icons.Filled.TheaterComedy,
                    contentDescription = "导演",
                    tint = Color.White,
                    modifier = Modifier.size(16.dp),
                )
            }

            Spacer(modifier = Modifier.width(8.dp))

            Text(
                text = "旁白",
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Medium,
                color = DirectorAvatarColor,
            )

            Surface(
                shape = RoundedCornerShape(8.dp),
                color = DirectorAvatarColor.copy(alpha = 0.1f),
            ) {
                Text(
                    text = "旁白",
                    style = MaterialTheme.typography.labelSmall,
                    color = DirectorAvatarColor.copy(alpha = 0.7f),
                    modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                )
            }
        }

        Surface(
            shape = RoundedCornerShape(16.dp),
            color = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.4f),
            shadowElevation = 0.dp,
            modifier = Modifier.fillMaxWidth(),
        ) {
            // 旁白配置
            val narrationConfig = MarkdownConfig(
                actorColor = ActorEmphasizeColor(
                    primary = DirectorAvatarColor.copy(alpha = 0.85f),
                ),
                paragraphSpacing = ParagraphSpacing(
                    enabled = true,
                    paragraphTopSpacing = 8,
                    paragraphBottomSpacing = 6,
                ),
                mixedLanguage = com.drama.app.ui.components.MixedLanguageConfig(
                    enabled = true,
                    lineHeightMultiplier = 1.5f,
                ),
            )

            MarkdownText(
                markdown = text,
                style = MaterialTheme.typography.bodyLarge.copy(
                    fontStyle = FontStyle.Italic,
                    lineHeight = 24.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                ),
                config = narrationConfig,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
            )
        }
    }
}
