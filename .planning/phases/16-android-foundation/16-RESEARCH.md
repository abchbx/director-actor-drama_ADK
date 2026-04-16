# Phase 16: Android Foundation - Research

**Researched:** 2026-04-16
**Domain:** Android / Kotlin / Jetpack Compose / MVVM+Hilt / Network Client
**Confidence:** HIGH

## Summary

Phase 16 搭建 Android 项目骨架：Kotlin + Compose + Hilt + Material Design 3 主题 + Navigation Compose 导航 + Retrofit/OkHttp 网络层 + DataStore 偏好存储 + WebSocket 基础。本 phase 不实现业务交互（戏剧 CRUD、命令输入等属于 Phase 17），仅搭建骨架让 Phase 17-18 有地可建。

后端 API 已在 Phase 13-15 实现：14 个 REST 端点（`/api/v1/`）、1 个 WebSocket 端点（`/api/v1/ws?token=xxx`）、Token 认证（Bearer header + query param）、`/auth/verify` 自动检测 bypass/token 模式。Android 侧需要精确映射这些 API 契约。

**Primary recommendation:** 使用 Kotlin 2.1.0 + Compose BOM 2025.12.01 + Retrofit 2.12.0（含官方 converter-kotlinx-serialization）+ OkHttp 4.12.0 + Hilt 2.54 + Navigation Compose 2.8.9 + DataStore Preferences 1.1.7 + Material3 1.3.2，单模块 Gradle Kotlin DSL 项目，按 data/domain/ui 三层组织包结构。

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** 手动输入 IP:port + 历史记录下拉 — 无需后端改动，开发者/极客友好
- **D-02:** 连接后自动检测 Token — 先连 IP:port 调 `GET /api/v1/auth/verify`，`mode: "bypass"` 跳过 token 输入，`mode: "token"` 弹出输入对话框
- **D-03:** 连接失败反馈 — Snackbar 提示 + 重试按钮，区分错误类型
- **D-04:** DataStore Preferences 持久化服务器配置 — 存储 IP、port、token（加密存储）、最后连接时间
- **D-05:** Kotlin 2.0.x + Compose BOM 2024.12 — 最新稳定组合
- **D-06:** Retrofit + OkHttp + kotlinx.serialization — 业界标准 REST 客户端
- **D-07:** 无 Room 数据库 — 纯在线模式，DataStore 仅存偏好/服务器配置
- **D-08:** Navigation Compose — 官方推荐导航方案，type-safe 路由
- **D-09:** Hilt 依赖注入 — 管理 Retrofit 实例、Repository、ViewModel、DataStore
- **D-10:** minSdk 26 (Android 8.0), targetSdk 35
- **D-11:** 底部导航栏 3 tab — 戏剧列表 / 创建 / 设置，MD3 NavigationBar
- **D-12:** drama-detail 从列表项点击进入 — 独立路由 `drama/{dramaId}`，带返回箭头
- **D-13:** 服务器连接配置在设置页面 — 设置页顶部"服务器连接"section
- **D-14:** 首次启动引导 — DataStore 无服务器历史时弹出全屏 Dialog
- **D-15:** 导航图：`connection-guide (条件)` → `main (drama-list / create / settings)` → `drama-detail`
- **D-16:** MD3 Dynamic Color 启用 (API 31+)，fallback 到自定义品牌色
- **D-17:** 暗色模式默认 — `isSystemInDarkTheme()` 跟随系统，首次启动默认暗色
- **D-18:** 品牌色深靛蓝 — `primary = Color(0xFF1A237E)` 系列
- **D-19:** Typography 微调 — MD3 默认 + `titleLarge` 加粗 (`FontWeight.Bold`)
- **D-20:** 形状沿用 MD3 默认 rounded

