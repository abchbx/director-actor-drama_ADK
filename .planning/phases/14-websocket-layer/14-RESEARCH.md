# Phase 14: WebSocket Layer - Research

**Researched:** 2026-04-15
**Domain:** FastAPI WebSocket + ADK Runner event stream observation
**Confidence:** HIGH

## Summary

Phase 14 为 Director-Actor Drama 的 FastAPI 应用层添加 WebSocket 实时推送能力。核心架构是 EventBridge（回调函数）观察 ADK Runner 事件流，将 function_call/function_response 映射为 18 种业务事件，通过 WebSocket 广播给连接的客户端。全局 `collections.deque(maxlen=100)` 作为 replay buffer 支持断线重连补发。

FastAPI 内置 WebSocket 支持（基于 Starlette），无需额外依赖。ConnectionManager 模式是 FastAPI 官方推荐的连接池管理方式，通过 `set[WebSocket]` 存储活跃连接，广播时遍历发送。心跳机制使用应用层 ping/pong（非协议级），因为 Starlette 的 WebSocket 不暴露底层 frame 控制接口。测试使用 `fastapi.testclient.TestClient.websocket_connect()` 进行同步式 WebSocket 测试。

**Primary recommendation:** 使用 FastAPI 内置 WebSocket + ConnectionManager 模式 + 回调注入 run_command_and_collect + 全局 deque replay buffer。零新依赖，全部基于现有 FastAPI/Starlette 和 Python stdlib。

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Hook run_command_and_collect — 在现有遍历循环中加入可选 `event_callback` 参数，每个 event 到达时若 callback 存在则调用。REST 端点不传 callback（行为不变），WS 场景传入广播回调。
- **D-02:** EventBridge 本质是 callback 函数 — 不是独立类/服务，而是传入 run_command_and_collect 的可调用对象，将 event 映射为 WS 事件后广播到连接池。
- **D-03:** 零侵入约束解读 — "不修改 tool 代码"指不改 12 个核心模块（tools.py, state_manager.py, actor_service.py 等），API 层代码（runner_utils.py, commands.py）是 Phase 13 新增，Phase 14 可自由修改。
- **D-04:** 创建 `event_mapper.py` — 以 `function_call.name` 为主要映射键，将 ADK 原始事件（function_call / function_response / final_response）转换为 18 种业务事件。
- **D-05:** 映射规则：start_drama→scene_start+status, next_scene→scene_start, director_narrate→narration, actor_speak→dialogue, write_scene→scene_end, update_emotion→actor_status, create_actor→actor_created, storm_discover_perspectives→storm_discover, storm_research_perspective→storm_research, storm_synthesize_outline→storm_outline, save_drama→save_confirm, load_drama→load_confirm, export_drama→progress
- **D-06:** 需额外处理：tension_update（next_scene/write_scene response 中张力值变化时发出）、typing（function_call 到达时立即发出）、cast_update（create_actor response 后触发）、end_narration（/end 命令的 final_response 中提取）、error（response 中 status:error 检测）
- **D-07:** 一个 function_call 可能映射为多个业务事件 — 例如 start_drama 同时触发 scene_start 和 status
- **D-08:** 全局共享 buffer — 单用户模式下所有 WS 客户端看到同一事件流，`collections.deque(maxlen=100)` 作为 replay buffer
- **D-09:** 简单重连握手 — WS 客户端连接后，首条消息发 `{"type": "replay", "events": [...]}`（buffer 中所有事件），然后进入实时推送模式
- **D-10:** 断线重连即重新建立 WS 连接 — 客户端重连后自动获得 replay buffer 补发，无需客户端发送特殊请求
- **D-11:** WS endpoint 是纯接收端（只读事件流 + 推送），不持有 Runner Lock
- **D-12:** REST 和 WS 共存不冲突 — REST 发命令（持有 Lock），WS 收推送（不持 Lock）
- **D-13:** 连接池管理 — 使用 set 存储 WebSocket 连接，新连接加入、断开移除，广播时遍历 set 逐一发送
- **D-14:** 心跳 15s ping/pong — 服务端每 15s 发 ping，30s 无 pong 视为超时断连
- **D-15:** WS endpoint 路径 `/api/v1/ws`
- **D-16:** flush-before-push — 推送事件前调用 `app.state.flush_state_sync()`

