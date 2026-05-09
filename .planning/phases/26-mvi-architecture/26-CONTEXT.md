# Phase 26: Android MVI 架构演进 — Context

**Phase:** 26-mvi-architecture
**Milestone:** v3.5 架构升级
**Depends on:** Phase 23 (tech-debt), Phase 25 (dual-chat-mode)
**Requirements:** MVI-01~MVI-07

---

## Objective

将现有 MVVM + StateFlow 架构演进为**严格 MVI（Model-View-Intent）**，实现 Intent → Reducer → State → Effect 单向数据流（UDF），从根本上消除多并发 WebSocket 消息推送导致的 UI 闪烁和状态不一致问题。

---

## Gap Analysis

### 已具备的基础

| 组件 | 状态 | 说明 |
|------|------|------|
| StateFlow | ✅ | 所有 VM 已使用 MutableStateFlow + data class UiState |
| 子组件化 | ✅ | Phase 23 完成 orchestrator 拆分，BubbleMerger / ConnectionOrchestrator 等 |
| 密封类 Event | ✅ | DramaDetailEvent / DramaListEvent 已使用 sealed class |
| Coroutines | ✅ | viewModelScope + Flow 已在全项目普及 |

### 待实现缺口

| 缺口 | 需求 | 改造方案 |
|------|------|----------|
| 无统一 Intent 入口 | MVI-01 | 创建 `BaseMviViewModel`，所有操作走 `processIntent()` |
| 无 Intent 队列化 | MVI-02 | `Channel<Intent>(UNLIMITED)` 顺序消费，消除并发竞态 |
| 无 Reducer 纯函数 | MVI-03 | `reduce(state, intent) -> newState`，无副作用 |
| WS 事件直接改 State | MVI-04 | WS 事件包装为 Intent 入队，不再直接 `_uiState.update` |
| Screen 直接调 VM 方法 | MVI-05 | Composable 只发送 Intent，严禁直接调用 VM public 方法 |
| 无 Effect 通道规范 | MVI-06 | `SharedFlow<Effect>` 处理一次性事件（导航/Toast/Haptic） |
| 无 MVI 基类抽象 | MVI-07 | `MviIntent` / `MviState` / `MviEffect` 标记接口 + 泛型基类 |

---

## Design Decisions

| ID | Decision | Choice | Rationale |
|----|----------|--------|-----------|
| D-26-01 | Intent 队列实现 | `Channel<Intent>(UNLIMITED)` + `consumeEach` | 顺序处理保证无并发竞态；UNLIMITED 防止 WS 消息突发导致阻塞 |
| D-26-02 | Reducer 位置 | VM 内部 `abstract fun reduce()` | 保持 Android 生态兼容性，不引入外部 MVI 库（如 Orbit/MVIKotlin） |
| D-26-03 | 子组件保留 | orchestrator 作为 Model 层保留 | Phase 23 子组件投入巨大，不复用乃浪费；子组件输出转为 Intent 入队 |
| D-26-04 | 迁移顺序 | DramaList → DramaCreate → DramaDetail | 由简到繁，先验证基座再攻主堡垒 |
| D-26-05 | Plan 数量 | 2 Plans | 26-01 基座+列表页（低风险验证），26-02 详情页完整迁移（高风险核心） |
| D-26-06 | Effect 命名 | `Effect` 替代 `Event` | MVI 语义：`State` 持续状态，`Effect` 一次性副作用，与现有 `Event` 类并存过渡 |

---

## Files to Modify

### 新建（MVI 基座）

1. `android/app/src/main/java/com/drama/app/ui/mvi/MviIntent.kt` — 标记接口
2. `android/app/src/main/java/com/drama/app/ui/mvi/MviState.kt` — 标记接口
3. `android/app/src/main/java/com/drama/app/ui/mvi/MviEffect.kt` — 标记接口
4. `android/app/src/main/java/com/drama/app/ui/mvi/BaseMviViewModel.kt` — 泛型基类

### Plan 26-01: DramaListScreen 迁移

5. `ui/screens/dramalist/DramaListViewModel.kt` — MVI 化
6. `ui/screens/dramalist/DramaListScreen.kt` — 只发送 Intent
7. `ui/screens/dramalist/DramaListIntent.kt` — 密封类（新建）
8. `ui/screens/dramalist/DramaListEffect.kt` — 密封类（新建）

### Plan 26-02: DramaDetailScreen 迁移

9. `ui/screens/dramadetail/DramaDetailViewModel.kt` — MVI 化 + Intent 队列
10. `ui/screens/dramadetail/DramaDetailScreen.kt` — 只发送 Intent
11. `ui/screens/dramadetail/DramaDetailIntent.kt` — 密封类（新建）
12. `ui/screens/dramadetail/DramaDetailEffect.kt` — 密封类（新建）
13. `ui/screens/dramacreate/DramaCreateViewModel.kt` — MVI 化
14. `ui/screens/dramacreate/DramaCreateScreen.kt` — 只发送 Intent

---

## Success Criteria

1. 所有 ViewModel **只有一个 public 方法**：`processIntent()`
2. WebSocket 事件、用户操作、系统回调 **全部经 Intent 队列顺序处理**
3. Reducer 为 **纯函数**，无副作用，可直接单元测试
4. 多并发 WS 消息推送时 **UI 无闪烁、state 无竞态**
5. 现有 orchestrator 子组件职责不变，输出通过 Intent 入队
6. DramaList / DramaCreate / DramaDetail 三屏全部完成迁移，编译通过
7. 单元测试覆盖 Reducer 关键路径

---

## Key References

- Phase 23 PLAN（子组件化基础）
- `DramaDetailViewModel.kt`（当前主 VM，将被 MVI 化）
- `DramaListViewModel.kt`（最简 VM，先迁移验证）
- `BaseMviViewModel` 设计参考（本文档 Design Decisions）
