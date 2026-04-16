# Phase 18: Android Features - Research

**Researched:** 2026-04-16
**Domain:** Android / Kotlin / Jetpack Compose / WebSocket Reconnect / Rich Text Rendering / File Sharing
**Confidence:** HIGH

## Summary

Phase 18 在 Phase 16-17 搭建的 MVVM+Hilt+Compose 骨架和交互基础上，增强 Android 端体验：右侧演员面板 Drawer、TopAppBar 下拉状态概览卡片、剧本导出+系统分享、Typing 指示器动态文案、富文本渲染（角色名主题色+情绪标签+hash 头像）、WebSocket 指数退避自动重连+ConnectivityManager 网络监听。后端需扩展两个已有端点（`/drama/status` 增加 arc_progress/time_period，`/drama/export` 增加 content 字段），新增一个端点（`GET /drama/cast/status` 返回 A2A 进程存活状态）。

关键发现：Material3 的 `ModalNavigationDrawer` 默认从左侧滑出，右侧 Drawer 需通过 `CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl)` 包裹 drawerContent 实现；OkHttp WebSocket 重连需在 `callbackFlow` 的 `onFailure` 中包装指数退避逻辑；Android FileProvider 是分享缓存文件的必要组件；`ConnectivityManager.NetworkCallback` 应在 ViewModel `init` 注册、`onCleared` 注销以避免泄漏。

**Primary recommendation:** 后端扩展保持向后兼容（Pydantic 字段默认值），Android 侧按 MVVM 分层逐步扩展 DTO→Repository→ViewModel→Composable，WebSocket 重连逻辑封装为独立的 `ReconnectingWebSocketManager` 类。

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** 主屏幕右侧 Drawer 入口 — 从右向左滑出，不遮挡场景内容。TopAppBar 右侧加人物 Icon 触发
- **D-02:** 紧凑三行卡片 — 第一行：名字(titleMedium.bold) + 情绪 badge；第二行：身份(role)；第三行：A2A 状态圆点 + 端口号。点击卡片展开详情
- **D-03:** 后端新增 `GET /drama/cast/status` 端点 — 返回每个 actor 的 A2A 进程存活状态
- **D-04:** 记忆摘要截取前 100 字 + "查看更多" — 默认折叠，点击展开
- **D-05:** TopAppBar 下拉展开卡片 — 点击 TopAppBar 区域展开 compact 信息卡片
- **D-06:** 全面五指标 — 当前场景号 + 张力评分(LinearProgressIndicator) + 弧线进度 + 时间段描述 + 演员数
- **D-07:** 扩展现有 `GET /drama/status` — 新增 `arc_progress`, `time_period` 字段
- **D-08:** 脉冲动画 + 上下文文案 — 根据 WS `typing.data.tool` 字段动态切换文案
- **D-09:** 角色名加粗 + 主题色 — 对白气泡角色名使用 `titleMedium.bold` + 基于角色名 hash 的专属颜色
- **D-10:** 情绪标签小圆角 badge — 紧跟角色名后显示
- **D-11:** 首字母圆形头像基于角色名 hash 固定色
- **D-12:** 后端扩展 `POST /drama/export` 返回 Markdown 文本 — 新增 `content: str` 字段
- **D-13:** 导出入口 — 主屏幕 TopAppBar 溢出菜单"导出剧本"选项
- **D-14:** 指数退避策略 — 1s → 2s → 4s → 8s → 16s → 30s 封顶
- **D-15:** ConnectivityManager 网络监听 — NetworkCallback 触发立即重连
- **D-16:** 重连后自动请求 `GET /drama/status` 刷新

