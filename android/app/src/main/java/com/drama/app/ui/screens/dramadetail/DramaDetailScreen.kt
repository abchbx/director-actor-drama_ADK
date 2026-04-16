package com.drama.app.ui.screens.dramadetail

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.People
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.runtime.CompositionLocalProvider
import com.drama.app.ui.screens.dramadetail.components.ActorDrawerContent
import com.drama.app.ui.screens.dramadetail.components.CommandInputBar
import com.drama.app.ui.screens.dramadetail.components.SceneBubbleList
import com.drama.app.ui.screens.dramadetail.components.SceneHistorySheet
import com.drama.app.ui.screens.dramadetail.components.TensionIndicator
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DramaDetailScreen(
    dramaId: String,
    viewModel: DramaDetailViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    val drawerState = rememberDrawerState(DrawerValue.Closed)

    // 收集一次性事件
    LaunchedEffect(Unit) {
        viewModel.events.collect { event ->
            when (event) {
                is DramaDetailEvent.ShowSnackbar ->
                    snackbarHostState.showSnackbar(event.message)
            }
        }
    }

    // Open/close drawer when showActorDrawer state changes
    LaunchedEffect(uiState.showActorDrawer) {
        if (uiState.showActorDrawer) {
            drawerState.open()
        } else {
            drawerState.close()
        }
    }

    var showOverflowMenu by remember { mutableStateOf(false) }

    ModalNavigationDrawer(
        drawerState = drawerState,
        drawerContent = {
            // RTL trick for right-side drawer (Pitfall 1)
            CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
                ModalDrawerSheet {
                    CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Ltr) {
                        ActorDrawerContent(
                            actors = uiState.actors,
                            onDismiss = {
                                viewModel.hideActorDrawer()
                                scope.launch { drawerState.close() }
                            },
                        )
                    }
                }
            }
        },
        content = {
            Scaffold(
                topBar = {
                    TopAppBar(
                        title = {
                            Column {
                                if (uiState.viewingHistoryScene != null) {
                                    Text(
                                        "查看第 ${uiState.viewingHistoryScene} 场（历史）",
                                        style = MaterialTheme.typography.titleMedium,
                                    )
                                } else {
                                    Text(uiState.theme, style = MaterialTheme.typography.titleMedium)
                                    Text(
                                        "第 ${uiState.currentScene} 场",
                                        style = MaterialTheme.typography.bodySmall,
                                    )
                                }
                            }
                        },
                        navigationIcon = {
                            if (uiState.viewingHistoryScene != null) {
                                IconButton(onClick = viewModel::returnToCurrentScene) {
                                    Icon(Icons.Filled.ArrowBack, contentDescription = "返回当前场景")
                                }
                            }
                        },
                        actions = {
                            // D-16: 张力指示
                            TensionIndicator(score = uiState.tensionScore)
                            // D-01: 演员面板入口
                            IconButton(onClick = {
                                viewModel.showActorDrawer()
                                scope.launch { drawerState.open() }
                            }) {
                                Icon(Icons.Filled.People, contentDescription = "演员面板")
                            }
                            // D-18: 历史按钮
                            IconButton(onClick = viewModel::showHistorySheet) {
                                Icon(Icons.Filled.History, contentDescription = "场景历史")
                            }
                            // D-23: 保存入口
                            Box {
                                IconButton(onClick = { showOverflowMenu = true }) {
                                    Icon(Icons.Filled.MoreVert, contentDescription = "更多")
                                }
                                DropdownMenu(
                                    expanded = showOverflowMenu,
                                    onDismissRequest = { showOverflowMenu = false },
                                ) {
                                    DropdownMenuItem(
                                        text = { Text("保存") },
                                        onClick = {
                                            viewModel.showSaveDialog()
                                            showOverflowMenu = false
                                        },
                                    )
                                }
                            }
                        },
                    )
                },
                snackbarHost = { SnackbarHost(snackbarHostState) },
                bottomBar = {
                    // D-12: 底部固定命令输入栏
                    CommandInputBar(
                        onCommand = viewModel::sendCommand,
                        isProcessing = uiState.isProcessing,
                    )
                },
            ) { innerPadding ->
                Box(modifier = Modifier.padding(innerPadding)) {
                    if (uiState.bubbles.isEmpty() && !uiState.isTyping) {
                        // 空场景提示
                        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            Text("等待戏剧开始...", style = MaterialTheme.typography.bodyLarge)
                        }
                    } else {
                        SceneBubbleList(
                            bubbles = uiState.bubbles,
                            isTyping = uiState.isTyping,
                            typingText = uiState.typingText,
                        )
                    }

                    // WS 连接状态指示
                    if (!uiState.isWsConnected) {
                        LinearProgressIndicator(modifier = Modifier.fillMaxWidth().align(Alignment.TopCenter))
                    }

                    // STORM 进度
                    uiState.stormPhase?.let { phase ->
                        Surface(
                            modifier = Modifier.align(Alignment.BottomCenter).padding(bottom = 128.dp),
                            color = MaterialTheme.colorScheme.surfaceVariant,
                        ) {
                            Text(phase, modifier = Modifier.padding(16.dp))
                        }
                    }
                }
            }
        },
    )

    // D-18/D-19: 场景历史 BottomSheet
    if (uiState.showHistorySheet) {
        SceneHistorySheet(
            scenes = uiState.historyScenes,
            onSceneClick = viewModel::viewHistoryScene,
            onDismiss = viewModel::hideHistorySheet,
        )
    }

    // D-23: 保存 Dialog
    if (uiState.showSaveDialog) {
        var saveName by remember { mutableStateOf("") }
        AlertDialog(
            title = { Text("保存戏剧") },
            text = {
                OutlinedTextField(
                    value = saveName,
                    onValueChange = { saveName = it },
                    placeholder = { Text("保存名（可选，默认用主题名）") },
                    singleLine = true,
                )
            },
            confirmButton = {
                TextButton(onClick = { viewModel.saveDrama(saveName) }) { Text("保存") }
            },
            dismissButton = {
                TextButton(onClick = viewModel::hideSaveDialog) { Text("取消") }
            },
        )
    }
}