### Claude's Discretion
- EventBridge callback 的具体签名和实现细节
- event_mapper.py 的内部结构和优化策略
- WebSocket 消息格式（Pydantic 模型）的具体字段设计
- 连接池的具体数据结构和线程安全策略
- 心跳定时器的实现方式（asyncio.Task vs 其他）
- replay buffer 与实时推送的时序保证

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WS-01 | WebSocket endpoint at `/api/v1/ws` receives real-time scene events | FastAPI WebSocket 路由注册 + ConnectionManager 广播模式 |
| WS-02 | 18 event types: scene_start, narration, dialogue, scene_end, tension_update, actor_created, actor_status, storm_discover, storm_research, storm_outline, error, typing, status, cast_update, progress, save_confirm, load_confirm, end_narration | event_mapper.py 以 function_call.name 为键映射 + 额外条件检测 |
| WS-03 | EventBridge observes ADK Runner event stream without modifying tool code | event_callback 注入 run_command_and_collect（D-01），不改 tools.py |
| WS-04 | 100-event replay buffer for reconnected clients to catch up | collections.deque(maxlen=100) + 连接时发送 replay 消息 |
| WS-05 | WebSocket connection lifecycle management (connect, heartbeat, disconnect, reconnect) | 应用层心跳 + ConnectionManager + asyncio.Task 心跳定时器 |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.135.3 | WebSocket endpoint + lifecycle | 已安装，内置 WebSocket 支持 [VERIFIED: uv run python] |
| Starlette | 0.52.1 | WebSocket 协议实现 | FastAPI 底层，提供 WebSocket 类 [VERIFIED: uv run python] |
| Pydantic | 2.12.5 | WS 事件消息模型 | 已安装，项目统一使用 v2 [VERIFIED: uv run python] |
| collections.deque | stdlib | Replay buffer | Python 标准库，O(1) append + 自动 maxlen 淘汰 [CITED: docs.python.org] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncio | stdlib | 心跳 Task + broadcast 协程 | 所有 WS 异步操作 |
| fastapi.testclient | 0.135.3 | WebSocket 端点测试 | TestClient.websocket_connect() [CITED: fastapi.tiangolo.com/advanced/testing-websockets] |
| httpx | 0.28.1 | AsyncClient 测试 | 已安装，API 测试用 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| 应用层 ping/pong | WebSocket 协议级 ping (0x9/0xA) | Starlette 不暴露 frame 级控制，必须用应用层 JSON 消息实现 [ASSUMED] |
| set[WebSocket] 连接池 | asyncio.Queue + fan-out | set 更简单，单用户场景无需 Queue 的背压控制 |
| collections.deque | Redis Pub/Sub + stream | 单进程单用户无需 Redis，deque 足够且零依赖 |
| callback 注入 | 独立 EventBridge 服务 + 订阅 Runner | callback 最小改动，REST 路径零影响（D-02 决策） |

**Installation:**
无需安装新依赖 — 所有组件来自 FastAPI/Starlette（已安装）和 Python 标准库。

**Version verification:**
```bash
# Already verified in this session:
fastapi=0.135.3, starlette=0.52.1, pydantic=2.12.5, uvicorn=0.44.0, pytest=8.4.2
```

## Architecture Patterns

### Recommended Project Structure
```
app/api/
├── app.py              # FastAPI app factory (已有，需注册 WS router + lifespan 初始化)
├── deps.py             # 依赖注入 (已有，需新增 get_connection_manager 等)
├── models.py           # Pydantic 模型 (已有，需新增 WS 事件模型)
├── runner_utils.py     # Runner 事件流 (已有，需加入 event_callback 参数)
├── event_mapper.py     # 新增：ADK 事件 → 18 种业务事件映射
├── ws_manager.py       # 新增：ConnectionManager + replay buffer + 心跳
├── routers/
│   ├── commands.py     # 命令端点 (已有，需传入 event_callback)
│   ├── queries.py      # 查询端点 (已有，不改)
│   └── websocket.py    # 新增：WebSocket endpoint 路由
```

### Pattern 1: EventCallback 注入模式
**What:** 在 `run_command_and_collect` 的事件流遍历循环中注入可选回调
**When to use:** REST 和 WS 共享同一 Runner 执行路径，WS 需实时推送事件
**Example:**
```python
# Source: 设计自现有 runner_utils.py (D-01 决策)
async def run_command_and_collect(
    runner: Runner,
    message: str,
    user_id: str,
    session_id: str,
    timeout: float = 120.0,
    event_callback: Callable[[Event], Awaitable[None]] | None = None,  # 新增
) -> dict[str, Any]:
    # ...
    async for event in runner.run_async(...):
        # 事件回调 — WS 场景传入，REST 场景为 None
        if event_callback:
            await event_callback(event)

        if event.is_final_response():
            # 现有逻辑...
```