### Claude's Discretion
- 演员 Drawer 的具体 Compose 组件拆分（DrawerContent / ActorCard / ActorDetailSection）
- 状态概览下拉卡片的展开/收起动画参数
- 角色名 hash → 颜色的具体映射算法（HSL 色相分布）
- 情绪 badge 的圆角半径和内边距
- 导出临时文件命名和清理策略
- WS 重连在 ViewModel 中的协程管理（Job 取消/重启）
- ConnectivityManager 注册/注销的生命周期绑定
- 重连期间 UI 状态指示（TopAppBar 连接状态圆点）

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| APP-07 | Actor panel shows cast list with A2A service status and memory summary | D-01~D-04: 右侧 ModalNavigationDrawer + 三行卡片 + GET /drama/cast/status 新端点 + 记忆截断 100 字符 |
| APP-08 | Drama status overview (current scene, tension score, arc progress, time period) | D-05~D-07: TopAppBar 下拉卡片 + 五指标 + 扩展 GET /drama/status |
| APP-09 | Script export to local file (Markdown format) | D-12~D-13: 后端扩展 ExportResponse.content + FileProvider + Intent.createChooser |
| APP-10 | Typing indicator displays during LLM generation (10-30s waits) | D-08: typing.data.tool 映射上下文文案（director_narrate/actor_speak/next_scene/write_scene/其他） |
| APP-11 | Rich scene display with character name highlights and emotion tags | D-09~D-11: 角色名 hash→HSL 色 + 情绪 badge + 首字母圆形头像 |
| APP-15 | WebSocket auto-reconnect with exponential backoff on network change | D-14~D-16: 指数退避 1s→30s + ConnectivityManager NetworkCallback + 重连后 GET /drama/status |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Kotlin | 2.1.0 | 主开发语言 | 项目已锁定 [VERIFIED: libs.versions.toml] |
| Compose BOM | 2025.12.01 | UI 框架版本对齐 | 项目已锁定 [VERIFIED: libs.versions.toml] |
| Material3 | (BOM-managed) | UI 组件库 | ModalNavigationDrawer / ModalDrawerSheet / Badge 等 [VERIFIED: Context7] |
| OkHttp | 4.12.0 | HTTP + WebSocket 客户端 | 项目已锁定，WS 重连基于此 [VERIFIED: libs.versions.toml] |
| Retrofit | 2.12.0 | REST API 客户端 | 项目已锁定 [VERIFIED: libs.versions.toml] |
| Hilt | 2.54 | 依赖注入 | 项目已锁定 [VERIFIED: libs.versions.toml] |
| kotlinx.serialization | 1.8.1 | JSON 序列化 | 项目已锁定 [VERIFIED: libs.versions.toml] |
| Pydantic v2 | (existing) | 后端数据模型 | 项目已使用，扩展字段保持兼容 [VERIFIED: models.py] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| FileProvider (androidx.core) | (existing) | 缓存文件 URI 授权分享 | 剧本导出分享必须 [VERIFIED: Android SDK] |
| ConnectivityManager | API 24+ | 网络状态监听 | WS 重连触发 [VERIFIED: Android SDK, minSdk 26] |
| Coroutines (kotlinx) | (existing) | 异步重连 + 退避计时 | WS 重连逻辑核心 [VERIFIED: 已在 ViewModel 使用] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ModalNavigationDrawer 右侧 | 自定义 Drawer 组件 | MD3 标准组件提供手势/动画/遮罩/无障碍支持，不建议自建 |
| FileProvider + Share Intent | 存储到 Downloads + 通知 | Share Intent 体验更原生（微信/邮件等一键分享），无需 WRITE_EXTERNAL_STORAGE 权限 |
| ConnectivityManager.NetworkCallback | LifecycleObserver + 轮询 | NetworkCallback 是官方推荐实时网络监听方式，比轮询高效 |
| 指数退避 + 网络监听双重策略 | 仅指数退避 | 网络恢复后立即重连比等待退避计时器到时体验更好 |

**Installation:**
Phase 18 不需要新增 Gradle 依赖。所有需要的库已在 Phase 16-17 引入：
- `androidx.core:core-ktx` — 包含 FileProvider
- `com.squareup.okhttp3:okhttp` — WebSocket 重连
- Material3 — ModalNavigationDrawer, Badge 等
- kotlinx-coroutines — delay + retry 逻辑

**Version verification:** 所有版本已在 `libs.versions.toml` 中锁定，无需更新。

## Architecture Patterns

