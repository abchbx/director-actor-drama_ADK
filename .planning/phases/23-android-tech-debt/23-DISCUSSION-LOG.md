# Phase 23: Android 技术债务治理 — Discussion Log

**Date:** 2026-04-26
**Status:** Discussion Complete → Ready for Planning
**Lens:** 造化宗师·追求完美 — 删繁就简，像素级完美

---

## 1. 造化宗师审视：17 个问题，几多本质？

造化宗师先质疑：此 17 个问题，真有 17 个乎？

剥去表象，直抵本质：

| 本质问题 | 衍生表象 | 数量 |
|----------|----------|------|
| **God Object** — 一个 VM 承担了 15+ 职责 | P0-1 (1537→1665行巨型VM), P1-4 (双重数据源无统一状态机), P2-1 (bubbleCounter非线程安全), P3-5 (轮询+WS+REST三通道) | **4** |
| **生命周期失控** — WS 连接不跟随 VM 生命周期 | P0-2 (WS全局单例+VM冲突), P2-2 (deprecated属性每次创建新Flow) | **2** |
| **安全裸奔** — 发布版本无任何防护 | P0-3 (无R8混淆), P1-3 (明文HTTP), P3-2 (Release日志泄露) | **3** |
| **DI 反模式** — 依赖注入违背基本原则 | P1-1 (baseUrl固定+runBlocking), P2-4 (每次验证新建Retrofit) | **2** |
| **零质量保障** — 无测试无CI | P1-2 (零测试覆盖), P3-3 (无CI/CD) | **2** |
| **数据层简陋** — 无缓存无重试 | P2-3 (hardcoded重试), P2-5 (无离线缓存), P3-4 (SceneBubble集中) | **3** |
| **体积浪费** | P3-1 (全量图标库) | **1** |

**造化宗师判决：17 个表象，7 个本质。治本不治标。**

---

## 2. P0 歼灭战深度剖析

### 2.1 DramaDetailViewModel 拆分方案

**当前状态：** 1665 行 God Object，职责包括：
- 初始化同步（startDrama/syncDramaState）
- WS 生命周期管理（connectWs/disconnectWs/reconnectWs）
- REST 轮询降级（pollDramaStatus/pollSceneDetail）
- 15+ WS 事件处理（handleWsEvent 巨型 when）
- 场景气泡加载（loadSceneBubbles/addBubbles）
- 场景历史（sceneHistory/scenes）
- 保存/加载（saveDrama/loadDrama/listSavedDramas）
- 演员面板（actors/actorPanelExpanded）
- 命令分发（sendCommand/sendChatMessage）
- 群聊消息（mention/senderName）
- 导出（exportDrama/isExporting）
- 状态刷新（refreshDramaStatus）

**拆分策略：** 不是简单的文件切割，而是按职责边界建立独立的 ViewModel 子组件。

```
DramaDetailViewModel (协调者, ~300行)
  ├── ConnectionOrchestrator (~250行) — WS连接/重连/心跳/轮询降级
  ├── BubbleMerger (~200行) — 气泡列表管理/去重/线程安全ID
  ├── CommandRouter (~150行) — 命令分发/群聊消息/mention路由
  ├── SaveLoadManager (~100行) — 保存/加载/列表
  └── ExportManager (~80行) — 导出/Share Intent
```

**造化宗师质问：** 为何不是独立的 ViewModel？

答：Android Compose Navigation 的 ScopedViewModel 机制下，多个 ViewModel 共享同一个 `SavedStateHandle` 很麻烦。采用子组件模式（组合而非继承），由主 VM 持有子组件引用，子组件通过 `Channel`/`SharedFlow` 向主 VM 上报事件。这样：
1. 主 VM 变成纯粹的协调者
2. 每个子组件可独立单元测试
3. 不破坏现有的 Compose UI 绑定

**关键设计决策：**

| ID | 决策 | 选择 | 理由 |
|----|------|------|------|
| D-23-01 | 拆分策略 | 子组件组合（非独立VM） | Compose ViewModel scope 共享复杂度 |
| D-23-02 | 子组件通信 | SharedFlow 事件上报 | 解耦 + 可测试 |
| D-23-03 | 气泡ID线程安全 | AtomicLong 替代 Int | 零冲突 |
| D-23-04 | 子组件生命周期 | 主 VM onCleared 时统一清理 | 无泄漏 |

### 2.2 WebSocketManager 生命周期统一

**当前问题：**
- `@Singleton` 全局单例 — 生命周期与 Activity 无关
- 自建 `reconnectScope` 永不取消
- `deprecated` 属性每次创建新协程
- 2 个 VM 同时观察 WS 事件，关闭时机冲突

