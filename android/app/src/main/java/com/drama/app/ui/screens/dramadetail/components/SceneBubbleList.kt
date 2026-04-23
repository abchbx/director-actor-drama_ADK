package com.drama.app.ui.screens.dramadetail.components

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearOutSlowInEasing
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.slideInVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import com.drama.app.domain.model.SceneBubble

/**
 * 场景气泡列表 — 带入场动画的对话流
 *
 * 动画特点：
 * - 每个新气泡从底部滑入 + 渐现（类似 iMessage）
 * - 自动滚动到最新消息
 * - TypingIndicator 带独立动画容器
 */
@Composable
fun SceneBubbleList(
    bubbles: List<SceneBubble>,
    isTyping: Boolean,
    typingText: String = "AI 正在思考...",
    modifier: Modifier = Modifier,
) {
    val listState = rememberLazyListState()

    // Auto-scroll to bottom when bubbles change
    LaunchedEffect(bubbles.size, isTyping) {
        if (bubbles.isNotEmpty()) {
            listState.animateScrollToItem(bubbles.lastIndex)
        }
    }

    LazyColumn(
        state = listState,
        modifier = modifier.fillMaxSize().padding(horizontal = 4.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        itemsIndexed(
            items = bubbles,
            key = { _, bubble -> bubble.id },
        ) { index, bubble ->
            // 每个气泡带入场动画：从底部滑入 + 渐现
            // 使用 index 计算延迟，形成瀑布效果
            val enterAnimation = fadeIn(
                animationSpec = tween(350, easing = FastOutSlowInEasing),
            ) + slideInVertically(
                initialOffsetY = { it / 3 },
                animationSpec = tween(400, easing = FastOutSlowInEasing),
            )

            androidx.compose.animation.AnimatedVisibility(
                visible = true,
                enter = enterAnimation,
            ) {
                when (bubble) {
                    is SceneBubble.Narration -> NarrationBubble(bubble)
                    is SceneBubble.Dialogue -> DialogueBubble(bubble)
                    is SceneBubble.UserMessage -> UserMessageBubble(bubble)
                    is SceneBubble.ActorInteraction -> ActorInteractionBubble(bubble)
                    is SceneBubble.SceneDivider -> SceneDivider(bubble)
                }
            }
        }

        // 思考指示器 — 独立动画项
        if (isTyping) {
            item(key = "typing_indicator") {
                androidx.compose.animation.AnimatedVisibility(
                    visible = true,
                    enter = fadeIn(tween(300)) + slideInVertically(
                        initialOffsetY = { it / 4 },
                        animationSpec = tween(350, easing = LinearOutSlowInEasing),
                    ),
                ) {
                    TypingIndicator(typingText = typingText)
                }
            }
        }
    }
}

@Composable
private fun SceneDivider(bubble: SceneBubble.SceneDivider) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 12.dp, horizontal = 16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        // 装饰线 + 中心点
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Box(
                modifier = Modifier
                    .weight(1f)
                    .height(1.dp)
                    .background(MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f))
            )
            Spacer(modifier = Modifier.width(8.dp))
            Box(
                modifier = Modifier
                    .size(6.dp)
                    .clip(CircleShape)
                    .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.6f))
            )
            Spacer(modifier = Modifier.width(8.dp))
            Box(
                modifier = Modifier
                    .weight(1f)
                    .height(1.dp)
                    .background(MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f))
            )
        }

        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = buildString {
                append("第 ")
                append(bubble.sceneNumber)
                append(" 场")
                if (bubble.sceneTitle.isNotBlank()) {
                    append(" · ")
                    append(bubble.sceneTitle)
                }
            },
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.primary.copy(alpha = 0.8f),
        )
    }
}