### Pattern 2: ConnectionManager 广播模式
**What:** FastAPI 官方推荐的 WebSocket 连接管理模式
**When to use:** 多客户端同时订阅同一事件流
**Example:**
```python
# Source: [CITED: fastapi.tiangolo.com/advanced/websockets]
from fastapi import WebSocket
from collections import deque
import asyncio

class ConnectionManager:
    def __init__(self):
        self.active_connections: set[WebSocket] = set()  # D-13: set 存储
        self.replay_buffer: deque[dict] = deque(maxlen=100)  # D-08

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        # D-09: 连接后先发 replay
        if self.replay_buffer:
            await websocket.send_json({
                "type": "replay",
                "events": list(self.replay_buffer)
            })

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)  # set 用 discard 更安全

    async def broadcast(self, event: dict):
        """广播事件到所有连接，同时追加到 replay buffer。"""
        self.replay_buffer.append(event)  # D-08
        # 并行发送，收集失败连接
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(event)
            except Exception:
                disconnected.add(connection)
        # 清理断连的连接
        for conn in disconnected:
            self.active_connections.discard(conn)
```

### Pattern 3: 应用层心跳模式
**What:** 使用 asyncio.Task 定时发送 JSON 心跳消息
**When to use:** Starlette WebSocket 不暴露协议级 ping frame，需应用层实现
**Example:**
```python
# Source: 设计自 D-14 决策
async def _heartbeat_loop(websocket: WebSocket, timeout: float = 30.0):
    """每 15s 发送应用层 ping，30s 无响应断连。"""
    while True:
        await asyncio.sleep(15)  # D-14: 15s interval
        try:
            await websocket.send_json({"type": "ping"})
            # 等待 pong 响应（需要在接收循环中处理）
        except Exception:
            break  # 连接已断
```

### Pattern 4: Event Mapper 模式
**What:** 将 ADK Runner 的 function_call.name 映射为 18 种业务事件
**When to use:** Runner 事件是底层 tool 调用，需转换为客户端关心的业务语义
**Example:**
```python
# Source: D-04/D-05/D-06/D-07 决策

# 映射表：function_call.name → list[事件类型]
TOOL_EVENT_MAP: dict[str, list[str]] = {
    "start_drama": ["scene_start", "status"],       # D-07: 一对多
    "next_scene": ["scene_start"],
    "director_narrate": ["narration"],
    "actor_speak": ["dialogue"],
    "write_scene": ["scene_end"],
    "update_emotion": ["actor_status"],
    "create_actor": ["actor_created"],
    "storm_discover_perspectives": ["storm_discover"],
    "storm_research_perspective": ["storm_research"],
    "storm_synthesize_outline": ["storm_outline"],
    "save_drama": ["save_confirm"],
    "load_drama": ["load_confirm"],
    "export_drama": ["progress"],
    "end_drama": ["end_narration"],  # final_response 中提取
}

def map_event(event: Event) -> list[dict]:
    """将 ADK Event 映射为 0~N 个业务事件。"""
    results = []
    if event.content and event.content.parts:
        for part in event.content.parts:
            if part.function_call:
                # D-06: function_call 到达即发 typing
                results.append({"type": "typing", "tool": part.function_call.name})
                # 映射 function_call.name
                fn_name = part.function_call.name
                if fn_name in TOOL_EVENT_MAP:
                    for event_type in TOOL_EVENT_MAP[fn_name]:
                        results.append(_build_event(event_type, part.function_call))
            if part.function_response:
                resp = part.function_response.response or {}
                # D-06: 检测 error
                if resp.get("status") == "error":
                    results.append({"type": "error", ...})
                # D-06: 检测 tension_update
                # D-06: 检测 cast_update (after create_actor)
                # ... 其他条件检测
    return results
```

