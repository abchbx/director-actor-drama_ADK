# Phase 14: WebSocket Layer - Context

**Gathered:** 2026-04-15
**Status:** Ready for planning

<domain>
## Phase Boundary

WebSocket 端点实时推送场景事件，EventBridge 观察 ADK Runner 事件流，100-event replay buffer 支持断线重连。不改 12 个核心模块（tools.py, state_manager.py 等），仅扩展 API 层。

</domain>

<decisions>
## Implementation Decisions

### EventBridge 架构
- **D-01:** Hook run_command_and_collect — 在现有遍历循环中加入可选 `event_callback` 参数，每个 event 到达时若 callback 存在则调用。REST 端点不传 callback（行为不变），WS 场景传入广播回调。
- **D-02:** EventBridge 本质是 callback 函数 — 不是独立类/服务，而是传入 run_command_and_collect 的可调用对象，将 event 映射为 WS 事件后广播到连接池。
- **D-03:** 零侵入约束解读 — "不修改 tool 代码"指不改 12 个核心模块（tools.py, state_manager.py, actor_service.py 等），API 层代码（runner_utils.py, commands.py）是 Phase 13 新增，Phase 14 可自由修改。

### 事件类型映射
- **D-04:** 创建 `event_mapper.py` — 以 `function_call.name` 为主要映射键，将 ADK 原始事件（function_call / function_response / final_response）转换为 18 种业务事件。
- **D-05:** 映射规则：
  - `start_drama` → scene_start + status
  - `next_scene` → scene_start
  - `director_narrate` → narration
  - `actor_speak` → dialogue
  - `write_scene` → scene_end
  - `update_emotion` → actor_status
  - `create_actor` → actor_created
  - `storm_discover_perspectives` → storm_discover
  - `storm_research_perspective` → storm_research
  - `storm_synthesize_outline` → storm_outline
  - `save_drama` → save_confirm
  - `load_drama` → load_confirm
  - `export_drama` → progress
- **D-06:** 需额外处理的事件：
  - `tension_update` — 在 `next_scene`/`write_scene` response 中检查张力值变化，有变化则额外发出
  - `typing` — 在 `function_call` 到达时立即发出（表示 LLM 正在处理）
  - `cast_update` — 在 `create_actor` response 后触发
  - `end_narration` — 在 `/end` 命令的 final_response 中提取
  - `error` — 从 response 中 `status: "error"` 检测
- **D-07:** 一个 function_call 可能映射为多个业务事件 — 例如 `start_drama` 同时触发 scene_start 和 status。

### Replay Buffer & 断线重连
- **D-08:** 全局共享 buffer — 单用户模式下所有 WS 客户端看到同一事件流，`collections.deque(maxlen=100)` 作为 replay buffer，EventBridge 每发一个事件同时 append 到 deque。
- **D-09:** 简单重连握手 — WS 客户端连接后，首条消息发 `{"type": "replay", "events": [...]}`（buffer 中所有事件），然后进入实时推送模式。无复杂握手协议。
- **D-10:** 断线重连即重新建立 WS 连接 — 客户端重连后自动获得 replay buffer 补发，无需客户端发送特殊请求。

### WebSocket 端点与 REST 并成
- **D-11:** WS endpoint 是纯接收端（只读事件流 + 推送），不持有 Runner Lock — REST 命令端点照常工作，WS 客户端自动收到事件推送。
- **D-12:** REST 和 WS 共存不冲突 — REST 发命令（持有 Lock），WS 收推送（不持 Lock）。用户通过 REST POST `/drama/next`，Runner 执行，EventBridge 通过 callback 推送事件到 WS。
- **D-13:** 连接池管理 — 使用 set 存储 WebSocket 连接，新连接加入、断开移除，广播时遍历 set 逐一发送。

### 心跳与生命周期
- **D-14:** 心跳 15s ping/pong — 服务端每 15s 发 ping，30s 无 pong 视为超时断连，从连接池移除。
- **D-15:** WS endpoint 路径 `/api/v1/ws` — 符合现有 API 版本前缀约定（API-04）。
- **D-16:** flush-before-push — 推送事件前调用 `app.state.flush_state_sync()`（STATE-02 hook 已就绪），确保内存与磁盘状态一致。

