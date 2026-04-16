package com.drama.app.ui.screens.dramadetail.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.drama.app.domain.model.SceneBubble

@Composable
fun SceneBubbleList(
    bubbles: List<SceneBubble>,
    isTyping: Boolean,
    typingText: String = "处理中...",
    modifier: Modifier = Modifier,
) {
    val listState = rememberLazyListState()

    // Pitfall 4: 自动滚动到底部
    LaunchedEffect(bubbles.size) {
        if (bubbles.isNotEmpty()) {
            listState.animateScrollToItem(bubbles.lastIndex)
        }
    }

    LazyColumn(
        state = listState,
        modifier = modifier.fillMaxSize().padding(horizontal = 8.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        items(items = bubbles, key = { it.id }) { bubble ->
            when (bubble) {
                is SceneBubble.Narration -> NarrationBubble(bubble)
                is SceneBubble.Dialogue -> DialogueBubble(bubble)
                is SceneBubble.SceneDivider -> {
                    HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))
                    Text(
                        text = "第 ${bubble.sceneNumber} 场${if (bubble.sceneTitle.isNotBlank()) "：${bubble.sceneTitle}" else ""}",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.outline,
                        modifier = Modifier.padding(bottom = 8.dp),
                    )
                }
            }
        }
        if (isTyping) {
            item(key = "typing_indicator") {
                TypingIndicator(typingText = typingText)
            }
        }
    }
}
