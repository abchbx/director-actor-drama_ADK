# Phase 23: Android 技术债务治理 - Research

**Researched:** 2026-04-26
**Domain:** Android/Kotlin 技术债务治理 — ViewModel 拆分、生命周期管理、R8 混淆、安全加固、测试覆盖
**Confidence:** HIGH

## Summary

Phase 23 治理 Android 客户端 17 个技术债务表象（归因为 7 个本质问题）。核心工作分为两波：23-01 P0 歼灭战（VM 拆分 + WS 生命周期 + R8 混淆 + SceneBubble 拆分）和 23-02 P1 阵地战（BaseUrl 动态化 + 测试覆盖 + 安全加固 + 数据源统一）。23-03 P2/P3 已标记 deferred。

代码库审计确认了关键数据点：DramaDetailViewModel 1665 行、WebSocketManager @Singleton + 自建永不取消的 reconnectScope、build.gradle.kts isMinifyEnabled=false、NetworkModule runBlocking 阻塞主线程、AndroidManifest usesCleartextTraffic=true、零测试覆盖。DISCUSSION-LOG 已完成造化宗师审视，18 项设计决策（D-23-01~D-23-18）已锁定。

**Primary recommendation:** 严格遵循 D-23-01~D-23-18 决策执行。VM 拆分采用子组件组合模式（非独立 VM），子组件通过 SharedFlow 事件上报；WS 降级 @ActivityScoped + acquire/release 引用计数；R8 保守 keep 策略；BaseUrlInterceptor + 内存缓存替代 runBlocking。

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
| ID | Decision | Choice |
|----|----------|--------|
| D-23-01 | VM 拆分策略 | 子组件组合（非独立VM） |
| D-23-02 | 子组件通信 | SharedFlow 事件上报 |
| D-23-03 | 气泡ID线程安全 | AtomicLong 替代 Int |
| D-23-04 | 子组件生命周期 | 主 VM onCleared 时统一清理 |
| D-23-05 | WS 作用域 | @ActivityScoped 替代 @Singleton |
| D-23-06 | 多VM共享 | 引用计数 acquire/release |
| D-23-07 | deprecated属性 | 删除，改为 StateFlow |
| D-23-08 | R8 范围 | isMinifyEnabled + shrinkResources |
| D-23-09 | ProGuard 策略 | 保守 keep（DTO/接口） + R8 自动分析 |
| D-23-10 | BaseUrl 切换 | BaseUrlInterceptor + 内存缓存 |
| D-23-11 | AuthRepository | 复用 OkHttpClient |
| D-23-12 | 测试策略 | 关键路径优先 |
| D-23-13 | 测试目标 | 拆分后的子组件 |
| D-23-14 | 明文HTTP | 关闭 + network_security_config 白名单 |
| D-23-15 | 日志拦截器 | BuildConfig.DEBUG 条件注入 |
| D-23-16 | 数据源策略 | WS优先/REST降级 |
| D-23-17 | SceneBubble 拆分 | 移入 23-01 与 BubbleMerger 同步 |
| D-23-18 | 23-03 优先级 | 标记 deferred |

### Claude's Discretion
无明确 discretion 项。所有关键决策已锁定。

### Deferred Ideas (OUT OF SCOPE)
- P2-3: 可配置重试策略 (RetryPolicy)
- P2-5: Room 离线缓存
- P3-1: 全量图标库按需引入
- P3-3: CI/CD (GitHub Actions)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ARCH-01 | DramaDetailViewModel God Object 1665行 | VM 子组件拆分模式 (§Architecture Patterns) |
| ARCH-02 | WebSocketManager @Singleton 生命周期失控 | @ActivityScoped + acquire/release 引用计数 (§Architecture Patterns) |
| ARCH-03 | R8 混淆未启用 | R8/ProGuard 保守 keep 规则 (§Standard Stack) |
| ARCH-04 | NetworkModule runBlocking ANR | BaseUrlInterceptor + 内存缓存 (§Architecture Patterns) |
| ARCH-05 | 零测试覆盖 | junit + mockito-kotlin + coroutines-test + turbine (§Standard Stack) |
| ARCH-06 | usesCleartextTraffic=true | network_security_config 白名单模式 (§Architecture Patterns) |
| ARCH-07 | deprecated 属性协程泄漏 | 删除 deprecated，改用 ConnectionState StateFlow (§Common Pitfalls) |
| ARCH-08 | AuthRepository 每次新建 Retrofit | 复用 OkHttpClient + @NoAuth 限定符 (§Architecture Patterns) |
| ARCH-09 | bubbleCounter 非线程安全 | AtomicLong 替代 Int (§Architecture Patterns) |
| ARCH-10 | REST+WS 双写 UI 闪烁 | WS优先/REST降级 SingleSourceOfTruth (§Architecture Patterns) |
| ARCH-11 | HttpLoggingInterceptor Release 泄露 | BuildConfig.DEBUG 条件注入 (§Architecture Patterns) |
| ARCH-12 | SceneBubble 252行集中单文件 | 拆分独立文件 (§Architecture Patterns) |
| ARCH-13 | 3秒 REST 轮询常开 | ConnectionOrchestrator WS优先策略 (§Architecture Patterns) |
| ARCH-14 | DramaDetailUiState 20+ 字段触发全量重组 | 子组件拆分后自然缓解 (§Architecture Patterns) |
| ARCH-15 | contentFingerprint equals/hashCode 风险 | BubbleMerger 去重逻辑 + 测试覆盖 (§Common Pitfalls) |
| ARCH-16 | onReconnected/onPermanentFailure 可变 var 非线程安全 | SharedFlow 替代回调 (§Architecture Patterns) |
| ARCH-17 | 轮询+WS+REST 三通道并发 | ConnectionOrchestrator 统一管理 (§Architecture Patterns) |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Kotlin | 2.1.0 | 主语言 | 项目已锁定 [VERIFIED: gradle/libs.versions.toml] |
| Hilt | 2.54 | 依赖注入 | 项目已锁定，支持 @ActivityScoped [VERIFIED: gradle/libs.versions.toml] |
| Compose BOM | 2025.12.01 | UI 框架 | 项目已锁定 [VERIFIED: gradle/libs.versions.toml] |
| Retrofit | 2.12.0 | REST 客户端 | 项目已锁定 [VERIFIED: gradle/libs.versions.toml] |
| OkHttp | 4.12.0 | HTTP/WebSocket 底层 | 项目已锁定 [VERIFIED: gradle/libs.versions.toml] |
| kotlinx-serialization-json | 1.8.1 | JSON 序列化 | 项目已锁定 [VERIFIED: gradle/libs.versions.toml] |
| DataStore Preferences | 1.1.7 | 轻量键值存储 | 项目已锁定 [VERIFIED: gradle/libs.versions.toml] |
| Lifecycle | 2.8.7 | ViewModel + runtime | 项目已锁定 [VERIFIED: gradle/libs.versions.toml] |