### Anti-Patterns to Avoid
- **不要用 asyncio.Queue 替代 deque 做 replay buffer**: Queue 消费后消失，不支持回放；deque 保留历史，支持新连接补发。
- **不要在 WS endpoint 中 await receive_text 永久阻塞**: 心跳需要读写交替，应使用 asyncio.create_task 并行处理接收和心跳。
- **不要广播时逐个 await send_json 不处理异常**: 一个客户端断连会阻断整个广播循环，必须 try/except 并收集断连。
- **不要在 event_callback 中获取 Runner Lock**: D-11 明确 WS 是纯接收端，callback 在 Runner 执行上下文中被调用，不应再请求 Lock。
- **不要在 function_response 映射中遗漏 status 字段**: tool 函数返回 `{"status": "success"|"error", "message": "..."}` 是核心约定（CONVENTIONS.md），error 检测必须基于此。

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| WebSocket 端点 | 手写 ASGI WebSocket handler | FastAPI `@router.websocket()` | 自动协议升级、异常处理、路由匹配 [CITED: fastapi.tiangolo.com] |
| 消息序列化 | 手写 JSON encode/decode | `websocket.send_json()` / Pydantic `model_dump()` | 自动处理类型、编码、边界情况 |
| 连接生命周期 | 手写连接/断连管理 | ConnectionManager 类（FastAPI 官方模式） | 统一管理连接池、广播、清理 [CITED: fastapi.tiangolo.com/advanced/websockets] |
| Replay buffer | 手写环形缓冲区 | `collections.deque(maxlen=100)` | 自动淘汰旧条目、O(1) 操作、线程安全（GIL 下） |
| 测试 WebSocket | 手写 WS 客户端 | `TestClient.websocket_connect()` | 同步 API，不需要真实服务器 [CITED: fastapi.tiangolo.com/advanced/testing-websockets] |

**Key insight:** FastAPI + Starlette 已提供所有 WebSocket 基础设施。Phase 14 的核心工作是事件映射（event_mapper.py）和回调注入（runner_utils.py 修改），不是从零构建 WebSocket 框架。

## Common Pitfalls

### Pitfall 1: 广播阻塞 — 单个慢客户端拖慢所有客户端
**What goes wrong:** 逐个 `await connection.send_json()` 时，一个网络慢的客户端会让所有后续客户端等待。
**Why it happens:** asyncio 是协作式并发，`await send_json()` 在网络缓冲区满时会挂起。
**How to avoid:** 使用 `asyncio.create_task()` 并行发送，或设置 `websocket.send_timeout`；更简单的方式是用 `asyncio.wait_for(send, timeout=5)` 给每次发送设超时。
**Warning signs:** 连接数 >1 时，事件推送延迟随客户端数线性增长。

### Pitfall 2: 心跳与接收循环冲突
**What goes wrong:** WS endpoint 中 `await websocket.receive_text()` 阻塞等待客户端消息，心跳 `send_json({"type": "ping"})` 无法执行。
**Why it happens:** 单个协程中无法同时等待读和写。
**How to avoid:** 使用 `asyncio.create_task()` 将心跳循环和接收循环并行运行，或使用 `asyncio.wait()` 同时等待多个事件源。推荐模式：主循环 receive_text，心跳作为独立 Task 运行。
**Warning signs:** 连接后心跳不工作，30s 后所有连接超时断开。

### Pitfall 3: EventCallback 中调用 flush_state_sync 的时序
**What goes wrong:** 在 function_response 回调中 flush 状态，但下一个 tool 可能还没执行完，flush 的是中间状态。
**Why it happens:** ADK Runner 在一个用户消息中可能调用多个 tool（如 next_scene → director_narrate → actor_speak → write_scene），每个 function_response 触发回调。
**How to avoid:** D-16 说"推送前 flush"，但应在推送业务事件时 flush，不是在每个底层 function_response 时 flush。建议：只在映射出的业务事件需要推送前 flush（如 scene_end、narration 等重要事件前），而非每个 function_response。
**Warning signs:** 磁盘上的 state.json 频繁写入但内容是中间态。

### Pitfall 4: deque 线程安全误判
**What goes wrong:** `collections.deque` 的 `append()` 和 `pop()` 是原子操作，但 `list(deque)` 快照不是原子的。
**Why it happens:** 在迭代 deque 时，另一个协程可能 append 新元素。虽然 asyncio 是单线程的，但在 `await` 点可能切换。
**How to avoid:** 在 `list(self.replay_buffer)` 取快照时不需要锁（因为 asyncio 单线程，list() 不含 await），但如果用线程则需要加锁。当前方案（单线程 asyncio）安全。
**Warning signs:** replay 中偶现事件顺序不一致。

