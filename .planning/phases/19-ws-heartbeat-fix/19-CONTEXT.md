# Phase 19: WebSocket Heartbeat Fix - Context

**Gathered:** 2026-04-25
**Status:** Ready for planning

<domain>
## Phase Boundary

修复 Android WebSocketManager 不响应服务端 ping 的 CRITICAL bug，确保 WS 连接持续稳定 >5 分钟无断连，自动重连后 replay buffer 正确消费无事件丢失，心跳超时恢复后 DramaDetailScreen 实时渲染恢复正常。

不改核心业务逻辑（tools.py、state_manager.py 等），仅修复 Android 端 WS 生命周期管理和后端心跳协调。

**Gap Closure:** Closes CRITICAL Gap 1 (WS Heartbeat Pong Missing)

</domain>

<decisions>
## Implementation Decisions

### 心跳 Pong 响应（已部分修复，需验证加固）
- **D-01:** WebSocketManager.onMessage() 第171-173行已实现 pong 响应 — 收到 `{"type":"ping"}` 后立即发送 `{"type":"pong"}`。这是 CRITICAL bug 的核心修复，代码已就位。
- **D-02:** 需要验证当前实现是否存在竞态条件 — onMessage 使用 `text.contains("\"type\"") && text.contains("\"ping\"")` 做字符串匹配而非 JSON 解析，可能在边缘情况下误匹配（如包含 "ping" 的其他消息）。
- **D-03:** 需要验证服务端 heartbeat() 是否正确调用 `record_pong()` — websocket.py 第104-105行已处理 `msg_type == "pong"` 调用 `manager.record_pong(websocket)`。

### 客户端自定义心跳机制
- **D-04:** WebSocketManager 有双心跳策略 — OkHttp pingInterval（WS 协议帧）+ 自定义文本心跳 `{"type":"heartbeat"}`。`useCustomHeartbeat` 标志控制切换。
- **D-05:** 当前自定义心跳发送 `{"type":"heartbeat"}` 而非 `{"type":"ping"}` — 服务端 websocket.py 接收循环仅识别 `msg_type == "pong"`，不识别 "heartbeat" 类型。这意味着客户端自定义心跳的响应可能被忽略，导致 `useCustomHeartbeat` 永远不会切换为 true。
- **D-06:** 需要确认：服务端是否应处理 `{"type":"heartbeat"}` 消息？如果客户端发 heartbeat，服务端应该回复 pong 让客户端知道自定义心跳可用。

### 连接稳定性验证
- **D-07:** 成功标准1要求 WS 连接持续 >5 分钟无断连 — 需要端到端测试验证。当前心跳间隔 15s（服务端）+ 30s（客户端），超时 30s，理论足够维持连接。
- **D-08:** 60s 接收超时（websocket.py 第87-90行）与 30s 心跳超时的协调 — 如果客户端正确响应 ping，60s 接收超时不应触发。

### Replay Buffer 断线重连
- **D-09:** 服务端 replay buffer 为 `deque(maxlen=100)`，客户端 onMessage 正确解析 `replay` 类型消息（第177-187行）。
- **D-10:** 重连后 replay buffer 消费需验证 — 连接建立后服务端自动发送 replay（D-09: connect() 后立即发送），客户端正确解析并 emit 到事件流。
- **D-11:** onWsReconnected() 回调处理完整 — 包含 switchToDrama、状态刷新、气泡合并去重（第995-1049行）。

### 心跳超时恢复后 UI 恢复
- **D-12:** DramaDetailViewModel.connectionState 密封类驱动 UI — Disconnected 时显示断连横幅，Reconnecting 时显示重连进度，Connected 时恢复实时渲染。
- **D-13:** 心跳超时导致服务端主动 close → 客户端 onClosed → 指数退避重连 → onReconnected 回调 → 状态对齐。这条链路需验证端到端。

### Claude's Discretion
- 心跳字符串匹配 vs JSON 解析的性能权衡
- 自定义心跳 `{"type":"heartbeat"}` 的服务端处理方式
- 测试策略：集成测试 vs 手动验证
- 是否需要添加 WS 连接健康监控指标

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 项目规划
- `.planning/ROADMAP.md` — Phase 19 定义、成功标准、依赖关系
- `.planning/REQUIREMENTS.md` — WS-05, APP-04, APP-15 需求定义
- `.planning/STATE.md` — v2.0 已决定的架构选型和风险表

