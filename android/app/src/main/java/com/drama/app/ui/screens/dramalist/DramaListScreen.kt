package com.drama.app.ui.screens.dramalist

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.spring
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.foundation.background
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.DoneAll
import androidx.compose.material.icons.filled.EditNote
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.SelectAll
import androidx.compose.material.icons.filled.TheaterComedy
import androidx.compose.material.icons.outlined.History
import androidx.compose.material.icons.outlined.PlayArrow
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.nestedscroll.NestedScrollConnection
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Popup
import androidx.compose.ui.window.PopupProperties
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.drama.app.domain.model.Drama

// ============================================================
// Main Screen
// ============================================================

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun DramaListScreen(
    onDramaClick: (String) -> Unit = {},
    viewModel: DramaListViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(Unit) {
        viewModel.events.collect { event ->
            when (event) {
                is DramaListEvent.ShowSnackbar -> snackbarHostState.showSnackbar(event.message)
            }
        }
    }
    // 退出选择模式时清理焦点
    if (!uiState.isSelectionMode) {
        DisposableEffect(Unit) {
            onDispose {}
        }
    }

    // 搜索框 focus requester（用于管理按钮点击时聚焦）
    val searchFocusRequester = remember { FocusRequester() }
    val focusManager = LocalFocusManager.current

    // Lazy list state 用于检测滚动位置，控制吸顶栏背景透明度
    val listState = rememberLazyListState()
    val isScrolled by remember {
        derivedStateOf { listState.firstVisibleItemIndex > 0 || listState.firstVisibleItemScrollOffset > 0 }
    }

    // 过滤后的数据
    val filteredDramas by remember(uiState.dramas, uiState.searchQuery, uiState.selectedStatusFilter) {
        derivedStateOf { viewModel.getFilteredDramas(uiState) }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) }
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding),
        ) {
            Column(modifier = Modifier.fillMaxSize()) {
                // === 1. 吸顶搜索栏区域 ===
                SearchHeader(
                    searchQuery = uiState.searchQuery,
                    onValueChange = viewModel::onSearchQueryChanged,
                    isScrolled = isScrolled,
                    modifier = Modifier.fillMaxWidth(),
                )

                // === 2. 状态筛选 Chips（含管理按钮） ===
                StatusFilterChips(
                    filters = viewModel.statusFilters,
                    selectedFilter = uiState.selectedStatusFilter,
                    onFilterChanged = viewModel::onStatusFilterChanged,
                    showManageButton = !uiState.isSelectionMode,
                    onManageClick = { viewModel.enterSelectionMode() },
                    modifier = Modifier.fillMaxWidth(),
                )

                if (filteredDramas.isNotEmpty()) {
                    HorizontalDivider(
                        color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.3f),
                        thickness = 0.5.dp,
                    )
                }

                // === 3. 剧本列表或空状态 ===
                when {
                    uiState.isLoading && filteredDramas.isEmpty() -> {
                        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            CircularProgressIndicator()
                        }
                    }

                    filteredDramas.isEmpty() && !uiState.isLoading -> {
                        EmptyState(
                            hasSearchOrFilter = uiState.searchQuery.isNotBlank() ||
                                uiState.selectedStatusFilter != null,
                            searchQuery = uiState.searchQuery,
                            totalDramas = uiState.dramas.size,
                        )
                    }

                    else -> {
                        LazyColumn(
                            state = listState,
                            modifier = Modifier
                                .fillMaxSize()
                                .weight(1f),
                            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            itemsIndexed(
                                items = filteredDramas,
                                key = { _, drama -> drama.folder },
                            ) { _, drama ->
                                DramaCard(
                                    drama = drama,
                                    isSelectionMode = uiState.isSelectionMode,
                                    isSelected = uiState.selectedFolders.contains(drama.folder),
                                    onToggleSelect = { viewModel.toggleSelection(drama.folder) },
                                    onDramaClick = onDramaClick,
                                    onLoadDrama = { viewModel.loadDrama(drama.theme) },
                                    onDeleteDrama = { viewModel.deleteDrama(drama.folder) },
                                )
                            }
                        }
                    }
                }
            }

            // === 错误提示 ===
            if (uiState.error != null) {
                Text(
                    text = uiState.error!!,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.align(Alignment.BottomCenter).padding(16.dp),
                )
            }

            // === 浮动批量操作条 ===
            var showBatchDeleteDialog by remember { mutableStateOf(false) }
            BatchActionBar(
                isVisible = uiState.isSelectionMode,
                selectedCount = uiState.selectedFolders.size,
                totalCount = filteredDramas.size,
                onSelectAll = {
                    if (uiState.selectedFolders.size == filteredDramas.size &&
                        uiState.selectedFolders.containsAll(filteredDramas.map { it.folder })
                    ) {
                        viewModel.clearSelection()
                    } else {
                        viewModel.selectAll(filteredDramas.map { it.folder })
                    }
                },
                onDelete = { showBatchDeleteDialog = true },
                onUpdateStatus = { status ->
                    viewModel.batchUpdateStatus(uiState.selectedFolders, status)
                },
                onCancel = { viewModel.exitSelectionMode() },
                modifier = Modifier.align(Alignment.BottomCenter),
            )

            // 批量删除确认对话框
            if (showBatchDeleteDialog) {
                AlertDialog(
                    onDismissRequest = { showBatchDeleteDialog = false },
                    title = { Text("批量删除？") },
                    text = { Text("确定要删除选中的 ${uiState.selectedFolders.size} 个剧本？此操作无法撤销。") },
                    confirmButton = {
                        TextButton(onClick = {
                            viewModel.batchDelete(uiState.selectedFolders)
                            showBatchDeleteDialog = false
                        }) { Text("删除") }
                    },
                    dismissButton = {
                        TextButton(onClick = { showBatchDeleteDialog = false }) { Text("取消") }
                    },
                )
            }
        }
    }
}