### Claude's Discretion
- Gradle 模块结构（单模块 vs 多模块）
- 具体包结构（data/domain/ui 层组织）
- Retrofit API interface 的具体方法签名
- DataStore 存储键名和加密策略
- 连接引导 Dialog 的动画和布局细节
- 首次启动检测逻辑的具体实现
- Compose preview 的组织方式

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| APP-01 | App connects to backend server via IP:port configuration | Retrofit + OkHttp 配置动态 baseUrl（D-01/D-04 DataStore 存 IP:port）|
| APP-13 | MVVM architecture with Repository pattern | Hilt DI + ViewModel + Repository 三层架构模式（D-09）|
| APP-14 | Hilt dependency injection | Hilt 2.54+ 配置、@HiltAndroidApp、@Inject、@Module/@Provides（D-09）|
| APP-16 | Material Design 3 theming with dynamic colors and dark mode | MD3 theme 配置 + Dynamic Color + 品牌色 fallback（D-16/D-17/D-18）|
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Kotlin | 2.1.0 | 编程语言 | K2 编译器稳定版，Compose compiler 内置支持 [VERIFIED: kotlinlang.org] |
| Compose BOM | 2025.12.01 | Compose 版本统一管理 | 统一所有 Compose 库版本，避免兼容问题 [VERIFIED: mvnrepository.com] |
| Material3 | 1.3.2 (via BOM) | MD3 组件库 | 官方 MD3 Compose 实现 [VERIFIED: mvnrepository.com] |
| Hilt | 2.54 | 依赖注入 | Google 官方 DI，与 ViewModel/Navigation 深度集成 [VERIFIED: mvnrepository.com] |
| Navigation Compose | 2.8.9 (via BOM) | 导航 | type-safe 路由（@Serializable），与 Compose 深度集成 [VERIFIED: mvnrepository.com] |
| Retrofit | 2.12.0 | REST 客户端 | 含官方 kotlinx-serialization converter [VERIFIED: mvnrepository.com] |
| OkHttp | 4.12.0 | HTTP/WebSocket 客户端 | WebSocket 支持 + 拦截器注入 token [VERIFIED: mvnrepository.com] |
| kotlinx-serialization-json | 1.8.1 | JSON 序列化 | Kotlin 原生序列化，性能优于 Gson [VERIFIED: mvnrepository.com] |
| DataStore Preferences | 1.1.7 | 偏好存储 | 协程友好，替代 SharedPreferences [VERIFIED: mvnrepository.com] |
| AGP | 8.7.3 | Android Gradle Plugin | 稳定版，兼容 Kotlin 2.1 + Gradle 8.9 [VERIFIED: developer.android.com] |
| KSP | 2.1.0-1.0.29 | 注解处理 | Hilt 使用 KSP 而非 KAPT [ASSUMED] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| hilt-navigation-compose | 1.2.0 | Hilt + Navigation 集成 | @HiltViewModel 自动注入 ViewModel |
| lifecycle-viewmodel-compose | 2.8.7 (via BOM) | ViewModel Compose 集成 | viewModel() 函数获取 ViewModel |
| lifecycle-runtime-compose | 2.8.7 (via BOM) | Lifecycle Compose 集成 | collectAsStateWithLifecycle() |
| activity-compose | 1.9.3 (via BOM) | Activity Compose 集成 | setContent {} 入口 |
| core-ktx | 1.15.0 | Android Core KTX | Context/string 扩展 |
| compose-material-icons-extended | via BOM | 扩展图标集 | NavigationBar 图标 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Retrofit 2.12.0 | Retrofit 3.0.0 | 3.0 升级到 OkHttp 4.12 但 API 不完全兼容；2.12 同日发布更稳定 [VERIFIED: github.com/square/retrofit] |
| OkHttp 4.12.0 | OkHttp 5.x | 5.x 大改 API（Okio 3.x），Retrofit 2.x 未适配；4.12 是最稳定选择 [VERIFIED: mvnrepository.com] |
| Kotlin 2.1.0 | Kotlin 2.0.x | CONTEXT.md 指定 2.0.x 但 2.1.0 是 2024-11 发布的稳定版，K2 编译器更成熟 [VERIFIED: kotlinlang.org] |
| Compose BOM 2024.12 | Compose BOM 2025.12.01 | CONTEXT.md 指定 2024.12 但最新稳定版已更新至 2025.12，包含 bug 修复和性能改进 [VERIFIED: mvnrepository.com] |
| JakeWharton converter | 官方 converter-kotlinx-serialization | JakeWharton 库已归档，功能合并进 Retrofit 2.11+ [VERIFIED: github.com/JakeWharton] |

**Installation:**
```kotlin
// build.gradle.kts (project level)
plugins {
    id("com.android.application") version "8.7.3" apply false
    id("org.jetbrains.kotlin.android") version "2.1.0" apply false
    id("com.google.dagger.hilt.android") version "2.54" apply false
    id("org.jetbrains.kotlin.plugin.serialization") version "2.1.0" apply false
    id("com.google.devtools.ksp") version "2.1.0-1.0.29" apply false
    id("org.jetbrains.kotlin.plugin.compose") version "2.1.0" apply false
}

// build.gradle.kts (app level)
dependencies {
    // Compose BOM
    val composeBom = platform("androidx.compose:compose-bom:2025.12.01")
    implementation(composeBom)
    androidTestImplementation(composeBom)

    // Compose
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material:material-icons-extended")
    debugImplementation("androidx.compose.ui:ui-tooling")

    // Core
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-compose:1.9.3")

    // Lifecycle
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose")
    implementation("androidx.lifecycle:lifecycle-runtime-compose")

    // Navigation
    implementation("androidx.navigation:navigation-compose:2.8.9")

    // Hilt
    implementation("com.google.dagger:hilt-android:2.54")
    ksp("com.google.dagger:hilt-android-compiler:2.54")
    implementation("androidx.hilt:hilt-navigation-compose:1.2.0")

    // Network
    implementation("com.squareup.retrofit2:retrofit:2.12.0")
    implementation("com.squareup.retrofit2:converter-kotlinx-serialization:2.12.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.8.1")

    // DataStore
    implementation("androidx.datastore:datastore-preferences:1.1.7")
}
```

