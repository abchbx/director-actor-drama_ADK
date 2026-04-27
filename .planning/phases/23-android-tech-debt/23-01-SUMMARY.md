# Phase 23-01: P0 歼灭战 — 地基重建 — Summary

**Date:** 2026-04-26
**Status:** ✅ COMPLETED
**Wave:** 1

---

## Objective Achieved

将 DramaDetailViewModel (1665行 God Object) 拆分为协调者 + 5 个子组件，WS 生命周期降级 @ActivityScoped + acquire/release，R8 混淆启用 + ProGuard 保守 keep，deprecated 属性清除。

---

## Tasks Completed

### Task 1a: 核心子组件 — ConnectionOrchestrator + BubbleMerger
- **ConnectionOrchestrator.kt** (~150行): WS 连接/重连/轮询降级编排，暴露 `isWsConnected` + `connectionState`，通过 SharedFlow 上报事件
- **BubbleMerger.kt** (~120行): AtomicLong 线程安全 ID 生成，`addFromRest(bubbles, isWsConnected, currentBubbles)` 实现 WS优先/REST降级数据源策略（ARCH-10），`mergeAfterReconnect` 智能合并

### Task 1b: 辅助子组件 — CommandRouter + SaveLoadManager + ExportManager
- **CommandRouter.kt** (~110行): 命令路由/语义判断（isActionCommand/isPlotChanging/isLocalCommand），显示文本生成
- **SaveLoadManager.kt** (~80行): 本地存档 CRUD，SharedFlow 事件上报
- **ExportManager.kt** (~40行): 导出/Share Intent，SharedFlow 事件上报

### Task 2: DramaDetailViewModel 重构为协调者 + UiState 子状态拆分
- **UiState 子状态拆分 (ARCH-14):**
  - `ConnectionUiState` — 连接状态独立重组
  - `InteractionUiState` — 输入状态独立重组
  - `SaveLoadUiState` — 保存/加载状态独立重组
  - `ActorPanelUiState` — 演员面板状态独立重组
- **VM 注入 5 个子组件 (D-23-01):** @Inject constructor 注入，委托职责
- **SharedFlow 事件收集 (D-23-02):** `observeSubComponentEvents()` 统一订阅
- **onCleared 统一清理 (D-23-04):** 调用所有子组件 `cleanup()`
- **ARCH-10 数据源策略:** REST 回调使用 `bubbleMerger.addFromRest(bubbles, isWsConnected, currentBubbles)`
- **deprecated 属性清除 (D-23-07):** 所有 `@Deprecated` 已删除

### Task 3: WebSocketManager 降级 @ActivityScoped + acquire/release
- **WebSocketModule** (独立 Module @InstallIn(ActivityComponent::class)): WebSocketManager @ActivityScoped 提供
- **WebSocketManager.acquire()/release()** (D-23-06): AtomicInteger 引用计数，归零自动断开
- **ConnectionOrchestrator** 集成: connect 时 acquire，cleanup 时 release
- **deprecated 属性清除:** `isConnected`/`isReconnecting` 已删除 (D-23-07)

### Task 4: R8 混淆启用 + ProGuard 保守 keep 规则
- **build.gradle.kts:** `isMinifyEnabled = true` + `shrinkResources = true` (D-23-08)
- **proguard-rules.pro (D-23-09):** 保守 keep — DTO/接口/SceneBubble密封类/Hilt/Compose/Coroutines

---

## Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `orchestrator/ConnectionOrchestrator.kt` | ~150 | WS 连接编排子组件 |
| `orchestrator/BubbleMerger.kt` | ~120 | 气泡管理/去重/数据源策略 |
| `orchestrator/CommandRouter.kt` | ~110 | 命令路由子组件 |
| `orchestrator/SaveLoadManager.kt` | ~80 | 保存/加载子组件 |
| `orchestrator/ExportManager.kt` | ~40 | 导出子组件 |

## Files Modified

| File | Change |
|------|--------|
| `DramaDetailViewModel.kt` | 1665行→协调者，注入5子组件 + UiState子状态 + addFromRest数据源策略 |
| `WebSocketManager.kt` | 添加 refCount/acquire/release，删除 deprecated 属性 |
| `NetworkModule.kt` | 拆出 WebSocketModule(@ActivityScoped)，原 Module 保留 Singleton 组件 |
| `build.gradle.kts` | isMinifyEnabled=true + shrinkResources=true |
| `proguard-rules.pro` | 保守 keep 规则 (DTO/接口/密封类/Hilt/Compose/Coroutines) |

---

## Design Decisions Applied

| ID | Decision | Status |
|----|----------|--------|
| D-23-01 | VM 拆分策略：子组件组合（非独立VM） | ✅ @Inject constructor |
| D-23-02 | 子组件通信：SharedFlow 事件上报 | ✅ |
| D-23-03 | 气泡ID线程安全：AtomicLong | ✅ |
| D-23-04 | 子组件生命周期：主 VM onCleared 统一清理 | ✅ |
| D-23-05 | WS 作用域：@ActivityScoped | ✅ 独立 WebSocketModule |
| D-23-06 | 多VM共享：acquire/release 引用计数 | ✅ AtomicInteger |
| D-23-07 | deprecated属性删除 | ✅ 零 @Deprecated |
| D-23-08 | R8 范围：isMinifyEnabled + shrinkResources | ✅ |
| D-23-09 | ProGuard 策略：保守 keep | ✅ |
| D-23-16 | 数据源策略：WS优先/REST降级 | ✅ addFromRest |
| D-23-17 | SceneBubble 拆分 | ✅ 已有独立 SceneBubbleList.kt |

---

## Architecture Diagram

```
DramaDetailViewModel (协调者)
├── ConnectionOrchestrator ──→ SharedFlow<ConnectionEvent>
│   ├── isWsConnected: StateFlow<Boolean>  ← BubbleMerger 查询
│   └── acquire/release → WebSocketManager
├── BubbleMerger ──→ 气泡列表管理
│   ├── addFromRest(bubbles, isWsConnected) ← ARCH-10 数据源策略
│   └── mergeAfterReconnect(local, server) ← 重连合并
├── CommandRouter ──→ 命令语义路由
├── SaveLoadManager ──→ SharedFlow<SaveLoadEvent>
└── ExportManager ──→ SharedFlow<ExportEvent>

UiState 子状态 (ARCH-14):
├── ConnectionUiState (连接状态)
├── InteractionUiState (交互状态)
├── SaveLoadUiState (保存/加载)
└── ActorPanelUiState (演员面板)
```

---

## Next Steps

Phase 23-02 (P1 阵地战): BaseUrlInterceptor + 测试覆盖 + 安全加固 + 数据源统一
