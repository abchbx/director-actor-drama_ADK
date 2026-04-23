package com.drama.app.ui.screens.dramadetail

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
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
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
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
import androidx.compose.material3.Surface
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
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
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.TheaterComedy
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.runtime.CompositionLocalProvider
import com.drama.app.ui.screens.dramadetail.components.ActorDrawerContent
import com.drama.app.ui.screens.dramadetail.components.ChatInputBar
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
            CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
                ModalDrawerSheet {
                    CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Ltr) {
                        ActorDrawerContent(
                            actors = uiState.actors,
                            isActorLoading = uiState.isActorLoading,
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
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    // 关键修复：同时消费状态栏和导航栏 insets，防止底部空白泄漏
                    .consumeWindowInsets(WindowInsets.statusBars)
                    .consumeWindowInsets(WindowInsets.navigationBars)
                    // ★ 不再手动添加 imeHeightPx padding — ChatInputBar 已有 .imePadding()
                    // 双重 padding 会导致输入法上方出现大片空白
            ) {
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
                        TensionIndicator(score = uiState.tensionScore)
                        IconButton(onClick = {
                            viewModel.showActorDrawer()
                            scope.launch { drawerState.open() }
                        }) {
                            Icon(Icons.Filled.People, contentDescription = "演员面板")
                        }
                        IconButton(onClick = viewModel::showHistorySheet) {
                            Icon(Icons.Filled.History, contentDescription = "场景历史")
                        }
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

                // 中间内容区域 — 填充剩余空间
                Box(modifier = Modifier.weight(1f)) {
                    if (uiState.bubbles.isEmpty() && !uiState.isTyping) {
                        // 空状态：带脉冲动画的引导性容器
                        DramaEmptyState()
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

                // 底部聊天输入栏 — 浮动玻璃态，带平滑的键盘跟随和入场动画
                androidx.compose.animation.AnimatedVisibility(
                    visible = true,
                    enter = slideInVertically(
                        initialOffsetY = { it },
                        animationSpec = tween(450, easing = FastOutSlowInEasing),
                    ) + fadeIn(tween(300)),
                    exit = slideOutVertically(
                        targetOffsetY = { it / 2 },
                        animationSpec = tween(250, easing = LinearOutSlowInEasing),
                    ) + fadeOut(tween(200)),
                ) {
                    ChatInputBar(
                        actors = uiState.actors.map { it.name },
                        onSend = viewModel::sendChatMessage,
                        onCommand = viewModel::sendCommand,
                        isProcessing = uiState.isProcessing,
                    )
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
            onDismissRequest = viewModel::hideSaveDialog,
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

// ============================================================
// DramaEmptyState — 空状态引导容器（带脉冲动画）
// ============================================================

/** 剧本详情页空状态：图标 + 引导文案，带轻微脉冲动画 */
@Composable
private fun DramaEmptyState() {
    // 脉冲动画：透明度 0.45 → 1.0 循环，2s 周期
    val infiniteTransition = rememberInfiniteTransition(label = "empty-pulse")
    val alpha by infiniteTransition.animateFloat(
        initialValue = 0.45f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(2000, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "alpha",
    )

    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            // 图标容器 — 圆形背景 + 脉冲效果
            Surface(
                shape = CircleShape,
                color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.5f),
                modifier = Modifier
                    .size(80.dp)
                    .graphicsLayer { this.alpha = alpha },
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(
                        imageVector = Icons.Filled.TheaterComedy,
                        contentDescription = null,
                        modifier = Modifier.size(36.dp),
                        tint = MaterialTheme.colorScheme.primary.copy(alpha = alpha),
                    )
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            // 主标题
            Text(
                text = "等待戏剧开始...",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Medium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )

            Spacer(modifier = Modifier.height(8.dp))

            // 副标题引导
            Text(
                text = "使用下方命令推进剧情",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f),
                textAlign = TextAlign.Center,
            )
        }
    }
}