**方案：** 引入 `ConnectionLifecycleOwner` 接口

```kotlin
interface ConnectionLifecycleOwner {
    fun acquireConnection(dramaId: String)
    fun releaseConnection()
    val connectionState: StateFlow<ConnectionState>
}

// DramaDetailViewModel 实现 ConnectionLifecycleOwner
// WebSocketManager 从 @Singleton 降级为 @ActivityScoped
// acquire/release 引用计数，最后一个释放时断开连接
```

**造化宗师判决：** `@Singleton` → `@ActivityScoped` 是治本。WS 连接属于页面级资源，不是应用级资源。谁创建谁销毁，大道至简。

| ID | 决策 | 选择 | 理由 |
|----|------|------|------|
| D-23-05 | WS 作用域 | @ActivityScoped 替代 @Singleton | 连接属于页面，非应用 |
| D-23-06 | 多VM共享 | 引用计数 acquire/release | 最后一个释放才断开 |
| D-23-07 | deprecated属性 | 删除，改为 StateFlow | 消除协程泄漏 |

### 2.3 R8 混淆

**当前：** `isMinifyEnabled = false`，APK 完全可逆向。

**方案：**
1. `isMinifyEnabled = true`（release）
2. 编写 ProGuard 规则保留：
   - Retrofit 接口（`-keep interface com.drama.app.data.remote.api.** { *; }`）
   - Pydantic 模型 DTO（`-keep class com.drama.app.data.remote.dto.** { *; }`）
   - Compose 相关（R8 自动处理）
   - Hilt 注入点
3. `shrinkResources = true`（资源压缩）

**造化宗师注意：** 这不是简单加一行 `isMinifyEnabled = true`。ProGuard 规则不完整 = 运行时 ClassNotFoundException = 白做。必须逐个验证 Retrofit DTO 序列化不被混淆。

| ID | 决策 | 选择 | 理由 |
|----|------|------|------|
| D-23-08 | R8 范围 | isMinifyEnabled + shrinkResources | 全面压缩 |
| D-23-09 | ProGuard 策略 | 保守 keep（DTO/接口） + R8 自动分析 | 安全优先 |

---

## 3. P1 阵地战深度剖析

### 3.1 BaseUrl 动态切换

**当前：** `NetworkModule` 中 `runBlocking { serverPreferences.serverConfig.first() }` 阻塞主线程。

**方案：** `BaseUrlInterceptor`

```kotlin
class BaseUrlInterceptor @Inject constructor(
    private val serverPreferences: ServerPreferences
) : Interceptor {
    override fun intercept(chain: Chain): Response {
        val baseUrl = runBlocking { serverPreferences.serverConfig.first() }
        val newUrl = chain.request().url.newBuilder()
            .scheme(baseUrl.scheme)
            .host(baseUrl.host)
            .port(baseUrl.port)
            .build()
        return chain.proceed(chain.request().newBuilder().url(newUrl).build())
    }
}
```

**造化宗师质问：** `runBlocking` 还在？！

答：Interceptor 的 `intercept()` 是同步方法，无法挂起。但这里的 `runBlocking` 与 NetworkModule 中的不同：
- NetworkModule 中：DI 初始化时阻塞**主线程** → ANR 风险
- Interceptor 中：OkHttp 的线程池中阻塞**后台线程** → 可接受

但可以更优雅：用 `serverPreferences.cachedBaseUrl`（在 DataStore 写入时缓存到内存变量），Interceptor 读取内存缓存，零阻塞。

| ID | 决策 | 选择 | 理由 |
|----|------|------|------|
| D-23-10 | BaseUrl 切换 | BaseUrlInterceptor + 内存缓存 | 零阻塞，无需重启 |
| D-23-11 | AuthRepository 新建 Retrofit | 改为复用 OkHttpClient | 减少资源浪费 |

### 3.2 测试覆盖

**当前：** 零测试，零测试依赖。

**方案：** 不追求 60% 覆盖率的虚荣指标。造化宗师要的是**关键路径的确定性**。

优先测试矩阵：

| 优先级 | 测试目标 | 类型 | 预计用例数 |
|--------|---------|------|-----------|
| P0 | BubbleMerger 去重/排序逻辑 | 单元测试 | 8 |
| P0 | CommandRouter 路由分发 | 单元测试 | 6 |
| P0 | ConnectionOrchestrator 状态机 | 单元测试 | 5 |
| P1 | WebSocketManager 重连逻辑 | 单元测试 | 4 |
| P1 | DramaRepository 接口契约 | 单元测试 | 6 |
| P2 | ViewModel 事件流 | Turbine 测试 | 4 |

