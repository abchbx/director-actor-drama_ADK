# Phase 17: Android Interaction - Research

**Researched:** 2026-04-16
**Domain:** Android / Kotlin / Jetpack Compose / MVVM+Hilt / WebSocket-driven UI / CRUD Interaction
**Confidence:** HIGH

## Summary

Phase 17 在 Phase 16 搭建的 Android 骨架基础上，实现戏剧 CRUD 交互的核心业务界面：创建戏剧（STORM 进度）→ 戏剧列表管理（卡片/菜单/删除确认）→ 主戏剧屏幕（实时场景渲染 + 命令输入栏）→ 场景历史浏览 → 保存/加载确认。全部 6 个屏幕/组件基于 MVVM + Hilt + Compose 模式，WebSocket 事件流驱动主屏幕实时更新。

**关键发现：** 后端 `/drama/status` 端点仅返回 `num_scenes`/`current_scene`，不返回场景列表数据（scenes 存在 `state["scenes"]` 但无 API 暴露）。场景历史功能（D-18~D-21）需要后端新增端点或扩展现有 `/status` 响应。这是本 phase 最重要的 API 契约缺口。

**Primary recommendation:** 沿用 Phase 16 MVVM + Hilt + Repository 三层架构，DramaItemDto 细化为 typed data class，WebSocket 事件通过 ViewModel 的 `viewModelScope.launch` + `callbackFlow` 收集驱动 StateFlow 更新，场景历史需后端配合新增 `/drama/scenes` 端点。

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** 全屏创建表单 — 主题输入框占屏幕中央，大字体 placeholder "输入你的戏剧主题..."，沉浸式创作体验
- **D-02:** 点击创建后调用 `POST /drama/start`，进入加载态 — LinearProgressIndicator + "导演正在构思世界观..."
- **D-03:** STORM 进度通过 WS 事件实时展示 — 收到 `storm_discover`/`storm_research`/`storm_outline` 事件时更新进度文案
- **D-04:** 创建完成自动跳转 — 收到 `scene_start` 事件后导航到 `DramaDetail(dramaId)`，无需独立 STORM 结果页面
- **D-05:** 若当前已有活跃 drama，`/start` 先自动保存旧 drama（后端 D-06 已实现），前端无需额外处理
- **D-06:** 紧凑卡片布局两行信息 — 第一行：主题（titleLarge 加粗）+ 状态 badge；第二行：场数 + 更新时间
- **D-07:** 三点菜单操作 — `IconButton` + `DropdownMenu` 包含：加载、恢复、删除
- **D-08:** 删除操作 AlertDialog 确认 — 防误删
- **D-09:** 空列表状态 — 居中插画 + 文案 + FAB 跳转创建 tab
- **D-10:** `DramaItemDto` 细化为 typed data class — 当前 `List<Map<String, JsonElement>>` 不可用
- **D-11:** 角色分段气泡渲染 — 旁白灰色左对齐，对白角色色右对齐，角色名 + 小圆形首字母头像
- **D-12:** 底部固定命令输入栏 — `BottomAppBar` 包含文本输入框 + 发送按钮 + 快捷芯片
- **D-13:** 快捷芯片交互 — `/next`/`/end` 直接发送；`/action`/`/speak` 点击后填入前缀 + 空格，光标聚焦等待输入
- **D-14:** Typing 指示器基础版 — 收到 WS `typing` 事件时场景底部显示脉冲动画 + "导演正在构思..."
- **D-15:** WS 事件驱动 UI 更新 — narration→旁白气泡，dialogue→对白气泡，scene_end→分割线，tension_update→张力指示，typing→指示器，error→Snackbar
- **D-16:** 顶部 TopAppBar — 戏剧主题 + 当前场景号 + 张力评分
- **D-17:** 进入 DramaDetail 时自动连接 WS + 订阅事件流
- **D-18:** 底部半屏 BottomSheet 展示历史 — 主屏幕右上角历史按钮
- **D-19:** BottomSheet 内容为场景摘要列表 — 场景号 + 前几行文字摘要，可滚动
- **D-20:** 点击历史场景跳转完整内容 — 替换主屏幕内容，TopAppBar 出现返回按钮
- **D-21:** 场景数据获取 — 通过 `GET /drama/status` 获取 `num_scenes`，后端需扩展返回 scenes 摘要列表
- **D-22:** 保存/加载操作 Snackbar 确认 — 成功提示"已保存：{save_name}"，失败提示错误信息
- **D-23:** 保存操作入口 — 主屏幕 TopAppBar 溢出菜单"保存"选项，弹 Dialog 输入保存名
- **D-24:** 加载操作入口 — 戏剧列表卡片的三点菜单"加载"项

### Claude's Discretion
- `DramaItemDto` 的具体字段设计和序列化策略
- 聊天气泡的 Compose 组件拆分方式（Bubble Composable）
- 命令输入文本解析逻辑（区分 `/` 命令 vs 自由文本 → `/action` 前缀）
- WS 事件到 UI 状态的 Flow 转换架构（StateFlow vs SharedFlow）
- BottomSheet 的 peekHeight 和展开行为
- 场景历史数据获取方案细节（API 扩展 vs 从现有 state 读取）
- 输入栏软键盘交互（imePadding、焦点管理）
- LazyColumn 自动滚动到底部策略