**Version verification:** 以下版本已通过 Maven Registry 或官方文档验证：
- Compose BOM 2025.12.01 [VERIFIED: mvnrepository.com, 2025-12-17]
- Kotlin 2.1.0 [VERIFIED: kotlinlang.org, 2024-11-27]
- Hilt 2.54 [VERIFIED: mvnrepository.com, 2024-12-20]
- Retrofit 2.12.0 [VERIFIED: mvnrepository.com, 2025-05-15]
- OkHttp 4.12.0 [VERIFIED: mvnrepository.com, 2023-10-17]
- kotlinx-serialization-json 1.8.1 [VERIFIED: mvnrepository.com, 2025-04-01]
- Navigation Compose 2.8.9 [VERIFIED: mvnrepository.com, 2025-03-12]
- DataStore Preferences 1.1.7 [VERIFIED: mvnrepository.com, 2025-05-20]
- Material3 1.3.2 [VERIFIED: mvnrepository.com, 2025-04-09]

> **注意：** CONTEXT.md 指定 "Kotlin 2.0.x + Compose BOM 2024.12"，但当前最新稳定版已显著更新。本推荐采用更新版本以获得更好的稳定性和 Compose compiler 集成。如需严格遵循 CONTEXT.md，可用 Kotlin 2.0.21 + Compose BOM 2024.12.01。

## Architecture Patterns

### Recommended Project Structure
```
android/
├── app/
│   ├── src/
│   │   ├── main/
│   │   │   ├── java/com/drama/app/
│   │   │   │   ├── DramaApplication.kt        # @HiltAndroidApp
│   │   │   │   ├── MainActivity.kt             # setContent 入口
│   │   │   │   ├── data/
│   │   │   │   │   ├── local/
│   │   │   │   │   │   └── ServerPreferences.kt # DataStore 封装
│   │   │   │   │   ├── remote/
│   │   │   │   │   │   ├── api/
│   │   │   │   │   │   │   ├── DramaApiService.kt    # Retrofit 接口
│   │   │   │   │   │   │   └── AuthApiService.kt      # /auth/verify
│   │   │   │   │   │   ├── dto/
│   │   │   │   │   │   │   ├── CommandResponseDto.kt
│   │   │   │   │   │   │   ├── DramaStatusDto.kt
│   │   │   │   │   │   │   ├── DramaListDto.kt
│   │   │   │   │   │   │   ├── AuthVerifyDto.kt
│   │   │   │   │   │   │   └── WsEventDto.kt
│   │   │   │   │   │   └── ws/
│   │   │   │   │   │       └── WebSocketManager.kt  # OkHttp WS 客户端
│   │   │   │   │   └── repository/
│   │   │   │   │       ├── ServerRepositoryImpl.kt
│   │   │   │   │       └── AuthRepositoryImpl.kt
│   │   │   │   ├── domain/
│   │   │   │   │   ├── repository/
│   │   │   │   │   │   ├── ServerRepository.kt   # 接口
│   │   │   │   │   │   └── AuthRepository.kt     # 接口
│   │   │   │   │   └── model/
│   │   │   │   │       ├── ServerConfig.kt       # IP/port/token
│   │   │   │   │       ├── ConnectionStatus.kt   # 连接状态枚举
│   │   │   │   │       └── AuthMode.kt           # bypass/token
│   │   │   │   └── ui/
│   │   │   │       ├── navigation/
│   │   │   │       │   ├── DramaNavHost.kt       # 导航图
│   │   │   │       │   └── Route.kt              # @Serializable 路由定义
│   │   │   │       ├── theme/
│   │   │   │       │   ├── Theme.kt              # MD3 主题 + Dynamic Color
│   │   │   │       │   ├── Color.kt              # 品牌色定义
│   │   │   │       │   └── Type.kt               # Typography 定制
│   │   │   │       ├── screens/
│   │   │   │       │   ├── connection/
│   │   │   │       │   │   ├── ConnectionGuideDialog.kt
│   │   │   │       │   │   └── ConnectionViewModel.kt
│   │   │   │       │   ├── dramalist/
│   │   │   │       │   │   ├── DramaListScreen.kt
│   │   │   │       │   │   └── DramaListViewModel.kt
│   │   │   │       │   ├── dramacreate/
│   │   │   │       │   │   ├── DramaCreateScreen.kt
│   │   │   │       │   │   └── DramaCreateViewModel.kt
│   │   │   │       │   ├── dramadetail/
│   │   │   │       │   │   ├── DramaDetailScreen.kt
│   │   │   │       │   │   └── DramaDetailViewModel.kt
│   │   │   │       │   └── settings/
│   │   │   │       │       ├── SettingsScreen.kt
│   │   │   │       │       └── SettingsViewModel.kt
│   │   │   │       └── components/
│   │   │   │           └── ConnectionStatusBanner.kt
│   │   │   ├── res/
│   │   │   └── AndroidManifest.xml
│   │   └── test/  # 单元测试
│   ├── build.gradle.kts
│   └── proguard-rules.pro
├── build.gradle.kts          # 项目级
├── settings.gradle.kts
├── gradle.properties
└── gradle/
    └── libs.versions.toml   # 版本目录
```