**总计：~33 个测试用例，覆盖核心拆分后的子组件。**

需添加的测试依赖：
- `junit`
- `mockito-kotlin`
- `kotlinx-coroutines-test`
- `turbine`（Flow 测试）

| ID | 决策 | 选择 | 理由 |
|----|------|------|------|
| D-23-12 | 测试策略 | 关键路径优先 | 不追求数字，追求确定性 |
| D-23-13 | 测试目标 | 拆分后的子组件 | 先拆再测，否则无法测 |

### 3.3 安全加固

**当前：**
- `usesCleartextTraffic=true` — 全局允许明文 HTTP
- Release 构建输出 HttpLoggingInterceptor.BODY — 日志泄露

**方案：**

1. `usesCleartextTraffic=false`
2. `network_security_config.xml` 仅放行本地开发：

```xml
<network-security-config>
    <base-config cleartextTrafficPermitted="false">
        <trust-anchors><certificates src="system" /></trust-anchors>
    </base-config>
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="true">10.0.2.2</domain>  <!-- 模拟器 -->
        <domain includeSubdomains="true">192.168.0.0/16</domain>  <!-- 局域网 -->
    </domain-config>
</network-security-config>
```

3. Release 构建条件禁用 HttpLoggingInterceptor：

```kotlin
if (BuildConfig.DEBUG) {
    httpClient.addInterceptor(HttpLoggingInterceptor().apply { level = BODY })
}
```

| ID | 决策 | 选择 | 理由 |
|----|------|------|------|
| D-23-14 | 明文HTTP | 关闭 + network_security_config 白名单 | 安全+开发兼容 |
| D-23-15 | 日志拦截器 | BuildConfig.DEBUG 条件注入 | Release 零泄露 |

### 3.4 单一数据源 (SingleSourceOfTruth)

**当前：** REST 轮询 + WS 推送双通道写入同一个 `UiState`，导致：
- WS 事件和 REST 响应竞争更新 UI → 闪烁
- 气泡列表可能重复添加

**方案：** WS 优先，REST 降级

```
WS 连接正常:
  → WS 事件 → UiState（唯一数据源）
  → REST 仅在用户主动刷新时调用

WS 断线降级:
  → REST 轮询 → UiState
  → WS 重连成功后，REST 轮询停止，WS 事件接管
```

实现方式：`ConnectionOrchestrator` 维护 `isWsConnected: StateFlow<Boolean>`，`BubbleMerger` 根据 WS 状态决定是否接受 REST 更新。

| ID | 决策 | 选择 | 理由 |
|----|------|------|------|
| D-23-16 | 数据源策略 | WS优先/REST降级 | 实时性优先，消除双写冲突 |

---

## 4. P2/P3 扫荡战

### P2 项目

| # | 问题 | 方案 | 优先级 |
|---|------|------|--------|
| P2-1 | bubbleCounter非线程安全 | 拆分到 BubbleMerger，用 AtomicLong | P0已覆盖 |
| P2-2 | deprecated属性每次创建新Flow | 删除deprecated属性，改 StateFlow | P0已覆盖 |
| P2-3 | hardcoded重试 | 可配置 RetryPolicy 参数 | P2 |
| P2-4 | AuthRepository每次新建Retrofit | 复用 OkHttpClient | P1已覆盖 |
| P2-5 | 无离线缓存 | Room 缓存层 | P2（大工程，可后续） |

### P3 项目

| # | 问题 | 方案 | 优先级 |
|---|------|------|--------|
| P3-1 | 全量图标库 | 按需引入，移除 extended | P3 |
| P3-2 | Release日志泄露 | BuildConfig条件 | P1已覆盖 |
| P3-3 | 无CI/CD | GitHub Actions workflow | P3 |
| P3-4 | SceneBubble 252行7子类 | 拆分到独立文件 | P3 |
| P3-5 | 三通道并发 | WS优先策略 | P1已覆盖 |

**造化宗师判决：** P2/P3 中大部分被 P0/P1 方案自动覆盖。真正独立的仅 P2-3（重试策略）、P2-5（离线缓存）、P3-1（图标库）、P3-3（CI/CD）、P3-4（SceneBubble拆分）。

---

## 5. Plan 分拆方案

造化宗师审视：3 个 Plan 的路线是否至臻？

### 23-01: P0 歼灭战 — 地基重建

**目标：** VM 拆分 + WS 生命周期 + R8 混淆