### Deferred Ideas (OUT OF SCOPE)
- 演员面板（角色列表 + A2A 状态 + 记忆摘要）— Phase 18 APP-07
- 富文本渲染增强（情绪标签 + 头像圆形标识）— Phase 18 APP-11
- WS 自动重连 + 指数退避 — Phase 18 APP-15
- 剧本导出为 Markdown + Share Intent — Phase 18 APP-09
- 戏剧状态概览（张力/弧线/时间段）— Phase 18 APP-08
- 更丰富的 Typing 指示器（脉冲动画增强）— Phase 18 APP-10
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| APP-02 | Drama creation screen with theme input, triggers STORM discovery | DramaCreateScreen + DramaCreateViewModel（D-01~D-05），调用 `POST /drama/start`，WS 监听 STORM 进度事件 |
| APP-03 | Drama list screen shows all saved dramas with load/resume/delete actions | DramaListScreen + DramaListViewModel（D-06~D-10），调用 `GET /drama/list`，DramaItemDto 细化 |
| APP-04 | Main drama screen displays current scene with real-time WebSocket updates | DramaDetailScreen + DramaDetailViewModel（D-11~D-17），WS 事件驱动气泡渲染 |
| APP-05 | Command input bar supports /next, /action, /speak, /end commands | BottomAppBar + Chip 组件（D-12~D-13），文本解析逻辑 |
| APP-06 | Scene history scrollable list with timeline navigation | BottomSheet + 场景摘要列表（D-18~D-21），**需后端扩展 API** |
| APP-12 | Save/load drama with confirmation feedback | Snackbar 确认（D-22~D-24），调用 `POST /drama/save` / `POST /drama/load` |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Kotlin | 2.1.0 | 编程语言 | Phase 16 已验证 [VERIFIED: libs.versions.toml] |
| Compose BOM | 2025.12.01 | Compose 版本管理 | Phase 16 已安装 [VERIFIED: libs.versions.toml] |
| Material3 | 1.4.0 (via BOM) | MD3 组件库 | 最新稳定版 [VERIFIED: developer.android.com, 2026-03-25] |
| Hilt | 2.54 | 依赖注入 | Phase 16 已安装 [VERIFIED: libs.versions.toml] |
| Navigation Compose | 2.8.9 | 导航 | Phase 16 已安装 [VERIFIED: libs.versions.toml] |
| Retrofit | 2.12.0 | REST 客户端 | Phase 16 已安装 [VERIFIED: libs.versions.toml] |
| OkHttp | 4.12.0 | HTTP/WebSocket | Phase 16 已安装 [VERIFIED: libs.versions.toml] |
| kotlinx-serialization-json | 1.8.1 | JSON 序列化 | Phase 16 已安装 [VERIFIED: libs.versions.toml] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| hilt-navigation-compose | 1.2.0 | Hilt + Navigation 集成 | @HiltViewModel 自动注入 |
| lifecycle-viewmodel-compose | 2.8.7 | ViewModel Compose 集成 | viewModel() 获取 ViewModel |
| lifecycle-runtime-compose | 2.8.7 | Lifecycle Compose 集成 | collectAsStateWithLifecycle() |
| compose-material-icons-extended | via BOM | 扩展图标集 | DropdownMenu/Chip/BottomSheet 图标 |

### Phase 17 新增（无需添加依赖）
| 功能 | 实现方式 | 说明 |
|------|----------|------|
| ModalBottomSheet | Material3 内置 | 场景历史 BottomSheet（D-18） |
| SnackbarHost + Scaffold | Material3 内置 | 保存/加载确认（D-22） |
| InputChip / SuggestionChip | Material3 内置 | 快捷命令芯片（D-12） |
| AlertDialog | Material3 内置 | 删除确认（D-08） |
| LinearProgressIndicator | Material3 内置 | 创建进度（D-02） |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ModalBottomSheet | BottomSheetScaffold | ModalBottomSheet 更轻量、独立弹出，不与主 Scaffold 冲突；BottomSheetScaffold 适合常驻面板 |
| InputChip | FilterChip | InputChip 有删除图标，适合已选标签；FilterChip 有选中态，适合命令分类；SuggestionChip 最适合"建议命令"场景 [VERIFIED: developer.android.com] |
| StateFlow | SharedFlow | StateFlow 有初始值、去重，适合 UI 状态；SharedFlow 适合一次性事件（导航、Snackbar）— 两者结合使用 |

**Installation:**
```bash
# 无需新增依赖 — Phase 17 使用的全部是 Material3 和 Compose 内置组件
# 所有依赖已在 Phase 16 的 build.gradle.kts 中配置
```

**Version verification:** 所有版本已通过 libs.versions.toml 验证（Phase 16 已安装并编译通过）。

## Architecture Patterns

