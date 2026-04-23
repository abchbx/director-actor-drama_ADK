package com.drama.app.ui.screens.dramadetail.components

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.StopCircle
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier

/**
 * 聊天式输入栏 - iMessage 风格极简胶囊设计 (M3).
 *
 * 布局: 命令行(/next /end) 在上 + 输入栏(TextField + Send) 在下.
 * 使用 imePadding() + navigationBarsPadding() 完美贴合键盘.
 * 命令按钮点击立即触发 onCommand, 不依赖输入框文字.
 * 极简胶囊: 24dp 圆角, surfaceContainerLowest 背景, 无边框.
 */
@Composable
fun ChatInputBar(
    actors: List<String>,
    onSend: (text: String, mention: String?) -> Unit,
    onCommand: (command: String) -> Unit,
    isProcessing: Boolean,
    modifier: Modifier = Modifier,
) {
    var inputText by remember { mutableStateOf("") }
    val focusRequester = remember { FocusRequester() }
    val keyboardController = LocalSoftwareKeyboardController.current

    // @提及选择器状态
    val showMentionPicker by remember(inputText) {
        derivedStateOf {
            val lastAt = inputText.lastIndexOf('@')
            if (lastAt < 0) return@derivedStateOf false
            val afterAt = inputText.substring(lastAt + 1)
            afterAt.isNotEmpty() && !afterAt.contains(' ')
        }
    }

    val mentionQuery by remember(inputText) {
        derivedStateOf {
            val lastAt = inputText.lastIndexOf('@')
            if (lastAt < 0) return@derivedStateOf ""
            inputText.substring(lastAt + 1)
        }
    }

    val filteredActors by remember(actors, mentionQuery) {
        derivedStateOf {
            if (mentionQuery.isBlank()) actors
            else actors.filter { it.contains(mentionQuery, ignoreCase = true) }
        }
    }

    Column(
        modifier = modifier
            .fillMaxWidth()
            .imePadding()
            .navigationBarsPadding()
            .padding(horizontal = 12.dp, vertical = 6.dp),
    ) {
        // @提及选择器弹出卡片
        if (showMentionPicker && filteredActors.isNotEmpty()) {
            Surface(
                shape = RoundedCornerShape(16.dp),
                color = MaterialTheme.colorScheme.surfaceContainerHigh.copy(alpha = 0.92f),
                shadowElevation = 8.dp,
                tonalElevation = 4.dp,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 6.dp),
            ) {
                LazyRow(
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 8.dp),
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    items(filteredActors) { actorName ->
                        MentionChip(
                            actorName = actorName,
                            onClick = {
                                val lastAt = inputText.lastIndexOf('@')
                                if (lastAt >= 0) {
                                    inputText = inputText.substring(0, lastAt) + "@$actorName "
                                }
                                focusRequester.requestFocus()
                            },
                        )
                    }
                }
            }
        }

        // ====== 极简胶囊容器 ======
        Surface(
            shape = RoundedCornerShape(24.dp),
            color = MaterialTheme.colorScheme.surfaceContainerLowest,
            shadowElevation = 2.dp,
            tonalElevation = 1.dp,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Column(
                modifier = Modifier.padding(start = 6.dp, end = 4.dp, top = 4.dp, bottom = 4.dp),
            ) {

                // ─── 第一行：命令芯片 (/next /end) ───
                if (!isProcessing && !inputText.isNotBlank()) {
                    Row(
                        horizontalArrangement = Arrangement.Start,
                    ) {
                        SuggestionChip(
                            onClick = {
                                onCommand("/next")
                            },
                            label = { Text("/next", style = MaterialTheme.typography.labelSmall) },
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        SuggestionChip(
                            onClick = {
                                onCommand("/end")
                            },
                            label = { Text("/end", style = MaterialTheme.typography.labelSmall) },
                        )
                    }
                    Spacer(modifier = Modifier.height(4.dp))
                }

                // ─── 第二行：输入框 + 发送按钮 ───
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    // 文本输入区域
                    Box(modifier = Modifier.weight(1f)) {
                        BasicTextField(
                            value = inputText,
                            onValueChange = { inputText = it },
                            enabled = !isProcessing,
                            textStyle = MaterialTheme.typography.bodyMedium.copy(
                                color = MaterialTheme.colorScheme.onSurface,
                            ),
                            singleLine = false,
                            maxLines = 4,
                            minLines = 1,
                            keyboardOptions = KeyboardOptions(
                                imeAction = ImeAction.Send,
                            ),
                            keyboardActions = KeyboardActions(
                                onSend = {
                                    if (inputText.isNotBlank()) {
                                        val mention = parseMention(inputText)
                                        onSend(inputText.trim(), mention)
                                        inputText = ""
                                        keyboardController?.hide()
                                    }
                                },
                            ),
                            cursorBrush = SolidColor(MaterialTheme.colorScheme.primary),
                            decorationBox = { innerTextField ->
                                Box(
                                    contentAlignment = Alignment.CenterStart,
                                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
                                ) {
                                    if (inputText.isEmpty()) {
                                        Text(
                                            "说点什么... (@角色名 私聊)",
                                            style = MaterialTheme.typography.bodyMedium,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.45f),
                                            maxLines = 1,
                                            overflow = TextOverflow.Ellipsis,
                                        )
                                    }
                                    innerTextField()
                                }
                            },
                            modifier = Modifier
                                .focusRequester(focusRequester)
                                .heightIn(max = 96.dp),
                        )
                    }

                    Spacer(modifier = Modifier.width(4.dp))

                    // 发送按钮 — 紧凑圆形
                    SendButton(
                        isProcessing = isProcessing,
                        hasText = inputText.isNotBlank(),
                        onClick = {
                            if (!isProcessing && inputText.isNotBlank()) {
                                val mention = parseMention(inputText)
                                onSend(inputText.trim(), mention)
                                inputText = ""
                            } else if (isProcessing) {
                                // 预留停止逻辑
                            }
                        },
                    )
                }
            }
        }
    }
}