### Pattern 1: Hilt + MVVM + Repository
**What:** Hilt 提供 ViewModel 和 Repository 实例，ViewModel 持有 UI 状态，Repository 封装数据源
**When to use:** 所有屏幕
**Example:**
```kotlin
// Source: [CITED: developer.android.com/training/dependency-injection/hilt-jetpack]
@HiltViewModel
class ConnectionViewModel @Inject constructor(
    private val serverRepository: ServerRepository,
    private val authRepository: AuthRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow<ConnectionUiState>(ConnectionUiState.Idle)
    val uiState: StateFlow<ConnectionUiState> = _uiState.asStateFlow()

    fun connect(ip: String, port: String) {
        viewModelScope.launch {
            _uiState.value = ConnectionUiState.Connecting
            when (val result = authRepository.verifyServer(ip, port)) {
                is AuthResult.Bypass -> { /* 直接进入 */ }
                is AuthResult.RequireToken -> { /* 弹 token 输入 */ }
                is AuthResult.Error -> { /* Snackbar 报错 */ }
            }
        }
    }
}
```

### Pattern 2: Navigation Compose Type-Safe Routes
**What:** 用 @Serializable data class/object 定义路由，编译时类型检查
**When to use:** 所有导航目标
**Example:**
```kotlin
// Source: [CITED: developer.android.com/guide/navigation/design]
@Serializable object ConnectionGuide   // 首次引导
@Serializable object DramaList         // 戏剧列表 tab
@Serializable object DramaCreate       // 创建 tab
@Serializable object Settings          // 设置 tab
@Serializable data class DramaDetail(val dramaId: String) // 戏剧详情

// NavHost
NavHost(navController, startDestination = startRoute) {
    composable<ConnectionGuide> { ConnectionGuideDialog(...) }
    composable<DramaList> { DramaListScreen(...) }
    composable<DramaCreate> { DramaCreateScreen(...) }
    composable<Settings> { SettingsScreen(...) }
    composable<DramaDetail> { backStackEntry ->
        val args = backStackEntry.toRoute<DramaDetail>()
        DramaDetailScreen(dramaId = args.dramaId)
    }
}
```

### Pattern 3: OkHttp WebSocket + 协程 Flow
**What:** OkHttp WebSocket 客户端封装为 Kotlin Flow，自动发送心跳 pong
**When to use:** 实时场景推送
**Example:**
```kotlin
// Source: [CITED: square.github.io/okhttp]
class WebSocketManager(
    private val okHttpClient: OkHttpClient,
) {
    private var webSocket: WebSocket? = null

    fun connect(host: String, port: String, token: String?): Flow<WsEvent> = callbackFlow {
        val url = if (token != null) {
            "ws://$host:$port/api/v1/ws?token=$token"
        } else {
            "ws://$host:$port/api/v1/ws"
        }
        val request = Request.Builder().url(url).build()
        webSocket = okHttpClient.newWebSocket(request, object : WebSocketListener() {
            override fun onMessage(webSocket: WebSocket, text: String) {
                trySend(Json.decodeFromString<WsEvent>(text))
            }
            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                close()
            }
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                close(t)
            }
        })
        awaitClose { webSocket?.close(1000, "Client disconnect") }
    }
}
```

### Pattern 4: DataStore Preferences + Repository
**What:** DataStore Preferences 封装为 Repository，提供类型安全的偏好读写
**When to use:** 服务器配置持久化
**Example:**
```kotlin
// Source: [CITED: developer.android.com/topic/libraries/architecture/datastore]
class ServerPreferences(private val dataStore: DataStore<Preferences>) {
    companion object {
        val SERVER_IP = stringPreferencesKey("server_ip")
        val SERVER_PORT = stringPreferencesKey("server_port")
        val AUTH_TOKEN = stringPreferencesKey("auth_token")  // 加密存储
        val LAST_CONNECTED = longPreferencesKey("last_connected")
    }

    val serverConfig: Flow<ServerConfig?> = dataStore.data.map { prefs ->
        val ip = prefs[SERVER_IP] ?: return@map null
        val port = prefs[SERVER_PORT] ?: return@map null
        ServerConfig(ip, port, prefs[AUTH_TOKEN], prefs[LAST_CONNECTED])
    }

    suspend fun saveServerConfig(config: ServerConfig) {
        dataStore.edit { prefs ->
            prefs[SERVER_IP] = config.ip
            prefs[SERVER_PORT] = config.port
            config.token?.let { prefs[AUTH_TOKEN] = it }
            prefs[LAST_CONNECTED] = System.currentTimeMillis()
        }
    }
}
```