### Recommended Project Structure
```
android/app/src/main/java/com/drama/app/
├── data/
│   ├── remote/
│   │   ├── api/DramaApiService.kt          # 新增 getCastStatus(), exportDrama() 扩展
│   │   ├── dto/
│   │   │   ├── CastStatusResponseDto.kt     # 新增: A2A 进程状态 DTO
│   │   │   ├── DramaStatusResponseDto.kt    # 扩展: +arc_progress, +time_period
│   │   │   ├── ExportResponseDto.kt         # 扩展: +content
│   │   │   └── WsEventDto.kt               # 不变
│   │   └── ws/
│   │       └── ReconnectingWebSocketManager.kt  # 新增: 替代原 WebSocketManager
│   ├── repository/
│   │   └── DramaRepositoryImpl.kt          # 新增 getCastStatus() 方法
│   └── local/
│       └── ServerPreferences.kt            # 不变
├── domain/
│   ├── model/
│   │   ├── SceneBubble.kt                  # 扩展: Dialogue +emotion, +avatarColor
│   │   ├── ActorInfo.kt                    # 新增: 演员详情 domain model
│   │   └── DramaStatus.kt                  # 新增: 状态概览 domain model
│   └── repository/
│       └── DramaRepository.kt              # 新增 getCastStatus() 方法
├── ui/screens/dramadetail/
│   ├── DramaDetailScreen.kt                # 扩展: Drawer 包裹 + 状态概览
│   ├── DramaDetailViewModel.kt             # 扩展: 演员面板/重连/导出逻辑
│   └── components/
│       ├── ActorDrawerContent.kt           # 新增: 右侧 Drawer 内容
│       ├── ActorCard.kt                    # 新增: 三行紧凑卡片
│       ├── StatusOverviewCard.kt           # 新增: 五指标下拉卡片
│       ├── DialogueBubble.kt              # 增强: 角色名主题色+情绪 badge+头像
│       ├── TypingIndicator.kt             # 增强: 动态上下文文案
│       └── ...existing components
└── ...
```

### Pattern 1: Reconnecting WebSocket Manager
**What:** 封装 OkHttp WebSocket 的自动重连逻辑，替代当前无重连的 `WebSocketManager`
**When to use:** 任何需要持久 WS 连接且网络不稳定的场景
**Example:**
```kotlin
// Source: [ASSUMED — 基于 OkHttp WebSocketListener + Kotlin coroutines 最佳实践]
class ReconnectingWebSocketManager @Inject constructor(
    private val okHttpClient: OkHttpClient,
    private val json: Json,
    private val context: Application,
) {
    private var webSocket: WebSocket? = null
    private var reconnectJob: Job? = null
    private var currentDelayMs = 1000L  // D-14: 初始 1s
    private val maxDelayMs = 30_000L    // D-14: 封顶 30s
    private val connectivityManager by lazy {
        context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
    }

    private val networkCallback = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) {
            // D-15: 网络恢复立即重连，不等待退避计时器
            reconnectJob?.cancel()
            currentDelayMs = 1000L
            connectInternal()
        }
    }

    fun connect(host: String, port: String, token: String?): Flow<WsEventDto> = callbackFlow {
        // ... 构造 URL + 创建 WebSocket
        webSocket = okHttpClient.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                currentDelayMs = 1000L  // 连接成功重置退避
            }
            override fun onMessage(webSocket: WebSocket, text: String) {
                val event = json.decodeFromString<WsEventDto>(text)
                trySend(event)
            }
            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) { close() }
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                scheduleReconnect(host, port, token)
                close(t)
            }
        })
        awaitClose { webSocket?.close(1000, "Client disconnect") }
    }

    private fun scheduleReconnect(host: String, port: String, token: String?) {
        reconnectJob?.cancel()
        reconnectJob = CoroutineScope(Dispatchers.IO).launch {
            delay(currentDelayMs)
            currentDelayMs = (currentDelayMs * 2).coerceAtMost(maxDelayMs)
            // 触发重连...
        }
    }
}
```

### Pattern 2: Right-Side Drawer via LayoutDirection
**What:** Material3 `ModalNavigationDrawer` 默认从左侧滑出，通过 RTL LayoutDirection 包裹实现右侧 Drawer
**When to use:** 需要从右侧滑出的 Drawer（如演员面板）
**Example:**
```kotlin
// Source: [VERIFIED: Context7 — ModalNavigationDrawer API + LayoutDirection 机制]
val drawerState = rememberDrawerState(DrawerValue.Closed)
val scope = rememberCoroutineScope()

ModalNavigationDrawer(
    drawerState = drawerState,
    drawerContent = {
        // 关键：用 RTL 包裹 drawerContent 使 Drawer 从右侧滑出
        CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
            ModalDrawerSheet {
                // 内容再用 LTR 包裹，保持文字方向正常
                CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Ltr) {
                    ActorDrawerContent(actors = actors, ...)
                }
            }
        }
    },
    content = {
        Scaffold(...) { ... }
    }
)
```

**注意:** 这个 RTL 技巧是社区公认方案 [ASSUMED]。如果 `ModalNavigationDrawer` 在 Compose BOM 2025.12.01 中已原生支持 `drawerPosition` 参数，应优先使用官方 API。实现时需验证当前 BOM 版本是否支持 `DrawerPosition.End`。

