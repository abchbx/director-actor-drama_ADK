package com.drama.app.ui.screens.dramadetail.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp

// Slash commands supported by the input bar
private val SLASH_COMMANDS = listOf(
    SlashCommand("/start", "<主题>", "开始一个新戏剧场景"),
    SlashCommand("/next", "", "推进到下一个情节"),
    SlashCommand("/action", "<描述>", "以主角身份执行动作"),
    SlashCommand("/cast", "", "查看当前演员阵容及状态"),
    SlashCommand("/save", "[名称]", "保存当前场景到本地"),
    SlashCommand("/load", "<名称>", "加载已保存的本地场景"),
    SlashCommand("/list", "", "列出所有本地存档"),
    SlashCommand("/delete", "<名称>", "删除指定的本地存档"),
    SlashCommand("/export", "", "导出当前场景"),
    SlashCommand("/status", "", "查看当前状态"),
    SlashCommand("/quit", "", "退出当前场景"),
)

private data class SlashCommand(
    val command: String,
    val args: String,
    val description: String,
) {
    val display: String get() = if (args.isNotEmpty()) "$command $args" else command
}

@Composable
fun ChatInputBar(
    actors: List<String>,
    onSend: (String, String?) -> Unit,
    onCommand: (String) -> Unit,
    isProcessing: Boolean,
    isTyping: Boolean = false,
    isWsConnected: Boolean = true,
    isReconnecting: Boolean = false,
    modifier: Modifier = Modifier,
) {
    var inputText by rememberSaveable { mutableStateOf("") }
    val focusRequester = remember { FocusRequester() }
    // ★ 强化：isProcessing 或 isTyping 期间均禁用输入，防止扰乱后端推理状态
    val isLocked = isProcessing || isTyping
    val inputEnabled = !isLocked

    // Slash command menu state — independent mutable state, not derived from focus
    var slashMenuExpanded by remember { mutableStateOf(false) }

    // Parse mention if text starts with @actor_name
    val mention = remember(inputText, actors) {
        if (inputText.startsWith("@") && actors.isNotEmpty()) {
            val namePart = inputText.substring(1).takeWhile { it != ' ' }
            actors.find { it == namePart }
        } else null
    }

    // Slash command filtering — only depends on input text
    val filteredCommands = remember(inputText) {
        val trimmed = inputText.trim()
        if (trimmed.startsWith("/") && !trimmed.contains(" ")) {
            SLASH_COMMANDS.filter { it.command.startsWith(trimmed) }
        } else {
            emptyList()
        }
    }

    Column(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 6.dp),
    ) {
        // Actor mention chips — quick @mention buttons
        if (actors.isNotEmpty()) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState())
                    .padding(bottom = 6.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.Start),
            ) {
                actors.forEach { actor ->
                    MentionChip(
                        label = "@$actor",
                        onClick = {
                            inputText = "@$actor "
                            focusRequester.requestFocus()
                        },
                    )
                }
            }
        }

        // Slash command dropdown menu (shown above the input row)
        Box(modifier = Modifier.fillMaxWidth()) {
            // Input row
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(20.dp))
                    .background(MaterialTheme.colorScheme.surfaceContainerLowest)
                    .padding(end = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                OutlinedTextField(
                    value = inputText,
                    onValueChange = { newText ->
                        inputText = newText
                        // Show slash menu when text starts with "/" and has no space (still typing command)
                        // Close menu when text no longer starts with "/" or a space was typed (command complete)
                        val trimmed = newText.trim()
                        slashMenuExpanded = trimmed.startsWith("/") && !trimmed.contains(" ")
                    },
                    modifier = Modifier
                        .weight(1f)
                        .focusRequester(focusRequester)
                        .heightIn(max = 100.dp),
                    placeholder = {
                        Text(
                            when {
                                isLocked -> "AI 正在思考，请稍候..."
                                isReconnecting -> "正在重新连接..."
                                !isWsConnected -> "离线模式 — 消息将通过 REST 发送"
                                else -> "以主角身份发言或输入命令..."
                            },
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.5f),
                        )
                    },
                    maxLines = 3,
                    enabled = inputEnabled,
                    textStyle = MaterialTheme.typography.bodyMedium,
                    shape = RoundedCornerShape(20.dp),
                    colors = androidx.compose.material3.TextFieldDefaults.colors(
                        focusedContainerColor = MaterialTheme.colorScheme.surfaceContainerLowest,
                        unfocusedContainerColor = MaterialTheme.colorScheme.surfaceContainerLowest,
                        focusedIndicatorColor = MaterialTheme.colorScheme.primary.copy(alpha = 0.5f),
                        unfocusedIndicatorColor = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.3f),
                        cursorColor = MaterialTheme.colorScheme.primary,
                        focusedTextColor = MaterialTheme.colorScheme.onSurface,
                        unfocusedTextColor = MaterialTheme.colorScheme.onSurface,
                        focusedLabelColor = MaterialTheme.colorScheme.primary,
                        unfocusedLabelColor = MaterialTheme.colorScheme.onSurfaceVariant,
                    ),
                )
                // Send / Stop button — 推理中显示停止状态，空闲时显示发送
                if (isLocked) {
                    // ★ 停止/等待状态：禁用的按钮 + Close 图标，提示用户正在处理
                    Surface(
                        shape = RoundedCornerShape(14.dp),
                        color = MaterialTheme.colorScheme.errorContainer,
                        modifier = Modifier.size(40.dp),
                    ) {
                        Box(contentAlignment = Alignment.Center, modifier = Modifier.size(36.dp)) {
                            Icon(
                                Icons.Filled.Close,
                                contentDescription = "等待中",
                                modifier = Modifier.size(18.dp),
                                tint = MaterialTheme.colorScheme.onErrorContainer.copy(alpha = 0.7f),
                            )
                        }
                    }
                } else {
                    // 正常发送按钮
                    IconButton(
                        onClick = {
                            if (inputText.isNotBlank()) {
                                val text = inputText.trim()
                                if (text.startsWith("/")) {
                                    onCommand(text)
                                } else {
                                    onSend(text, mention)
                                }
                                inputText = ""
                            }
                        },
                        enabled = inputText.isNotBlank(),
                        modifier = Modifier.size(40.dp),
                    ) {
                        Surface(
                            shape = RoundedCornerShape(14.dp),
                            color = if (inputText.isNotBlank())
                                MaterialTheme.colorScheme.primary
                            else
                                MaterialTheme.colorScheme.surfaceContainerHighest,
                        ) {
                            Box(contentAlignment = Alignment.Center, modifier = Modifier.size(36.dp)) {
                                Icon(
                                    Icons.AutoMirrored.Filled.Send,
                                    contentDescription = "发送",
                                    modifier = Modifier.size(18.dp),
                                    tint = if (inputText.isNotBlank())
                                        MaterialTheme.colorScheme.onPrimary
                                    else
                                        MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.4f),
                                )
                            }
                        }
                    }
                }
            }

            // Slash command dropdown menu
            DropdownMenu(
                expanded = slashMenuExpanded && filteredCommands.isNotEmpty(),
                onDismissRequest = { slashMenuExpanded = false },
                modifier = Modifier
                    .widthIn(min = 220.dp, max = 300.dp)
                    .background(MaterialTheme.colorScheme.surfaceContainerLowest),
            ) {
                filteredCommands.forEach { cmd ->
                    DropdownMenuItem(
                        text = {
                            Column {
                                Text(
                                    text = cmd.display,
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = MaterialTheme.colorScheme.onSurface,
                                )
                                Text(
                                    text = cmd.description,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        },
                        onClick = {
                            inputText = cmd.command + " "
                            slashMenuExpanded = false
                            focusRequester.requestFocus()
                        },
                    )
                }
            }
        }
    }
}

@Composable
private fun MentionChip(
    label: String,
    onClick: () -> Unit,
) {
    Surface(
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.secondaryContainer,
        onClick = onClick,
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSecondaryContainer,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 7.dp),
        )
    }
}