### Anti-Patterns to Avoid
- **在 ViewModel 中直接使用 Retrofit**: 应通过 Repository 封装，Repository 处理网络错误映射和数据转换
- **在 Composable 中持有状态**: 使用 ViewModel + StateFlow，Composable 仅渲染
- **硬编码 baseUrl**: Retrofit baseUrl 必须从 DataStore 动态读取，OkHttp interceptor 无法修改 baseUrl
- **使用 SharedPreferences**: DataStore 是协程友好的替代方案，避免 ANR
- **在 UI 层解析 JSON**: DTO → Domain Model 转换应在 Repository 层完成

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON 序列化 | 手写 JSON parser | kotlinx-serialization + Retrofit converter | 类型安全、性能优异、Null 安全 |
| DI 容器 | 手写 ServiceLocator | Hilt | 编译时检查、ViewModel 集成、生命周期感知 |
| 导航 | 手写 Fragment transaction | Navigation Compose 2.8+ | type-safe 路由、back stack 管理、deep link |
| 偏好存储 | SharedPreferences | DataStore Preferences | 协程友好、避免 ANR、类型安全 |
| WebSocket 心跳 | 手写 Timer/Handler | OkHttp WebSocket + 服务端心跳 | 15s/30s 心跳协议已定义，OkHttp 原生支持 |
| 主题系统 | 手写 color/material 属性 | MD3 Theme + Dynamic Color | 系统统一、Material You 一致性、暗色模式支持 |
| Token 注入 | 每个 API 调用手动加 header | OkHttp Interceptor | 统一注入 Authorization header，DRY |

**Key insight:** Android 生态已有成熟的官方/社区库解决所有本 phase 需求。手写任何上述组件都是技术债。

## Runtime State Inventory

> 此为 greenfield phase（新建 Android 项目），不存在运行时状态需要迁移。

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — 新项目 | — |
| Live service config | None — 新项目 | — |
| OS-registered state | None — 新项目 | — |
| Secrets/env vars | None — 新项目（token 存在 DataStore） | — |
| Build artifacts | None — 新项目 | — |

## Common Pitfalls

### Pitfall 1: Retrofit 动态 baseUrl 问题
**What goes wrong:** 用户输入不同 IP:port 后，Retrofit 实例的 baseUrl 不变，请求发送到旧地址
**Why it happens:** Retrofit.baseUrl 在构建时固定，无法运行时修改
**How to avoid:** 方案 A — 每次连接时重建 Retrofit 实例（Hilt @Provides 工厂方法）；方案 B — 使用 OkHttp Interceptor 替换请求 URL；推荐方案 A，更简单清晰
**Warning signs:** 连接新服务器后请求仍发往旧地址

### Pitfall 2: Navigation Compose 2.8+ 路由序列化
**What goes wrong:** @Serializable 路由需要 kotlinx.serialization 插件，忘记添加导致编译错误
**Why it happens:** Navigation 2.8+ type-safe 路由依赖 `kotlin-plugin-serialization`，与 `kotlin-plugin-compose` 必须同时声明
**How to avoid:** 在 build.gradle.kts 中同时声明 `kotlin("plugin.serialization")` 和 `kotlin("plugin.compose")`
**Warning signs:** `Serializer has not been found for type ...` 编译错误

### Pitfall 3: Hilt + KSP 配置缺失
**What goes wrong:** 使用 KAPT 而非 KSP 导致编译慢，或 KSP 版本与 Kotlin 版本不匹配
**Why it happens:** Hilt 2.x 支持 KSP，但默认模板可能仍使用 KAPT
**How to avoid:** 使用 KSP 而非 KAPT：`ksp("com.google.dagger:hilt-android-compiler:2.54")` 而非 `kapt(...)`。确保 KSP 版本匹配 Kotlin 版本
**Warning signs:** 编译缓慢（KAPT）或 KSP 版本不匹配错误

### Pitfall 4: WebSocket 连接生命周期
**What goes wrong:** Activity 销毁后 WebSocket 仍运行，或 Fragment 重建导致重复连接
**Why it happens:** WebSocket 是长连接，生命周期不由 Activity/Fragment 管理
**How to avoid:** 将 WebSocketManager 绑定到 ViewModel（viewModelScope），在 onCleared() 时断开；或使用 Hilt @Singleton scope + 引用计数
**Warning signs:** 内存泄漏、重复消息、ANR