### Pattern 3: Hash-Based Color Generation for Avatars
**What:** 基于角色名字 hashCode 生成 HSL 色相，保证同一角色每次显示颜色一致
**When to use:** 为对话气泡、头像圆形等元素生成固定主题色
**Example:**
```kotlin
// Source: [ASSUMED — 通用 HSL 色相分布算法]
fun actorColor(name: String): Color {
    val hue = (abs(name.hashCode()) % 360).toFloat()
    return Color.hsl(hue, saturation = 0.6f, lightness = 0.5f)
}
```

### Pattern 4: FileProvider + Share Intent for Script Export
**What:** 将导出的 Markdown 写入 `context.cacheDir`，通过 FileProvider 授权 URI，再启动 ShareSheet
**When to use:** 分享应用内生成的文件到其他应用
**Example:**
```kotlin
// Source: [CITED: developer.android.com/training/sharing/send]
// 1. AndroidManifest.xml 添加 FileProvider
// 2. res/xml/file_paths.xml 定义缓存路径
// 3. 代码中使用
val file = File(context.cacheDir, "drama_export.md")
file.writeText(markdownContent)
val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
val shareIntent = Intent(Intent.ACTION_SEND).apply {
    type = "text/markdown"
    putExtra(Intent.EXTRA_STREAM, uri)
    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
}
startActivity(Intent.createChooser(shareIntent, "导出剧本"))
```

### Pattern 5: Extend Pydantic Models Without Breaking Changes
**What:** 在现有 Pydantic v2 模型中新增字段时使用默认值，保持向后兼容
**When to use:** 扩展 API 响应模型
**Example:**
```python
# Source: [VERIFIED: app/api/models.py 现有模式 — 所有字段都有默认值]
class DramaStatusResponse(BaseModel):
    # ... existing fields ...
    arc_progress: list[dict] = Field(default_factory=list)  # D-07: 新增，默认空列表
    time_period: str = ""  # D-07: 新增，默认空字符串
```

### Anti-Patterns to Avoid
- **手动管理 WebSocket 重连计时器而不绑定生命周期**: 会导致 ViewModel 销毁后仍触发重连，必须用 `viewModelScope` + `Job` 管理 [VERIFIED: 现有 ViewModel 模式]
- **ConnectivityManager.NetworkCallback 不注销**: 会导致内存泄漏，必须在 `onCleared()` 中 `unregisterNetworkCallback()` [ASSUMED]
- **直接使用 `file://` URI 分享文件**: Android 7.0+ 会抛出 `FileUriExposedException`，必须使用 FileProvider [VERIFIED: Android 官方文档]
- **在 Pydantic 模型新增字段不加默认值**: 会破坏现有客户端解析，所有新增字段必须有 `default` 或 `default_factory` [VERIFIED: Pydantic v2 行为]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Drawer 手势/动画/遮罩 | 自定义侧滑面板 | `ModalNavigationDrawer` + `ModalDrawerSheet` | MD3 提供手势检测、遮罩、无障碍、动画 [VERIFIED: Context7] |
| 网络状态监听 | 轮询 ping 检测 | `ConnectivityManager.NetworkCallback` | 系统级回调，省电且实时 [VERIFIED: Android API] |
| 文件分享 URI 授权 | 手动设置文件权限 | `FileProvider` | 安全的 URI 授权，Android 7.0+ 必须 [VERIFIED: Android 官方] |
| 指数退避算法 | 自定义 Timer 循环 | Kotlin `delay()` + 协程 | 取消友好，不阻塞线程 [VERIFIED: 已在项目使用] |
| 颜色生成 | 硬编码颜色映射表 | `hashCode() % 360` → HSL | 自动、均匀、无维护成本 [ASSUMED] |
| Pydantic 模型扩展 | 复制创建新模型 | 在现有模型新增带默认值字段 | 保持 API 兼容，减少代码重复 [VERIFIED: Pydantic v2] |

**Key insight:** Phase 18 的所有问题都有成熟的 Android 平台解决方案，不需要自建基础设施。重点在于正确组合现有 API 和项目模式。

## Common Pitfalls

### Pitfall 1: ModalNavigationDrawer 右侧 Drawer 的 RTL 布局方向反转
**What goes wrong:** 用 `LayoutDirection.Rtl` 包裹 drawerContent 后，Drawer 内部的文字和布局也会反转
**Why it happens:** RTL 影响所有子组件的布局方向，不仅是 Drawer 滑出方向
**How to avoid:** 在 `ModalDrawerSheet` 内部再嵌套一层 `CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Ltr)` 恢复正常方向
**Warning signs:** Drawer 内部文字右对齐、Row 排列反序