// ============================================================
// Components
// ============================================================

/** 吸顶搜索栏 — 带动态背景透明度 */
@Composable
private fun SearchHeader(
    searchQuery: String,
    onValueChange: (String) -> Unit,
    isScrolled: Boolean,
    modifier: Modifier = Modifier,
) {
    val containerColor by animateColorAsState(
        targetValue = if (isScrolled)
            MaterialTheme.colorScheme.surface
        else
            Color.Transparent,
        animationSpec = spring(stiffness = Spring.StiffnessMediumLow),
        label = "searchBgColor",
    )

    val elevationColor by animateColorAsState(
        targetValue = if (isScrolled)
            Color.Black.copy(alpha = 0.06f)
        else
            Color.Transparent,
        animationSpec = spring(stiffness = Spring.StiffnessMediumLow),
        label = "elevationColor",
    )

    Column(
        modifier = modifier.background(containerColor).padding(start = 16.dp, end = 16.dp, top = 12.dp),
    ) {
        OutlinedTextField(
            value = searchQuery,
            onValueChange = onValueChange,
            placeholder = { Text("搜索剧本...") },
            leadingIcon = {
                Icon(Icons.Filled.TheaterComedy, "搜索", tint = MaterialTheme.colorScheme.onSurfaceVariant)
            },
            singleLine = true,
            shape = RoundedCornerShape(24.dp),
            colors = TextFieldDefaults.colors(
                focusedContainerColor = MaterialTheme.colorScheme.surfaceContainerHighest.copy(alpha = 0.6f),
                unfocusedContainerColor = MaterialTheme.colorScheme.surfaceContainerHighest.copy(alpha = 0.5f),
            ),
            modifier = Modifier.fillMaxWidth().height(48.dp),
        )
        Spacer(modifier = Modifier.height(10.dp))
        if (isScrolled) {
            HorizontalDivider(color = elevationColor)
        }
    }
}