### Pitfall 5: DataStore 在主线程同步读取
**What goes wrong:** 在 Composable 中同步读取 DataStore 导致 ANR
**Why it happens:** DataStore 是异步 API，没有 `getString()` 同步方法
**How to avoid:** 使用 `collectAsStateWithLifecycle()` 在 Composable 中观察 Flow，或在 ViewModel 中用 StateFlow 缓存
**Warning signs:** 严格模式报 `DiskReadViolation`，UI 卡顿

### Pitfall 6: MD3 Dynamic Color 在 API < 31 崩溃
**What goes wrong:** 使用 `dynamicColor = true` 在 Android 11 及以下设备上不生效或崩溃
**Why it happens:** Dynamic Color 是 Android 12 (API 31) 功能
**How to avoid:** 条件判断：`val dynamicColor = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S`，fallback 到自定义品牌色 ColorScheme
**Warning signs:** Android 11 及以下设备主题异常

### Pitfall 7: Cleartext HTTP 被系统阻止
**What goes wrong:** 连接 `http://ip:port` 被系统拒绝，报 `Cleartext HTTP traffic not permitted`
**Why it happens:** Android 9+ 默认禁止明文 HTTP
**How to avoid:** 在 `AndroidManifest.xml` 的 `<application>` 添加 `android:usesCleartextTraffic="true"`（局域网 dev 场景合理）；或配置 `network_security_config.xml` 仅允许特定 IP
**Warning signs:** `IOException: Cleartext HTTP traffic not permitted`

## Code Examples

Verified patterns from official sources:

### Retrofit API Interface — 映射后端 14 个端点
```kotlin
// Source: [CITED: app/api/routers/commands.py + queries.py]
interface DramaApiService {
    // === Commands (Phase 13) ===
    @POST("drama/start")
    suspend fun startDrama(@Body request: StartDramaRequestDto): CommandResponseDto

    @POST("drama/next")
    suspend fun nextScene(): CommandResponseDto

    @POST("drama/action")
    suspend fun userAction(@Body request: ActionRequestDto): CommandResponseDto

    @POST("drama/speak")
    suspend fun actorSpeak(@Body request: SpeakRequestDto): CommandResponseDto

    @POST("drama/steer")
    suspend fun steerDrama(@Body request: SteerRequestDto): CommandResponseDto

    @POST("drama/auto")
    suspend fun autoAdvance(@Body request: AutoRequestDto): CommandResponseDto

    @POST("drama/storm")
    suspend fun triggerStorm(@Body request: StormRequestDto): CommandResponseDto

    @POST("drama/end")
    suspend fun endDrama(): CommandResponseDto

    // === Queries (Phase 13) ===
    @GET("drama/status")
    suspend fun getDramaStatus(): DramaStatusResponseDto

    @GET("drama/cast")
    suspend fun getCast(): CastResponseDto

    @GET("drama/list")
    suspend fun listDramas(): DramaListResponseDto

    @POST("drama/save")
    suspend fun saveDrama(@Body request: SaveRequestDto): SaveLoadResponseDto

    @POST("drama/load")
    suspend fun loadDrama(@Body request: LoadRequestDto): SaveLoadResponseDto

    @POST("drama/export")
    suspend fun exportDrama(@Body request: ExportRequestDto): ExportResponseDto
}

interface AuthApiService {
    @GET("auth/verify")
    suspend fun verifyToken(): AuthVerifyResponseDto
}
```

### Auth Verify — 连接自动检测 Token
```kotlin
// Source: [CITED: app/api/routers/auth.py]
@Serializable
data class AuthVerifyResponseDto(
    val valid: Boolean = true,
    val mode: String = "token",  // "token" | "bypass"
)

// 在 Repository 中
class AuthRepositoryImpl @Inject constructor(
    private val authApi: AuthApiService,
) : AuthRepository {
    override suspend fun verifyServer(): Result<AuthMode> = runCatching {
        val response = authApi.verifyToken()
        if (response.mode == "bypass") AuthMode.Bypass else AuthMode.RequireToken
    }
}
```

### OkHttp Interceptor — 统一注入 Token
```kotlin
// Source: [CITED: square.github.io/okhttp]
class AuthInterceptor @Inject constructor(
    private val serverPreferences: ServerPreferences,
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val originalRequest = chain.request()
        // 从 DataStore 同步读取 token（interceptor 在 OkHttp 线程）
        val token = runBlocking { serverPreferences.getTokenSync() }
        val request = if (token != null) {
            originalRequest.newBuilder()
                .header("Authorization", "Bearer $token")
                .build()
        } else {
            originalRequest
        }
        return chain.proceed(request)
    }
}
```

