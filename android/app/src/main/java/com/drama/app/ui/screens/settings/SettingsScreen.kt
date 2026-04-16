package com.drama.app.ui.screens.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.Dialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.drama.app.ui.screens.connection.ConnectionGuideDialog

@Composable
fun SettingsScreen(
    viewModel: SettingsViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    var showConnectionDialog by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text(
            text = "设置",
            style = MaterialTheme.typography.headlineMedium,
        )

        // D-13: 服务器连接 section
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text(
                    text = "服务器连接",
                    style = MaterialTheme.typography.titleMedium,
                )
                Spacer(modifier = Modifier.height(8.dp))

                if (uiState.serverConfig != null) {
                    Text(
                        text = "${uiState.serverConfig!!.ip}:${uiState.serverConfig!!.port}",
                        style = MaterialTheme.typography.bodyLarge,
                    )
                    Text(
                        text = if (uiState.isConnected) "已连接" else "未连接",
                        color = if (uiState.isConnected)
                            MaterialTheme.colorScheme.primary
                        else
                            MaterialTheme.colorScheme.error,
                    )
                } else {
                    Text(
                        text = "未配置服务器",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }

                Spacer(modifier = Modifier.height(8.dp))
                OutlinedButton(
                    onClick = { showConnectionDialog = true },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(if (uiState.serverConfig != null) "修改连接" else "配置连接")
                }
            }
        }
    }

    // 连接配置 Dialog
    if (showConnectionDialog) {
        Dialog(onDismissRequest = { showConnectionDialog = false }) {
            ConnectionGuideDialog(
                onConnected = { showConnectionDialog = false },
            )
        }
    }
}