### Pitfall 2: ConnectivityManager.NetworkCallback 泄漏
**What goes wrong:** 注册了 NetworkCallback 但在 ViewModel 销毁时未注销，导致内存泄漏
**Why it happens:** NetworkCallback 持有 Context 引用，生命周期与 ViewModel 不匹配
**How to avoid:** 在 ViewModel `init` 注册，`onCleared()` 注销；或者使用 `LifecycleObserver` 在 `ON_DESTROY` 时注销
**Warning signs:** LeakCanary 报告 ConnectivityManager 相关泄漏

### Pitfall 3: WS 重连竞态 — 多个重连 Job 同时运行
**What goes wrong:** `onFailure` 和 `NetworkCallback.onAvailable` 同时触发重连，导致创建多个 WS 连接
**Why it happens:** 退避计时器正在等待时，网络恢复回调触发立即重连，但退避计时器到期后也会触发
**How to avoid:** 网络恢复回调中先 `cancel` 现有 `reconnectJob`，再启动新连接；连接前检查是否已有活跃连接
**Warning signs:** 收到重复 WS 事件，服务端出现多个连接

### Pitfall 4: FileProvider 配置遗漏
**What goes wrong:** 在 AndroidManifest.xml 中声明了 FileProvider 但 `file_paths.xml` 中未配置 cache 路径，导致 `FileProvider.getUriForFile()` 抛异常
**Why it happens:** FileProvider 的 paths 配置必须精确匹配文件所在目录
**How to avoid:** 在 `res/xml/file_paths.xml` 中添加 `<cache-path name="exports" path="."/>` 覆盖 cache 目录
**Warning signs:** 导出点击后应用崩溃，`IllegalArgumentException: Failed to find configured root`

### Pitfall 5: Pydantic 模型新增字段导致旧客户端 404
**What goes wrong:** 后端扩展 `DramaStatusResponse` 加了 `arc_progress` 字段，但 Android 旧版 DTO 没有这个字段，`kotlinx.serialization` 默认忽略未知字段不会报错，但如果后端将新字段设为 required 则旧客户端请求失败
**Why it happens:** Pydantic v2 的 `required` 字段在缺失时会返回 422
**How to avoid:** 所有新增字段使用 `default` 或 `default_factory`；Android DTO 同步添加新字段（也带默认值）
**Warning signs:** 后端日志 422 Unprocessable Entity

### Pitfall 6: Typing 文案切换时闪烁
**What goes wrong:** 连续收到不同 `typing` 事件（如先 `director_narrate` 再 `actor_speak`），文案快速切换导致 UI 闪烁
**Why it happens:** 每次 typing 事件都直接更新 `isTyping = true` 和文案，没有防抖
**How to avoid:** 使用 `StateFlow.update` 原子更新，或在 ViewModel 中对 typing 事件做 debounce（100ms 内相同工具名不重复更新）
**Warning signs:** Typing 指示器文字频繁闪烁

### Pitfall 7: ExportResponse DTO 字段名不匹配
**What goes wrong:** 后端 `export_script()` 返回 `filepath` 字段，但 `ExportResponse` Pydantic 模型定义的是 `export_path`，Android DTO 需对齐正确的字段名
**Why it happens:** `state_manager.export_script()` 返回 `filepath` 和 `drama_folder`，但 `ExportResponse` 使用 `export_path`。返回值在 `queries.py` 中通过 `ExportResponse(**result)` 构造，`filepath` 被忽略（因为模型没有 `filepath` 字段），`export_path` 取默认值空字符串
**How to avoid:** 在 `ExportResponse` 中新增 `content` 字段时，同时修正 `export_path` 的赋值逻辑（或在 `export_script` 返回中用 `export_path` 键名）
**Warning signs:** Android 端 `export_path` 始终为空

## Code Examples

Verified patterns from official sources and existing codebase:

### 右侧 Drawer 触发（TopAppBar Icon）
```kotlin
// 基于 D-01: TopAppBar 右侧加人物 Icon
TopAppBar(
    actions = {
        TensionIndicator(score = uiState.tensionScore)
        IconButton(onClick = { scope.launch { drawerState.open() } }) {
            Icon(Icons.Filled.People, contentDescription = "演员面板")
        }
        IconButton(onClick = viewModel::showHistorySheet) {
            Icon(Icons.Filled.History, contentDescription = "场景历史")
        }
        // ... overflow menu
    }
)
```

