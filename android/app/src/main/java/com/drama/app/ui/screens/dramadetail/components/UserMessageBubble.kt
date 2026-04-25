package com.drama.app.ui.screens.dramadetail.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
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
import androidx.compose.material.icons.filled.Person
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.drama.app.domain.model.SceneBubble
import com.drama.app.ui.components.MarkdownText

/** ★ 主角专属头像颜色 — 帷幕深红渐变 */
private val ProtagonistAvatarColor = Color(0xFFB71C1C)
private val ProtagonistAvatarColorLight = Color(0xFFEF5350)

/**
 * ★ 主角消息气泡 — 右对齐，专属头像，primary 渐变气泡背景
 * 
 * 设计要点：
 * - 右侧气泡，带头像在右边（微信/Telegram 风格）
 * - 专属深红帷幕渐变头像，主角图标
 * - @提及标签更精致
 * - Markdown 渲染支持
 */
@Composable
fun UserMessageBubble(bubble: SceneBubble.UserMessage) {
    val displayName = bubble.senderName.ifBlank { "主角" }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(start = 36.dp, end = 10.dp, top = 4.dp, bottom = 4.dp),
        horizontalArrangement = Arrangement.End,
        verticalAlignment = Alignment.Top,
    ) {
        // 内容列 — 右对齐
        Column(horizontalAlignment = Alignment.End) {
            // ★ 主角名称标签
            Text(
                text = displayName,
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.Medium,
                color = ProtagonistAvatarColor.copy(alpha = 0.85f),
                modifier = Modifier.padding(end = 4.dp, bottom = 2.dp),
            )

            // @提及提示 — 更精致的标签样式
            if (bubble.mention != null) {
                Surface(
                    shape = RoundedCornerShape(8.dp),
                    color = ProtagonistAvatarColor.copy(alpha = 0.08f),
                ) {
                    Text(
                        text = "@${bubble.mention}",
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Medium,
                        color = ProtagonistAvatarColor.copy(alpha = 0.7f),
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                    )
                }
            }

            // ★ 消息气泡 — 右对齐，帷幕红渐变底色，圆角
            Surface(
                shape = RoundedCornerShape(
                    topStart = 18.dp,
                    topEnd = 4.dp,   // 右上角小圆角（靠近自己）
                    bottomStart = 18.dp,
                    bottomEnd = 18.dp,
                ),
                color = ProtagonistAvatarColor.copy(alpha = 0.08f),
                shadowElevation = 1.dp,
                tonalElevation = 2.dp,
            ) {
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

        Spacer(modifier = Modifier.width(10.dp))

        // ★ 主角专属头像 — 深红帷幕渐变 + Person 图标
        Box(
            modifier = Modifier
                .size(36.dp)
                .clip(CircleShape)
                .background(
                    brush = Brush.linearGradient(
                        colors = listOf(ProtagonistAvatarColor, ProtagonistAvatarColorLight)
                    )
                )
                .shadow(2.dp, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                imageVector = Icons.Filled.Person,
                contentDescription = displayName,
                tint = Color.White,
                modifier = Modifier.size(20.dp),
            )
        }
    }
}