/** 状态筛选 Chips — Apple 风格横向滚动，右侧内嵌管理按钮 */
@Composable
private fun StatusFilterChips(
    filters: List<Pair<String, String?>>,
    selectedFilter: String?,
    onFilterChanged: (String?) -> Unit,
    showManageButton: Boolean = false,
    onManageClick: () -> Unit = {},
    modifier: Modifier = Modifier,
) {
    val scrollState = rememberScrollState()

    Row(
        modifier = modifier.padding(vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Row(
            modifier = Modifier
                .weight(1f)
                .horizontalScroll(scrollState),
            horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.Start),
        ) {
            Spacer(modifier = Modifier.width(4.dp))
            filters.forEach { (label, value) ->
                FilterChip(
                    selected = selectedFilter == value,
                    onClick = { onFilterChanged(value) },
                    label = {
                        Text(
                            text = label,
                            style = MaterialTheme.typography.labelLarge,
                            fontWeight = if (selectedFilter == value) FontWeight.SemiBold else FontWeight.Normal,
                        )
                    },
                    leadingIcon = null,
                    shape = RoundedCornerShape(20.dp),
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = MaterialTheme.colorScheme.secondaryContainer,
                        selectedLabelColor = MaterialTheme.colorScheme.onSecondaryContainer,
                        selectedLeadingIconColor = MaterialTheme.colorScheme.onSecondaryContainer,
                    ),
                )
            }
            Spacer(modifier = Modifier.width(4.dp))
        }

        AnimatedVisibility(
            visible = showManageButton,
            enter = fadeIn(),
            exit = fadeOut(),
        ) {
            Surface(
                shape = RoundedCornerShape(20.dp),
                color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.7f),
                onClick = onManageClick,
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        text = "管理",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onPrimaryContainer,
                    )
                    Spacer(modifier = Modifier.width(3.dp))
                    Icon(
                        imageVector = Icons.Filled.SelectAll,
                        contentDescription = "进入管理模式",
                        modifier = Modifier.size(15.dp),
                        tint = MaterialTheme.colorScheme.onPrimaryContainer,
                    )
                }
            }
        }
    }
}

/** 空状态展示 */
@Composable
private fun EmptyState(hasSearchOrFilter: Boolean, searchQuery: String, totalDramas: Int) {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Icon(
                imageVector = Icons.Filled.TheaterComedy,
                contentDescription = null,
                modifier = Modifier.size(80.dp),
                tint = MaterialTheme.colorScheme.primary.copy(alpha = 0.35f),
            )
            Spacer(modifier = Modifier.height(16.dp))

            if (hasSearchOrFilter) {
                Text(
                    text = if (searchQuery.isNotBlank()) "\"$searchQuery\" 未找到结果" else "无匹配的剧本",
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                )
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "试试其他关键词或清除筛选条件",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.7f),
                )
            } else {
                Text(
                    text = "还没有剧本",
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                )
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "点击 + 开始创作你的第一个戏剧",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.7f),
                )
            }
        }
    }
}