### Testing (需新增)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| junit | 4.13.2 | 测试框架基础 | 所有单元测试 [VERIFIED: Maven Central] |
| mockito-kotlin | 5.4.0 | Kotlin Mock 框架 | 依赖隔离测试 [VERIFIED: Maven Central] |
| kotlinx-coroutines-test | 1.10.2 | 协程测试 | 测试 suspend 函数和 Flow [VERIFIED: Maven Central] |
| turbine | 1.2.0 | Flow 测试工具 | 测试 StateFlow/SharedFlow 发射值 [VERIFIED: Maven Central] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| mockito-kotlin 5.4.0 | MockK 1.13.x | MockK 对 Kotlin 更友好但社区小；mockito-kotlin 官方维护，与 JUnit 生态兼容性好 |
| junit 4.13.2 | junit 5 (Jupiter) | JUnit 5 功能更强但 Android 资料少；JUnit 4 与 Android 生态最兼容 |

**Installation (libs.versions.toml additions):**
```toml
[versions]
junit = "4.13.2"
mockito-kotlin = "5.4.0"
kotlinx-coroutines-test = "1.10.2"
turbine = "1.2.0"

[libraries]
junit = { group = "junit", name = "junit", version.ref = "junit" }
mockito-kotlin = { group = "org.mockito.kotlin", name = "mockito-kotlin", version.ref = "mockito-kotlin" }
kotlinx-coroutines-test = { group = "org.jetbrains.kotlinx", name = "kotlinx-coroutines-test", version.ref = "kotlinx-coroutines-test" }
turbine = { group = "app.cash.turbine", name = "turbine", version.ref = "turbine" }
```

**build.gradle.kts additions:**
```kotlin
dependencies {
    testImplementation(libs.junit)
    testImplementation(libs.mockito.kotlin)
    testImplementation(libs.kotlinx.coroutines.test)
    testImplementation(libs.turbine)
}
```

## Architecture Patterns

### Recommended Project Structure (子组件拆分后)
```
ui/screens/dramadetail/
├── DramaDetailViewModel.kt          # 协调者 (~300行)
├── sub/                              # 子组件目录
│   ├── ConnectionOrchestrator.kt     # WS连接/重连/轮询降级 (~250行)
│   ├── BubbleMerger.kt              # 气泡列表管理/去重/AtomicLong ID (~200行)
│   ├── CommandRouter.kt             # 命令分发/群聊路由 (~150行)
│   ├── SaveLoadManager.kt           # 保存/加载/列表 (~100行)
│   └── ExportManager.kt             # 导出/Share Intent (~80行)
├── components/                       # UI 组件 (现有，不动)
└── DramaDetailUiState.kt            # 提取到独立文件

domain/model/scenebubble/            # SceneBubble 拆分后
├── SceneBubble.kt                   # 密封类基类 (~30行)
├── Narration.kt                     # 旁白子类
├── Dialogue.kt                      # 对话子类
├── UserMessage.kt                   # 用户消息子类
├── ActorInteraction.kt              # 角色互动子类
├── SceneDivider.kt                  # 场景分隔子类
├── SystemError.kt                   # 错误子类
└── PlotGuidance.kt                  # 剧情引导子类

data/remote/interceptor/
├── AuthInterceptor.kt               # 现有
├── NetworkExceptionInterceptor.kt   # 现有
└── BaseUrlInterceptor.kt            # 新增：动态 baseUrl
```

### Pattern 1: ViewModel 子组件组合 (D-23-01)

**What:** 将 God Object ViewModel 拆分为多个子组件类，由主 VM 持有引用并协调。
**When to use:** 当 ViewModel 承担 >5 个职责，单文件超过 500 行。