### Pitfall 5: WebSocket 断连未清理导致内存泄漏
**What goes wrong:** 客户端异常断开（网络断开、进程崩溃），服务端未检测到，连接对象留在 active_connections 中。
**Why it happens:** TCP 半开连接 — 服务端没有尝试发送数据就不知道连接已断。
**How to avoid:** 心跳机制（D-14）正是为此设计 — 定期 ping 检测死连接。确保 broadcast 中的 send 异常也清理连接。
**Warning signs:** active_connections 数量持续增长，已断开客户端的连接对象不被回收。

### Pitfall 6: REST 命令端点忘记传 event_callback
**What goes wrong:** 新增 WS 层后，REST 命令端点仍传 event_callback=None，导致 WS 客户端收不到事件。
**Why it happens:** 8 个命令端点都需要修改，容易遗漏。
**How to avoid:** 在 `app.state` 上存储 ConnectionManager 引用，命令端点从 `request.app.state.connection_manager` 获取 broadcaster 回调，集中管理而非每个端点单独传。
**Warning signs:** REST 命令执行成功但 WS 客户端无推送。

### Pitfall 7: TestClient WebSocket 测试不支持真实异步
**What goes wrong:** `TestClient.websocket_connect()` 使用同步 API，不能测试 `asyncio.create_task` 心跳等异步逻辑。
**Why it happens:** TestClient 将异步 WebSocket 端点转为同步调用，某些异步交互模式不兼容。
**How to avoid:** 心跳等纯异步逻辑用 mock 测试单独验证，端到端 WS 行为用真实 uvicorn 服务器 + 异步 WS 客户端测试（集成测试层）。
**Warning signs:** TestClient 中心跳 Task 不运行或超时。

## Code Examples

### EventCallback 集成（runner_utils.py 修改）
```python
# Source: 设计自现有 runner_utils.py + D-01/D-02/D-16 决策
from typing import Any, Callable, Awaitable
from google.adk.events import Event

async def run_command_and_collect(
    runner: Runner,
    message: str,
    user_id: str,
    session_id: str,
    timeout: float = 120.0,
    event_callback: Callable[[Event], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    """Run a command through the ADK Runner and collect structured results.

    Args:
        event_callback: Optional async callback invoked for each Runner event.
            When provided (WS scenario), receives every event for real-time push.
            When None (REST scenario), behavior unchanged.
    """
    content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=message)],
    )

    async def _collect() -> dict[str, Any]:
        final_text = ""
        tool_results: list[dict] = []

        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=content,
        ):
            # D-01: 事件回调 — WS 场景传入，REST 场景为 None
            if event_callback:
                try:
                    await event_callback(event)
                except Exception:
                    pass  # 回调异常不应阻断 Runner 执行

            if event.is_final_response():
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            final_text += part.text
            elif event.content and event.content.parts:
                for part in event.content.parts:
                    if part.function_response and part.function_response.response:
                        tool_results.append(dict(part.function_response.response))

        return {"final_response": final_text, "tool_results": tool_results}

    try:
        return await asyncio.wait_for(_collect(), timeout=timeout)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Command execution timed out")
```

### WebSocket Endpoint（routers/websocket.py）
```python
# Source: [CITED: fastapi.tiangolo.com/advanced/websockets] + D-14/D-15 决策
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time scene event push (WS-01/WS-05).

    Flow:
    1. Accept connection → send replay buffer (D-09)
    2. Start heartbeat task (D-14)
    3. Receive loop: handle pong + client messages
    4. On disconnect: clean up heartbeat + remove from pool
    """
    manager = websocket.app.state.connection_manager
    await manager.connect(websocket)
    heartbeat_task = asyncio.create_task(
        manager.heartbeat(websocket)
    )
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")
            if msg_type == "pong":
                manager.record_pong(websocket)
            # 可扩展：客户端请求等
    except WebSocketDisconnect:
        pass
    finally:
        heartbeat_task.cancel()
        manager.disconnect(websocket)
```

### WebSocket 事件消息模型（models.py 扩展）
```python
# Source: 设计自 D-04/D-05 + 现有 models.py Pydantic 模式
from pydantic import BaseModel, Field
from datetime import datetime

class WsEvent(BaseModel):
    """Base model for all WebSocket event messages."""
    type: str = Field(..., description="Event type (one of 18 business types)")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    data: dict = Field(default_factory=dict, description="Event payload")

class ReplayMessage(BaseModel):
    """Replay buffer message sent on connection (D-09)."""
    type: str = "replay"
    events: list[WsEvent] = Field(default_factory=list)

class HeartbeatMessage(BaseModel):
    """Application-level heartbeat (D-14)."""
    type: str = "ping"  # or "pong" for response
```