### Recommended Project Structure（Phase 17 新增/修改文件）
```
android/app/src/main/java/com/drama/app/
├── data/
│   ├── remote/
│   │   ├── dto/
│   │   │   ├── DramaItemDto.kt          # 新增：替代 List<Map<String, JsonElement>>
│   │   │   ├── SceneDto.kt              # 新增：场景数据模型（D-21）
│   │   │   └── ...（Phase 16 已有）
│   │   ├── api/
│   │   │   └── DramaApiService.kt       # 修改：新增 getDramaScenes()
│   │   └── ws/
│   │       └── WebSocketManager.kt      # 不修改，Phase 16 已完整
│   └── repository/
│       ├── DramaRepositoryImpl.kt       # 新增：戏剧 CRUD + WS 事件封装
│       └── ...（Phase 16 已有）
├── domain/
│   ├── model/
│   │   ├── Drama.kt                     # 新增：戏剧 domain model
│   │   ├── SceneBubble.kt              # 新增：场景气泡 domain model
│   │   ├── CommandType.kt              # 新增：命令类型枚举
│   │   └── ...（Phase 16 已有）
│   └── repository/
│       └── DramaRepository.kt           # 新增：Repository 接口
├── ui/
│   ├── screens/
│   │   ├── dramacreate/
│   │   │   ├── DramaCreateScreen.kt     # 重写：全屏创建表单 + STORM 进度
│   │   │   └── DramaCreateViewModel.kt  # 重写：创建 + WS 进度逻辑
│   │   ├── dramalist/
│   │   │   ├── DramaListScreen.kt       # 重写：卡片列表 + 三点菜单 + 空状态
│   │   │   └── DramaListViewModel.kt    # 重写：列表加载 + 操作
│   │   ├── dramadetail/
│   │   │   ├── DramaDetailScreen.kt     # 重写：主戏剧屏幕 + 命令栏 + 历史面板
│   │   │   ├── DramaDetailViewModel.kt  # 重写：WS 事件驱动 + 命令发送
│   │   │   └── components/              # 新增：子组件目录
│   │   │       ├── SceneBubbleList.kt   # 气泡列表
│   │   │       ├── NarrationBubble.kt   # 旁白气泡
│   │   │       ├── DialogueBubble.kt    # 对白气泡
│   │   │       ├── CommandInputBar.kt   # 命令输入栏
│   │   │       ├── SceneHistorySheet.kt # 场景历史 BottomSheet
│   │   │       ├── TypingIndicator.kt   # Typing 指示器
│   │   │       └── TensionIndicator.kt  # 张力指示器
│   │   └── settings/                    # 不修改
│   ├── navigation/
│   │   ├── DramaNavHost.kt             # 修改：新增导航回调（创建→详情）
│   │   └── Route.kt                    # 不修改
│   └── components/                      # 可选：共享组件
└── di/
    └── DramaModule.kt                  # 新增：DramaRepository DI 绑定
```

### Pattern 1: ViewModel + StateFlow + WebSocket 事件驱动
**What:** ViewModel 持有 `MutableStateFlow<UiState>`，进入屏幕时连接 WS，收集事件 Flow 转换为 UI 状态更新
**When to use:** DramaDetailScreen（主戏剧屏幕）— 所有 WS 事件驱动 UI
**Example:**
```kotlin
// Source: [CITED: developer.android.com/topic/libraries/architecture/viewmodel]
@HiltViewModel
class DramaDetailViewModel @Inject constructor(
    private val dramaRepository: DramaRepository,
    private val webSocketManager: WebSocketManager,
    private val serverPreferences: ServerPreferences,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {

    private val dramaId: String = savedStateHandle["dramaId"] ?: ""

    private val _uiState = MutableStateFlow(DramaDetailUiState())
    val uiState: StateFlow<DramaDetailUiState> = _uiState.asStateFlow()

    // 一次性事件（导航、Snackbar）
    private val _events = MutableSharedFlow<DramaDetailEvent>()
    val events: SharedFlow<DramaDetailEvent> = _events.asSharedFlow()

    private var wsJob: Job? = null

    fun connectWebSocket() {
        viewModelScope.launch {
            val config = serverPreferences.serverConfig.first() ?: return@launch
            webSocketManager.connect(config.ip, config.port, config.token)
                .catch { e -> _uiState.update { it.copy(error = e.message) } }
                .collect { event -> handleWsEvent(event) }
        }
    }

    fun disconnectWebSocket() {
        wsJob?.cancel()
        webSocketManager.disconnect()
    }

    private fun handleWsEvent(event: WsEventDto) {
        when (event.type) {
            "narration" -> _uiState.update { it.copy(
                bubbles = it.bubbles + NarrationBubble(event.data["text"]?.jsonPrimitive?.content ?: "")
            )}
            "dialogue" -> _uiState.update { it.copy(
                bubbles = it.bubbles + DialogueBubble(
                    actorName = event.data["actor_name"]?.jsonPrimitive?.content ?: "",
                    text = event.data["text"]?.jsonPrimitive?.content ?: ""
                )
            )}
            "scene_start" -> { /* 新场景开始，可清空或保留历史 */ }
            "scene_end" -> _uiState.update { it.copy(
                currentScene = it.currentScene + 1
            )}
            "tension_update" -> _uiState.update { it.copy(
                tensionScore = event.data["tension_score"]?.jsonPrimitive?.intOrNull ?: 0
            )}
            "typing" -> _uiState.update { it.copy(isTyping = true) }
            "storm_discover" -> _uiState.update { it.copy(stormPhase = "发现新视角...") }
            "storm_research" -> _uiState.update { it.copy(stormPhase = "深入研究...") }
            "storm_outline" -> _uiState.update { it.copy(stormPhase = "综合构思大纲...") }
            "error" -> { /* 触发 Snackbar */ }
        }
    }

    override fun onCleared() {
        super.onCleared()
        disconnectWebSocket()
    }
}
```