### Claude's Discretion
- EventBridge callback 的具体签名和实现细节
- event_mapper.py 的内部结构和优化策略
- WebSocket 消息格式（Pydantic 模型）的具体字段设计
- 连接池的具体数据结构和线程安全策略
- 心跳定时器的实现方式（asyncio.Task vs 其他）
- replay buffer 与实时推送的时序保证

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 项目规划
- `.planning/ROADMAP.md` — Phase 14 定义、成功标准、依赖关系
- `.planning/REQUIREMENTS.md` — WS-01~05 需求定义
- `.planning/STATE.md` — v2.0 已决定的架构选型和风险表
- `.planning/PROJECT.md` — 项目愿景、约束、技术债

### Phase 13 上下文（直接前置）
- `.planning/phases/13-api-foundation/13-CONTEXT.md` — API 层决策、Runner 集成策略、flush-on-push hook
- `.planning/phases/13-api-foundation/13-VERIFICATION.md` — Phase 13 验证通过的证据

### 代码库分析
- `.planning/codebase/ARCHITECTURE.md` — 整体架构、数据流、StormRouter 路由逻辑
- `.planning/codebase/CONVENTIONS.md` — 命名、docstring、返回值格式约定
- `.planning/codebase/CONCERNS.md` — 技术债、已知 bug、安全顾虑
- `.planning/codebase/STRUCTURE.md` — 目录结构、模块依赖图、新代码放置指南
- `.planning/codebase/STACK.md` — 依赖版本、测试框架、环境配置

### 核心源码
- `app/api/runner_utils.py` — **关键**：run_command_and_collect 遍历 Runner 事件流，Phase 14 需在此加入 event_callback
- `app/api/app.py` — FastAPI app factory，lifespan 中设置 flush_before_push，WS endpoint 需在此注册
- `app/api/deps.py` — 依赖注入（Runner, Lock, ToolContextAdapter），WS 可能需要新增依赖
- `app/api/models.py` — Pydantic 模型，WS 事件模型需扩展此文件或新建
- `app/api/routers/commands.py` — 命令端点，需传入 event_callback 给 run_command_and_collect
- `cli.py` §172-220 — CLI 事件流处理参考（function_call/function_response 遍历模式）
- `app/state_manager.py` — flush_state_sync() 引用，推送前调用

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `run_command_and_collect()` (`app/api/runner_utils.py`): 已遍历 Runner 事件流，提取 final_response + tool_results。Phase 14 在此加入可选 event_callback 即可复用。
- `flush_state_sync` (`app/state_manager.py`): Phase 13-04 已创建的同步 flush 函数，推送前调用确保状态持久化。
- `app.state.flush_before_push` + `app.state.flush_state_sync` (`app/api/app.py`): 已在 lifespan 中设置的 hook 属性，Phase 14 直接使用。
- `asyncio.Lock` (`app.state.runner_lock`): Runner 访问序列化，WS 不需要获取此 Lock。
- `ToolContextAdapter` (`app/api/deps.py`): 可用于 WS 场景读取 session state。
- Pydantic 模型体系 (`app/api/models.py`): 已有 CommandResponse 等模型，WS 事件模型可继承此模式。
- FastAPI CORS + 版本前缀 (`app/api/app.py`): WS endpoint `/api/v1/ws` 遵循已有约定。

### Established Patterns
- Runner 事件流遍历: `async for event in runner.run_async(...)` → 检查 `is_final_response()` / `function_call` / `function_response`
- 命令格式: `f"/{command} {args}"` — REST 端点构造 CLI 风格消息发给 Runner
- 返回值格式: `{"status": "success"|"error", "message": "...", ...领域字段}` — WS 事件应沿用
- 依赖注入: FastAPI `Depends()` 模式 — WS endpoint 可复用 `get_runner`, `get_runner_lock`

### Integration Points
- `app/api/runner_utils.py`: 需修改 run_command_and_collect 加入 event_callback 参数
- `app/api/routers/commands.py`: 8 个命令端点需传入 event_callback（当 WS 客户端连接时）
- `app/api/app.py`: 需注册 WS endpoint，lifespan 中初始化连接池和 replay buffer
- `app/api/deps.py`: 可能需要新增 WS 相关依赖（连接池、event broadcaster）

</code_context>

<specifics>
## Specific Ideas

- EventBridge 作为 callback 而非独立服务 — 最小改动，REST 路径不受影响
- 全局 deque replay buffer — 单用户模式最简实现，无需按客户端隔离
- WS 连接后先发 replay 再切实时 — 客户端无需发送特殊请求
- function_call 到达即发 typing 事件 — 让 Android 端显示"导演正在构思..."
- 一个 tool call 可能映射多个业务事件 — event_mapper 返回 list[WsEvent]

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 14-websocket-layer*
*Context gathered: 2026-04-15*
