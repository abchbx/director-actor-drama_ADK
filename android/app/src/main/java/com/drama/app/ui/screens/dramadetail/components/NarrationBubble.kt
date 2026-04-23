package com.drama.app.ui.screens.dramadetail.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.drama.app.domain.model.SceneBubble

@Composable
fun NarrationBubble(bubble: SceneBubble.Narration) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 24.dp, vertical = 8.dp),
        contentAlignment = Alignment.Center,
    ) {
        // Elegant card with italic narration
        Box(
            modifier = Modifier
                .shadow(2.dp, RoundedCornerShape(12.dp))
                .clip(RoundedCornerShape(12.dp))
                .background(
                    MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f)
                )
                .padding(horizontal = 20.dp, vertical = 14.dp),
        ) {
            // ★ 支持 \n 换行：Compose Text 默认不解析 \n，需用 AnnotatedString 分段渲染
            val textStyle = MaterialTheme.typography.bodyLarge.copy(
                fontStyle = FontStyle.Italic,
                lineHeight = 22.sp,
                letterSpacing = 0.3.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                text = buildAnnotatedString {
                    bubble.text.split("\n").forEachIndexed { idx, line ->
                        if (idx > 0) append("\n")
                        withStyle(textStyle.toSpanStyle()) { append(line) }
                    }
                },
                textAlign = TextAlign.Start,
            )
        }
    }
}
