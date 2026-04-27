# Phase 19-01 Summary: WebSocket Heartbeat Fix

**Plan:** 19-01
**Status:** ✅ COMPLETE
**Date:** 2026-04-25

## Objective

修复 Android WebSocketManager 心跳响应的 CRITICAL bug：用结构化 JSON 解析替换脆弱的字符串匹配，移除死代码的自定义心跳机制，调整 OkHttp pingInterval 避免与应用层心跳冲突，加固服务端接收循环处理客户端 heartbeat 消息。

## Changes Made

### Task 1: 客户端心跳修复 — JSON 解析替换字符串匹配 + 移除死代码

**WebSocketManager.kt** (6 changes):
1. ✅ 新增 `import kotlinx.serialization.json.jsonObject` 和 `import kotlinx.serialization.json.jsonPrimitive`
2. ✅ `onMessage()` 重写：使用 `json.parseToJsonElement(text).jsonObject` 解析消息 + `when` 表达式分发处理 `ping`/`pong`/`replay`/其他类型
3. ✅ 移除 `useCustomHeartbeat` 字段（原 L60）
4. ✅ 移除 `heartbeatJob` 字段（原 L59）
5. ✅ 移除 `startHeartbeat()` 方法（原 L278-297）
6. ✅ 移除 `stopHeartbeat()` 方法（原 L300-303）
7. ✅ 移除 `onOpen()` 中 `startHeartbeat(webSocket)` 调用（原 L156）
8. ✅ 移除 `onClosed()` 中 `stopHeartbeat()` 调用（原 L219）
9. ✅ 移除 `onFailure()` 中 `stopHeartbeat()` 调用（原 L247）
10. ✅ 移除 `disconnect()` 中 `stopHeartbeat()` 调用（原 L361）
11. ✅ 移除 companion object 中 `HEARTBEAT_INTERVAL_MS` 常量（原 L394）

**NetworkModule.kt** (1 change):
- ✅ `pingInterval(30, TimeUnit.SECONDS)` → `pingInterval(60, TimeUnit.SECONDS)` — TCP keepalive 角色，不与 15s 应用层心跳冲突

### Task 2: 服务端心跳加固 + 生命周期测试验证

**websocket.py** (1 change):
- ✅ 添加 `msg_type == "heartbeat"` 处理分支：`record_pong()` + 回复 `{"type":"pong"}`（兼容旧客户端）

**test_ws_manager.py** (新增 TestHeartbeatMessageTypeHandling 类，5 个测试):
- ✅ `test_pong_message_records_pong` — 收到 pong 时调用 record_pong
- ✅ `test_heartbeat_message_records_pong` — 收到 heartbeat 时也 record_pong（兼容）
- ✅ `test_heartbeat_timeout_with_no_pong` — 无 pong 时超时断连
- ✅ `test_pong_resets_timeout_clock` — pong 重置超时计时
- ✅ `test_heartbeat_task_cancellation_cleans_up` — 心跳任务取消正常退出

**test_ws_lifecycle.py** (新增 TestHeartbeatRecoveryLifecycle 类，3 个测试):
- ✅ `test_reconnect_receives_replay_after_heartbeat_timeout` — 心跳超时断连后重连 replay 补发
- ✅ `test_pong_keeps_connection_alive_through_multiple_cycles` — 持续 pong 多轮心跳存活
- ✅ `test_replay_buffer_no_event_loss_on_reconnect` — 重连后 replay 无事件丢失

### Task 3: 客户端 UI 恢复链路代码审查

**审查结论 — 全线链路完整：**
- D-13: 心跳超时→断连→重连→状态对齐 链路完整（onClosed → scheduleReconnect → onOpen → onReconnected）
- D-11: onWsReconnected() 回调执行 switchToDrama + getDramaStatus + getSceneBubbles + mergeBubblesAfterReconnect
- D-12: ConnectionState 密封类驱动 ConnectionStateIndicator UI（Disconnected 红色横幅、Reconnecting 进度条、Connected 隐藏）
- D-07: 15s ping + 即时 pong + 30s timeout + 60s TCP keepalive = 理论永不断连
- D-08: 60s 接收超时与 30s 心跳超时协调正确，无冲突
- APP-15: 客户端 replay 消费链路完整（ReplayMessageDto → tryEmit → handleWsEvent 过滤 replay）

### 附带修复

**app/agent.py**: 添加 `actor_speak_batch` 缺失的 import（阻碍测试执行的旧债）

## Test Results

```
56 passed in 1.69s
```

- 原 test_ws_manager.py: 20 tests → 25 tests (+5 TestHeartbeatMessageTypeHandling)
- 原 test_ws_lifecycle.py: 11 tests → 14 tests (+3 TestHeartbeatRecoveryLifecycle)
- 所有新增测试覆盖 WS-05, APP-04, APP-15 需求

## Success Criteria Verification

| # | Criterion | Status |
|---|-----------|--------|
| 1 | WebSocketManager 收到 {"type":"ping"} 后通过 JSON 解析发送 {"type":"pong"} | ✅ parseToJsonElement + when |
| 2 | 自定义心跳机制完全移除（5 项死代码不存在） | ✅ grep 确认 0 匹配 |
| 3 | OkHttp pingInterval = 60s | ✅ NetworkModule.kt L62 |
| 4 | 服务端 websocket.py 处理 {"type":"heartbeat"} 消息 | ✅ elif 分支 + record_pong + send_json pong |
| 5 | 服务端测试全部通过（新增 8 个） | ✅ 56 passed |
| 6 | 心跳超时→断连→重连→replay buffer 补发 链路测试通过 | ✅ TestHeartbeatRecoveryLifecycle |
| 7 | UI 恢复链路代码审查通过（D-07/08/11/12/13） | ✅ 审查报告 |
| 8 | 客户端 replay buffer 消费链路确认正确 | ✅ 代码审查 |