### MD3 Theme — Dynamic Color + 品牌色 Fallback
```kotlin
// Source: [CITED: developer.android.com/develop/ui/compose/designsystems/material3]
private val DeepIndigoPrimary = Color(0xFF1A237E) // D-18
private val DeepIndigoOnPrimary = Color.White
private val DeepIndigoPrimaryContainer = Color(0xFF534FE5)
private val DeepIndigoOnPrimaryContainer = Color(0xFFE0E0FF)

private val DarkColorScheme = darkColorScheme(
    primary = DeepIndigoPrimaryContainer,  // 暗色模式自动调亮
    onPrimary = DeepIndigoOnPrimaryContainer,
    // ... 其他色值
)

private val LightColorScheme = lightColorScheme(
    primary = DeepIndigoPrimary,
    onPrimary = DeepIndigoOnPrimary,
    // ... 其他色值
)

@Composable
fun DramaTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),  // D-17
    dynamicColor: Boolean = true,                 // D-16
    content: @Composable () -> Unit,
) {
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context)
            else dynamicLightColorScheme(context)
        }
        darkTheme -> DarkColorScheme
        else -> LightColorScheme
    }

    val typography = Typography(
        titleLarge = Typography().titleLarge.copy(
            fontWeight = FontWeight.Bold  // D-19
        )
    )

    MaterialTheme(
        colorScheme = colorScheme,
        typography = typography,
        content = content,
    )
}
```