### Pattern 2: Domain Model + DTO 转换在 Repository
**What:** Repository 层负责 DTO → Domain Model 转换，ViewModel 只暴露 domain model
**When to use:** DramaListResponseDto → List<Drama>，DramaStatusResponseDto → DramaStatus
**Example:**
```kotlin
// Source: [CITED: developer.android.com/topic/architecture/data-layer]
// Domain model
data class Drama(
    val folder: String,
    val theme: String,
    val status: String,
    val updatedAt: String,
    val currentScene: Int,
)

// DTO (细化的 typed data class, D-10)
@Serializable
data class DramaItemDto(
    val folder: String = "",
    val theme: String = "",
    val status: String = "unknown",
    val updated_at: String = "Unknown",
    val current_scene: Int = 0,
    val snapshots: List<String> = emptyList(),  // snapshot_only 类型的戏剧
)

@Serializable
data class DramaListResponseDto(
    val dramas: List<DramaItemDto> = emptyList(),
)

// Repository 转换
class DramaRepositoryImpl @Inject constructor(
    private val dramaApiService: DramaApiService,
) : DramaRepository {
    override suspend fun listDramas(): Result<List<Drama>> = runCatching {
        dramaApiService.listDramas().dramas.map { dto ->
            Drama(
                folder = dto.folder,
                theme = dto.theme,
                status = dto.status,
                updatedAt = dto.updated_at,
                currentScene = dto.current_scene,
            )
        }
    }
}
```

### Pattern 3: ModalBottomSheet 场景历史
**What:** 使用 Material3 ModalBottomSheet 显示场景历史列表
**When to use:** D-18 场景历史面板
**Example:**
```kotlin
// Source: [CITED: developer.android.com/develop/ui/compose/components/bottom-sheets]
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SceneHistorySheet(
    scenes: List<SceneSummary>,
    onSceneClick: (Int) -> Unit,
    onDismiss: () -> Unit,
) {
    val sheetState = rememberModalBottomSheetState()

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
    ) {
        LazyColumn {
            items(scenes) { scene ->
                ListItem(
                    headlineContent = { Text("第${scene.sceneNumber}场") },
                    supportingContent = { Text(scene.title) },
                    modifier = Modifier.clickable { onSceneClick(scene.sceneNumber) },
                )
            }
        }
    }
}
```

### Pattern 4: 命令输入栏 + 快捷芯片
**What:** BottomAppBar 内嵌 TextField + SuggestionChip 组
**When to use:** D-12/D-13 命令输入栏
**Example:**
```kotlin
// Source: [CITED: developer.android.com/develop/ui/compose/components/chips]
@Composable
fun CommandInputBar(
    onCommand: (String, String?) -> Unit,  // (command, argument?)
    isProcessing: Boolean,
) {
    var inputText by remember { mutableStateOf("") }
    val focusRequester = remember { FocusRequester() }

    Column {
        // 快捷芯片行
        Row(
            modifier = Modifier.horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            SuggestionChip(
                onClick = { onCommand("/next", null) },  // D-13: 直接发送
                label = { Text("/next") },
            )
            SuggestionChip(
                onClick = {
                    inputText = "/action "  // D-13: 填入前缀
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
                onClick = { onCommand("/end", null) },
                label = { Text("/end") },
            )
        }

        // 输入行
        BottomAppBar {
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
                        parseAndSend(inputText, onCommand)
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
```

### Pattern 5: SnackbarHost + 一次性事件
**What:** 用 SharedFlow 发射一次性事件（Snackbar、导航），在 Composable 中收集
**When to use:** 保存/加载确认（D-22）、错误提示
**Example:**
```kotlin
// ViewModel
sealed class DramaListEvent {
    data class ShowSnackbar(val message: String) : DramaListEvent()
    data class NavigateToDetail(val dramaId: String) : DramaListEvent()
}

@HiltViewModel
class DramaListViewModel @Inject constructor(...) : ViewModel() {
    private val _events = MutableSharedFlow<DramaListEvent>()
    val events: SharedFlow<DramaListEvent> = _events.asSharedFlow()

    fun deleteDrama(folder: String) {
        viewModelScope.launch {
            // 调用 API 删除
            _events.emit(DramaListEvent.ShowSnackbar("已删除：$folder"))
        }
    }
}

// Composable 中收集
LaunchedEffect(Unit) {
    viewModel.events.collect { event ->
        when (event) {
            is DramaListEvent.ShowSnackbar ->
                snackbarHostState.showSnackbar(event.message)
            is DramaListEvent.NavigateToDetail ->
                onDramaClick(event.dramaId)
        }
    }
}
```

### Anti-Patterns to Avoid
- **在 Composable 中直接调用 API**: 应通过 ViewModel → Repository，Composable 仅观察 StateFlow
- **用 StateFlow 发射一次性事件**: StateFlow 会缓存最新值，新订阅者会立即收到旧事件 — 用 SharedFlow(replay=0) 代替
- **WS 事件在 Composable 中直接处理**: 应在 ViewModel 中收集 WS Flow，转换为 UiState 更新
- **硬编码 WS 事件字段名**: 应定义常量或使用 sealed class 映射事件类型
- **在 LazyColumn 中使用 Column 嵌套大量项**: 场景气泡列表应使用 LazyColumn，避免 Column + Modifier.verticalScroll 导致性能问题
- **忘记处理 WS 连接失败**: callbackFlow 的 catch 必须更新 UI 状态（error 字段），否则用户看不到断连
- **ModalBottomSheet 忘记 @OptIn**: Material3 的 ModalBottomSheet 仍标记为 ExperimentalMaterial3Api

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 底部弹出面板 | 自定义 BottomSheet 动画 | Material3 ModalBottomSheet | 手势拖拽、半屏展开、scrim、动画全部内置 |
| Snackbar 管理 | 自定义 Toast/Dialog | Scaffold + SnackbarHost + SnackbarHostState | 生命周期感知、队列管理、自定义 action |
| 命令解析器 | 正则匹配所有可能命令 | 简单 when 分支 + 前缀识别 | 只有 4 个命令 + 自由文本，复杂解析过度设计 |
| 气泡渲染 | 自定义 Layout/Canvas | Row + Card + Surface | Compose 声明式组件足够，自定义 Layout 性能收益极小 |
| 列表动画 | 手写 DiffUtil + ItemAnimator | LazyColumn + animateItem() | Compose 内置 item 动画，无需手动管理 |
| 删除确认 | 自定义 Dialog | Material3 AlertDialog | 标准确认/取消交互，无障碍支持 |

