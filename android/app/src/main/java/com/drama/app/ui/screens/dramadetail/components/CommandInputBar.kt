package com.drama.app.ui.screens.dramadetail.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.text.FocusRequester
import androidx.compose.foundation.text.focusRequester
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun CommandInputBar(
    onCommand: (String) -> Unit,
    isProcessing: Boolean,
    modifier: Modifier = Modifier,
) {
    var inputText by remember { mutableStateOf("") }
    val focusRequester = remember { FocusRequester() }

    Column(
        modifier = modifier.imePadding(),  // Pitfall 5: 软键盘适配
    ) {
        // D-12/D-13: 快捷芯片行
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 4.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            SuggestionChip(
                onClick = { onCommand("/next") },  // D-13: 直接发送
                label = { Text("/next") },
            )
            SuggestionChip(
                onClick = {
                    inputText = "/action "  // D-13: 填入前缀 + 空格
                    focusRequester.requestFocus()
                },
                label = { Text("/action") },
            )
            SuggestionChip(
                onClick = {
                    inputText = "/speak "
                    focusRequester.requestFocus()
                },
                label = { Text("/speak") },
            )
            SuggestionChip(
                onClick = { onCommand("/end") },  // D-13: 直接发送
                label = { Text("/end") },
            )
        }

        // 输入行
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedTextField(
                value = inputText,
                onValueChange = { inputText = it },
                modifier = Modifier
                    .weight(1f)
                    .focusRequester(focusRequester),
                placeholder = { Text("输入命令或描述...") },
                maxLines = 3,
                enabled = !isProcessing,
            )
            IconButton(
                onClick = {
                    if (inputText.isNotBlank()) {
                        onCommand(inputText)
                        inputText = ""
                    }
                },
                enabled = !isProcessing && inputText.isNotBlank(),
            ) {
                Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "发送")
            }
        }
    }
}
