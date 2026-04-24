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
import com.drama.app.ui.theme.ActorPalette
import com.drama.app.ui.theme.MarkdownColors

/** 导演头像颜色 - 专属配色 */
private val DirectorAvatarColor = Color(0xFF6A5ACD)  // 紫色系

/**
 * 微信群聊风格旁白气泡
 * - 导演专属头像图标（戏剧面具）
 * - 居中显示叙述文本
 */
@Composable
fun NarrationBubble(bubble: SceneBubble.Narration) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 6.dp),
        verticalAlignment = Alignment.Top,
    ) {
        // ★ 导演专属头像
        Box(
            modifier = Modifier
                .size(36.dp)
                .clip(CircleShape)
                .background(
                    brush = Brush.linearGradient(
                        colors = listOf(
                            DirectorAvatarColor,
                            DirectorAvatarColor.copy(alpha = 0.7f)
                        )
                    )
                )
                .shadow(2.dp, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                imageVector = Icons.Filled.TheaterComedy,
                contentDescription = "导演",
                tint = Color.White,
                modifier = Modifier.size(22.dp),
            )
        }

        Spacer(modifier = Modifier.width(10.dp))

        // 叙述内容
        Column(
            modifier = Modifier.weight(1f),
            horizontalAlignment = Alignment.Start,
        ) {
            // 导演标签
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.padding(bottom = 4.dp),
            ) {
                Text(
                    text = "旁白",
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.Medium,
                    color = DirectorAvatarColor,
                )
            }

            // 叙述气泡，支持 Markdown 渲染，默认为斜体风格
            Surface(
                shape = RoundedCornerShape(
                    topStart = 4.dp,
                    topEnd = 16.dp,
                    bottomStart = 16.dp,
                    bottomEnd = 16.dp,
                ),
                color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.8f),
                shadowElevation = 1.dp,
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

                MarkdownText(
                    markdown = bubble.text,
                    style = MaterialTheme.typography.bodyLarge.copy(
                        fontStyle = FontStyle.Italic,
                        lineHeight = 24.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    ),
                    config = narrationConfig,
                    modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
                )
            }
        }
    }
}

/**
 * 实时旁白气泡 - 用于 typing 状态下的实时旁白显示
 * 样式略有不同，带有"正在输入"动画效果
 */
@Composable
fun RealtimeNarrationBubble(text: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 6.dp),
        verticalAlignment = Alignment.Top,
    ) {
        // ★ 导演头像
        Box(
            modifier = Modifier
                .size(36.dp)
                .clip(CircleShape)
                .background(
                    brush = Brush.linearGradient(
                        colors = listOf(
                            DirectorAvatarColor,
                            DirectorAvatarColor.copy(alpha = 0.7f)
                        )
                    )
                )
                .shadow(2.dp, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                imageVector = Icons.Filled.TheaterComedy,
                contentDescription = "导演",
                tint = Color.White,
                modifier = Modifier.size(22.dp),
            )
        }

        Spacer(modifier = Modifier.width(10.dp))

        Column(
            modifier = Modifier.weight(1f),
            horizontalAlignment = Alignment.Start,
        ) {
            Text(
                text = "旁白",
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Medium,
                color = DirectorAvatarColor,
                modifier = Modifier.padding(bottom = 4.dp),
            )

            Surface(
                shape = RoundedCornerShape(
                    topStart = 4.dp,
                    topEnd = 16.dp,
                    bottomStart = 16.dp,
                    bottomEnd = 16.dp,
                ),
                color = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.6f),
                shadowElevation = 1.dp,
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
                    modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
                )
            }
        }
    }
}