**Key insight:** Phase 17 的 UI 交互模式都是 Material3 标准组件覆盖的场景。自定义任何上述组件都是技术债，且损失无障碍和一致性。

## Runtime State Inventory

> 此为功能填充 phase（在 Phase 16 骨架上实现业务逻辑），不涉及重命名/迁移。但需注意以下运行时状态：

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | DataStore 存储的服务器 IP/port/token（Phase 16 已有） | 仅读取，无需修改 |
| Live service config | WebSocketManager 单例（Hilt Singleton）— 连接状态需在进入/离开 DramaDetail 时管理 | 代码编辑：ViewModel 生命周期绑定 |
| OS-registered state | None | — |
| Secrets/env vars | Token 存在 EncryptedSharedPreferences（Phase 16 已有） | 仅读取，无需修改 |
| Build artifacts | Phase 16 APK 已编译 | 增量编译即可 |

**后端状态（需注意但不在 Android 代码修改范围）：**
- 后端 `state["scenes"]` 存储场景列表数据，但无 API 端点暴露 — 需新增 `/drama/scenes` 或扩展 `/status`（见 Open Questions）
- 后端 `list_dramas()` 返回的 `dramas` 数组中每项包含 `folder`/`theme`/`status`/`updated_at`/`current_scene` — 已验证 [VERIFIED: app/state_manager.py:790-797]

## Common Pitfalls

### Pitfall 1: DramaListResponseDto 反序列化失败
**What goes wrong:** 当前后端 `list_dramas()` 返回 `dramas: list[dict]`，Android DTO 定义为 `List<Map<String, JsonElement>>`，无法类型安全地读取字段
**Why it happens:** 后端 Pydantic 模型 `DramaListResponse.dramas: list[dict]` 是 untyped dict，不同戏剧项的字段不一致（有 `snapshots` 字段 vs 无）
**How to avoid:** 细化为 `DramaItemDto` typed data class（D-10），用 `@Serializable` + 默认值处理字段缺失。后端 `list_dramas()` 已返回 `folder`/`theme`/`status`/`updated_at`/`current_scene` [VERIFIED: app/state_manager.py:790-797]
**Warning signs:** `JsonDecodingException` 或字段读取返回 null

### Pitfall 2: 场景历史无 API 端点
**What goes wrong:** D-18~D-21 需要场景列表，但 `/drama/status` 仅返回 `num_scenes` 和 `current_scene`，不返回 scenes 数组
**Why it happens:** Phase 13 API 设计时未暴露 `state["scenes"]` 数据
**How to avoid:** 必须新增后端 API（见 Open Questions #1），或在现有 `/status` 端点扩展返回 scenes 摘要。不能跳过 — 场景历史是 Phase 17 成功标准 #5
**Warning signs:** 前端无法展示历史场景列表

### Pitfall 3: WebSocket 连接在 ViewModel onCleared 时未断开
**What goes wrong:** Activity 销毁后 WebSocket 仍运行，导致内存泄漏和幽灵消息
**Why it happens:** WebSocketManager 是 Hilt @Singleton，生命周期不随 ViewModel 自动管理
**How to avoid:** ViewModel `onCleared()` 中调用 `webSocketManager.disconnect()`；或使用 `viewModelScope` 的 Job 管理 WS 收集
**Warning signs:** 退出 DramaDetail 后仍收到 WS 事件、内存持续增长

### Pitfall 4: LazyColumn 不自动滚动到底部
**What goes wrong:** 新气泡追加到底部时，列表不自动滚动，用户看不到最新内容
**Why it happens:** LazyColumn 默认不追踪最新项
**How to avoid:** 使用 `LaunchedEffect(bubbles.size)` + `lazyListState.animateScrollToItem(bubbles.lastIndex)`；或 `snapshotFlow { listState.layoutInfo }` 监听变化
**Warning signs:** 新消息出现但屏幕不滚动

### Pitfall 5: 快捷芯片与软键盘冲突
**What goes wrong:** 点击 `/action` 芯片后聚焦输入框，软键盘弹出遮挡命令栏
**Why it happens:** BottomAppBar 不会被软键盘推上去，需要 `Modifier.imePadding()`
**How to avoid:** 命令输入栏所在容器使用 `Modifier.imePadding()`，或在 Scaffold 中配置 `WindowCompat.setDecorFitsSystemWindows(window, false)` + edge-to-edge
**Warning signs:** 软键盘遮挡输入框

### Pitfall 6: WS replay 消息未处理
**What goes wrong:** 连接 WS 后收到的首条 replay 消息（包含 100 条历史事件）被当作普通事件处理，导致气泡重复
**Why it happens:** WebSocketManager 的 `callbackFlow` 不区分 replay 消息和实时消息
**How to avoid:** 在 ViewModel 中处理 `type == "replay"` 消息 — 提取 `events` 数组批量转换为初始气泡列表，不逐条追加
**Warning signs:** 进入 DramaDetail 后气泡重复显示

