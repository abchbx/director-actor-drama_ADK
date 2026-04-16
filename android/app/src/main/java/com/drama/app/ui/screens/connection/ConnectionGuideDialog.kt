package com.drama.app.ui.screens.connection

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Snackbar
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.drama.app.domain.model.ConnectionStatus

@Composable
fun ConnectionGuideDialog(
    onConnected: () -> Unit,
    viewModel: ConnectionViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val savedConfig by viewModel.savedServerConfig.collectAsStateWithLifecycle()

    // D-04: 下次启动自动填充上次连接
    LaunchedEffect(savedConfig) {
        if (savedConfig != null && uiState.ip.isEmpty()) {
            viewModel.updateIp(savedConfig!!.ip)
            viewModel.updatePort(savedConfig!!.port)
        }
    }

    // 连接成功后回调
    LaunchedEffect(uiState.status) {
        if (uiState.status is ConnectionStatus.Connected) {
            onConnected()
        }
    }

    // D-14: 全屏 Dialog
    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(32.dp),
        contentAlignment = Alignment.Center,
    ) {
        Card(
            modifier = Modifier.fillMaxWidth(),
        ) {
            Column(
                modifier = Modifier.padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                Text(
                    text = "连接 Drama 服务器",
                    style = MaterialTheme.typography.headlineMedium,
                )

                Text(
                    text = "输入后端服务器的 IP 地址和端口",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )

                // D-01: IP 输入
                OutlinedTextField(
                    value = uiState.ip,
                    onValueChange = viewModel::updateIp,
                    label = { Text("IP 地址") },
                    placeholder = { Text(savedConfig?.ip ?: "192.168.1.100") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    enabled = uiState.status !is ConnectionStatus.Connecting,
                )

                // D-01: Port 输入
                OutlinedTextField(
                    value = uiState.port,
                    onValueChange = viewModel::updatePort,
                    label = { Text("端口") },
                    placeholder = { Text(savedConfig?.port ?: "8000") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    modifier = Modifier.fillMaxWidth(),
                    enabled = uiState.status !is ConnectionStatus.Connecting,
                )

                // D-02: Token 输入（需要时弹出）
                if (uiState.showTokenInput) {
                    OutlinedTextField(
                        value = uiState.token,
                        onValueChange = viewModel::updateToken,
                        label = { Text("API Token") },
                        placeholder = { Text("输入服务器 Token") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Button(
                        onClick = viewModel::submitToken,
                        modifier = Modifier.fillMaxWidth(),
                        enabled = uiState.token.isNotBlank(),
                    ) {
                        Text("确认连接")
                    }
                } else {
                    // 连接按钮
                    Button(
                        onClick = viewModel::connect,
                        modifier = Modifier.fillMaxWidth(),
                        enabled = uiState.ip.isNotBlank() && uiState.port.isNotBlank() &&
                            uiState.status !is ConnectionStatus.Connecting,
                    ) {
                        if (uiState.status is ConnectionStatus.Connecting) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(20.dp),
                                color = MaterialTheme.colorScheme.onPrimary,
                                strokeWidth = 2.dp,
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                        }
                        Text(if (uiState.status is ConnectionStatus.Connecting) "连接中..." else "连接")
                    }
                }

                // D-03: 错误反馈
                if (uiState.status is ConnectionStatus.Error) {
                    val error = uiState.status as ConnectionStatus.Error
                    Snackbar(
                        action = {
                            TextButton(onClick = viewModel::clearError) {
                                Text("重试")
                            }
                        },
                        modifier = Modifier.padding(8.dp),
                    ) {
                        Text(error.message)
                    }
                }
            }
        }
    }
}
