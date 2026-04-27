package com.drama.app.ui.screens.dramadetail.components

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.unit.dp

fun getTypingText(toolName: String?): String = when (toolName) {
    // Director 系列工具
    "director_narrate" -> "导演正在构思旁白..."
    "next_scene", "write_scene" -> "剧情推进中..."
    "start_drama" -> "正在初始化剧本..."

    // Actor 系列工具
    "actor_speak" -> "演员正在回复..."
    "actor_speak_batch" -> "多位演员正在回应..."
    "actor_chime_in" -> "角色想要发言..."
    "create_actor" -> "正在创建角色..."

    // ★ Semantic Retriever — 语义记忆检索
    "retrieve_relevant_scenes", "semantic_retriever",
    "backfill_tags", "memory_search", "memory_recall" -> "正在检索人物记忆..."

    // ★ Dynamic STORM — 剧情推演
    "storm_discover_perspectives", "storm_research_perspective",
    "storm_synthesize_outline", "dynamic_storm" -> "正在推演剧情走向..."

    // 用户操作
    "user_action" -> "剧情推进中..."

    // 其他工具
    "save_drama", "load_drama", "export_drama" -> "正在处理存档..."
    "update_emotion" -> "更新角色情绪..."
    "steer_drama" -> "调整剧情方向..."
    "auto_advance" -> "自动推进中..."
    "end_drama" -> "正在落幕..."

    else -> "AI 正在思考..."
}

/**
 * 思考指示器 — 三点脉冲波纹动画
 *
 * 设计特点：
 * - 三个圆点错开 200ms 相位，形成真正的波浪效果
 * - 配合文字说明当前操作类型
 * - 玻璃态背景胶囊容器
 * - 固定高度容器，确保出现/消失时无跳动
 *
 * 关键优化：
 * - 三个 dot 的动画参数相同但初始偏移不同，产生波浪节拍
 * - 容器固定 minHeight，避免 scale 动画引起整体布局跳动
 */
@Composable
fun TypingIndicator(typingText: String = "AI 正在思考...", elapsedSeconds: Int = 0) {
    val infiniteTransition = rememberInfiniteTransition(label = "typing-dots")

    // 三个点错开相位，形成波浪效果
    // dot1: 0ms 偏移，dot2: 200ms 偏移，dot3: 400ms 偏移
    val dot1Scale by infiniteTransition.animateFloat(
        initialValue = 0.4f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(600, delayMillis = 0, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "dot1",
    )
    val dot2Scale by infiniteTransition.animateFloat(
        initialValue = 0.4f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(600, delayMillis = 200, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "dot2",
    )
    val dot3Scale by infiniteTransition.animateFloat(
        initialValue = 0.4f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(600, delayMillis = 400, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "dot3",
    )

    // 格式化耗时文本
    val timerText = if (elapsedSeconds > 0) {
        val min = elapsedSeconds / 60
        val sec = elapsedSeconds % 60
        if (min > 0) "${min}m${sec}s" else "${sec}s"
    } else null

    val displayText = if (timerText != null) "$typingText ($timerText)" else typingText

    // 固定高度行容器，防止 scale 动画导致布局跳动
    Row(
        modifier = Modifier
            .height(TYPING_ROW_HEIGHT)
            .padding(horizontal = 20.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        // 三点波纹容器
        Row(
            modifier = Modifier
                .clip(shape = CircleShape)
                .background(MaterialTheme.colorScheme.surfaceContainerHigh.copy(alpha = 0.6f))
                .padding(horizontal = 10.dp, vertical = 6.dp),
            horizontalArrangement = Arrangement.spacedBy(5.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TypingDot(scale = dot1Scale)
            TypingDot(scale = dot2Scale)
            TypingDot(scale = dot3Scale)
        }

        Spacer(modifier = Modifier.width(10.dp))

        Text(
            text = displayText,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f),
        )
    }
}

/** 单个跳动圆点 — 固定容器大小 + scale 变换，不引起布局重排 */
@Composable
private fun TypingDot(scale: Float) {
    Box(
        modifier = Modifier
            .size(8.dp) // 固定容器尺寸
            .graphicsLayer {
                scaleX = scale
                scaleY = scale
            },
        contentAlignment = Alignment.Center,
    ) {
        Box(
            modifier = Modifier
                .size(6.dp)
                .clip(CircleShape)
                .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.7f)),
        )
    }
}

/** TypingIndicator 行的固定高度，与 SceneBubbleList 的空占位高度对齐 */
internal val TYPING_ROW_HEIGHT = 44.dp