```kotlin
// Source: [CITED: Android官方ViewModel指南 + 项目DISCUSSION-LOG]

// 子组件基类 — 持有 viewModelScope 引用但不继承 ViewModel
abstract class ViewModelSubComponent(
    protected val viewModelScope: CoroutineScope,
) {
    /** 主 VM onCleared 时调用，子组件清理资源 */
    open fun onCleared() {}
}

// 子组件示例 — ConnectionOrchestrator
class ConnectionOrchestrator(
    viewModelScope: CoroutineScope,
    private val webSocketManager: WebSocketManager,
    private val serverPreferences: ServerPreferences,
) : ViewModelSubComponent(viewModelScope) {

    private val _connectionState = MutableStateFlow<ConnectionState>(ConnectionState.Disconnected)
    val connectionState: StateFlow<ConnectionState> = _connectionState.asStateFlow()

    // SharedFlow 事件上报给主 VM
    private val _events = MutableSharedFlow<ConnectionEvent>()
    val events: SharedFlow<ConnectionEvent> = _events.asSharedFlow()

    fun acquireConnection(dramaId: String) { ... }
    fun releaseConnection() { ... }

    override fun onCleared() {
        releaseConnection()
    }
}

// 主 VM 作为协调者
@HiltViewModel
class DramaDetailViewModel @Inject constructor(
    /* 依赖注入 */
) : ViewModel() {
    // 子组件实例 — 在 init 块中创建
    private val connectionOrchestrator = ConnectionOrchestrator(viewModelScope, webSocketManager, serverPreferences)
    private val bubbleMerger = BubbleMerger(viewModelScope)
    private val commandRouter = CommandRouter(viewModelScope, dramaRepository, bubbleMerger)
    private val saveLoadManager = SaveLoadManager(viewModelScope, dramaSaveRepository, dramaRepository)
    private val exportManager = ExportManager(viewModelScope, dramaRepository)

    init {
        // 订阅子组件事件
        viewModelScope.launch {
            connectionOrchestrator.events.collect { event ->
                when (event) {
                    is ConnectionEvent.StateChanged -> _uiState.update { it.copy(connectionState = event.state) }
                    is ConnectionEvent.WsEvent -> handleWsEventFromOrchestrator(event.wsEvent)
                }
            }
        }
    }

    override fun onCleared() {
        super.onCleared()
        connectionOrchestrator.onCleared()
        bubbleMerger.onCleared()
        commandRouter.onCleared()
        saveLoadManager.onCleared()
        exportManager.onCleared()
    }
}
```

**关键约束：**
- 子组件不是 ViewModel，不享受 `@HiltViewModel` 的自动 DI。依赖通过主 VM 构造函数传入。
- 子组件通过 `SharedFlow` 向主 VM 上报事件，不直接修改 `_uiState`。
- 主 VM 持有唯一的 `_uiState`，是 Single Source of Truth。

### Pattern 2: WebSocket @ActivityScoped + 引用计数 (D-23-05/06)

**What:** 将 WebSocketManager 从 @Singleton 降级为 @ActivityScoped，多个 VM 通过 acquire/release 引用计数共享连接。
**When to use:** 当 WS 连接属于页面级资源，多个 VM 需要共享同一连接。

```kotlin
// Source: [CITED: Hilt官方文档 — ActivityScoped]

// 1. 修改 DI 声明
@Module
@InstallIn(ActivityComponent::class)  // 从 SingletonComponent 改为 ActivityComponent
object WebSocketModule {
    @Provides
    @ActivityScoped  // 从 @Singleton 改为 @ActivityScoped
    fun provideWebSocketManager(
        okHttpClient: OkHttpClient,
        json: Json,
        @ApplicationContext context: Context,
    ): WebSocketManager {
        return WebSocketManager(okHttpClient, json, context)
    }
}

// 2. WebSocketManager 添加引用计数
class WebSocketManager @Inject constructor(...) {
    private val refCount = java.util.concurrent.atomic.AtomicInteger(0)

    fun acquire(host: String, port: String, token: String?, baseUrl: String? = null): Flow<WsEventDto> {
        if (refCount.getAndIncrement() == 0) {
            // 第一个 acquire：建立连接
            connect(host, port, token, baseUrl)
        }
        return _events.asSharedFlow()
    }

    fun release() {
        if (refCount.decrementAndGet() <= 0) {
            // 最后一个 release：断开连接
            refCount.set(0)
            disconnect()
        }
    }
}

// 3. ViewModel 使用
@HiltViewModel
class DramaDetailViewModel @Inject constructor(
    private val webSocketManager: WebSocketManager,  // Hilt 自动注入 ActivityScoped 实例
) : ViewModel() {
    init {
        webSocketManager.acquire(host, port, token, baseUrl)
    }

    override fun onCleared() {
        webSocketManager.release()  // 引用计数 -1
    }
}
```

**关键约束：**
- `@InstallIn(ActivityComponent::class)` 需要 Activity 使用 `@AndroidEntryPoint`。项目已使用 Hilt，MainActivity 应已标注。
- `@ActivityScoped` 实例在 Activity 销毁时自动清理，但 WS 连接应通过 acquire/release 主动管理。
- DramaCreateViewModel 和 DramaDetailViewModel 共享同一 Activity 中的 WS 连接——acquire/release 引用计数正是为此设计。

### Pattern 3: BaseUrlInterceptor + 内存缓存 (D-23-10)

**What:** 用 OkHttp Interceptor 动态替换请求 URL，替代 Retrofit 构建时固定的 baseUrl。
**When to use:** 当用户需要运行时切换服务器地址而不重启 Activity。

