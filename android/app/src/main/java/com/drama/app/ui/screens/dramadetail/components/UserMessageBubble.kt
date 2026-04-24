package com.drama.app.ui.screens.dramadetail.components

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.drama.app.domain.model.SceneBubble
import com.drama.app.ui.components.MarkdownText

/** 用户消息气泡 — 右对齐，渐变 primary 色背景，带微妙阴影 */
@Composable
fun UserMessageBubble(bubble: SceneBubble.UserMessage) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(start = 48.dp, end = 10.dp, top = 4.dp, bottom = 4.dp),
        horizontalArrangement = Arrangement.End,
    ) {
        Column(horizontalAlignment = Alignment.End) {
            // @提及提示 — 更精致的标签样式
            if (bubble.mention != null) {
                Surface(
                    shape = RoundedCornerShape(8.dp),
                    color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.5f),
                ) {
                    Text(
                        text = "@${bubble.mention}",
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Medium,
                        color = MaterialTheme.colorScheme.primary.copy(alpha = 0.75f),
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                    )
                }
            }

            // 消息气泡 — 右对齐，圆角，带微妙阴影和渐变感，支持 Markdown 渲染
            Surface(
                shape = RoundedCornerShape(
                    topStart = 18.dp,
                    topEnd = 4.dp,   // 右上角小圆角（靠近自己）
                    bottomStart = 18.dp,
                    bottomEnd = 18.dp,
                ),
                color = MaterialTheme.colorScheme.primary.copy(alpha = 0.1f),
                shadowElevation = 1.dp,
                tonalElevation = 2.dp,
            ) {
                // ★ Markdown 渲染：支持 **加粗**、*斜体*、`代码`、[链接](url) 等
                MarkdownText(
                    markdown = bubble.text,
                    style = MaterialTheme.typography.bodyLarge.copy(
                        lineHeight = 22.sp,
                        color = MaterialTheme.colorScheme.onSurface,
                    ),
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 11.dp),
                )
            }
        }
    }
}
