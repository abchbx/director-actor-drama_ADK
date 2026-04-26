# Phase 23: Android 技术债务治理 — Context

**Phase:** 23-android-tech-debt
**Milestone:** v2.5 技术债务治理
**Depends on:** Phase 19, Phase 20, Phase 21, Phase 22
**Requirements:** ARCH-01~ARCH-17 (技术评估发现)

---

## Objective

治理 Android 客户端 17 个技术债务问题。经造化宗师审视，17 个表象归因为 7 个本质问题。按 P0→P1→P2/P3 优先级推进，聚焦地基重建。

---

## 7 个本质问题

| # | 本质问题 | 衍生表象 | 影响 |
|---|----------|----------|------|
| 1 | God Object — 一个 VM 承担 15+ 职责 | P0-1, P1-4, P2-1, P3-5 | 可维护性极差，可测试性为零 |
| 2 | 生命周期失控 — WS 连接不跟随 VM 生命周期 | P0-2, P2-2 | 连接泄露/闪烁/事件丢失 |
| 3 | 安全裸奔 — 发布版本无任何防护 | P0-3, P1-3, P3-2 | APK 可逆向，明文 HTTP |
| 4 | DI 反模式 — 依赖注入违背基本原则 | P1-1, P2-4 | runBlocking ANR，资源浪费 |
| 5 | 零质量保障 — 无测试无 CI | P1-2, P3-3 | 重构信心为零 |
| 6 | 数据层简陋 — 无缓存无重试 | P2-3, P2-5, P3-4 | 体验断裂 |
| 7 | 体积浪费 | P3-1 | APK 增 2MB |

---

## Current State (Codebase Audit 2026-04-26)

| File | Lines | Key Evidence |
|------|-------|-------------|
| `DramaDetailViewModel.kt` | **1665** | God Object: 初始化同步、WS生命周期、REST轮询、15+事件处理、气泡管理、场景历史、保存/加载、演员面板、命令分发、群聊消息、导出 |
| `WebSocketManager.kt` | 351 | `@Singleton` + 自建 `reconnectScope` 永不取消 + deprecated 属性每次创建新协程 |
| `build.gradle.kts` | 87 | `isMinifyEnabled = false` |
| `NetworkModule.kt` | 106 | `runBlocking { serverPreferences.serverConfig.first() }` 阻塞主线程 |
| `AndroidManifest.xml` | 28 | `usesCleartextTraffic=true` |
| `SceneBubble.kt` | 252 | 7 子类集中单文件，contentFingerprint equals/hashCode 风险 |
| `AuthRepositoryImpl.kt` | 60 | 每次验证新建 Retrofit 实例 |
| 单元测试 | **0** | src/test/ 不存在，无 JUnit/Mockito/Turbine 依赖 |

---

## Design Decisions

| ID | Decision | Choice | Rationale |
|----|----------|--------|-----------|
| D-23-01 | VM 拆分策略 | 子组件组合（非独立VM） | Compose ViewModel scope 共享复杂度 |
| D-23-02 | 子组件通信 | SharedFlow 事件上报 | 解耦 + 可测试 |
| D-23-03 | 气泡ID线程安全 | AtomicLong 替代 Int | 零冲突 |
| D-23-04 | 子组件生命周期 | 主 VM onCleared 时统一清理 | 无泄漏 |
| D-23-05 | WS 作用域 | @ActivityScoped 替代 @Singleton | 连接属于页面，非应用 |
| D-23-06 | 多VM共享 | 引用计数 acquire/release | 最后一个释放才断开 |
| D-23-07 | deprecated属性 | 删除，改为 StateFlow | 消除协程泄漏 |
| D-23-08 | R8 范围 | isMinifyEnabled + shrinkResources | 全面压缩 |
| D-23-09 | ProGuard 策略 | 保守 keep（DTO/接口） + R8 自动分析 | 安全优先 |
| D-23-10 | BaseUrl 切换 | BaseUrlInterceptor + 内存缓存 | 零阻塞，无需重启 |
| D-23-11 | AuthRepository | 复用 OkHttpClient | 减少资源浪费 |
| D-23-12 | 测试策略 | 关键路径优先 | 不追求数字，追求确定性 |
| D-23-13 | 测试目标 | 拆分后的子组件 | 先拆再测，否则无法测 |
| D-23-14 | 明文HTTP | 关闭 + network_security_config 白名单 | 安全+开发兼容 |
| D-23-15 | 日志拦截器 | BuildConfig.DEBUG 条件注入 | Release 零泄露 |
| D-23-16 | 数据源策略 | WS优先/REST降级 | 实时性优先，消除双写冲突 |
| D-23-17 | SceneBubble 拆分 | 移入 23-01 与 BubbleMerger 同步 | 强相关，同步拆分避免二次重构 |
| D-23-18 | 23-03 优先级 | 标记 deferred | P2/P3 不影响核心功能 |

