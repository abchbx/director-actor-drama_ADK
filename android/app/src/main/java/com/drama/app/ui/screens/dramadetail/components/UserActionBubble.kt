package com.drama.app.ui.screens.dramadetail.components

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.DirectionsRun
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.drama.app.domain.model.SceneBubble

/** ★ 主角动作行为专用颜色 — 暖琥珀渐变 */
private val ActionColor = Color(0xFFE65100)
private val ActionColorLight = Color(0xFFFF8F00)

/**
 * ★ 主角动作行为气泡 — 居中斜体无气泡，强调行为的发生
 *
 * 设计要点：
 * - 居中显示，无气泡背景，以斜体文字+动作图标呈现
 * - 类似旁白或舞台提示，但用琥珀色区分于导演旁白
 * - 小型动作图标 + 主角名 + 斜体动作描述
 * - 强调"行为正在发生"的语义
 */
@Composable
fun UserActionBubble(bubble: SceneBubble.UserMessage) {
    val displayName = bubble.senderName.ifBlank { "主角" }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 24.dp, vertical = 6.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        // ★ 动作标签行 — 动作图标 + 主角名
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(bottom = 4.dp),
        ) {
            // ★ 动作图标 — 琥珀色圆形背景
            androidx.compose.foundation.layout.Box(
                modifier = Modifier
                    .size(20.dp)
                    .clip(CircleShape)
                    .background(
                        brush = Brush.linearGradient(
                            colors = listOf(ActionColor, ActionColorLight)
                        )
                    ),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    imageVector = Icons.Filled.DirectionsRun,
                    contentDescription = "动作",
                    tint = Color.White,
                    modifier = Modifier.size(12.dp),
                )
            }

            Spacer(modifier = Modifier.width(6.dp))

            Text(
                text = displayName,
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.Medium,
                color = ActionColor.copy(alpha = 0.85f),
            )

            Spacer(modifier = Modifier.width(6.dp))

            Text(
                text = "动作",
                style = MaterialTheme.typography.labelSmall,
                color = ActionColor.copy(alpha = 0.5f),
            )
        }

        // ★ 动作描述 — 居中斜体，无气泡包裹
        Text(
            text = bubble.text,
            style = MaterialTheme.typography.bodyLarge.copy(
                fontStyle = FontStyle.Italic,
                fontWeight = FontWeight.Medium,
                lineHeight = 22.sp,
                color = ActionColor.copy(alpha = 0.8f),
                textAlign = TextAlign.Center,
            ),
            modifier = Modifier.padding(horizontal = 16.dp),
        )
    }
}