### Event Mapper 核心结构（event_mapper.py）
```python
# Source: D-04/D-05/D-06/D-07 决策
from google.adk.events import Event

# D-05: 映射表
TOOL_EVENT_MAP: dict[str, list[str]] = {
    "start_drama": ["scene_start", "status"],
    "next_scene": ["scene_start"],
    "director_narrate": ["narration"],
    "actor_speak": ["dialogue"],
    "write_scene": ["scene_end"],
    "update_emotion": ["actor_status"],
    "create_actor": ["actor_created", "cast_update"],  # D-06: cast_update
    "storm_discover_perspectives": ["storm_discover"],
    "storm_research_perspective": ["storm_research"],
    "storm_synthesize_outline": ["storm_outline"],
    "save_drama": ["save_confirm"],
    "load_drama": ["load_confirm"],
    "export_drama": ["progress"],
    "end_drama": ["end_narration"],
}

# D-06: 条件事件检测器
CONDITIONAL_EVENTS: dict[str, Callable] = {
    "tension_update": _detect_tension_change,
    "error": _detect_error,
}

def map_runner_event(event: Event) -> list[WsEvent]:
    """Map an ADK Runner Event to 0~N business events.

    D-07: One function_call can map to multiple business events.
    D-06: Additional conditional events detected from response data.
    """
    results = []
    if not event.content or not event.content.parts:
        return results

    for part in event.content.parts:
        # Handle function_call → typing + mapped events
        if part.function_call:
            fn_name = part.function_call.name
            results.append(WsEvent(type="typing", data={"tool": fn_name}))
            for event_type in TOOL_EVENT_MAP.get(fn_name, []):
                results.append(WsEvent(
                    type=event_type,
                    data=_extract_call_data(event_type, part.function_call)
                ))

        # Handle function_response → conditional events
        if part.function_response:
            resp = part.function_response.response or {}
            fn_name = part.function_response.name

            # D-06: error detection
            if resp.get("status") == "error":
                results.append(WsEvent(type="error", data={
                    "tool": fn_name,
                    "message": resp.get("message", ""),
                }))

            # D-06: tension_update detection
            if fn_name in ("next_scene", "write_scene"):
                tension = _extract_tension(resp)
                if tension is not None:
                    results.append(WsEvent(type="tension_update", data={
                        "tension_score": tension,
                    }))

            # Emit response data for mapped event types
            if fn_name in TOOL_EVENT_MAP:
                for event_type in TOOL_EVENT_MAP[fn_name]:
                    results.append(WsEvent(
                        type=event_type,
                        data=_extract_response_data(event_type, resp)
                    ))

    # Handle final_response → end_narration (D-06)
    if event.is_final_response() and event.content and event.content.parts:
        for part in event.content.parts:
            if part.text and part.text.strip():
                results.append(WsEvent(type="end_narration", data={
                    "text": part.text.strip()
                }))

    return results
```

### ConnectionManager 与 Lifespan 集成（app.py 修改）
```python
# Source: 设计自现有 app.py + D-08/D-13/D-16 决策
from app.api.ws_manager import ConnectionManager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing startup code ...

    # Phase 14: Initialize ConnectionManager
    manager = ConnectionManager()
    app.state.connection_manager = manager

    yield

    # Phase 14: Cleanup on shutdown
    # Close all active WS connections
    for ws in list(manager.active_connections):
        try:
            await ws.close()
        except Exception:
            pass

    # ... existing shutdown code ...
```