### Pitfall 7: 创建戏剧后导航时机错误
**What goes wrong:** `POST /drama/start` 返回成功后立即导航，但 STORM 过程可能还在进行
**Why it happens:** REST 响应返回 ≠ STORM 完成。根据 D-04，应等 `scene_start` WS 事件才导航
**How to avoid:** 创建后不导航，等 WS `scene_start` 事件再跳转。加载态 UI 显示 STORM 进度
**Warning signs:** 用户看到不完整的戏剧或白屏

### Pitfall 8: 戏剧列表卡片操作语义混淆
**What goes wrong:** "加载"和"恢复"操作含义不清 — 用户不理解 `POST /drama/load` vs 直接进入
**Why it happens:** 后端 `load` 是从保存点恢复，不是"打开当前活跃戏剧"
**How to avoid:** 三点菜单标签清晰区分："继续"（导航到 DramaDetail，如果有活跃 drama）、"加载存档"（调用 `POST /drama/load`，输入保存名）、"删除"。根据 D-07 决定具体菜单项
**Warning signs:** 用户误操作加载覆盖当前进度

## Code Examples

Verified patterns from official sources and project code:

### DramaItemDto — 细化 typed data class（D-10）
```kotlin
// Source: [VERIFIED: app/state_manager.py:790-797 — list_dramas() 返回字段]
@Serializable
data class DramaItemDto(
    val folder: String = "",
    val theme: String = "",
    val status: String = "unknown",
    val updated_at: String = "Unknown",
    val current_scene: Int = 0,
    val snapshots: List<String> = emptyList(),  // 仅 snapshot_only 类型有
)

// 替换原有 DramaListResponseDto
@Serializable
data class DramaListResponseDto(
    val dramas: List<DramaItemDto> = emptyList(),
)
```

### WsEventDto.data 字段读取 — 使用 JsonElement
```kotlin
// Source: [VERIFIED: app/api/event_mapper.py — 事件 data 结构]
// narration 事件: { "tool": "director_narrate" }
// dialogue 事件: { "actor_name": "xxx", "tool": "actor_speak" }
// scene_end 事件: { "scene_number": 5, "scene_title": "xxx" }
// tension_update: { "tension_score": 7 }
// storm_discover: { "tool": "storm_discover_perspectives" }
// save_confirm: { "message": "xxx" }
// load_confirm: { "message": "xxx", "theme": "xxx" }

// 读取 data 字段的方式（kotlinx-serialization.json）
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.contentOrNull

fun WsEventDto.getString(key: String): String? =
    data[key]?.jsonPrimitive?.contentOrNull

fun WsEventDto.getInt(key: String): Int? =
    data[key]?.jsonPrimitive?.intOrNull
```

### SceneBubble Domain Model — 区分旁白和对白
```kotlin
// Source: [CITED: D-11 决策 — 角色分段气泡渲染]
sealed class SceneBubble {
    abstract val id: String  // 用于 LazyColumn key

    data class Narration(
        override val id: String,
        val text: String,
    ) : SceneBubble()

    data class Dialogue(
        override val id: String,
        val actorName: String,
        val text: String,
    ) : SceneBubble()

    data class SceneDivider(
        override val id: String,
        val sceneNumber: Int,
        val sceneTitle: String = "",
    ) : SceneBubble()
}
```

### CommandType — 命令类型枚举
```kotlin
// Source: [CITED: D-12/D-13 — 命令输入栏支持 /next /action /speak /end]
enum class CommandType(val prefix: String, val needsArgument: Boolean) {
    NEXT("/next", false),
    ACTION("/action", true),
    SPEAK("/speak", true),
    END("/end", false),
    FREE_TEXT("", false);  // 自由文本 → 当作 /action 处理

    companion object {
        fun fromInput(input: String): CommandType {
            val trimmed = input.trimStart()
            return entries.firstOrNull { trimmed.startsWith(it.prefix) } ?: FREE_TEXT
        }
    }
}
```

### DramaDetailUiState — 主屏幕状态
```kotlin
// Source: [CITED: D-15/D-16 — WS 事件驱动 UI 更新]
data class DramaDetailUiState(
    val theme: String = "",
    val currentScene: Int = 0,
    val tensionScore: Int = 0,
    val bubbles: List<SceneBubble> = emptyList(),
    val isTyping: Boolean = false,
    val isProcessing: Boolean = false,  // 命令发送中
    val stormPhase: String? = null,     // STORM 进度文案
    val isWsConnected: Boolean = false,
    val viewingHistoryScene: Int? = null,  // 正在查看的历史场景号
    val historyScenes: List<SceneSummary> = emptyList(),
    val error: String? = null,
)

data class SceneSummary(
    val sceneNumber: Int,
    val title: String,
    val description: String = "",  // 前几行摘要
)

sealed class DramaDetailEvent {
    data class ShowSnackbar(val message: String) : DramaDetailEvent()
    data class NavigateBack(val reason: String) : DramaDetailEvent()
}
```

### DramaCreateUiState — 创建屏幕状态
```kotlin
// Source: [CITED: D-01~D-05 — 全屏创建表单 + STORM 进度]
data class DramaCreateUiState(
    val theme: String = "",
    val isCreating: Boolean = false,
    val stormPhase: String? = null,  // "发现新视角..." / "深入研究..." / "综合构思大纲..."
    val error: String? = null,
)

sealed class DramaCreateEvent {
    data class NavigateToDetail(val dramaId: String) : DramaCreateEvent()
}
```

