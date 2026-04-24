package com.drama.app.ui.screens.dramadetail.components

import androidx.compose.animation.AnimatedVisibility
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
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.KeyboardArrowDown
import com.drama.app.domain.model.SceneBubble
import kotlinx.coroutines.launch

/**
 * 场景气泡列表 — 带入场动画的对话流
 *
 * 优化特性：
 * - LazyColumn key = { it.id }，确保高效 diff & 稳定 recomposition
 * - 智能自动滚动：仅当用户接近底部时才自动跟随新消息
 * - "新消息提示"悬浮按钮：向上滚动后一键跳回最新消息
 * - TypingIndicator 固定高度占位，消除出现/消失时的跳动
 * - 每个气泡带淡入 + 位移动画
 */
@Composable
fun SceneBubbleList(
    bubbles: List<SceneBubble>,
    isTyping: Boolean,
    typingText: String = "AI 正在思考...",
    modifier: Modifier = Modifier,
) {
    val listState = rememberLazyListState()
    val scope = rememberCoroutineScope()

    // ── 是否接近底部的判断（最后可见项在倒数 3 以内）──
    val isNearBottom by remember {
        derivedStateOf {
            val lastVisible = listState.layoutInfo.visibleItemsInfo.lastOrNull()?.index ?: 0
            val totalItems = listState.layoutInfo.totalItemsCount
            totalItems == 0 || lastVisible >= totalItems - 3
        }
    }

    // ── 是否显示"新消息"悬浮按钮 ──
    // 当用户不在底部且有新消息到达时，显示悬浮按钮
    val showNewMessageButton by remember {
        derivedStateOf {
            val lastVisible = listState.layoutInfo.visibleItemsInfo.lastOrNull()?.index ?: 0
            val totalItems = listState.layoutInfo.totalItemsCount
            totalItems > 3 && lastVisible < totalItems - 3
        }
    }

    // ── 自动滚动：仅当接近底部且有新消息/typing 变化时 ──
    LaunchedEffect(bubbles.size, isTyping) {
        if (bubbles.isNotEmpty() && isNearBottom) {
            val targetIndex = if (isTyping) bubbles.size else bubbles.lastIndex
            listState.animateScrollToItem(targetIndex)
        }
    }

    Box(modifier = modifier) {
        LazyColumn(
            state = listState,
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 4.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
            // 底部留白：为 TypingIndicator 占位预留空间，避免列表跳动
            contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 8.dp),
        ) {
            itemsIndexed(
                items = bubbles,
                key = { _, bubble -> bubble.id },
            ) { index, bubble ->
                // 每个气泡带入场动画：淡入 + 从底部滑入
                val enterAnimation = fadeIn(
                    animationSpec = tween(350, easing = FastOutSlowInEasing),
                ) + slideInVertically(
                    initialOffsetY = { it / 3 },
                    animationSpec = tween(400, easing = FastOutSlowInEasing),
                )

                AnimatedVisibility(
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

            // 思考指示器 — 始终保留固定高度空间，消除出现/消失时的跳动
            item(key = "typing_indicator") {
                // 固定高度容器，无论 typing 状态如何都占据相同空间
                Box(modifier = Modifier.height(TYPING_ROW_HEIGHT)) {
                    AnimatedVisibility(
                        visible = isTyping,
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

        // ── "新消息"悬浮按钮 ──
        AnimatedVisibility(
            visible = showNewMessageButton,
            enter = fadeIn(tween(200)) + slideInVertically(
                initialOffsetY = { it },
                animationSpec = tween(250, easing = FastOutSlowInEasing),
            ),
            exit = androidx.compose.animation.fadeOut(tween(150)) + androidx.compose.animation.slideOutVertically(
                targetOffsetY = { it },
                animationSpec = tween(200),
            ),
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .padding(bottom = 16.dp),
        ) {
            FilledIconButton(
                onClick = {
                    scope.launch {
                        val targetIndex = if (isTyping) bubbles.size else bubbles.lastIndex
                        listState.animateScrollToItem(targetIndex)
                    }
                },
                modifier = Modifier.padding(8.dp),
                shape = CircleShape,
                colors = IconButtonDefaults.filledIconButtonColors(
                    containerColor = MaterialTheme.colorScheme.primary.copy(alpha = 0.85f),
                    contentColor = MaterialTheme.colorScheme.onPrimary,
                ),
            ) {
                Icon(
                    imageVector = Icons.Filled.KeyboardArrowDown,
                    contentDescription = "跳到最新消息",
                    modifier = Modifier.size(20.dp),
                )
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