/** 浮动批量操作条 */
@Composable
private fun BatchActionBar(
    isVisible: Boolean,
    selectedCount: Int,
    totalCount: Int,
    onSelectAll: () -> Unit,
    onDelete: () -> Unit,
    onUpdateStatus: (String) -> Unit,
    onCancel: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var showStatusMenu by remember { mutableStateOf(false) }
    var showDeleteConfirm by remember { mutableStateOf(false) }

    AnimatedVisibility(
        visible = isVisible,
        enter = slideInHorizontally(initialOffsetX = { it / 2 }),
        exit = fadeOut(),
        modifier = modifier.padding(bottom = 8.dp),
    ) {
        Surface(
            shape = RoundedCornerShape(24.dp),
            color = MaterialTheme.colorScheme.inverseSurface.copy(alpha = 0.95f),
            shadowElevation = 8.dp,
            tonalElevation = 4.dp,
        ) {
            Row(
                modifier = Modifier
                    .padding(horizontal = 16.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text(
                    text = "$selectedCount / $totalCount",
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                Spacer(modifier = Modifier.width(8.dp))

                // 全选按钮
                Surface(shape = CircleShape, color = MaterialTheme.colorScheme.secondaryContainer, onClick = onSelectAll) {
                    Icon(Icons.Filled.DoneAll, "全选", modifier = Modifier.size(36.dp).padding(8.dp), tint = MaterialTheme.colorScheme.onSecondaryContainer)
                }

                // 修改状态按钮
                Box {
                    Surface(shape = CircleShape, color = MaterialTheme.colorScheme.primaryContainer, onClick = { showStatusMenu = true }) {
                        Icon(Icons.Filled.EditNote, "修改状态", modifier = Modifier.size(36.dp).padding(8.dp), tint = MaterialTheme.colorScheme.onPrimaryContainer)
                    }
                    DropdownMenu(expanded = showStatusMenu, onDismissRequest = { showStatusMenu = false }) {
                        DropdownMenuItem(text = { Text("演出中") }, onClick = { showStatusMenu = false; onUpdateStatus("acting") })
                        DropdownMenuItem(text = { Text("已落幕") }, onClick = { showStatusMenu = false; onUpdateStatus("ended") })
                        DropdownMenuItem(text = { Text("筹备中") }, onClick = { showStatusMenu = false; onUpdateStatus("setup") })
                    }
                }

                // 删除按钮
                Surface(shape = CircleShape, color = MaterialTheme.colorScheme.errorContainer, onClick = { showDeleteConfirm = true }) {
                    Icon(Icons.Filled.Delete, "批量删除", modifier = Modifier.size(36.dp).padding(8.dp), tint = MaterialTheme.colorScheme.onErrorContainer)
                }

                Spacer(modifier = Modifier.weight(1f))

                // 取消按钮
                Surface(shape = CircleShape, color = MaterialTheme.colorScheme.surfaceVariant, onClick = onCancel) {
                    Icon(Icons.Filled.Close, "取消选择", modifier = Modifier.size(36.dp).padding(8.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }

    if (showDeleteConfirm) {
        AlertDialog(
            onDismissRequest = { showDeleteConfirm = false },
            title = { Text("批量删除？") },
            text = { Text("确定删除 $selectedCount 个已选剧本？此操作无法撤销。") },
            confirmButton = {
                TextButton(onClick = { onDelete(); showDeleteConfirm = false }) { Text("删除") }
            },
            dismissButton = {
                TextButton(onClick = { showDeleteConfirm = false }) { Text("取消") }
            },
        )
    }
}

// ============================================================
// Drama Card — 支持普通模式与批量选择模式
// ============================================================

@Composable
private fun DramaCard(
    drama: Drama,
    isSelectionMode: Boolean,
    isSelected: Boolean,
    onToggleSelect: () -> Unit,
    onDramaClick: (String) -> Unit,
    onLoadDrama: () -> Unit,
    onDeleteDrama: () -> Unit,
) {
    var showMenu by remember { mutableStateOf(false) }
    var showDeleteDialog by remember { mutableStateOf(false) }

    ElevatedCard(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.elevatedCardColors(
            containerColor = if (isSelected && isSelectionMode)
                MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.15f)
            else
                MaterialTheme.colorScheme.surface,
        ),
        elevation = CardDefaults.elevatedCardElevation(
            defaultElevation = if (isSelected) 4.dp else 2.dp,
        ),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable(enabled = !isSelectionMode) {
                    if (!isSelectionMode) onDramaClick(drama.folder)
                }
                .padding(start = if (isSelectionMode) 4.dp else 16.dp, end = 8.dp, top = 16.dp, bottom = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            // === 左侧 Checkbox（选择模式下滑入） ===
            AnimatedVisibility(
                visible = isSelectionMode,
                enter = slideInHorizontally(initialOffsetX = { -it }),
                exit = slideOutHorizontally(targetOffsetX = { -it }),
            ) {
                Surface(
                    shape = CircleShape,
                    color = if (isSelected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.3f),
                    border = null,
                    modifier = Modifier
                        .size(26.dp)
                        .padding(2.dp)
                        .clickable(interactionSource = null, indication = null) { onToggleSelect() },
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        if (isSelected) {
                            Icon(Icons.Filled.Check, "已选中", modifier = Modifier.size(18.dp), tint = MaterialTheme.colorScheme.onPrimary)
                        }
                    }
                }
                Spacer(modifier = Modifier.width(8.dp))
            }

            // === 戏剧图标 ===
            Box(
                modifier = Modifier
                    .size(44.dp)
                    .clip(CircleShape)
                    .background(MaterialTheme.colorScheme.primaryContainer),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    Icons.Filled.TheaterComedy, null,
                    modifier = Modifier.size(24.dp),
                    tint = MaterialTheme.colorScheme.onPrimaryContainer,
                )
            }

            Spacer(modifier = Modifier.width(14.dp))

            // === 中间信息区 ===
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = drama.theme,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Spacer(modifier = Modifier.height(4.dp))
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Surface(
                        shape = RoundedCornerShape(8.dp),
                        color = when (drama.status) {
                            "acting" -> MaterialTheme.colorScheme.primaryContainer
                            "ended" -> MaterialTheme.colorScheme.tertiaryContainer
                            "setup" -> MaterialTheme.colorScheme.secondaryContainer
                            else -> MaterialTheme.colorScheme.surfaceVariant
                        },
                    ) {
                        Text(
                            text = when (drama.status) {
                                "acting" -> "演出中"
                                "ended" -> "已落幕"
                                "setup" -> "筹备中"
                                else -> drama.status
                            },
                            style = MaterialTheme.typography.labelSmall,
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                            color = when (drama.status) {
                                "acting" -> MaterialTheme.colorScheme.onPrimaryContainer
                                "ended" -> MaterialTheme.colorScheme.onTertiaryContainer
                                "setup" -> MaterialTheme.colorScheme.onSecondaryContainer
                                else -> MaterialTheme.colorScheme.onSurfaceVariant
                            },
                        )
                    }
                    Text(
                        text = "${drama.currentScene} 场",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            // === 右侧菜单按钮 ===
            AnimatedVisibility(
                visible = !isSelectionMode,
                enter = fadeIn(),
                exit = fadeOut(),
            ) {
                IconButton(onClick = { showMenu = true }) {
                    Icon(Icons.Filled.MoreVert, "更多操作", modifier = Modifier.size(20.dp))
                }
            }
        }
    }

    // ★ 玻璃态系统菜单 — 使用 Popup 精确定位到三点按钮
    if (!isSelectionMode && showMenu) {
        Popup(
            alignment = Alignment.TopEnd,
            offset = IntOffset(x = with(LocalDensity.current) { (-4).dp.toPx().toInt() }, y = with(LocalDensity.current) { (-8).dp.toPx().toInt() }),
            properties = PopupProperties(
                focusable = true,
                dismissOnBackPress = true,
                dismissOnClickOutside = true,
            ),
            onDismissRequest = { showMenu = false },
        ) {
            Surface(
                shape = RoundedCornerShape(14.dp),
                color = MaterialTheme.colorScheme.surface.copy(alpha = 0.92f),
                shadowElevation = 16.dp,
                tonalElevation = 8.dp,
                border = BorderStroke(0.5.dp, Color.White.copy(alpha = 0.15f)),
                modifier = Modifier.padding(vertical = 6.dp),
            ) {
                Column(modifier = Modifier.widthIn(min = 160.dp, max = 200.dp)) {
                    // 继续 — Play 图标（主色调）
                    GlassyMenuItem(
                        icon = { Icon(Icons.Outlined.PlayArrow, null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(18.dp)) },
                        label = "继续",
                        labelColor = MaterialTheme.colorScheme.onSurface,
                        onClick = { showMenu = false; onDramaClick(drama.folder) },
                    )

                    // 加载存档 — History 图标（次色调）
                    GlassyMenuItem(
                        icon = { Icon(Icons.Outlined.History, null, tint = MaterialTheme.colorScheme.secondary, modifier = Modifier.size(18.dp)) },
                        label = "加载存档",
                        labelColor = MaterialTheme.colorScheme.onSurface,
                        onClick = { showMenu = false; onLoadDrama() },
                    )

                    HorizontalDivider(
                        color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.3f),
                        modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp),
                    )

                    // 删除 — Delete 图标（红色警告色）
                    GlassyMenuItem(
                        icon = { Icon(Icons.Filled.Delete, null, tint = MaterialTheme.colorScheme.error, modifier = Modifier.size(18.dp)) },
                        label = "删除",
                        labelColor = MaterialTheme.colorScheme.error,
                        onClick = { showMenu = false; showDeleteDialog = true },
                    )
                }
            }
        }
    }

    // 删除确认对话框
    if (showDeleteDialog) {
        AlertDialog(
            onDismissRequest = { showDeleteDialog = false },
            title = { Text("删除戏剧？") },
            text = { Text("此操作不可恢复") },
            confirmButton = {
                TextButton(onClick = { onDeleteDrama(); showDeleteDialog = false }) { Text("删除") }
            },
            dismissButton = {
                TextButton(onClick = { showDeleteDialog = false }) { Text("取消") }
            },
        )
    }
}

/**
 * 玻璃态菜单项 — iOS 系统菜单风格行组件
 * 带 18dp 彩色图标、标签文字、按压高亮效果
 */
@Composable
private fun GlassyMenuItem(
    icon: @Composable () -> Unit,
    label: String,
    labelColor: Color = MaterialTheme.colorScheme.onSurface,
    onClick: () -> Unit,
) {
    Surface(
        shape = RoundedCornerShape(10.dp),
        color = Color.Transparent,
        modifier = Modifier
            .fillMaxWidth()
            .clickable(interactionSource = null, indication = null) { onClick() }
            .padding(horizontal = 12.dp, vertical = 8.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            icon()
            Spacer(modifier = Modifier.width(12.dp))
            Text(
                text = label,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium,
                color = labelColor,
            )
        }
    }
}