```kotlin
// Source: [CITED: OkHttp Interceptor官方文档 + 项目DISCUSSION-LOG]

class BaseUrlInterceptor @Inject constructor(
    private val serverPreferences: ServerPreferences,
) : Interceptor {
    override fun intercept(chain: Chain): Response {
        val cachedBaseUrl = serverPreferences.cachedBaseUrl  // 内存缓存，零阻塞
        if (cachedBaseUrl.isNullOrBlank()) return chain.proceed(chain.request())

        val originalUrl = chain.request().url
        val newUrl = originalUrl.newBuilder()
            .scheme(cachedBaseUrl.scheme)
            .host(cachedBaseUrl.host)
            .port(cachedBaseUrl.port)
            .build()
        return chain.proceed(chain.request().newBuilder().url(newUrl).build())
    }
}

// ServerPreferences 添加内存缓存
class ServerPreferences @Inject constructor(
    private val dataStore: DataStore<Preferences>,
    private val secureStorage: SecureStorage,
) {
    // 内存缓存 — DataStore 写入时同步更新
    @Volatile private var _cachedBaseUrl: HttpUrl? = null
    val cachedBaseUrl: HttpUrl? get() = _cachedBaseUrl

    val serverConfig: Flow<ServerConfig?> = dataStore.data.map { prefs ->
        val config = // ... 现有逻辑
        // 更新内存缓存
        config?.toApiBaseUrl()?.let { url ->
            _cachedBaseUrl = url.toHttpUrl()
        }
        config
    }

    suspend fun saveServerConfig(config: ServerConfig) {
        dataStore.edit { /* 现有逻辑 */ }
        // 同步更新内存缓存
        config.toApiBaseUrl().let { url ->
            _cachedBaseUrl = url.toHttpUrl()
        }
        secureStorage.saveToken(config.token)
    }
}
```

**关键约束：**
- Retrofit 的 baseUrl 变为占位符（如 `http://localhost/`），实际 URL 由 Interceptor 动态替换。
- 内存缓存在 `saveServerConfig()` 时同步更新，Interceptor 读取时零阻塞。
- 首次启动时 DataStore 可能未初始化完成，需要 fallback 占位 URL。

### Pattern 4: R8/ProGuard 保守 Keep 规则 (D-23-08/09)

**What:** 启用 R8 混淆 + shrinkResources，用保守 keep 规则保护 Retrofit DTO/接口。
**When to use:** Release 构建必须启用混淆。

```kotlin
// build.gradle.kts
buildTypes {
    release {
        isMinifyEnabled = true
        isShrinkResources = true
        proguardFiles(
            getDefaultProguardFile("proguard-android-optimize.txt"),
            "proguard-rules.pro"
        )
    }
}
```

```proguard
# proguard-rules.pro — 保守 keep 策略

# === Retrofit 接口 — 方法名和参数名用于反射 ===
-keep,allowobfuscation interface com.drama.app.data.remote.api.** { *; }

# === DTO 类 — kotlinx-serialization 反射访问字段 ===
-keep class com.drama.app.data.remote.dto.** { *; }

# === SceneBubble 密封类 — 序列化需要类名匹配 @SerialName ===
-keep class com.drama.app.domain.model.SceneBubble { *; }
-keep class com.drama.app.domain.model.SceneBubble$* { *; }
-keep class com.drama.app.domain.model.InteractionType { *; }

# === Hilt 注入点 — @Inject 构造函数和 @Module 方法 ===
-dontwarn dagger.hilt.**
-keep class com.drama.app.di.** { *; }

# === Kotlin Serialization — 需要保留 companion object ===
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.AnnotationsKt

# === Coroutine — MainDispatcherFactory ===
-keepnames class kotlinx.coroutines.internal.MainDispatcherFactory {}
-keepnames class kotlinx.coroutines.CoroutineExceptionHandler {}

# === OkHttp — 连接池和 WebSocket ===
-dontwarn okhttp3.**
-dontwarn okio.**
```

**关键约束：**
- kotlinx-serialization 使用 `@SerialName` 做多态序列化，类名和字段名不能被混淆。必须 keep 所有 DTO 和密封类子类。
- Retrofit 接口方法名用于反射创建代理，必须 keep。
- Hilt 的 `@Module` 类必须 keep，否则 DI 图不完整。
- 首次启用 R8 后，必须逐个 API 端点验证 Release 构建。

### Pattern 5: network_security_config 白名单 (D-23-14)

**What:** 关闭全局 cleartext，仅允许本地开发 IP 的明文 HTTP。
**When to use:** 局域网开发场景需要明文，但生产环境应强制 HTTPS。

```xml
<!-- res/xml/network_security_config.xml -->
<network-security-config>
    <!-- 默认禁止明文 -->
    <base-config cleartextTrafficPermitted="false">
        <trust-anchors>
            <certificates src="system" />
        </trust-anchors>
    </base-config>

    <!-- 仅允许本地开发环境的明文通信 -->
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="true">10.0.2.2</domain>       <!-- Android 模拟器 → 宿主机 -->
        <domain includeSubdomains="true">localhost</domain>        <!-- 本地回环 -->
        <domain includeSubdomains="true">127.0.0.1</domain>       <!-- 本地回环 -->
        <!-- 注意：192.168.x.x 等 LAN IP 无法用 domain-config 精确匹配，
             需要在 debug 构建中使用 debug-only 的安全配置覆盖 -->
    </domain-config>
</network-security-config>
```

```xml
<!-- res/xml/network_security_config_debug.xml (可选: debug 构建专用) -->
<network-security-config>
    <base-config cleartextTrafficPermitted="true">
        <trust-anchors>
            <certificates src="system" />
            <certificates src="user" />
        </trust-anchors>
    </base-config>
</network-security-config>
```

**关键约束：**
- `domain-config` 不支持 CIDR 表示法（如 `192.168.0.0/16`），只能匹配精确域名/IP。 [CITED: Android官方文档]
- LAN 开发时需要连接 `192.168.x.x`，这些 IP 无法在 `domain-config` 中白名单化。
- **推荐方案：** Release 用严格配置（仅 localhost/10.0.2.2），Debug 用宽松配置（cleartextTrafficPermitted=true）。可通过 `buildTypes` 的 `resValue` 或 manifest placeholder 区分。