### 测试 WebSocket 端点
```python
# Source: [CITED: fastapi.tiangolo.com/advanced/testing-websockets]
from fastapi.testclient import TestClient

def test_websocket_replay_on_connect():
    """New WS connection receives replay buffer events (WS-04/D-09)."""
    app = create_app()
    client = TestClient(app)

    # Pre-populate replay buffer
    app.state.connection_manager.replay_buffer.append(
        {"type": "scene_start", "data": {"scene": 1}}
    )

    with client.websocket_connect("/api/v1/ws") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "replay"
        assert len(data["events"]) == 1
        assert data["events"][0]["type"] == "scene_start"

def test_websocket_heartbeat():
    """Server sends ping, client responds pong (WS-05/D-14)."""
    # Note: Heartbeat timing is hard to test with TestClient.
    # Test the heartbeat logic separately with mock timers.
    pass
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| WebSocket 协议级 ping | 应用层 JSON ping/pong | Starlette 0.x 至今 | Starlette 不暴露 WS frame 控制，必须用应用层消息 |
| 同步 WS 测试 | TestClient.websocket_connect() | FastAPI 0.100+ | 同步 API 测试 WS，简单但无法测试异步交互 |
| threading.Lock for WS | asyncio single-threaded | Python 3.7+ | asyncio 单线程无需锁，但需注意 await 点的协程切换 |

**Deprecated/outdated:**
- `websockets` 库直接使用: FastAPI 内置 WebSocket 支持，无需额外 `websockets` 库
- `fastapi-websocket-rpc` 等第三方库: 过度工程化，内置功能足够

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Starlette WebSocket 不暴露协议级 ping/pong frame 控制 | Architecture Patterns | 如果 Starlette 支持协议级 ping，可简化心跳实现 |
| A2 | asyncio 单线程下 deque 操作无需加锁 | Common Pitfalls | 如果引入多线程（如后台 flush），需加锁 |
| A3 | TestClient.websocket_connect() 可以测试 replay 补发 | Code Examples | 如果 TestClient 行为与真实 WS 不一致，需集成测试 |
| A4 | event_callback 中的异常不应阻断 Runner 执行 | Code Examples | 如果回调异常表示严重问题，可能需要不同处理策略 |
| A5 | 一个 Runner 命令执行期间 event_callback 不会被并发调用 | Architecture Patterns | ADK Runner 的 run_async 是 async generator，单线程串行产出事件 |

**If this table is empty:** All claims in this research were verified or cited — no user confirmation needed.

## Open Questions (RESOLVED)

1. **心跳与 receive 循环的并行实现** — RESOLVED
   - What we know: D-14 要求 15s ping + 30s timeout，需要心跳 Task 和 receive Task 并行
   - What's unclear: `asyncio.create_task` 心跳 + 主循环 `receive_json()` 的精确交互模式 — 心跳 Task 中如何检测 pong 超时
   - Recommendation: 使用 `asyncio.shield` + `asyncio.wait_for` 模式，心跳 Task 独立运行并维护 `last_pong_time`，超过 30s 主动关闭连接
   - Resolution: Plan 14-03 Task 1 implements `asyncio.create_task` heartbeat with `last_pong_time` tracking and `is_pong_expired()` check, 15s ping interval and 30s timeout

2. **event_callback 在 commands.py 中的传递方式** — RESOLVED
   - What we know: 8 个命令端点都需要传入 event_callback
   - What's unclear: 是每个端点单独构建 callback，还是从 app.state 获取统一的 broadcaster
   - Recommendation: 从 `request.app.state.connection_manager` 获取 manager，构建 `manager.create_broadcast_callback(flush_fn)` 统一入口
   - Resolution: Plan 14-02 Task 1 uses `request.app.state.connection_manager.create_broadcast_callback(flush_fn)` for all 8 command endpoints

3. **flush_state_sync 调用时机** — RESOLVED
   - What we know: D-16 说"推送前 flush"，但 Runner 执行一个命令可能产生多个事件
   - What's unclear: 是每个事件推送前都 flush，还是只在重要事件前 flush
   - Recommendation: 在 event_callback 中检测到有 WS 客户端时，在映射和推送前调用 flush_state_sync()。由于 flush 是幂等的（只写入 dirty 的 state），多次调用开销不大
   - Resolution: Plan 14-02 Task 1 passes `flush_fn=flush_state_sync` to `create_broadcast_callback`, called once per broadcast cycle (before mapping and pushing)

4. **end_drama 的 end_narration 事件来源** — RESOLVED
   - What we know: D-06 说从 `/end` 命令的 final_response 中提取
   - What's unclear: final_response 的文本是否就是终幕旁白，还是需要从 tool_results 中的 end_drama response 提取
   - Recommendation: 检查 end_drama tool 的返回值 — 它返回 `formatted_narration` 字段（参考 cli.py _content_keys），应从 function_response 中提取，而非 final_response
   - Resolution: Plan 14-02 Task 2 maps `end_drama` function_response to `end_narration` event type, extracting from response dict rather than final_response text

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| FastAPI | WS endpoint | ✓ | 0.135.3 | — |
| Starlette | WebSocket 类 | ✓ | 0.52.1 | — |
| uvicorn | ASGI server | ✓ | 0.44.0 | — |
| Python 3.11 | asyncio + typing | ✓ | 3.11.1 | — |
| pytest | 测试 | ✓ | 8.4.2 | — |
| pytest-asyncio | 异步测试 | ✓ | 0.23.8+ | — |
| httpx | API 测试 | ✓ | 0.28.1 | — |

**Missing dependencies with no fallback:**
- None — 所有依赖已安装

**Missing dependencies with fallback:**
- None

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 + pytest-asyncio |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/unit/ -q -x` |
| Full suite command | `uv run pytest tests/unit/ tests/integration/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WS-01 | WS endpoint at /api/v1/ws accepts connections | unit | `uv run pytest tests/unit/test_ws_manager.py::test_connect -x` | ❌ Wave 0 |
| WS-02 | 18 event types emitted correctly | unit | `uv run pytest tests/unit/test_event_mapper.py -x` | ❌ Wave 0 |
| WS-03 | EventBridge observes Runner events via callback | unit | `uv run pytest tests/unit/test_runner_utils.py::test_event_callback -x` | ❌ Wave 0 |
| WS-04 | Replay buffer sends on reconnect | unit | `uv run pytest tests/unit/test_ws_manager.py::test_replay -x` | ❌ Wave 0 |
| WS-05 | Heartbeat + disconnect + reconnect lifecycle | unit | `uv run pytest tests/unit/test_ws_manager.py::test_heartbeat -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_event_mapper.py tests/unit/test_ws_manager.py -q`
- **Per wave merge:** `uv run pytest tests/unit/ -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_event_mapper.py` — covers WS-02 (18 event type mapping)
- [ ] `tests/unit/test_ws_manager.py` — covers WS-01/WS-04/WS-05 (connection, replay, heartbeat)
- [ ] `tests/unit/test_runner_utils.py` update — covers WS-03 (event_callback parameter)
- [ ] No new framework install needed — pytest + pytest-asyncio already available

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase 15 负责，WS 此阶段不鉴权 |
| V3 Session Management | no | 单用户模式，无 session 鉴别 |
| V4 Access Control | no | Phase 15 负责 |
| V5 Input Validation | yes | Pydantic WsEvent 模型校验 WS 消息格式 |
| V6 Cryptography | no | 局域网场景，ws:// (非 wss://) |

### Known Threat Patterns for FastAPI WebSocket

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| WS 连接耗尽（DoS） | Denial of Service | 连接数上限 + 超时断连 |
| WS 消息注入 | Tampering | Pydantic 校验接收消息 + 忽略未知 type |
| 跨域 WS 连接 | Spoofing | Phase 15 Token 验证（此阶段暂不实现） |
| 事件流信息泄露 | Information Disclosure | replay buffer 仅含最近 100 事件，不含敏感 API key |

## Sources

### Primary (HIGH confidence)
- FastAPI Context7 `/websites/fastapi_tiangolo` - WebSocket endpoint, ConnectionManager, testing-websockets
- 代码库直接验证 - FastAPI 0.135.3, Starlette 0.52.1, Pydantic 2.12.5 版本确认
- ADK Event/Part/FunctionCall 结构 - 通过 `uv run python` 直接检查字段

### Secondary (MEDIUM confidence)
- FastAPI 官方文档 WebSocket 模式 [CITED: fastapi.tiangolo.com/advanced/websockets]
- TestClient WebSocket 测试模式 [CITED: fastapi.tiangolo.com/advanced/testing-websockets]

### Tertiary (LOW confidence)
- Starlette WebSocket 不支持协议级 ping — 基于对 Starlette 源码的理解 [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - 全部基于已安装的 FastAPI/Starlette + Python stdlib，无需新依赖
- Architecture: HIGH - FastAPI 官方 ConnectionManager 模式 + 现有代码库已确认可修改点
- Pitfalls: HIGH - 基于实际 WebSocket 开发经验和 FastAPI 文档验证
- Event mapping: MEDIUM - 映射逻辑依赖对 ADK Runner 事件流的精确理解，需实现时验证

**Research date:** 2026-04-15
**Valid until:** 2026-05-15 (stable: FastAPI WebSocket API 长期稳定)