### DramaListUiState — 列表屏幕状态
```kotlin
// Source: [CITED: D-06~D-10 — 紧凑卡片 + 三点菜单]
data class DramaListUiState(
    val dramas: List<Drama> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null,
)

sealed class DramaListEvent {
    data class ShowSnackbar(val message: String) : DramaListEvent()
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| BottomSheetScaffold | ModalBottomSheet | Material3 1.1+ | 独立弹出，不与主 Scaffold 冲突，更灵活 |
| Snackbar via ScaffoldState | SnackbarHostState + Scaffold | Material3 1.0+ | 更好的生命周期管理和队列支持 |
| StateFlow 发射一次性事件 | SharedFlow(replay=0) | Kotlin Coroutines 1.4+ | 避免新订阅者收到旧事件 |
| LazyColumn + Modifier.animateItem | 无需手动 DiffUtil | Compose 1.4+ | 内置 item 动画 |
| AndroidView + RecyclerView | 纯 Compose LazyColumn | Compose 1.0+ | 声明式列表，无 View 互操作开销 |

**Deprecated/outdated:**
- `rememberScaffoldState()`: Material3 Scaffold 使用 `SnackbarHostState` 替代
- `BottomSheetScaffold`: 适合常驻面板，场景历史更适合 `ModalBottomSheet`
- `Chip` (Material2): Material3 使用 `SuggestionChip` / `InputChip` / `FilterChip` / `AssistChip`

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | 后端 `list_dramas()` 返回的 dict 字段包括 `folder`/`theme`/`status`/`updated_at`/`current_scene` | Architecture | 需验证实际 JSON 字段名（snake_case vs camelCase）— 已验证 [VERIFIED: state_manager.py] |
| A2 | 后端需要新增场景列表 API 端点供场景历史使用 | Common Pitfalls | 如果可以扩展 `/status` 返回 scenes 摘要，可能无需新端点 |
| A3 | WS `narration`/`dialogue` 事件的 data 中包含 `text` 字段（从 event_mapper 推断） | Code Examples | 需验证实际事件 data 结构 — event_mapper 未在 narration 中传递文本内容 [VERIFIED: event_mapper.py:39] |
| A4 | ModalBottomSheet 仍标记 ExperimentalMaterial3Api | Architecture | 如果已稳定，可移除 @OptIn — Material3 1.4.0 可能已稳定 |
| A5 | `save_drama` 后端可接受空 `save_name`（用主题名作为默认） | Architecture | 如果后端不接受空字符串，前端需默认填入主题名 [VERIFIED: models.py:57 save_name: str = ""] |
| A6 | `POST /drama/load` 的 `save_name` 参数需从列表 UI 获取 | Architecture | 列表卡片三点菜单"加载"需知道可用保存点名 — 但 `/drama/list` 不返回 snapshots 列表 |
| A7 | 删除戏剧无专门 API 端点 — 可能需要新增 `DELETE /drama/{folder}` | Architecture | 如果后端无删除端点，该功能无法实现 — 需验证 |

## Open Questions

1. **场景历史 API 缺口（关键）**
   - What we know: `/drama/status` 仅返回 `num_scenes`/`current_scene`，`state["scenes"]` 包含完整场景数据但无 API 暴露
   - What's unclear: 是新增 `/drama/scenes` 端点，还是扩展现有 `/status` 返回 scenes 摘要？后端 `load_archived_scene(theme, scene_num)` 函数已存在，可包装为 API
   - Recommendation: 新增 `GET /drama/scenes` 返回场景摘要列表（scene_number + title + description 前 50 字），新增 `GET /drama/scenes/{scene_number}` 返回完整场景。这是最干净的方案，不破坏现有 `/status` 契约

2. **删除戏剧 API 缺口**
   - What we know: D-08 要求删除操作，后端无 `DELETE` 端点
   - What's unclear: 后端是否已有删除功能？`list_dramas()` 扫描文件夹，删除可能只需删除文件夹
   - Recommendation: 新增 `DELETE /drama/{folder}` 端点。如果后端不方便修改，Phase 17 可暂时隐藏删除功能，Phase 18 补齐

3. **加载保存名来源**
   - What we know: `POST /drama/load` 需要 `save_name` 参数；`/drama/list` 返回的 drama 项中部分有 `snapshots` 字段
   - What's unclear: "加载"操作是加载戏剧的某个保存点（需要保存名），还是恢复整个戏剧？用户从列表点"加载"时，保存名从哪来？
   - Recommendation: 列表卡片三点菜单的"加载"实际应为"恢复戏剧"（调用 `/drama/load` 传入 `save_name = theme`），不需要用户输入保存名。"加载存档"是更高级功能可推迟

4. **WS narration/dialogue 事件中是否包含文本内容**
   - What we know: `event_mapper.py` 的 `_extract_call_data` 对 narration 只返回 `{"tool": "director_narrate"}`，对 dialogue 返回 `{"actor_name": "xxx", "tool": "actor_speak"}`。实际文本内容在 `function_response` 中
   - What's unclear: `function_response` 返回的数据中是否有 `text`/`content` 字段？需要验证实际 ADK 事件流
   - Recommendation: `_extract_response_data` 对大部分事件类型返回空 dict，narration/dialogue 的实际文本内容可能通过 `end_narration` 事件或 `final_response` 传递。需要测试验证，或在后端 event_mapper 中扩展 narration/dialogue 的 data 提取逻辑

5. **Typing 事件与实际内容的关系**
   - What we know: `typing` 事件在 `function_call` 到达时触发（D-14），实际内容在 `function_response` 后到达
   - What's unclear: typing 指示器应在收到下一条 narration/dialogue 事件时关闭，还是等到 `function_response`？
   - Recommendation: 收到非 `typing` 类型的内容事件时自动关闭 typing 指示器。这是最简单可靠的逻辑

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Android SDK | 构建验证 | ✗ | — | 需安装（同 Phase 16 限制） |
| JDK 17 | AGP 8.7 | ✗ | — | 同 Phase 16 |
| Kotlin 2.1.0 | 编译 | ✓ | via Gradle | — |
| FastAPI 后端 | API 调用 | ✗ | — | 需启动 `uv run python -m app.api.main` |
| Android 模拟器/设备 | UI 测试 | ✗ | — | 需要 Android Studio 或 adb |

**Missing dependencies with no fallback:**
- FastAPI 后端：需手动启动才能测试 API 调用。纯代码编写不需要，但验证需要
- Android SDK + 模拟器：构建和运行 Android App 必需

**Missing dependencies with fallback:**
- JDK 20 替代 JDK 17：与 Phase 16 相同，通常兼容

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | JUnit 5 + Mockito + Kotlin Coroutines Test |
| Config file | 无 — 在 build.gradle.kts 配置 |
| Quick run command | `./gradlew test` |
| Full suite command | `./gradlew testDebugUnitTest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| APP-02 | 创建戏剧 + STORM 进度 | unit | `./gradlew test --tests DramaCreateViewModelTest` | ❌ Wave 0 |
| APP-03 | 戏剧列表 + 加载/删除 | unit | `./gradlew test --tests DramaListViewModelTest` | ❌ Wave 0 |
| APP-04 | 主屏幕 WS 实时更新 | unit | `./gradlew test --tests DramaDetailViewModelTest` | ❌ Wave 0 |
| APP-05 | 命令输入栏 /next /action /speak /end | unit | `./gradlew test --tests CommandTypeTest` | ❌ Wave 0 |
| APP-06 | 场景历史浏览 | unit | `./gradlew test --tests DramaDetailViewModelTest` | ❌ Wave 0 |
| APP-12 | 保存/加载确认 | unit | `./gradlew test --tests DramaDetailViewModelTest` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `./gradlew test`
- **Per wave merge:** `./gradlew testDebugUnitTest`
- **Phase gate:** Full suite green + 手动验证 UI 交互