### Pattern 6: WS优先/REST降级数据源策略 (D-23-16)

**What:** ConnectionOrchestrator 维护 WS 连接状态，BubbleMerger 根据状态决定接受哪个数据源。
**When to use:** REST 和 WS 双通道写入同一 UiState 导致闪烁。

```kotlin
// Source: [CITED: 项目DISCUSSION-LOG §3.4]

class ConnectionOrchestrator(...) : ViewModelSubComponent(viewModelScope) {
    val isWsConnected: StateFlow<Boolean> = connectionState.map {
        it == ConnectionState.Connected
    }.stateIn(viewModelScope, SharingStarted.Eagerly, false)

    fun shouldAcceptRestUpdate(): Boolean = !isWsConnected.value
}

class BubbleMerger(...) : ViewModelSubComponent(viewModelScope) {
    fun addFromRest(bubbles: List<SceneBubble>, isWsConnected: Boolean): List<SceneBubble> {
        if (isWsConnected) return emptyList()  // WS 连接时拒绝 REST 气泡
        return mergeBubbles(currentBubbles, bubbles)
    }

    fun addFromWs(bubble: SceneBubble): List<SceneBubble> {
        return mergeBubbles(currentBubbles, listOf(bubble))
    }
}
```

### Anti-Patterns to Avoid

- **子组件直接修改 _uiState：** 子组件只能通过 SharedFlow 上报事件，主 VM 是唯一修改 _uiState 的地方。违反则破坏 Single Source of Truth。
- **子组件持有 ViewModel 引用：** 子组件只持有 `viewModelScope: CoroutineScope`，不持有 `ViewModel` 实例。否则产生循环引用。
- **R8 全局 -keep class * { *; }：** 这等于不混淆。必须精确 keep，只保留必要的类。
- **network_security_config 全局允许 cleartext：** 这等于没改。必须用 domain-config 限制范围。

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 动态 BaseUrl | 自建 URL 拼接工厂 | BaseUrlInterceptor | OkHttp Interceptor 是官方机制，自动处理 scheme/host/port 重写 |
| 引用计数 | 手动 synchronized 计数器 | AtomicInteger | 并发安全，零锁开销 |
| 协程测试调度器 | 自建 TestCoroutineScope | UnconfinedTestDispatcher + runTest | 官方 kotlinx-coroutines-test 处理了延迟虚拟化和异常传播 |
| Flow 测试 | 手动 collect + assertThat | Turbine | Turbine 处理了超时、缓冲、completion 等边界情况 |
| 网络安全配置 | 代码层拦截 HTTP 请求 | network_security_config.xml | Android 系统级强制，代码层可被绕过 |

**Key insight:** 本阶段的"不要自己造"核心在于：Android 生态已有成熟方案解决每个子问题。R8 混淆、OkHttp Interceptor、Hilt 作用域、DataStore 缓存、Turbine 测试——每个都是千锤百炼的方案，自建必然遗漏边界条件。

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | DataStore: `drama_settings` (server_ip, server_port, server_base_url, last_connected); `drama_saves` (local save names) | 无需数据迁移——BaseUrlInterceptor 仅改读取方式，不改存储格式 |
| Live service config | WebSocketManager @Singleton DI 声明在 NetworkModule.kt + Hilt 编译期生成的代码 | 代码修改：`@InstallIn(SingletonComponent)` → `@InstallIn(ActivityComponent)`，`@Singleton` → `@ActivityScoped`；需确保 Hilt 重新编译 |
| OS-registered state | 无 — 项目无后台 Service/WorkManager/AlarmManager | 无需操作 |
| Secrets/env vars | SecureStorage 加密存储 auth token; DataStore 明文存储 server IP:port | 无需操作 — token 存储方式不变 |
| Build artifacts | `android/app/build/` 目录包含 debug APK 编译产物 | R8 启用后需 clean rebuild：`./gradlew clean assembleRelease` |

**Nothing found in category:** OS-registered state — verified by codebase scan (no Service/WorkManager/AlarmManager registrations).

## Common Pitfalls

### Pitfall 1: VM 拆分后 SharedFlow 事件丢失
**What goes wrong:** 子组件在 `_events.tryEmit()` 时，主 VM 的 `collect` 可能尚未启动，导致事件丢失。
**Why it happens:** SharedFlow 默认 `replay=0`，新订阅者不会收到历史事件。子组件 init 中发射的事件可能早于主 VM 的 collect。
**How to avoid:** 使用 `MutableSharedFlow<T>(extraBufferCapacity = 64)`（项目 WebSocketManager 已用此模式），或在主 VM init 中先 collect 再触发子组件初始化。
**Warning signs:** 拆分后 UI 不显示初始状态（如连接状态为 Disconnected 但未更新）。

### Pitfall 2: @ActivityScoped 导致跨 Activity 注入失败
**What goes wrong:** 将 WebSocketManager 改为 `@ActivityScoped` 后，如果 Service 或 Application 级组件尝试注入它，Hilt 报错。
**Why it happens:** `@ActivityScoped` 只能注入到 ActivityComponent 子图中，无法从 SingletonComponent 访问。
**How to avoid:** 确认所有 WebSocketManager 的注入点都在 Activity/Fragment/ViewModel 中（代码扫描确认：只有 DramaDetailViewModel 和 DramaCreateViewModel 使用，都是 @HiltViewModel，OK）。
**Warning signs:** Hilt 编译错误 `Dependency 'WebSocketManager' is not available from SingletonComponent`。