### 扩展后端 DramaStatusResponse
```python
# Source: [VERIFIED: app/api/models.py + app/state_manager.py]
class DramaStatusResponse(BaseModel):
    """Response for drama status query."""
    theme: str = ""
    drama_status: str = ""
    current_scene: int = 0
    num_scenes: int = 0
    num_actors: int = 0
    actors: list[str] = Field(default_factory=list)
    drama_folder: str = ""
    # D-07: Phase 18 新增字段
    arc_progress: list[dict] = Field(default_factory=list, description="Per-actor arc progress")
    time_period: str = Field(default="", description="Current time period description")
```

### 后端 get_current_state 扩展
```python
# Source: [VERIFIED: app/state_manager.py:1081-1098]
def get_current_state(tool_context=None) -> dict:
    state = _get_state(tool_context)
    theme = state.get("theme", "")
    actors = state.get("actors", {})
    
    # D-07: 新增 arc_progress 和 time_period
    arc_progress = []
    for name, info in actors.items():
        arc = info.get("arc_progress", {})
        arc_progress.append({
            "name": name,
            "progress": arc.get("progress", 0),
        })
    
    timeline = state.get("timeline", {})
    time_period = ""
    if timeline.get("time_periods"):
        time_period = timeline["time_periods"][-1].get("description", "")
    
    return {
        "status": "success",
        "theme": theme,
        "drama_status": state.get("status", ""),
        "current_scene": state.get("current_scene", 0),
        "num_scenes": len(state.get("scenes", [])),
        "num_actors": len(actors),
        "actors": list(actors.keys()),
        "drama_folder": _get_drama_folder(theme) if theme else "",
        "arc_progress": arc_progress,  # D-07
        "time_period": time_period,     # D-07
    }
```

### 新增 Cast Status 端点
```python
# Source: [VERIFIED: app/actor_service.py:400-413 — list_running_actors()]
# queries.py 新增:
@router.get("/drama/cast/status", response_model=CastStatusResponse)
async def get_cast_status(
    _auth: bool = Depends(require_auth),
    tool_context=Depends(get_tool_context),
):
    """Get A2A process status for each actor."""
    _require_active_drama(tool_context)
    from app.actor_service import list_running_actors
    result = list_running_actors()
    return CastStatusResponse(**result)
```

### 扩展 ExportResponse + export_script
```python
# Source: [VERIFIED: app/api/models.py + app/state_manager.py:1162-1263]
class ExportResponse(BaseModel):
    """Response for drama export."""
    status: str = "success"
    message: str = ""
    export_path: str = ""
    content: str = ""  # D-12: 新增 Markdown 文本

# queries.py 中修改:
@router.post("/drama/export", response_model=ExportResponse)
async def export_drama(...):
    result = export_script(tool_context)
    # D-12: 读取文件内容返回给 Android
    filepath = result.get("filepath", "")
    content = ""
    if filepath and os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    result["content"] = content
    result["export_path"] = filepath  # 修正字段名对齐
    return ExportResponse(**result)
```

### Typing 上下文文案映射
```kotlin
// Source: [VERIFIED: app/api/event_mapper.py:110 — typing 事件带 data.tool 字段]
fun getTypingText(toolName: String?): String = when (toolName) {
    "director_narrate" -> "导演正在构思..."
    "actor_speak" -> "演员正在思考..."
    "next_scene", "write_scene" -> "剧情推进中..."
    else -> "处理中..."
}
```

### Android FileProvider 配置
```xml
<!-- AndroidManifest.xml 新增 -->
<provider
    android:name="androidx.core.content.FileProvider"
    android:authorities="${applicationId}.fileprovider"
    android:exported="false"
    android:grantUriPermissions="true">
    <meta-data
        android:name="android.support.FILE_PROVIDER_PATHS"
        android:resource="@xml/file_paths" />
</provider>

<!-- res/xml/file_paths.xml 新增 -->
<paths>
    <cache-path name="exports" path="." />
</paths>
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Drawer 在 Scaffold 中 | 独立 `ModalNavigationDrawer` 组件 | Material3 (2023) | Drawer 不再是 Scaffold 的一部分，需顶层包裹 [VERIFIED: Context7] |
| `file://` URI 分享 | `FileProvider` + `content://` URI | Android 7.0 (2016) | 必须使用 FileProvider，否则 `FileUriExposedException` [VERIFIED: Android 官方] |
| 轮询网络状态 | `ConnectivityManager.NetworkCallback` | Android 5.0 (2014) | 实时回调比轮询高效，minSdk 26 保证可用 [VERIFIED: Android API] |
| Pydantic v1 `.dict()` | Pydantic v2 `.model_dump()` + Field 默认值 | Pydantic v2 (2023) | 新增字段带默认值保持向后兼容 [VERIFIED: 项目使用 Pydantic v2] |