| 任务 | 文件 | 预计行数 |
|------|------|---------|
| 创建 ConnectionOrchestrator | 新建 | ~250 |
| 创建 BubbleMerger | 新建 | ~200 |
| 创建 CommandRouter | 新建 | ~150 |
| 创建 SaveLoadManager | 新建 | ~100 |
| 创建 ExportManager | 新建 | ~80 |
| 重构 DramaDetailViewModel | 改造 | ~300 |
| WebSocketManager 降级 @ActivityScoped | 改造 | ~351 |
| 删除 deprecated 属性 | 改造 | -30 |
| R8 混淆 + ProGuard 规则 | 新建+改造 | ~50 |
| build.gradle.kts 启用混淆 | 改造 | 5 |

**修改文件数：** ~10 文件（5 新建 + 5 改造）

**风险：** VM 拆分是侵入式重构，需确保 UI 行为零回归

### 23-02: P1 阵地战 — 质量与安全

**目标：** 动态 BaseUrl + 测试覆盖 + 安全加固 + 数据源统一

| 任务 | 文件 | 预计行数 |
|------|------|---------|
| BaseUrlInterceptor + 内存缓存 | 新建+改造 | ~60 |
| ServerPreferences 添加缓存 | 改造 | ~15 |
| AuthRepositoryImpl 复用 OkHttpClient | 改造 | ~20 |
| 关闭 usesCleartextTraffic + security config | 改造+新建 | ~25 |
| HttpLoggingInterceptor 条件注入 | 改造 | ~10 |
| 添加测试依赖 | 改造 | ~20 |
| BubbleMerger 单元测试 | 新建 | ~120 |
| CommandRouter 单元测试 | 新建 | ~100 |
| ConnectionOrchestrator 单元测试 | 新建 | ~80 |
| ConnectionOrchestrator WS优先策略 | 改造 | ~30 |

**修改文件数：** ~12 文件（5 新建 + 7 改造）

### 23-03: P2/P3 扫荡战 — 锦上添花

**目标：** 重试策略 + Room 缓存 + CI/CD + 体积优化

| 任务 | 文件 |
|------|------|
| 可配置 RetryPolicy | 新建 |
| Room 数据库 + DAO + Entity | 新建 |
| Room 缓存 Repository 装饰器 | 新建 |
| 移除 material-icons-extended | 改造 |
| SceneBubble 拆分独立文件 | 改造 |
| GitHub Actions workflow | 新建 |

**造化宗师判决：** 23-03 是可选的。P2/P3 不影响核心功能和稳定性。建议标记为 `deferred`，聚焦 23-01 和 23-02。

---

## 6. 依赖关系

```
23-01 (P0歼灭战: VM拆分 + WS生命周期 + R8)
  │
  ├─ VM拆分 → 23-02 的测试才有目标可测
  ├─ WS生命周期统一 → 23-02 的数据源策略才有基础
  │
  ▼
23-02 (P1阵地战: BaseUrl + 测试 + 安全 + 数据源)
  │
  ├─ 测试依赖 23-01 的子组件拆分
  ├─ 数据源统一依赖 23-01 的 ConnectionOrchestrator
  │
  ▼
23-03 (P2/P3扫荡战) — 可 deferred
```

---

## 7. 关键风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| VM 拆分引入 UI 回归 | 高 | 高 | 逐职责迁移，每步手动验证 UI 行为 |
| R8 ProGuard 规则不完整 | 中 | 高 | 保守 keep 策略，逐个验证 API 调用 |
| BaseUrlInterceptor 缓存不一致 | 低 | 中 | DataStore 写入时同步更新内存缓存 |
| @ActivityScoped WS 影响多页面 | 中 | 中 | 引用计数 acquire/release |

---

## 8. 造化宗师终极质问

**此方案，已到极致否？**

审视结论：

1. ✅ **7 个本质问题** 已识别，17 个表象归因完毕
2. ✅ **P0 先行** — 地基不稳，上层白搭
3. ✅ **VM 拆分用子组件** — 不是简单的文件切割，是职责边界重建
4. ✅ **WS 降级 @ActivityScoped** — 谁创建谁销毁，大道至简
5. ✅ **23-03 标记 deferred** — 不做无用功
6. ⚠️ **测试覆盖** — 33 个用例而非 60% 覆盖率虚荣指标，但这是正确的取舍

**造化宗师不满意之处：**

- P2-5 离线缓存（Room）被推迟，但用户在地铁上用 App 会断线 → 体验断裂。是否应提前？
- SceneBubble 252 行 7 子类被推迟拆分，但它与 BubbleMerger 强相关 → 拆 VM 时顺手拆？

**裁决：** 将 SceneBubble 拆分移入 23-01（与 BubbleMerger 同步），离线缓存留在 23-03。

---

*造化宗师审视完毕。删繁就简，7 本质驾驭 17 表象，至臻之境。*