### Pitfall 3: R8 混淆后 Retrofit 序列化崩溃
**What goes wrong:** Release 构建运行时 `ClassNotFoundException` 或 JSON 字段名不匹配。
**Why it happens:** Retrofit 用反射调用接口方法，kotlinx-serialization 用 `@SerialName` 匹配 JSON 字段。混淆后类名/字段名改变，反射找不到或字段名不匹配。
**How to avoid:** 保守 keep 所有 DTO 类和 Retrofit 接口。逐个 API 端点在 Release 构建上验证。
**Warning signs:** Debug 构建正常，Release 构建崩溃；或 JSON 反序列化返回默认值而非实际数据。

### Pitfall 4: network_security_config 不支持 LAN CIDR
**What goes wrong:** 按讨论中的方案写 `<domain includeSubdomains="true">192.168.0.0/16</domain>`，但 Android 实际不支持 CIDR 表示法。
**Why it happens:** Android 的 `domain-config` 只匹配精确域名或 IP 字符串，不支持 CIDR 范围。
**How to avoid:** Debug 构建用宽松配置（`cleartextTrafficPermitted=true`），Release 构建只白名单 `10.0.2.2`（模拟器）和 `localhost`。LAN 开发用 Debug 构建。
**Warning signs:** 连接局域网 IP 时报 `Cleartext HTTP traffic not permitted`。

### Pitfall 5: BaseUrlInterceptor 首次启动缓存为空
**What goes wrong:** 首次安装后，`ServerPreferences.cachedBaseUrl` 为 null，所有网络请求使用占位 URL，全部失败。
**Why it happens:** 内存缓存在 DataStore 首次读取后才更新，但首次启动时 DataStore 可能还未写入。
**How to avoid:** 在 `BaseUrlInterceptor` 中，如果缓存为 null 则 `chain.proceed(chain.request())`（使用 Retrofit 占位 URL）；或在 Application.onCreate 中预热缓存。
**Warning signs:** 首次启动后所有网络请求 404。

### Pitfall 6: BubbleMerger 的 contentFingerprint 碰撞
**What goes wrong:** 两个不同消息因为前 N 个字符相同而被错误去重。
**Why it happens:** `contentFingerprint` 使用 `text.take(60)` 或 `text.take(80)`，不同消息可能有相同前缀。
**How to avoid:** 增加 fingerprint 长度（如 take(120)），或在 BubbleMerger 中增加 id-based 去重作为安全网。测试中必须覆盖此场景。
**Warning signs:** 重连后丢失消息，或列表中消息突然消失。

### Pitfall 7: 子组件引用主 VM 的 _uiState 造成循环
**What goes wrong:** 子组件持有主 VM 的 `_uiState` 引用，直接读取或修改它，产生隐式依赖。
**Why it happens:** 拆分时图方便，子组件直接 `_uiState.value` 读取当前状态。
**How to avoid:** 子组件所需的状态通过构造函数参数传入（如 `isWsConnected: Boolean`），不持有 StateFlow 引用。主 VM 负责将状态传递给子组件方法。
**Warning signs:** 子组件方法签名包含 `uiState: DramaDetailUiState` 参数。

## Code Examples

### 子组件事件定义与主 VM 订阅
```kotlin
// Source: [ASSUMED] — 基于项目 DISCUSSION-LOG 和 Kotlin SharedFlow 最佳实践

sealed class ConnectionEvent {
    data class StateChanged(val state: ConnectionState) : ConnectionEvent()
    data class WsEvent(val wsEvent: WsEventDto) : ConnectionEvent()
    data class Reconnected(val serverScene: Int) : ConnectionEvent()
    data object PermanentFailure : ConnectionEvent()
}

// 主 VM 订阅
viewModelScope.launch {
    connectionOrchestrator.events.collect { event ->
        when (event) {
            is ConnectionEvent.StateChanged ->
                _uiState.update { it.copy(connectionState = event.state) }
            is ConnectionEvent.WsEvent ->
                bubbleMerger.addFromWs(mapWsEventToBubble(event.wsEvent))
            is ConnectionEvent.Reconnected ->
                handleReconnectSync(event.serverScene)
            is ConnectionEvent.PermanentFailure ->
                addErrorBubble("WebSocket 连接失败，已降级到 REST 轮询")
        }
    }
}
```

### BubbleMerger 测试示例
```kotlin
// Source: [CITED: Turbine官方文档 + kotlinx-coroutines-test官方指南]

class BubbleMergerTest {
    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()  // UnconfinedTestDispatcher

    private lateinit var merger: BubbleMerger

    @Before
    fun setup() {
        merger = BubbleMerger(StandardTestDispatcher())
    }

    @Test
    fun `deduplication removes duplicate fingerprint`() = runTest {
        val bubble1 = SceneBubble.Narration(id = "1", text = "Hello world")
        val bubble2 = SceneBubble.Narration(id = "2", text = "Hello world")  // 相同 fingerprint

        merger.addFromWs(bubble1)
        merger.addFromWs(bubble2)

        assertEquals(1, merger.currentBubbles.size)
    }

    @Test
    fun `REST bubbles rejected when WS connected`() = runTest {
        val restBubbles = listOf(SceneBubble.Dialogue(id = "r1", actorName = "A", text = "Hi"))

        val result = merger.addFromRest(restBubbles, isWsConnected = true)
        assertTrue(result.isEmpty())
    }
}

// DispatcherRule for coroutines test
class MainDispatcherRule(
    private val testDispatcher: TestDispatcher = UnconfinedTestDispatcher()
) : TestWatcher() {
    override fun starting(description: Description) {
        Dispatchers.setMain(testDispatcher)
    }
    override fun finished(description: Description) {
        Dispatchers.resetMain()
    }
}
```