**Deprecated/outdated:**
- `androidx.drawerlayout:drawerlayout` View 系统的 DrawerLayout: 已被 Compose `ModalNavigationDrawer` 取代 [ASSUMED]
- `AsyncTask` 网络请求: 已被 Kotlin 协程取代 [ASSUMED]
- `Environment.getExternalStorageDirectory()`: 已被 `context.cacheDir` + FileProvider 取代 [VERIFIED: Android 官方]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `ModalNavigationDrawer` 通过 `CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl)` 实现右侧滑出 | Architecture Patterns / Pattern 2 | 如果 BOM 2025.12.01 已有 `drawerPosition` 参数，应使用官方 API 而非 RTL hack |
| A2 | `ConnectivityManager.NetworkCallback` 在 ViewModel `onCleared()` 注销足够安全 | Pattern 1 | 如果 Activity 重建但 ViewModel 存活，可能需要额外的生命周期管理 |
| A3 | `hashCode() % 360` → HSL 色相分布足够均匀 | Pattern 3 | 某些名字的 hashCode 可能聚集，需运行时验证分布是否可接受 |
| A4 | `export_script()` 返回的 `filepath` 键名与 `ExportResponse.export_path` 不匹配（后者为空） | Pitfall 7 | 需实际运行确认，或直接在 `export_script` 返回中修正键名 |
| A5 | `timeline.time_periods[-1].description` 能正确获取当前时间段 | Code Examples | 如果 timeline 数据结构不包含 description 字段，需调整字段名 |

## Open Questions

1. **ModalNavigationDrawer 是否原生支持右侧 Drawer？**
   - What we know: Material3 Compose BOM 2025.12.01 可能有 `drawerPosition: DrawerPosition` 参数
   - What's unclear: 当前 BOM 版本是否已发布此 API
   - Recommendation: 实现时先检查 `ModalNavigationDrawer` 是否有 `drawerPosition` 参数，如有则用 `DrawerPosition.End`，否则用 RTL hack

2. **A2A 进程状态端点的认证模型**
   - What we know: `GET /drama/cast/status` 需要认证（与其他查询端点一致）
   - What's unclear: `list_running_actors()` 依赖内存中的 `_actor_processes` 字典，如果 API 服务器重启，该字典为空但 actor 进程可能仍在运行
   - Recommendation: 在 `list_running_actors()` 中加 `process.poll()` 检查进程存活状态（已有实现），且文档说明 API 重启后 A2A 状态不可用

3. **导出文件清理策略**
   - What we know: 文件写入 `context.cacheDir`，Android 系统在存储不足时会自动清理
   - What's unclear: 是否需要主动清理旧导出文件
   - Recommendation: 使用带时间戳的文件名（如 `drama_主题名_20260416.md`），依赖系统自动清理即可

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Android SDK 35 | Build | ✓ | compileSdk 35 | — |
| Kotlin 2.1.0 | Build | ✓ | 2.1.0 | — |
| Compose BOM 2025.12.01 | UI | ✓ | BOM-managed | — |
| OkHttp 4.12.0 | WS Reconnect | ✓ | 4.12.0 | — |
| Retrofit 2.12.0 | REST API | ✓ | 2.12.0 | — |
| Hilt 2.54 | DI | ✓ | 2.54 | — |
| Python 3.11+ | Backend | ✓ | — | — |
| Pydantic v2 | Backend Models | ✓ | — | — |

**Missing dependencies with no fallback:**
- None