### Wave 0 Gaps
- [ ] `app/src/test/` — 测试目录需创建（Phase 16 未创建测试）
- [ ] JUnit 5 + Mockito + Coroutines Test 依赖需添加到 build.gradle.kts
- [ ] `DramaCreateViewModelTest` — 创建流程 + STORM 进度
- [ ] `DramaListViewModelTest` — 列表加载 + 删除操作
- [ ] `DramaDetailViewModelTest` — WS 事件处理 + 命令发送 + 场景历史
- [ ] `CommandTypeTest` — 命令解析逻辑

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Token 认证 via AuthInterceptor（Phase 16 已实现） |
| V3 Session Management | yes | WS token 通过 query param（Phase 16 已实现） |
| V4 Access Control | no | 单用户模式，无角色区分 |
| V5 Input Validation | yes | 主题输入长度校验（后端 max_length=200），命令输入 sanitize |
| V6 Cryptography | partial | Token 加密存储（Phase 16 EncryptedSharedPreferences） |

### Known Threat Patterns for Android + Network

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Command injection via free text | Tampering | 后端 Runner 使用 ADK 安全框架，不直接执行 shell 命令 |
| XSS-like via drama content | Information Disclosure | Compose Text 组件不解析 HTML，纯文本渲染天然安全 |
| CSRF via WebSocket | Tampering | WS token 认证（AUTH-03），非浏览器场景无 CSRF 风险 |
| Accidental data loss | Tampering | 删除操作 AlertDialog 确认（D-08），防误删 |

## Sources

### Primary (HIGH confidence)
- `app/api/models.py` — 后端 Pydantic 请求/响应模型（API 契约）
- `app/api/routers/commands.py` — 8 个命令端点的路径和请求体
- `app/api/routers/queries.py` — 6 个查询端点的路径和响应格式
- `app/api/event_mapper.py` — 18 种 WS 事件映射规则
- `app/api/ws_manager.py` — ConnectionManager + replay buffer + heartbeat
- `app/state_manager.py:771-818` — `list_dramas()` 返回字段确认
- `android/app/src/main/java/com/drama/app/` — Phase 16 完整 Android 骨架源码
- `.planning/phases/16-android-foundation/16-RESEARCH.md` — Phase 16 技术栈和架构决策

### Secondary (MEDIUM confidence)
- developer.android.com — Compose 组件 API（ModalBottomSheet、SnackbarHost、Chip）
- Material3 1.4.0 release notes — 组件稳定性状态

### Tertiary (LOW confidence)
- WS narration/dialogue 事件的 data 字段中是否包含文本内容 — 需运行时验证 [ASSUMED]
- `DELETE /drama/{folder}` 后端是否已有 — 需验证 [ASSUMED: 不存在]
- `POST /drama/load` 传入 `save_name = theme` 是否能恢复戏剧 — 需验证 [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — 所有库已在 Phase 16 验证安装
- Architecture: HIGH — MVVM + Hilt + Repository 模式沿用 Phase 16
- API 契约: HIGH — 直接读取后端源码确认，但 WS 事件 data 内容需运行时验证
- Pitfalls: HIGH — 基于 Android Compose 开发经验和项目代码分析
- 场景历史 API: MEDIUM — 后端需配合新增端点，具体方案待确认

**Research date:** 2026-04-16
**Valid until:** 2026-05-16（Android 生态版本更新较快，30 天有效期）