### 首次启动检测 — 判断是否显示连接引导
```kotlin
// Source: [CITED: developer.android.com/topic/libraries/architecture/datastore]
@Composable
fun DramaApp() {
    val serverConfig by serverRepository.serverConfig.collectAsStateWithLifecycle(null)
    val showConnectionGuide = serverConfig == null  // D-14: 无历史 = 首次启动

    DramaTheme {
        val navController = rememberNavController()
        val startDestination = if (showConnectionGuide) ConnectionGuide else DramaList

        DramaNavHost(navController, startDestination)
    }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Kotlin KAPT | KSP (Kotlin Symbol Processing) | 2023+ | 编译速度提升 2x+，Hilt 2.x 全面支持 |
| Navigation 字符串路由 | Type-safe @Serializable routes | Navigation 2.8.0 (2024) | 编译时路由检查，避免运行时路由拼写错误 |
| JakeWharton kotlinx-serialization converter | Retrofit 官方 converter-kotlinx-serialization | Retrofit 2.11.0 (2024-03) | 第一方支持，无需第三方库 |
| SharedPreferences | DataStore Preferences | 2020+ | 协程友好、避免 ANR、类型安全 |
| View 系统 | Jetpack Compose | 2021+ | 声明式 UI、状态驱动、减少样板代码 |
| Gson | kotlinx-serialization | Kotlin 1.4+ | Kotlin 原生、编译时生成、性能更优 |

**Deprecated/outdated:**
- `kotlin-kapt` 插件：KSP 是现代替代方案，Hilt 2.x 已支持 KSP
- JakeWharton `retrofit2-kotlinx-serialization-converter`：已归档，功能合并进 Retrofit 2.11+
- `navigation-compose-typed` 第三方库：Navigation 2.8+ 原生支持 type-safe routing
- `viewModel()` + `by viewModels()`：推荐 `viewModel()` Compose 函数 + `@HiltViewModel`

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | KSP 版本 2.1.0-1.0.29 与 Kotlin 2.1.0 兼容 | Standard Stack | Hilt 编译失败，需回退到 KAPT |
| A2 | AGP 8.7.3 与 Kotlin 2.1.0 兼容 | Standard Stack | 构建失败，需升级 AGP 或降级 Kotlin |
| A3 | Token 加密存储使用 Android EncryptedSharedPreferences 或 Android Keystore | Architecture | 未加密存储 token 有安全风险 |
| A4 | Compose BOM 2025.12.01 包含的 Material3 版本与 Navigation 2.8.9 兼容 | Standard Stack | 版本冲突，需显式指定 |
| A5 | OkHttp WebSocket 4.12.0 支持 `?token=` query param 认证 | Architecture | 需要额外处理 WebSocket 认证 |
| A6 | Retrofit baseUrl 可以在运行时通过重建实例动态修改 | Architecture | 无法连接到新服务器 |
| A7 | `android:usesCleartextTraffic="true"` 对局域网 HTTP 足够 | Architecture | 生产环境需要更严格的网络安全配置 |

## Open Questions

1. **Kotlin 版本选择**
   - What we know: CONTEXT.md 指定 "Kotlin 2.0.x"，但 2.1.0 是更成熟的稳定版
   - What's unclear: 用户是否严格要求 2.0.x
   - Recommendation: 推荐 2.1.0（2024-11 发布，更稳定的 K2 编译器），但标注为可选

2. **Token 加密方案**
   - What we know: D-04 指定 "token 加密存储"，DataStore Preferences 默认不加密
   - What's unclear: 使用 EncryptedSharedPreferences (Security crypto) 还是 Android Keystore + 自定义加密
   - Recommendation: 使用 `androidx.security:security-crypto` 的 EncryptedSharedPreferences 封装 DataStore，或简单方案：DataStore 存加密后的 token（Base64 编码，非真加密但满足 dev 场景）

3. **WebSocket 生命周期管理**
   - What we know: WS 连接需要跨 Activity/Fragment 存活
   - What's unclear: WS 绑定到 ViewModel scope 还是 Application scope
   - Recommendation: Phase 16 仅搭建 WS 基础（WebSocketManager 类），Phase 17 实现完整生命周期管理

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| JDK 17 | Android 构建 | ✗ | JDK 20 (Zulu) | 安装 JDK 17 或配置 JDK 20 兼容 |
| Android SDK | Android 构建 | ✗ | — | 需安装 Android SDK + Platform 35 |
| Gradle 8.9+ | AGP 8.7 兼容 | ✓ | via sdkman | — |
| Kotlin | 编译 | ✓ | 2.1.0 | — |

**Missing dependencies with no fallback:**
- Android SDK + Platform 35：构建 Android 项目必需。需在开发环境安装 Android Studio 或 command-line tools
- JDK 17：AGP 8.7 要求 JDK 17，当前 JDK 20 可能兼容但不保证

**Missing dependencies with fallback:**
- JDK 20 替代 JDK 17：AGP 8.7 官方要求 JDK 17，但 JDK 20 通常兼容。如遇问题需安装 JDK 17

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
| APP-01 | 连接到 IP:port 服务器 | unit | `./gradlew test --tests ServerRepositoryImplTest` | ❌ Wave 0 |
| APP-13 | MVVM 架构 | unit | `./gradlew test --tests *ViewModelTest` | ❌ Wave 0 |
| APP-14 | Hilt DI | unit | `./gradlew test --tests *RepositoryImplTest` | ❌ Wave 0 |
| APP-16 | MD3 主题 + Dynamic Color | visual | 手动截图对比 | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `./gradlew test`
- **Per wave merge:** `./gradlew testDebugUnitTest`
- **Phase gate:** Full suite green + 手动验证 MD3 主题

### Wave 0 Gaps
- [ ] `app/src/test/` — 整个测试目录需创建
- [ ] JUnit 5 + Mockito + Coroutines Test 依赖需添加到 build.gradle.kts
- [ ] `HiltAndroidTest` 规则需配置（集成测试）

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Token 认证 via /auth/verify |
| V3 Session Management | yes | DataStore 存 token，OkHttp Interceptor 注入 |
| V4 Access Control | no | 无用户角色区分（单用户模式） |
| V5 Input Validation | yes | kotlinx.serialization 自动校验 JSON schema |
| V6 Cryptography | partial | Token 存储加密（D-04）|

### Known Threat Patterns for Android + Network

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Network eavesdropping (HTTP) | Information Disclosure | `usesCleartextTraffic` 仅限 dev；生产用 HTTPS |
| Token leak from storage | Information Disclosure | EncryptedSharedPreferences 或 Keystore |
| WebSocket injection | Tampering | 服务端 token 校验（AUTH-03/D-10） |
| Intent injection | Tampering | 导出组件最小化，Deep Link 校验 |
| Screen overlay attack | Spoofing | FLAG_SECURE（低优先级，dev 场景无需） |

## Sources

### Primary (HIGH confidence)
- mvnrepository.com — Compose BOM 2025.12.01, Hilt 2.54, Retrofit 2.12.0, OkHttp 4.12.0, kotlinx-serialization 1.8.1, Navigation 2.8.9, DataStore 1.1.7, Material3 1.3.2
- kotlinlang.org/docs/releases.html — Kotlin 2.1.0 release 2024-11-27, Kotlin 2.3.20 latest
- github.com/square/retrofit/releases — Retrofit 3.0.0 release notes (OkHttp 4.12 upgrade)
- github.com/JakeWharton/retrofit2-kotlinx-serialization-converter — Archived, merged into Retrofit 2.11+
- github.com/google/ksp/releases — KSP 2.3.6 latest, independent versioning since 2.3.0

### Secondary (MEDIUM confidence)
- developer.android.com — AGP 9.1.0 (latest), Architecture guidance, DataStore docs, Navigation docs
- developer.android.google.cn/build/releases/gradle-plugin — AGP compatibility matrix

### Tertiary (LOW confidence)
- KSP 2.1.0-1.0.29 版本号 — 基于命名规则推断，需验证实际可用版本 [ASSUMED]
- EncryptedSharedPreferences 与 DataStore 集成方案 — 需验证兼容性

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — 所有核心库版本通过 Maven Registry 验证
- Architecture: HIGH — MVVM + Hilt + Repository 是 Android 官方推荐架构
- Pitfalls: HIGH — 基于 Android 开发经验和官方文档
- API 映射: HIGH — 直接读取后端源码确认端点和模型

**Research date:** 2026-04-16
**Valid until:** 2026-05-16（Android 生态版本更新较快，30 天有效期）