### Phase 14 上下文（WebSocket 后端实现）
- `.planning/phases/14-websocket-layer/14-CONTEXT.md` — 18 种 WS 事件类型、心跳机制、EventBridge、replay buffer

### Phase 18 上下文（Android WS 重连）
- `.planning/phases/18-android-features/18-CONTEXT.md` — WS 自动重连策略、ConnectivityManager、重连后状态对齐

### 核心源码 — 后端
- `app/api/ws_manager.py` — **关键**：ConnectionManager 心跳实现（15s ping/30s timeout）、record_pong、replay buffer
- `app/api/routers/websocket.py` — **关键**：WS endpoint 接收循环、pong 处理、60s 接收超时
- `app/api/event_mapper.py` — 事件映射规则（理解 WS 事件流）

### 核心源码 — Android
- `android/app/src/main/java/com/drama/app/data/remote/ws/WebSocketManager.kt` — **关键**：WS 连接管理、pong 响应、自定义心跳、重连策略、ConnectivityManager
- `android/app/src/main/java/com/drama/app/data/remote/ws/ConnectionState.kt` — 连接状态密封类
- `android/app/src/main/java/com/drama/app/data/remote/dto/WsEventDto.kt` — WS 事件 DTO + HeartbeatMessageDto
- `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt` — **关键**：WS 事件处理、重连回调、connectionState 驱动 UI
- `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailScreen.kt` — ConnectionStateIndicator 组件

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `WebSocketManager.onMessage()` 已有 pong 响应（第171-173行）— CRITICAL bug 核心修复已就位
- `ConnectionManager.heartbeat()` 完整实现 15s ping + 30s timeout — 服务端心跳机制完备
- `websocket.py` 接收循环正确处理 `msg_type == "pong"` 并调用 `record_pong()` — pong 记录链路完整
- `WebSocketManager` 指数退避重连（2s→30s 封顶）+ ConnectivityManager 网络恢复触发重连 — 重连策略完备
- `DramaDetailViewModel.onWsReconnected()` 重连后状态强制对齐 — switchToDrama + 状态刷新 + 气泡合并去重
- `ConnectionState` 密封类精确描述连接生命周期 — UI 消费无歧义

### Established Patterns
- OkHttp WS + callbackFlow 事件流模式
- 服务端应用层心跳（JSON ping/pong）而非 WS 协议帧
- 双心跳策略：OkHttp pingInterval + 自定义文本心跳，自动切换
- 重连回调模式：onReconnected / onPermanentFailure

### Integration Points
- 服务端 `ConnectionManager.heartbeat()` → `websocket.send_json({"type":"ping"})` → 客户端 `onMessage()` → `webSocket.send({"type":"pong"})` → 服务端 `record_pong()`
- 客户端 `WebSocketManager.startHeartbeat()` → `webSocket.send({"type":"heartbeat"})` → **服务端不识别此类型** ← 潜在问题
- 客户端断连 → `onClosed/onFailure` → `scheduleReconnect()` → 指数退避 → `connectInternal()` → 服务端 `connect()` → replay buffer 补发

### Potential Issues Found
1. **自定义心跳不被服务端识别**: 客户端发送 `{"type":"heartbeat"}`，服务端接收循环仅处理 `msg_type == "pong"`，"heartbeat" 类型被忽略。这导致 `useCustomHeartbeat` 标志不会被设为 true，自定义心跳实际只发不收回复。
2. **心跳字符串匹配精度**: `text.contains("\"ping\"")` 可能误匹配包含 "ping" 的其他消息内容。
3. **初始 pong 时间戳**: `connect()` 时初始化 `_last_pong[websocket] = time.monotonic()`，这意味着首次 heartbeat 检查前有 15s 窗口，不会立即超时。这是正确行为。

</code_context>

<specifics>
## Specific Ideas

- 修复自定义心跳交互：客户端发 `{"type":"heartbeat"}` 时，服务端应回复 `{"type":"pong"}` 让客户端确认自定义心跳可用
- 改进字符串匹配为 JSON 解析：`json.decodeFromString<HeartbeatMessageDto>(text)` 后判断 type 字段，更精确
- 添加 WS 连接健康日志：连接时长、心跳统计、重连次数，便于排查
- 端到端测试：启动服务端 + Android 客户端，保持 >5 分钟连接，验证无断连

</specifics>

<deferred>
## Deferred Ideas

None — phase scope is clear and focused on the heartbeat fix.

</deferred>

---

*Phase: 19-ws-heartbeat-fix*
*Context gathered: 2026-04-25*
