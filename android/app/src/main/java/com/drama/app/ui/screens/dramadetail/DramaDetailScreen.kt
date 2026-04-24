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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.wrapContentHeight
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
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
import androidx.compose.runtime.saveable.rememberSaveable
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
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.CloudOff
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
    skipLoad: Boolean = false,
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
            // === 初始化同步中的全屏加载 ===
            if (uiState.initialSyncing) {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center,
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        CircularProgressIndicator()
                        Spacer(modifier = Modifier.height(16.dp))
                        Text(
                            "正在同步剧本数据...",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            } else if (uiState.initError != null) {
                // === 初始化失败：错误 + 重试按钮 ===
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center,
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(
                            imageVector = Icons.Filled.TheaterComedy,
                            contentDescription = null,
                            modifier = Modifier.size(64.dp),
                            tint = MaterialTheme.colorScheme.error.copy(alpha = 0.6f),
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        Text(
                            uiState.initError!!,
                            style = MaterialTheme.typography.bodyLarge,
                            color = MaterialTheme.colorScheme.error,
                            textAlign = TextAlign.Center,
                            modifier = Modifier.padding(horizontal = 32.dp),
                        )
                        Spacer(modifier = Modifier.height(24.dp))
                        Button(onClick = viewModel::retryInit) {
                            Icon(
                                Icons.Filled.Refresh,
                                contentDescription = null,
                                modifier = Modifier.size(18.dp),
                            )
                            Spacer(modifier = Modifier.size(8.dp))
                            Text("重试")
                        }
                    }
                }
            } else {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    // 仅消费状态栏 insets，防止 TopAppBar 被遮挡
                    // 导航栏 insets 不在这里消费，避免 imePadding() 计算时被扣除
                    .consumeWindowInsets(WindowInsets.statusBars)
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

                // 离线断连横幅
                // ★ 修复：初始同步期间不显示横幅（WS 可能还在复用连接的过渡期）
                // 只在真正降级到 REST 模式（未连接且未在重连且初始化已完成）时显示横幅
                ConnectionBanner(
                    isConnected = uiState.isWsConnected,
                    isReconnecting = uiState.isReconnecting,
                    isInitialSyncing = uiState.initialSyncing,
                )

                // 中间内容区域 — 填充剩余空间
                Box(modifier = Modifier.weight(1f)) {
                    when {
                        uiState.outlineSummary.isNotBlank() && uiState.currentScene == 0 && uiState.bubbles.isEmpty() -> {
                            OutlineConfirmPanel(
                                outline = uiState.outlineSummary,
                                onConfirm = { viewModel.sendCommand("/action 开始") },
                            )
                        }
                        uiState.bubbles.isEmpty() && !uiState.isTyping -> {
                            // 空状态：带脉冲动画的引导性容器
                            DramaEmptyState()
                        }
                        else -> {
                            SceneBubbleList(
                                bubbles = uiState.bubbles,
                                isTyping = uiState.isTyping,
                                typingText = uiState.typingText,
                            )
                        }
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
                // ★ imePadding() 必须应用在 AnimatedVisibility 外侧，避免动画容器阻断 insets 传递
                androidx.compose.animation.AnimatedVisibility(
                    visible = true,
                    modifier = Modifier.imePadding(),
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
                        isWsConnected = uiState.isWsConnected,
                        isReconnecting = uiState.isReconnecting,
                    )
                }
            }
            } // end else (not initialSyncing, not initError)
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
        var saveName by rememberSaveable { mutableStateOf("") }
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
// OutlineConfirmPanel — 大纲确认面板（第0场时展示）
// ============================================================

@Composable
private fun OutlineConfirmPanel(
    outline: String,
    onConfirm: () -> Unit,
) {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 16.dp, vertical = 24.dp),
        contentAlignment = Alignment.Center,
    ) {
        Surface(
            shape = RoundedCornerShape(16.dp),
            color = MaterialTheme.colorScheme.surfaceContainerHigh,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Column(
                modifier = Modifier.padding(20.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text(
                    text = "剧本大纲",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold,
                )
                Spacer(modifier = Modifier.height(12.dp))
                Text(
                    text = outline,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(max = 360.dp)
                        .verticalScroll(androidx.compose.foundation.rememberScrollState()),
                )
                Spacer(modifier = Modifier.height(20.dp))
                Button(
                    onClick = onConfirm,
                    shape = RoundedCornerShape(12.dp),
                    modifier = Modifier.fillMaxWidth(0.7f),
                ) {
                    Text("确认方向，开始创作")
                }
            }
        }
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

// ============================================================
// ConnectionBanner — 离线断连横幅
// ============================================================

/** 断连横幅：在 TopAppBar 下方显示"连接已断开，正在尝试重连..." */
@Composable
private fun ConnectionBanner(
    isConnected: Boolean,
    isReconnecting: Boolean = false,
    isInitialSyncing: Boolean = false,
) {
    // ★ 修复：初始同步期间不显示横幅（避免 WS 复用过渡期的闪烁）
    // 只在真正降级到 REST 模式（未连接且未在重连且初始化已完成）时显示
    AnimatedVisibility(
        visible = !isConnected && !isReconnecting && !isInitialSyncing,
        enter = slideInVertically(initialOffsetY = { -it }) + fadeIn(tween(200)),
        exit = slideOutVertically(targetOffsetY = { -it }) + fadeOut(tween(200)),
    ) {
        Surface(
            color = MaterialTheme.colorScheme.errorContainer,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .wrapContentHeight()
                    .padding(horizontal = 16.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.Center,
            ) {
                Icon(
                    imageVector = Icons.Filled.CloudOff,
                    contentDescription = null,
                    modifier = Modifier.size(16.dp),
                    tint = MaterialTheme.colorScheme.onErrorContainer,
                )
                Spacer(modifier = Modifier.size(8.dp))
                Text(
                    text = "WebSocket 连接失败，已降级到 REST 轮询模式",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onErrorContainer,
                )
            }
        }
    }
}