/**
 * 发送/停止按钮 — 紧凑圆形，Primary 强调色
 */
@Composable
private fun SendButton(
    isProcessing: Boolean,
    hasText: Boolean,
    onClick: () -> Unit,
) {
    val infiniteTransition = rememberInfiniteTransition(label = "send-pulse")
    val pulseScale by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 1.12f,
        animationSpec = infiniteRepeatable(
            animation = tween(800, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "pulse",
    )

    Surface(
        shape = CircleShape,
        color = when {
            isProcessing -> MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.5f)
            hasText -> MaterialTheme.colorScheme.primary
            else -> MaterialTheme.colorScheme.surfaceContainerHighest.copy(alpha = 0.4f)
        },
        onClick = onClick,
        modifier = Modifier
            .size(36.dp)
            .then(
                if (!isProcessing && hasText)
                    Modifier.graphicsLayer { scaleX = pulseScale; scaleY = pulseScale }
                else Modifier
            ),
    ) {
        Box(contentAlignment = Alignment.Center, modifier = Modifier.size(36.dp)) {
            Icon(
                imageVector = if (isProcessing) Icons.Filled.StopCircle else Icons.AutoMirrored.Filled.Send,
                contentDescription = if (isProcessing) "处理中" else "发送",
                modifier = Modifier.size(18.dp),
                tint = when {
                    isProcessing -> MaterialTheme.colorScheme.error
                    hasText -> MaterialTheme.colorScheme.onPrimary
                    else -> MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.3f)
                },
            )
        }
    }
}

/** @提及芯片 */
@Composable
private fun MentionChip(
    actorName: String,
    onClick: () -> Unit,
) {
    Surface(
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.75f),
        onClick = onClick,
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Surface(
                shape = CircleShape,
                color = MaterialTheme.colorScheme.primary.copy(alpha = 0.15f),
                modifier = Modifier.size(20.dp),
            ) {
                Box(contentAlignment = Alignment.Center, modifier = Modifier.size(20.dp)) {
                    Text(
                        text = actorName.firstOrNull()?.uppercase() ?: "?",
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
            }
            Spacer(modifier = Modifier.width(6.dp))
            Text(
                text = actorName,
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.Medium,
                color = MaterialTheme.colorScheme.onSecondaryContainer,
            )
        }
    }
}

/** 解析 @提及 */
private fun parseMention(text: String): String? {
    val regex = Regex("@(\\S+)")
    val match = regex.find(text) ?: return null
    return match.groupValues[1]
}
