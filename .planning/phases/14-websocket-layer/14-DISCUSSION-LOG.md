# Phase 14: WebSocket Layer - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-15
**Phase:** 14-websocket-layer
**Areas discussed:** EventBridge Architecture, Event Type Mapping, Replay Buffer & Reconnect, WebSocket & REST Concurrency

---

## EventBridge Architecture

|| Option | Description | Selected |
|--------|-------------|----------|
| A: Hook run_command_and_collect | 在现有遍历循环中加入可选 event_callback 参数 | ✓ |
| B: 新建流式消费者 | 创建 run_command_and_stream() 替代，WS 专用路径 | |
| C: 中间广播层 | Queue/Channel 解耦，WS 独立消费 | |

**User's choice:** Claude discretion (all you decide)
**Selected:** Option A — Hook run_command_and_collect
**Rationale:** Runner 事件流只有一个入口（runner.run_async()），创建第二个消费者违反单 Runner 单 Session 约束。中间广播层增加无谓复杂度。在现有遍历循环中加可选 callback 改动最小，REST 不受影响。

---

## Event Type Mapping

|| Option | Description | Selected |
|--------|-------------|----------|
| A: function_call.name 映射 + 额外推断 | 以 tool 名为主要键，部分事件需额外处理 | ✓ |
| B: 全部从 function_response 推断 | 等工具返回后再判断事件类型 | |
| C: 混合：function_call 发 typing，response 发具体事件 | 双阶段推送 | |

**User's choice:** Claude discretion (all you decide)
**Selected:** Option A — function_call.name 映射 + 额外推断
**Rationale:** function_call 到达时即可推断大部分事件类型，无需等待 response。typing 事件在 function_call 时立即发出。部分事件（tension_update, error）需从 response 中额外检测。一个 function_call 可映射多个业务事件。

---

## Replay Buffer & Reconnect

|| Option | Description | Selected |
|--------|-------------|----------|
| A: 全局共享 buffer | deque(maxlen=100)，所有客户端共享 | ✓ |
| B: 按客户端独立 buffer | 每个连接维护自己的 buffer | |
| C: 无 buffer，重连时重新查询状态 | 断线后通过 REST 获取当前状态 | |

**User's choice:** Claude discretion (all you decide)
**Selected:** Option A — 全局共享 buffer
**Rationale:** 单用户模式——所有 WS 客户端看到同一事件流。全局 deque 最简实现。重连即重新建立 WS 连接，自动获得 replay 补发。无需复杂握手协议。

---

## WebSocket & REST Concurrency

|| Option | Description | Selected |
|--------|-------------|----------|
| A: 共存，REST 优先 | REST 发命令持 Lock，WS 只收推送不持 Lock | ✓ |
| B: WS 也能发命令 | WS 连接上可发送命令消息 | |
| C: WS 替代 REST | 所有命令通过 WS 发送，REST 废弃 | |

**User's choice:** Claude discretion (all you decide)
**Selected:** Option A — 共存，REST 优先
**Rationale:** REST 和 WS 是同一用户的两种交互方式，不冲突。WS 是纯接收端，不争 Runner Lock。用户通过 REST 发命令，WS 自动收到事件推送。WS 发命令是 scope creep（属于新能力）。

---

## Claude's Discretion

- EventBridge callback 的具体签名和实现细节
- event_mapper.py 的内部结构和优化策略
- WebSocket 消息格式（Pydantic 模型）的具体字段设计
- 连接池的具体数据结构和线程安全策略
- 心跳定时器的实现方式
- replay buffer 与实时推送的时序保证

## Deferred Ideas

None — all decisions stayed within Phase 14 scope
