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
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.drama.app.domain.model.SceneBubble
import com.drama.app.ui.theme.ActorPalette

fun actorColor(name: String): Color {
    val idx = Math.abs(name.hashCode()) % ActorPalette.size
    return ActorPalette[idx]
}

@Composable
fun DialogueBubble(bubble: SceneBubble.Dialogue) {
    val color = actorColor(bubble.actorName)

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(start = 12.dp, end = 48.dp, top = 6.dp, bottom = 2.dp),
        verticalAlignment = Alignment.Top,
    ) {
        // Avatar — 36dp circle with gradient
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

        // Content column
        Column {
            // Name + emotion
            Row(verticalAlignment = Alignment.CenterVertically) {
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

            Spacer(modifier = Modifier.width(2.dp))

            // Speech bubble — chat-style with rounded corners
            // ★ 支持 \n 换行：Compose Text 默认不解析 \n，需用 AnnotatedString 分段渲染
            Surface(
                shape = RoundedCornerShape(
                    topStart = 4.dp,  // Small radius near avatar
                    topEnd = 16.dp,
                    bottomStart = 16.dp,
                    bottomEnd = 16.dp,
                ),
                color = color.copy(alpha = 0.08f),
                modifier = Modifier.padding(top = 4.dp),
                shadowElevation = 1.dp,
            ) {
                val textStyle = MaterialTheme.typography.bodyLarge.copy(
                    lineHeight = 22.sp,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                Text(
                    text = buildAnnotatedString {
                        bubble.text.split("\n").forEachIndexed { idx, line ->
                            if (idx > 0) append("\n")
                            withStyle(textStyle.toSpanStyle()) { append(line) }
                        }
                    },
                    modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
                )
            }
        }
    }
}
