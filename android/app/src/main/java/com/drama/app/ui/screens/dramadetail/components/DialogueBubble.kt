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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.drama.app.domain.model.SceneBubble
import com.drama.app.ui.components.ActorEmphasizeColor
import com.drama.app.ui.components.MarkdownConfig
import com.drama.app.ui.components.MarkdownText
import com.drama.app.ui.components.ParagraphSpacing
import com.drama.app.ui.components.QuoteStyle
import com.drama.app.ui.theme.ActorPalette

/** 根据角色名称生成一致的颜色 */
fun actorColor(name: String): Color {
    val idx = Math.abs(name.hashCode()) % ActorPalette.size
    return ActorPalette[idx]
}

/**
 * 微信群聊风格角色对话气泡
 * - 左侧显示角色头像（根据名称生成颜色一致的占位头像）
 * - 角色名称和情绪标签
 * - 聊天气泡样式
 */
@Composable
fun DialogueBubble(bubble: SceneBubble.Dialogue) {
    val color = actorColor(bubble.actorName)

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(start = 12.dp, end = 48.dp, top = 6.dp, bottom = 2.dp),
        verticalAlignment = Alignment.Top,
    ) {
        // ★ 角色头像 - 36dp 圆形渐变背景
        Box(
            modifier = Modifier
                .size(36.dp)
                .clip(CircleShape)
                .background(
                    brush = Brush.linearGradient(
                        colors = listOf(color, color.copy(alpha = 0.7f))
                    )
                )
                .shadow(2.dp, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                text = bubble.actorName.firstOrNull()?.uppercase() ?: "?",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
                color = Color.White,
            )
        }

        Spacer(modifier = Modifier.width(10.dp))

        // 内容列
        Column(
            modifier = Modifier.weight(1f),
        ) {
            // 角色名称 + 情绪标签
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.padding(bottom = 2.dp),
            ) {
                Text(
                    text = bubble.actorName,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    color = color,
                )
                if (bubble.emotion.isNotBlank()) {
                    Spacer(modifier = Modifier.width(6.dp))
                    Surface(
                        shape = RoundedCornerShape(10.dp),
                        color = color.copy(alpha = 0.12f),
                    ) {
                        Text(
                            text = bubble.emotion,
                            style = MaterialTheme.typography.labelSmall,
                            fontStyle = FontStyle.Italic,
                            color = color,
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                        )
                    }
                }
            }

            // ★ 聊天气泡 - 微信风格圆角，支持 Markdown 渲染
            Surface(
                shape = RoundedCornerShape(
                    topStart = 4.dp,   // 头像侧小圆角
                    topEnd = 16.dp,
                    bottomStart = 16.dp,
                    bottomEnd = 16.dp,
                ),
                color = color.copy(alpha = 0.08f),
                shadowElevation = 1.dp,
            ) {
                // ★ Markdown 渲染：支持 **加粗**、*斜体*、`代码`、[链接](url) 等
                // 使用 MarkdownConfig 配置角色强调色和段落间距
                val markdownConfig = MarkdownConfig(
                    actorColor = ActorEmphasizeColor(
                        primary = color,
                        secondary = color.copy(alpha = 0.7f),
                        tertiary = color.copy(alpha = 0.85f),
                    ),
                    useActorColorForEmphasis = true,
                    quoteStyle = QuoteStyle(
                        enabled = true,
                        cornerRadius = 12,
                        backgroundColor = color.copy(alpha = 0.06f),
                        leftBorderWidth = 3,
                        padding = 10,
                        showQuoteBar = true,
                    ),
                    paragraphSpacing = ParagraphSpacing(
                        enabled = true,
                        paragraphTopSpacing = 6,
                        paragraphBottomSpacing = 4,
                        listItemSpacing = 4,
                        headingBottomMargin = 6,
                    ),
                )

                MarkdownText(
                    markdown = bubble.text,
                    style = MaterialTheme.typography.bodyLarge.copy(
                        lineHeight = 24.sp,
                        color = MaterialTheme.colorScheme.onSurface,
                    ),
                    config = markdownConfig,
                    modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
                )
            }
        }
    }
}

/**
 * 实时对话气泡 - 用于 typing 状态下的实时显示
 * 带有渐变背景表示"正在输入"
 */
@Composable
fun RealtimeDialogueBubble(actorName: String, text: String) {
    val color = actorColor(actorName)

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(start = 12.dp, end = 48.dp, top = 6.dp, bottom = 2.dp),
        verticalAlignment = Alignment.Top,
    ) {
        // 角色头像
        Box(
            modifier = Modifier
                .size(36.dp)
                .clip(CircleShape)
                .background(
                    brush = Brush.linearGradient(
                        colors = listOf(color, color.copy(alpha = 0.7f))
                    )
                )
                .shadow(2.dp, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                text = actorName.firstOrNull()?.uppercase() ?: "?",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
                color = Color.White,
            )
        }

        Spacer(modifier = Modifier.width(10.dp))

        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = actorName,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
                color = color,
                modifier = Modifier.padding(bottom = 2.dp),
            )

            // 带动画效果的实时气泡，支持 Markdown 渲染
            Surface(
                shape = RoundedCornerShape(
                    topStart = 4.dp,
                    topEnd = 16.dp,
                    bottomStart = 16.dp,
                    bottomEnd = 16.dp,
                ),
                color = color.copy(alpha = 0.12f),
                shadowElevation = 1.dp,
            ) {
                val markdownConfig = MarkdownConfig(
                    actorColor = ActorEmphasizeColor(
                        primary = color,
                        secondary = color.copy(alpha = 0.7f),
                    ),
                    paragraphSpacing = ParagraphSpacing(
                        enabled = true,
                        paragraphTopSpacing = 6,
                        paragraphBottomSpacing = 4,
                    ),
                )

                MarkdownText(
                    markdown = text,
                    style = MaterialTheme.typography.bodyLarge.copy(
                        lineHeight = 24.sp,
                        color = MaterialTheme.colorScheme.onSurface,
                    ),
                    config = markdownConfig,
                    modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
                )
            }
        }
    }
}
