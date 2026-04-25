package com.drama.app.ui.screens.dramadetail.components

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.unit.dp
import com.drama.app.domain.model.ActorInfo

/**
 * 演员面板 — Apple Style 重构版
 *
 * - 标题紧贴顶部，无多余留白
 * - 加载中显示 Skeleton Screen（骨架屏）
 * - 卡片从底部逐个弹出的交错动画 (Stagger Effect)
 */
@Composable
fun ActorDrawerContent(
    actors: List<ActorInfo>,
    isActorLoading: Boolean = false,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier = modifier.fillMaxSize()) {
        // ── 紧凑标题栏 ──
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 8.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = "演员面板",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = androidx.compose.ui.text.font.FontWeight.SemiBold,
            )
            IconButton(onClick = onDismiss, modifier = Modifier.size(36.dp)) {
                Icon(Icons.Filled.Close, contentDescription = "关闭", modifier = Modifier.size(20.dp))
            }
        }

        // ── 内容区域 ──
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 12.dp),
        ) {
            when {
                isActorLoading && actors.isEmpty() -> {
                    // 骨架屏 (Skeleton Screen)
                    LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        items(5) { _ ->
                            ActorCardSkeleton()
                        }
                    }
                }
                actors.isEmpty() && !isActorLoading -> {
                    // 空状态
                    Column(
                        modifier = Modifier.fillMaxSize(),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center,
                    ) {
                        Text(
                            text = "暂无演员，输入 /cast 加载",
                            style = MaterialTheme.typography.bodyLarge,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = "演员将在戏剧启动后出现",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f),
                        )
                    }
                }
                else -> {
                    // 演员列表 — 带交错入场动画
                    ActorListWithStagger(actors = actors)
                }
            }
        }
    }
}

/**
 * 演员列表 — 交错入场动画 (Stagger Animation)
 *
 * 每张卡片延迟 index * 60ms 入场，配合 spring 弹性曲线
 */
@Composable
private fun ActorListWithStagger(actors: List<ActorInfo>) {
    LazyColumn(
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        itemsIndexed(actors, key = { _, actor -> actor.name }) { index, actor ->
            StaggerItem(index = index) {
                ActorCard(actor = actor, onClick = {})
            }
        }
    }
}

/**
 * 单项交错动画包装器
 */
@Composable
private fun StaggerItem(
    index: Int,
    content: @Composable () -> Unit,
) {
    val transition = androidx.compose.animation.core.updateTransition(
        targetState = true,
        label = "stagger_$index",
    )

    val animAlpha by transition.animateFloat(
        transitionSpec = {
            tween(
                durationMillis = 350,
                delayMillis = index * 60,
                easing = FastOutSlowInEasing,
            )
        },
        label = "alpha",
    ) { visible -> if (visible) 1f else 0f }

    val animOffsetY by transition.animateFloat(
        transitionSpec = {
            spring(
                dampingRatio = Spring.DampingRatioMediumBouncy,
                stiffness = Spring.StiffnessLow,
            )
        },
        label = "offsetY",
    ) { visible -> if (visible) 0f else 40f }

    val animScale by transition.animateFloat(
        transitionSpec = {
            spring(
                dampingRatio = Spring.DampingRatioMediumBouncy,
                stiffness = Spring.StiffnessMediumLow,
            )
        },
        label = "scale",
    ) { visible -> if (visible) 1f else 0.9f }

    Box(
        modifier = Modifier
            .offset(y = animOffsetY.dp)
            .scale(animScale)
            .alpha(animAlpha),
    ) {
        content()
    }
}

/**
 * 骨架屏单条 (Skeleton Card)
 * 模拟真实卡片的布局结构，使用 shimmer 动画效果
 */
@Composable
private fun ActorCardSkeleton() {
    val infiniteTransition = rememberInfiniteTransition(label = "shimmer")

    val shimmerAlpha by infiniteTransition.animateFloat(
        initialValue = 0.3f,
        targetValue = 0.7f,
        animationSpec = infiniteRepeatable(
            animation = tween(800, easing = LinearOutSlowInEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "shimmer_alpha",
    )

    val shimmerColor = MaterialTheme.colorScheme.surfaceContainerHighest.copy(alpha = shimmerAlpha)

    Surface(
        shape = RoundedCornerShape(20.dp),
        color = MaterialTheme.colorScheme.surface.copy(alpha = 0.4f),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            // 头像骨架
            Box(
                modifier = Modifier
                    .size(48.dp)
                    .clip(CircleShape)
                    .background(shimmerColor),
            )

            Spacer(modifier = Modifier.width(12.dp))

            Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(7.dp)) {
                // 名称骨架
                Box(
                    modifier = Modifier
                        .height(18.dp)
                        .fillMaxWidth(0.45f)
                        .clip(RoundedCornerShape(4.dp))
                        .background(shimmerColor),
                )
                // 角色骨架
                Box(
                    modifier = Modifier
                        .height(13.dp)
                        .fillMaxWidth(0.65f)
                        .clip(RoundedCornerShape(4.dp))
                        .background(shimmerColor),
                )
                // 标签行骨架
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Box(
                        modifier = Modifier
                            .height(18.dp)
                            .width(60.dp)
                            .clip(RoundedCornerShape(6.dp))
                            .background(shimmerColor),
                    )
                    Box(
                        modifier = Modifier
                            .height(18.dp)
                            .width(44.dp)
                            .clip(RoundedCornerShape(6.dp))
                            .background(shimmerColor),
                    )
                }
            }
        }
    }
}