### Turbine Flow 测试示例
```kotlin
// Source: [CITED: Turbine GitHub README — github.com/Antimonit/turbine]

@Test
fun `connectionOrchestrator emits state changes`() = runTest {
    val orchestrator = ConnectionOrchestrator(
        viewModelScope = this,
        webSocketManager = mockWebSocketManager,
        serverPreferences = mockServerPreferences,
    )

    orchestrator.connectionState.test {
        assertEquals(ConnectionState.Disconnected, awaitItem())
        orchestrator.acquireConnection("test-drama")
        assertEquals(ConnectionState.Connecting, awaitItem())
    }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| @Singleton WebSocketManager | @ActivityScoped + acquire/release | D-23-05/06 决策 | WS 连接跟随 Activity 生命周期，不再泄漏 |
| runBlocking baseUrl | BaseUrlInterceptor + 内存缓存 | D-23-10 决策 | 零阻塞，运行时切换服务器 |
| isMinifyEnabled=false | isMinifyEnabled=true + 保守 keep | D-23-08/09 决策 | Release APK 混淆保护 |
| usesCleartextTraffic=true | network_security_config 白名单 | D-23-14 决策 | 仅本地开发允许明文 |
| deprecated isConnected/isReconnecting | ConnectionState StateFlow | D-23-07 决策 | 消除协程泄漏 |
| Int bubbleCounter | AtomicLong | D-23-03 决策 | 线程安全 ID 生成 |
| REST+WS 双写 | WS优先/REST降级 | D-23-16 决策 | 消除 UI 闪烁 |

**Deprecated/outdated:**
- `WebSocketManager.isConnected` / `isReconnecting`：每次访问创建新 MutableStateFlow + 协程，必须删除 [VERIFIED: 代码审计 lines 80-97]
- `NetworkModule.provideRetrofit()` 中的 `runBlocking`：主线程阻塞，必须替换 [VERIFIED: 代码审计 line 76]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | @ActivityScoped 的 WebSocketManager 可被 @HiltViewModel 注入 | Architecture Patterns | Hilt 编译错误，需改用其他作用域策略 |
| A2 | kotlinx-serialization 的 @SerialName 机制在 R8 混淆后仍然工作（前提是 keep 了 DTO 类） | Architecture Patterns | JSON 反序列化失败，需额外 keep 规则 |
| A3 | domain-config 不支持 CIDR，192.168.x.x LAN IP 无法白名单化 | Common Pitfalls | 需要采用 Debug/Release 分离配置策略 |
| A4 | DramaCreateViewModel 不调用 `webSocketManager.disconnect()`（代码注释说不调用来保持连接给 DramaDetailVM） | Architecture Patterns | acquire/release 引用计数需正确处理此场景 |
| A5 | Hilt 2.54 支持 @InstallIn(ActivityComponent::class) + @ActivityScoped | Architecture Patterns | 需升级 Hilt 版本 |

**A5 验证：** Hilt 自 2.31+ 支持 `ActivityComponent` 和 `@ActivityScoped`。项目使用 Hilt 2.54，完全支持。[CITED: Android开发者文档 — Hilt组件生命周期]

## Open Questions

1. **DramaCreateViewModel 的 WS 连接移交机制**
   - What we know: 当前代码注释说 DramaCreateVM 导航到 DramaDetailVM 时不调用 `webSocketManager.disconnect()`，以保持连接
   - What's unclear: 改为 acquire/release 后，DramaCreateVM 的 release 是否应在导航前调用？如果 DramaDetailVM 的 acquire 在 DramaCreateVM 的 release 之前，则引用计数不会降为 0，连接不断
   - Recommendation: DramaCreateVM 在 `onCleared()` 时 release，DramaDetailVM 在 `init` 时 acquire。由于两个 VM 都在同一 Activity 中，@ActivityScoped 实例相同，引用计数从 1→2→1 不会断连

2. **network_security_config 对 192.168.x.x 的处理**
   - What we know: `domain-config` 不支持 CIDR，LAN IP 无法精确白名单
   - What's unclear: Release 构建是否需要允许 192.168.x.x 明文
   - Recommendation: Release 构建仅允许 localhost/10.0.2.2；LAN 开发使用 Debug 构建（宽松配置）。这在 CONTEXT.md 的 D-23-14 中已隐含

3. **R8 对 kotlinx-serialization 插件的影响**
   - What we know: kotlinx-serialization 编译器插件在编译期生成 serializer，字段名以字符串常量存储
   - What's unclear: R8 是否可能内联这些常量后混淆原始类字段名
   - Recommendation: keep 所有 DTO 和密封类子类。首次 Release 构建后必须逐个 API 端点验证

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| JDK 17 | Android 编译 | ✓ (CI) | — | — |
| Android SDK / compileSdk 35 | 构建目标 | ✓ | 35 | — |
| Gradle 8.x | 构建系统 | ✓ | — | — |
| Kotlin 2.1.0 | 主语言 | ✓ | 2.1.0 | — |
| Hilt 2.54 | DI 框架 | ✓ | 2.54 | — |

**Missing dependencies with no fallback:**
- 无 — 所有编译时依赖已在项目中声明

**Missing dependencies with fallback:**
- 无测试依赖（需新增 junit, mockito-kotlin, kotlinx-coroutines-test, turbine）— 但这是 23-02 的任务，不阻塞 23-01

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | JUnit 4 + kotlinx-coroutines-test + Turbine |
| Config file | none — 见 Wave 0 |
| Quick run command | `./gradlew :app:testDebugUnitTest --tests "com.drama.app.*"` |
| Full suite command | `./gradlew :app:testDebugUnitTest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ARCH-01 | BubbleMerger 去重/排序逻辑 | unit | `./gradlew :app:testDebugUnitTest --tests "*.BubbleMergerTest"` | ❌ Wave 0 |
| ARCH-02 | ConnectionOrchestrator 状态机 | unit | `./gradlew :app:testDebugUnitTest --tests "*.ConnectionOrchestratorTest"` | ❌ Wave 0 |
| ARCH-05 | CommandRouter 路由分发 | unit | `./gradlew :app:testDebugUnitTest --tests "*.CommandRouterTest"` | ❌ Wave 0 |
| ARCH-06 | WebSocketManager 重连逻辑 | unit | `./gradlew :app:testDebugUnitTest --tests "*.WebSocketManagerTest"` | ❌ Wave 0 |
| ARCH-10 | WS优先/REST降级策略 | unit | `./gradlew :app:testDebugUnitTest --tests "*.SingleSourceOfTruthTest"` | ❌ Wave 0 |
| ARCH-03 | R8 混淆 Release 构建 | manual | `./gradlew assembleRelease && unzip -l app/build/outputs/apk/release/*.apk \| grep com.drama` | ❌ Wave 0 |
| ARCH-04 | BaseUrlInterceptor 动态 URL | unit | `./gradlew :app:testDebugUnitTest --tests "*.BaseUrlInterceptorTest"` | ❌ Wave 0 |
| ARCH-06 | network_security_config | manual | 检查 Release 构建连接局域网 IP 行为 | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `./gradlew :app:testDebugUnitTest --tests "com.drama.app.subcomponent.*"`
- **Per wave merge:** `./gradlew :app:testDebugUnitTest`
- **Phase gate:** Full suite green + Release APK 验证混淆生效