---

## Plan Breakdown

### 23-01: P0 歼灭战 — 地基重建

**目标：** VM 拆分 + WS 生命周期 + R8 混淆 + SceneBubble 拆分

| 任务 | 类型 |
|------|------|
| 创建 ConnectionOrchestrator (~250行) | 新建 |
| 创建 BubbleMerger (~200行) | 新建 |
| 创建 CommandRouter (~150行) | 新建 |
| 创建 SaveLoadManager (~100行) | 新建 |
| 创建 ExportManager (~80行) | 新建 |
| 重构 DramaDetailViewModel → 协调者 (~300行) | 改造 |
| WebSocketManager 降级 @ActivityScoped + acquire/release | 改造 |
| 删除 deprecated 属性，改 StateFlow | 改造 |
| SceneBubble 拆分独立文件 | 改造 |
| R8 混淆 + ProGuard 规则 | 新建+改造 |

**~10 文件（5+ 新建，5 改造）**

### 23-02: P1 阵地战 — 质量与安全

**目标：** 动态 BaseUrl + 测试覆盖 + 安全加固 + 数据源统一

| 任务 | 类型 |
|------|------|
| BaseUrlInterceptor + ServerPreferences 内存缓存 | 新建+改造 |
| AuthRepositoryImpl 复用 OkHttpClient | 改造 |
| 关闭 usesCleartextTraffic + network_security_config | 改造+新建 |
| HttpLoggingInterceptor 条件注入 | 改造 |
| 添加测试依赖 (junit, mockito-kotlin, coroutines-test, turbine) | 改造 |
| BubbleMerger / CommandRouter / ConnectionOrchestrator 单元测试 | 新建 |
| ConnectionOrchestrator WS优先策略 | 改造 |

**~12 文件（5+ 新建，7 改造）**

### 23-03: P2/P3 扫荡战 — [DEFERRED]

**目标：** 可配置重试策略 + Room 离线缓存 + CI/CD + 体积优化

标记为 deferred，聚焦 23-01 和 23-02。

---

## Success Criteria

1. DramaDetailViewModel 拆分为协调者 + 5 子组件，主文件 <400 行
2. WebSocketManager 降级 @ActivityScoped，acquire/release 引用计数
3. Release 构建启用 R8 混淆，APK 类名/方法名不可读
4. BaseUrlInterceptor 替代 runBlocking，切换服务器无需重启
5. 核心子组件单元测试 ~33 用例通过
6. usesCleartextTraffic=false + network_security_config 仅放行本地开发
7. WS优先/REST降级单一数据源，消除 UI 闪烁
8. SceneBubble 拆分独立文件
9. deprecated 属性已删除，改用 StateFlow

---

## Key References

- Discussion: `.planning/phases/23-android-tech-debt/23-DISCUSSION-LOG.md`
- Codebase Audit: `.planning/codebase/CONCERNS.md`
- DramaDetailViewModel: `android/.../dramadetail/DramaDetailViewModel.kt`
- WebSocketManager: `android/.../ws/WebSocketManager.kt`
- NetworkModule: `android/.../di/NetworkModule.kt`
- SceneBubble: `android/.../domain/model/SceneBubble.kt`
- AuthRepositoryImpl: `android/.../repository/AuthRepositoryImpl.kt`
- Build: `android/app/build.gradle.kts`
- Manifest: `android/app/src/main/AndroidManifest.xml`
