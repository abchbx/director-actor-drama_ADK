package com.drama.app.ui.screens.dramadetail.components

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
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
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Explore
import androidx.compose.material.icons.filled.Error
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.unit.dp
import com.drama.app.domain.model.SceneBubble
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/** ★ 剧情引导反馈颜色 */
private val PlotGuidanceColor = Color(0xFF6A5ACD)  // 紫色系，与导演头像同色系

/**
 * 场景气泡列表 — 带入场动画的对话流
 *
 * 优化特性：
 * - reverseLayout = true：最新消息始终在底部，无需手动滚动
 * - 数据反序 + reverseLayout：新消息自然追加到底部
 * - LazyColumn key = { it.id }，确保高效 diff & 稳定 recomposition
 * - "新消息提示"悬浮按钮：向上滚动后一键跳回最新消息
 * - TypingIndicator 固定高度占位，消除出现/消失时的跳动
 * - 每个气泡带淡入 + 位移动画
 * - ★ 剧情引导反馈动画
 */
@Composable
fun SceneBubbleList(
    bubbles: List<SceneBubble>,
    isTyping: Boolean,
    typingText: String = "AI 正在思考...",
    typingElapsedSeconds: Int = 0,
    modifier: Modifier = Modifier,
) {
    val listState = rememberLazyListState()
    val scope = rememberCoroutineScope()

    // reverseLayout + reversed data: index 0 = newest message, at the bottom of screen
    val reversedBubbles = remember(bubbles) { bubbles.reversed() }

    // ── 是否接近底部（最新消息区域）──
    val isNearBottom by remember {
        derivedStateOf {
            val firstVisible = listState.layoutInfo.visibleItemsInfo.firstOrNull()?.index ?: 0
            firstVisible <= 3
        }
    }

    // ── 是否显示"新消息"悬浮按钮 ──
    val showNewMessageButton by remember {
        derivedStateOf {
            val firstVisible = listState.layoutInfo.visibleItemsInfo.firstOrNull()?.index ?: 0
            firstVisible > 3
        }
    }

    // ── 自动滚动：仅当接近底部且有新消息到达时 ──
    LaunchedEffect(bubbles.size, isTyping) {
        if (bubbles.isNotEmpty() && isNearBottom) {
            listState.animateScrollToItem(0)
        }
    }

    Box(modifier = modifier) {
        LazyColumn(
            state = listState,
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 4.dp),
            reverseLayout = true,
            verticalArrangement = Arrangement.spacedBy(4.dp),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(top = 8.dp, bottom = 8.dp),
        ) {
            // 思考指示器 — 在 reverseLayout 中作为第一个 item，显示在最底部
            item(key = "typing_indicator") {
                Box(modifier = Modifier.height(TYPING_ROW_HEIGHT)) {
                    AnimatedVisibility(
                        visible = isTyping,
                        enter = fadeIn(tween(300)) + slideInVertically(
                            initialOffsetY = { it / 4 },
                            animationSpec = tween(350, easing = LinearOutSlowInEasing),
                        ),
                    ) {
                        TypingIndicator(typingText = typingText, elapsedSeconds = typingElapsedSeconds)
                    }
                }
            }

            // 消息列表（反序：newest first，配合 reverseLayout 最新消息在底部）
            items(
                items = reversedBubbles,
                key = { bubble -> bubble.id },
            ) { bubble ->
                // ★ 修复：LazyColumn 回收复用 item 时，AnimatedVisibility(visible=true) 会重新播放 enter 动画，
                // 导致上下滑动时已有消息重复播放入场动画（看起来像流式输出）。
                // 改用 remember 跟踪该 id 是否已播放过动画，只播放一次。
                val hasAnimated = remember(bubble.id) { mutableSetOf<String>() }
                val shouldAnimate = !hasAnimated.contains(bubble.id).also {
                    hasAnimated.add(bubble.id)
                }

                if (shouldAnimate) {
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
                        BubbleContent(bubble = bubble)
                    }
                } else {
                    BubbleContent(bubble = bubble)
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
            exit = fadeOut(tween(150)) + slideOutVertically(
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
                        listState.animateScrollToItem(0)
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

/**
 * 系统错误气泡 — 左对齐，红色 Card 样式
 */
@Composable
private fun SystemErrorBubble(bubble: SceneBubble.SystemError) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.errorContainer,
            contentColor = MaterialTheme.colorScheme.onErrorContainer,
        ),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 10.dp),
            verticalAlignment = Alignment.Top,
        ) {
            Icon(
                imageVector = Icons.Filled.Error,
                contentDescription = null,
                modifier = Modifier.size(16.dp),
                tint = MaterialTheme.colorScheme.error,
            )
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = bubble.text,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.error,
            )
        }
    }
}

/**
 * 统一气泡内容渲染 — 提取自 items 块，供动画和非动画路径复用
 */
@Composable
private fun BubbleContent(bubble: SceneBubble) {
    when (bubble) {
        is SceneBubble.Narration -> NarrationBubble(bubble)
        is SceneBubble.Dialogue -> DialogueBubble(bubble)
        // ★ 交互语义区分：动作行为→居中斜体无气泡，直接对话→右侧聊天气泡
        is SceneBubble.UserMessage -> {
            if (bubble.isAction) UserActionBubble(bubble)
            else UserMessageBubble(bubble)
        }
        is SceneBubble.ActorInteraction -> ActorInteractionBubble(bubble)
        is SceneBubble.SceneDivider -> SceneDivider(bubble)
        is SceneBubble.SystemError -> SystemErrorBubble(bubble)
        is SceneBubble.PlotGuidance -> PlotGuidanceBubble(bubble)
    }
}

/**
 * ★ 剧情引导反馈气泡 — 短暂动画确认导演已接收到剧情变动
 *
 * 设计要点：
 * - 居中显示，半透明紫色渐变背景
 * - 探索图标 + 脉冲动画
 * - 3秒后自动淡出
 */
@Composable
private fun PlotGuidanceBubble(bubble: SceneBubble.PlotGuidance) {
    // ★ 脉冲动画：图标呼吸效果
    val infiniteTransition = rememberInfiniteTransition(label = "plot_guidance_pulse")
    val pulseAlpha by infiniteTransition.animateFloat(
        initialValue = 0.6f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(800, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "pulse_alpha",
    )

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 24.dp, vertical = 4.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Surface(
            shape = RoundedCornerShape(20.dp),
            color = PlotGuidanceColor.copy(alpha = 0.08f),
            modifier = Modifier.fillMaxWidth(),
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.Center,
            ) {
                // ★ 脉冲探索图标
                Icon(
                    imageVector = Icons.Filled.Explore,
                    contentDescription = null,
                    modifier = Modifier
                        .size(18.dp)
                        .graphicsLayer { alpha = pulseAlpha },
                    tint = PlotGuidanceColor.copy(alpha = 0.8f),
                )

                Spacer(modifier = Modifier.width(8.dp))

                Text(
                    text = bubble.text,
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.Medium,
                    fontStyle = FontStyle.Italic,
                    color = PlotGuidanceColor.copy(alpha = 0.75f),
                )
            }
        }
    }
}