### Wave 0 Gaps
- [ ] `src/test/java/com/drama/app/` — 测试目录不存在，需创建
- [ ] `libs.versions.toml` — 需添加 junit, mockito-kotlin, kotlinx-coroutines-test, turbine 版本和库声明
- [ ] `build.gradle.kts` — 需添加 testImplementation 依赖
- [ ] `src/test/java/com/drama/app/BubbleMergerTest.kt` — BubbleMerger 去重测试
- [ ] `src/test/java/com/drama/app/CommandRouterTest.kt` — CommandRouter 路由测试
- [ ] `src/test/java/com/drama/app/ConnectionOrchestratorTest.kt` — ConnectionOrchestrator 状态机测试
- [ ] `MainDispatcherRule.kt` — 共享的协程测试 Rule

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Token-based auth via SecureStorage (existing) |
| V3 Session Management | yes | WebSocket token via query parameter (known risk, deferred) |
| V4 Access Control | no | Single-user LAN app |
| V5 Input Validation | yes | CommandType.fromInput() validation (existing) |
| V6 Cryptography | yes | EncryptedSharedPreferences for token (existing security-crypto) |
| V8 Data Protection | yes | R8 obfuscation (new), network_security_config (new) |
| V9 Communication Security | yes | Cleartext traffic restriction (new), BuildConfig.DEBUG logging guard (new) |

### Known Threat Patterns for Android/Kotlin Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| APK reverse engineering | Information Disclosure | R8 obfuscation + shrinkResources (ARCH-03) |
| Network traffic interception | Tampering, Information Disclosure | network_security_config 禁止明文 (ARCH-06) |
| Auth token in WS URL query parameter | Information Disclosure | 已知风险，LAN 场景可接受；生产需迁移到 WS auth message |
| Release build logging sensitive data | Information Disclosure | BuildConfig.DEBUG 条件注入 HttpLoggingInterceptor (ARCH-11) |
| runBlocking ANR → 崩溃日志泄露 | Denial of Service | BaseUrlInterceptor 替代 runBlocking (ARCH-04) |

## Sources

### Primary (HIGH confidence)
- 项目代码库审计：DramaDetailViewModel.kt (1665行), WebSocketManager.kt (351行), NetworkModule.kt (106行), build.gradle.kts, AndroidManifest.xml, SceneBubble.kt (252行), AuthRepositoryImpl.kt (60行)
- CONTEXT.md 决策：D-23-01~D-23-18 全部锁定
- DISCUSSION-LOG.md：造化宗师审视，7本质/17表象归因
- CONCERNS.md：代码库审计报告

### Secondary (MEDIUM confidence)
- Maven Central: turbine 1.2.0, mockito-kotlin 5.4.0, kotlinx-coroutines-test 1.10.2, junit 4.13.2 [VERIFIED]
- Hilt 2.54 ActivityComponent 支持 [CITED: Android开发者文档]
- network_security_config 不支持 CIDR [CITED: 多个开发者社区验证]

### Tertiary (LOW confidence)
- R8 对 kotlinx-serialization 插件的完整兼容性 — 需 Release 构建验证 [ASSUMED]
- @ActivityScoped WS 在多个 ViewModel 间的实际行为 — 需集成测试验证 [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — 项目依赖已锁定，测试库版本已从 Maven Central 验证
- Architecture: HIGH — CONTEXT.md 已锁定 18 项设计决策，代码库已完整审计
- Pitfalls: HIGH — 7 个常见陷阱全部来自代码审计或 Android 官方文档

**Research date:** 2026-04-26
**Valid until:** 2026-05-26 (30 days — 项目依赖稳定，无快速变化因素)