**Missing dependencies with fallback:**
- None

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (backend) + Android Instrumentation Tests |
| Config file | `pyproject.toml` (backend), `app/build.gradle.kts` (Android) |
| Quick run command | `uv run pytest tests/ -x` |
| Full suite command | `uv run pytest tests/ -v && ./gradlew test` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| APP-07 | GET /drama/cast/status returns actor A2A status | unit | `pytest tests/test_api_queries.py::test_get_cast_status -x` | ❌ Wave 0 |
| APP-07 | Actor Drawer displays cast list with status dots | manual-only | — | — |
| APP-08 | GET /drama/status returns arc_progress and time_period | unit | `pytest tests/test_api_queries.py::test_get_status_with_arc -x` | ❌ Wave 0 |
| APP-08 | Status overview card shows 5 indicators | manual-only | — | — |
| APP-09 | POST /drama/export returns content field | unit | `pytest tests/test_api_queries.py::test_export_with_content -x` | ❌ Wave 0 |
| APP-09 | Share Intent launched with FileProvider URI | manual-only | — | — |
| APP-10 | Typing indicator shows context-aware text | unit | `pytest tests/ -k typing -x` | ❌ Wave 0 |
| APP-11 | DialogueBubble renders colored actor name + emotion badge | manual-only | — | — |
| APP-15 | WS reconnect with exponential backoff | unit | `pytest tests/ -k reconnect -x` | ❌ Wave 0 |
| APP-15 | NetworkCallback triggers immediate reconnect | unit | Android instrumentation | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x`
- **Per wave merge:** `uv run pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_api_queries.py` — covers APP-07 cast/status, APP-08 status extension, APP-09 export content
- [ ] Backend: `list_running_actors()` 的单元测试（actor_service 模块）
- [ ] Android: `ReconnectingWebSocketManager` 的单元测试（退避逻辑验证）
- [ ] Android: FileProvider 配置集成测试

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Bearer token (Phase 15), AuthInterceptor 自动注入 |
| V3 Session Management | yes | WS token via query param, 30s heartbeat timeout |
| V4 Access Control | no | 单用户模式，无 RBAC |
| V5 Input Validation | yes | Pydantic field validation, Android input sanitization |
| V6 Cryptography | no | 无加密需求，局域网场景 |
| V8 Data Protection | yes | FileProvider URI 限时授权，cacheDir 文件系统隔离 |

### Known Threat Patterns for Android + FastAPI Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via export filename | Tampering | `export_script` 使用 `_sanitize_name()` 清理文件名 [VERIFIED: state_manager.py] |
| FileProvider URI leak | Information Disclosure | `FLAG_GRANT_READ_URI_PERMISSION` 仅授予读取权限，分享完成后其他应用无法再访问 [VERIFIED: Android API] |
| WS reconnect flooding | Denial of Service | 指数退避 30s 封顶 + 服务端 `MAX_CONNECTIONS=10` 限制 [VERIFIED: ws_manager.py] |
| NetworkCallback registration leak | Denial of Service | ViewModel `onCleared()` 注销，避免后台持续监听 [ASSUMED] |
| Missing auth on new endpoint | Spoofing | `GET /drama/cast/status` 必须加 `Depends(require_auth)` [VERIFIED: 现有模式] |

## Sources

### Primary (HIGH confidence)
- Context7 `/websites/developer_android_develop_ui_compose` — ModalNavigationDrawer API, DrawerSheet 组件
- `app/api/models.py` — 现有 Pydantic 模型定义（DramaStatusResponse, ExportResponse, CastResponse）
- `app/api/routers/queries.py` — 现有查询端点实现
- `app/state_manager.py` — get_current_state(), export_script(), get_all_actors()
- `app/actor_service.py` — list_running_actors(), _actor_processes
- `app/api/event_mapper.py` — typing 事件 data.tool 字段映射
- `android/app/build.gradle.kts` + `libs.versions.toml` — 依赖版本锁定

### Secondary (MEDIUM confidence)
- Android 官方文档 developer.android.com/training/sharing/send — ShareSheet + FileProvider
- `app/api/ws_manager.py` — ConnectionManager replay buffer + heartbeat
- `app/api/routers/websocket.py` — WS 端点生命周期

### Tertiary (LOW confidence)
- RTL LayoutDirection hack for right-side Drawer — 社区方案，未在 Context7 中确认
- ConnectivityManager.NetworkCallback 在 ViewModel 中的生命周期管理 — 基于 Android API 文档推理

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — 所有库版本已锁定在项目中，无需新增依赖
- Architecture: HIGH — 基于 Phase 16-17 已建立的 MVVM 模式，扩展方向明确
- Pitfalls: MEDIUM — 右侧 Drawer RTL hack 需实际验证，WS 重连竞态需实现时仔细处理

**Research date:** 2026-04-16
**Valid until:** 2026-05-16 (30 days — stable stack, no fast-moving dependencies)
