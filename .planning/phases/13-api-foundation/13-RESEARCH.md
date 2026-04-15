# Phase 13: API Foundation - Research

**Researched:** 2026-04-15
**Domain:** FastAPI REST API wrapping ADK Runner + state migration
**Confidence:** HIGH

## Summary

Phase 13 在现有 DramaRouter + Runner 架构之上搭建 FastAPI REST 层，将 14 个 CLI 命令映射为 HTTP 端点。核心挑战不是 FastAPI 本身（已作为 google-adk 传递依赖安装 v0.135.3），而是**事件循环兼容性**和**全局状态迁移**。

FastAPI + ADK Runner 天然兼容——两者都运行在 asyncio 事件循环上，`Runner.run_async()` 是原生 async generator，可直接在 FastAPI async 端点中 `async for event in runner.run_async(...)` 遍历。主要陷阱在于 `trigger_storm()` 内部使用 `asyncio.run()` 和 ThreadPoolExecutor 来桥接 sync/async，这在 FastAPI 的持续运行事件循环中会出问题。解决方案：API 层直接调用 `dynamic_storm()`（async 原生），绕过 `trigger_storm()` 桥接层。

全局状态迁移（STATE-01）风险低——`_current_drama_folder` 是 CONCERNS.md 确认的 dead code，唯一读取者 `_get_current_theme()` 已优先从 `tool_context.state` 读取。迁移策略：删除全局变量 + 让 `_get_current_theme(tool_context=None)` 在 `tool_context is None` 时抛异常而非静默降级。

**Primary recommendation:** 使用 FastAPI lifespan 创建共享 Runner + InMemorySessionService，命令式端点用 `async for event in runner.run_async()` 收集完整结果，查询式端点直接调 state_manager 函数。不修改 12 个核心模块的内部逻辑。

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** 共享 Runner + 单 Session — 与 CLI 行为一致，单用户模式最简单，互斥天然保证
- **D-02:** 命令式端点同步等待完整结果 — 120s 超时（与 A2A 调用一致），Phase 14 加 WebSocket 后自然升级为流式体验
- **D-03:** 返回 final_response + 结构化 tool 结果 — 提取 scene_number, formatted_scene, actors_in_scene, narration 等关键字段
- **D-04:** 混合错误码模式 — 端点级错误（无 drama、参数无效）HTTP 4xx，tool 内部业务错误 200 + status: error
- **D-05:** save/load 直接调 state_manager — 数据操作不需要 LLM，更快更可预测
- **D-06:** `/start` 先自动保存旧 drama 再覆盖 — 安全优先，不丢数据
- **D-07:** Lock file 互斥 — PID 写入 `app/.api.lock`，CLI 和 API 启动时互检，进程崩溃时可检测 stale lock
- **D-08:** Session 生命周期绑定 FastAPI 进程 — startup 事件创建 Runner + Session，shutdown 时清理 Actor 服务 + 删除 lock file
- **D-09:** 直接用 `state["drama"]["theme"]` — 已存在且冗余，无需额外抽象
- **D-10:** 删除 `_current_drama_folder` 全局变量，强制要求 tool_context — `_get_current_theme(tool_context)` 必须传参，无参报错
- **D-11:** CLI 自然兼容 — 所有交互走 Runner，tool_context 自动注入，无需额外适配

### Claude's Discretion
- Pydantic 模型具体字段设计（请求/响应结构体）
- FastAPI 路由组织方式（单文件 vs 多文件 router）
- Lock file 的 stale 检测策略（PID 存活检查 + 超时）
- 命令式端点从 Runner 事件流中提取结构化结果的实现方式
- CORS 具体允许的 origin 列表

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| API-01 | FastAPI application wraps existing DramaRouter without modifying 12 core modules | DramaRouter 是 BaseAgent 子类，root_agent 模块级单例可直接引用；Runner.run_async() 是原生 async generator，FastAPI async 端点可直接调用；无需修改核心模块 |
| API-02 | 14 REST endpoints map all CLI commands | 8 个命令式端点走 Runner（start/next/action/speak/steer/auto/end/storm），6 个查询式端点直接读 state（status/cast/save/load/list/export）；具体端点映射见 Architecture Patterns |
| API-03 | Pydantic v2 models define request/response schemas for all endpoints | Pydantic v2.12.5 已安装；FastAPI 0.135.3 原生支持 Pydantic v2；已有先例 `app/app_utils/typing.py` |
| API-04 | API versioning via URL prefix `/api/v1/` | 使用 FastAPI APIRouter + `app.include_router(router, prefix="/api/v1")` 实现 [VERIFIED: Context7] |
| API-05 | CORS middleware allows Android app origin | 使用 `fastapi.middleware.cors.CORSMiddleware` + `allow_origins` 配置 [VERIFIED: Context7] |
| STATE-01 | `_current_drama_folder` global variable migrated to session-scoped context | 全局变量在 state_manager.py:21，仅被 _get_current_theme 读取且已有 tool_context 优先路径；init_drama_state:546 和 load_progress:766 设置它；迁移：删除全局 + 让无参调用报错 [VERIFIED: codebase grep] |
| STATE-02 | Debounce flush-on-push: state is force-saved before WebSocket push events | 现有 debounce 机制（DEBOUNCE_SECONDS=5, _save_dirty flag, flush_state_sync()）可复用；API 层在推送前调 flush_state_sync()；Plan 13-04 实现 |
| STATE-03 | API server supports one active drama session at a time (single-user mode preserved) | 共享 Runner + 单 Session (D-01) 天然保证；Lock file (D-07) 确保 CLI 和 API 互斥 |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | 0.135.3 | REST API framework | 已作为 google-adk 传递依赖安装 [VERIFIED: uv pip show] |
| pydantic | 2.12.5 | Request/response models | FastAPI 原生集成，已有项目先例 [VERIFIED: uv run python] |
| starlette | 0.52.1 | ASGI toolkit (FastAPI 底层) | FastAPI 依赖 [VERIFIED: uv pip show] |
| uvicorn | 0.44.0 | ASGI server | 已安装，用于运行 FastAPI + Actor A2A 服务 [VERIFIED: uv run python] |
| google-adk | 1.28.1 | Agent framework | Runner + InMemorySessionService + ToolContext [VERIFIED: uv run python] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | 0.28.1 | Async HTTP client | A2A 调用内部使用，API 层无需直接用 [VERIFIED: uv run python] |
| python-dotenv | >=1.0.0 | .env loading | 复用现有 .env 配置模式 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| FastAPI | Flask | Flask 是 sync-only，与 ADK Runner async 模式冲突严重；FastAPI 原生 async |
| FastAPI | Litestar | 功能相当但非标准选择，团队不熟悉 |
| uvicorn | hypercorn | uvicorn 已在项目依赖中，Actor A2A 服务也用 uvicorn |

**Installation:**
```bash
# FastAPI and dependencies already installed as transitive deps of google-adk
# No additional installation needed for core functionality
# If adding explicit dependency to pyproject.toml:
uv add fastapi  # Already present transitively, makes it a direct dependency
```

**Version verification:** FastAPI 0.135.3, Pydantic 2.12.5, Starlette 0.52.1, uvicorn 0.44.0, google-adk 1.28.1 — all verified via `uv pip show` / `uv run python` on 2026-04-15.

## Architecture Patterns

### Recommended Project Structure
```
app/
├── api/                    # NEW: FastAPI application layer
│   ├── __init__.py         # Export create_app()
│   ├── app.py              # FastAPI app factory + lifespan + CORS + router mounting
│   ├── routers/            # Endpoint groups
│   │   ├── __init__.py
│   │   ├── commands.py     # 8 command-style endpoints (start/next/action/speak/steer/auto/end/storm)
│   │   └── queries.py      # 6 query-style endpoints (status/cast/save/load/list/export)
│   ├── models.py           # Pydantic v2 request/response models
│   ├── deps.py             # Shared dependencies (runner, session state, lock)
│   └── runner_utils.py     # Runner event stream → structured result extraction
├── agent.py                # UNCHANGED: DramaRouter + root_agent
├── state_manager.py        # MODIFIED: Remove _current_drama_folder (STATE-01)
├── tools.py                # UNCHANGED
└── ...                     # UNCHANGED
```

### Pattern 1: FastAPI Lifespan for Runner + Session (D-01/D-08)
**What:** 使用 asynccontextmanager 管理 Runner 和 Session 的生命周期
**When to use:** FastAPI app startup/shutdown
**Example:**
```python
# Source: FastAPI official docs [CITED: fastapi.tiangolo.com/advanced/events]
from contextlib import asynccontextmanager
from fastapi import FastAPI
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from app.agent import root_agent

APP_NAME = "app"
USER_ID = "drama_user"
SESSION_ID = "drama_session"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create Runner + Session
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )
    app.state.runner = runner
    app.state.session_service = session_service
    # Create lock file (D-07)
    _create_lock_file()
    yield
    # Shutdown: cleanup actors + delete lock file (D-08)
    from app.actor_service import stop_all_actor_services
    stop_all_actor_services()
    _delete_lock_file()
```

### Pattern 2: Command-style Endpoint — Runner Event Stream Extraction (D-02/D-03)
**What:** 命令式端点通过 Runner.run_async() 发送消息，遍历事件流提取结构化结果
**When to use:** start, next, action, speak, steer, auto, end, storm — 需要 LLM 处理的端点
**Example:**
```python
# Source: Based on cli.py::_send_message pattern [VERIFIED: codebase]
from google.genai import types
from fastapi import HTTPException
import asyncio

async def run_command(runner: Runner, message: str, timeout: float = 120.0) -> dict:
    """Send command to Runner and extract structured result from event stream."""
    content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=message)],
    )
    
    final_text = ""
    tool_results = []
    
    try:
        async for event in asyncio.timeout(timeout).__aenter__(), runner.run_async(
            user_id=USER_ID, session_id=SESSION_ID, new_message=content,
        ):
            # Wait... asyncio.timeout needs different usage pattern
            pass
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Command timed out")
    
    # Better pattern using asyncio.wait_for:
    async def _collect():
        nonlocal final_text, tool_results
        async for event in runner.run_async(
            user_id=USER_ID, session_id=SESSION_ID, new_message=content,
        ):
            if event.is_final_response() and event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        final_text += part.text
            # Extract tool results for structured data (D-03)
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.function_response and part.function_response.response:
                        tool_results.append(part.function_response.response)
    
    await asyncio.wait_for(_collect(), timeout=timeout)
    
    return {
        "final_response": final_text,
        "tool_results": tool_results,
    }
```

### Pattern 3: Query-style Endpoint — Direct State Access (D-05)
**What:** 查询式端点直接调用 state_manager 函数，不经过 LLM
**When to use:** status, cast, save, load, list, export
**Example:**
```python
# Source: Based on existing state_manager API [VERIFIED: codebase]
from app.state_manager import save_progress, load_progress, list_dramas, flush_state_sync

@router.post("/drama/save")
async def save_drama_endpoint(request: SaveRequest, runner_dep=Depends(get_runner)):
    state = runner_dep.app.state.session_service  # access session
    # Need tool_context for state_manager functions
    # Direct call with session state:
    result = save_progress(save_name=request.save_name, tool_context=tool_context)
    if result["status"] == "error":
        return JSONResponse(content=result, status_code=200)  # D-04: 200 + status: error
    return result
```

### Pattern 4: API Versioning via APIRouter (API-04)
**What:** 使用 APIRouter prefix 实现版本化
**When to use:** 所有端点
**Example:**
```python
# Source: [VERIFIED: Context7 /websites/fastapi_tiangolo]
from fastapi import APIRouter, FastAPI

v1_router = APIRouter()
# ... define endpoints on v1_router ...

app = FastAPI(lifespan=lifespan)
app.include_router(v1_router, prefix="/api/v1")
```

### Pattern 5: Lock File Mutual Exclusion (D-07)
**What:** PID-based lock file 确保 CLI 和 API 不同时运行
**When to use:** FastAPI startup / CLI 启动
**Example:**
```python
import os, psutil

LOCK_FILE = os.path.join(os.path.dirname(__file__), ".api.lock")

def _create_lock_file():
    if os.path.exists(LOCK_FILE):
        # Stale detection: check if PID is still alive
        with open(LOCK_FILE) as f:
            pid = int(f.read().strip())
        if psutil.pid_exists(pid):
            raise RuntimeError(f"Another instance is running (PID: {pid})")
        # Stale lock — remove it
        os.remove(LOCK_FILE)
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

def _delete_lock_file():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)
```

**Note:** psutil is NOT currently in dependencies. Two alternatives:
1. Add `psutil` as dependency (recommended — robust PID checking)
2. Use `os.kill(pid, 0)` + catch ProcessLookupError (stdlib-only, no dependency)

### Anti-Patterns to Avoid
- **`asyncio.run()` inside FastAPI handlers:** FastAPI 已在运行事件循环，嵌套 `asyncio.run()` 会抛 `RuntimeError: This event loop is already running`。这是 `trigger_storm()` 的现有问题（tools.py:1114-1124），API 层必须绕过此函数直接调用 `dynamic_storm()`。
- **同步阻塞调用:** `time.sleep(2)` 在 `actor_service.py::create_actor_service` 中阻塞事件循环。但 API 层不直接调用此函数——它由 ADK Agent 通过 tool 调用触发，在 Runner 的 async 上下文中执行。Phase 13 不修改此问题。
- **模块级 Runner 实例:** 不要在模块级创建 Runner，应在 lifespan 中创建并存储在 `app.state` 上，确保事件循环就绪后再初始化。
- **从 API 层直接调用 tool 函数:** Tool 函数需要 `ToolContext` 参数，这是 ADK Runner 内部注入的。API 层应通过 `Runner.run_async()` 间接调用（命令式），或构造合适的 ToolContext（查询式）。

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CORS configuration | Manual CORS headers | `fastapi.middleware.cors.CORSMiddleware` | 浏览器 CORS 规范复杂（preflight、credentials），中间件已处理所有边缘情况 |
| Request validation | Manual type checking | Pydantic v2 + FastAPI dependency injection | 自动类型校验、错误消息、OpenAPI 文档生成 |
| Event loop management | Custom async/sync bridging | FastAPI async endpoints + `Runner.run_async()` | FastAPI 管理事件循环，Runner 是原生 async generator |
| API documentation | Manual doc writing | FastAPI auto-generated OpenAPI/Swagger | 零成本获得交互式 API 文档（/docs, /redoc） |
| Lock file stale detection | Custom PID checking logic | `os.kill(pid, 0)` + exception handling (stdlib) | 足够可靠，无需额外依赖 |

**Key insight:** FastAPI + Pydantic + ADK Runner 的组合天然兼容——三者都是 async-native。不要尝试在它们之间搭建同步桥。

## Runtime State Inventory

> Phase 13 involves state migration (_current_drama_folder removal) and adding lock file state.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `_current_drama_folder` global in state_manager.py:21 — dead code, not stored in any DB or file | Code edit: delete global, modify `_get_current_theme` to require tool_context |
| Stored data | `_save_dirty`, `_save_timer`, `_latest_theme`, `_latest_state_ref` module globals in state_manager.py:149-152 | Code edit: these are debounce state, already thread-safe via Timer; no migration needed |
| Live service config | `app/.api.lock` — NEW file to be created at API startup | Code edit: create lock management module; contains PID string only |
| OS-registered state | None — no systemd/launchd/Task Scheduler registrations | None required |
| Secrets/env vars | `app/.env` contains OPENAI_API_KEY, OPENAI_BASE_URL, MODEL_NAME — no changes needed | None — API server reads same .env as CLI |
| Build artifacts | None — no compiled artifacts or installed packages need updating | None required |

## Common Pitfalls

### Pitfall 1: Event Loop Conflict with trigger_storm()
**What goes wrong:** `trigger_storm()` (tools.py:1106-1124) internally uses `asyncio.run()` and `ThreadPoolExecutor` to bridge sync→async. In FastAPI's already-running event loop, `asyncio.get_event_loop().is_running()` returns True, causing it to use the ThreadPoolExecutor path, which works but adds unnecessary thread overhead and complexity.
**Why it happens:** `trigger_storm` was designed for CLI context where it might be called from sync code.
**How to avoid:** API 层直接调用 `dynamic_storm()` (async native)，绕过 `trigger_storm()` 桥接。Runner 通过 tool 调用 `trigger_storm` 时，ADK 内部会正确处理 async/sync 桥接。
**Warning signs:** `RuntimeError: This event loop is already running` or unexpected thread pool usage.

### Pitfall 2: ToolContext Construction for Query-style Endpoints
**What goes wrong:** 查询式端点（save/load/status 等）需要 ToolContext 来调用 state_manager 函数，但 ToolContext 是 ADK 内部类型，通常由 Runner 自动注入。手动构造可能遗漏必需字段。
**Why it happens:** D-05 要求 save/load 直接调 state_manager，不走 Runner。
**How to avoid:** 创建一个轻量级 ToolContext 适配器，只包含 `state` 属性（dict），因为 state_manager 函数只访问 `tool_context.state["drama"]`。验证方法：grep 所有被 API 直接调用的 state_manager 函数，确认它们只访问 `tool_context.state`。
**Warning signs:** `AttributeError: 'ToolContext' object has no attribute 'xxx'` 或 `KeyError: 'drama'`

### Pitfall 3: Debounce Timer Thread Safety
**What goes wrong:** `_set_state()` 使用 `threading.Timer` 做防抖。FastAPI 运行在 asyncio 事件循环中，Timer 回调在独立线程执行，与 asyncio 不在同一上下文。`_flush_state()` 调用 `_save_state_to_file()` 是纯文件 I/O（线程安全），所以实际上没有竞争条件。但如果未来添加了 asyncio-aware 的保存逻辑，就会出问题。
**Why it happens:** Phase 12 的 debounce 使用 threading.Timer 而非 asyncio 机制。
**How to avoid:** Phase 13 不修改 debounce 机制。STATE-02 的 flush-on-push 只需在推送前调用 `flush_state_sync()`，这是线程安全的。
**Warning signs:** 文件写入交错、JSON 损坏。

### Pitfall 4: Session State Access Without ToolContext
**What goes wrong:** 查询式端点需要读取 session state 但没有 ToolContext。直接访问 `session.state` 需要通过 `InMemorySessionService.get_session()` 获取 Session 对象。
**Why it happens:** D-05 要求直接调 state_manager，但 state_manager 函数期望 `tool_context` 参数。
**How to avoid:** 两种方案：(A) 创建 MockToolContext wrapper 持有 session.state 引用；(B) 修改部分 state_manager 函数接受 `state: dict` 参数。推荐方案 A，不修改核心模块。
**Warning signs:** `TypeError: expected ToolContext, got MagicMock` 或 state 读取不到。

### Pitfall 5: /start Endpoint Overwriting Active Drama
**What goes wrong:** 用户调用 `/start` 创建新戏剧时，如果当前有活跃戏剧，其未保存状态会丢失。
**Why it happens:** `init_drama_state()` 直接覆盖 session state。
**How to avoid:** D-06 要求先自动保存旧 drama。实现：在 `/start` 端点中，检测 `state["drama"]["theme"]` 是否存在，若存在则先调 `save_progress()` + `flush_state_sync()`。
**Warning signs:** 用户报告数据丢失。

### Pitfall 6: Runner Concurrent Access
**What goes wrong:** 两个 HTTP 请求同时调用 `runner.run_async()`，导致 ADK Session 并发修改。
**Why it happens:** FastAPI 默认并发处理请求；Runner + InMemorySessionService 不是线程安全的。
**How to avoid:** 使用 `asyncio.Lock` 确保同一时间只有一个 Runner 调用在执行。这符合单用户模式 (STATE-03) 和互斥要求 (D-01)。
**Warning signs:** State 数据不一致、对话交错、session corruption。

## Code Examples

Verified patterns from official sources and codebase:

### FastAPI App Factory with Lifespan
```python
# Source: [VERIFIED: Context7 /websites/fastapi_tiangolo] + adapted for ADK Runner
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from app.agent import root_agent

APP_NAME = "app"
USER_ID = "drama_user"
SESSION_ID = "drama_session"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )
    app.state.runner = runner
    app.state.session_service = session_service
    app.state.runner_lock = asyncio.Lock()
    yield
    # Shutdown
    from app.actor_service import stop_all_actor_services
    from app.state_manager import flush_state_sync
    flush_state_sync()
    stop_all_actor_services()

def create_app() -> FastAPI:
    app = FastAPI(
        title="Director-Actor Drama API",
        version="2.0.0",
        lifespan=lifespan,
    )
    # CORS (API-05)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # TODO: restrict to Android app origin
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # API versioning (API-04)
    from app.api.routers import commands, queries
    app.include_router(commands.router, prefix="/api/v1")
    app.include_router(queries.router, prefix="/api/v1")
    return app
```

### Command-style Endpoint Pattern
```python
# Source: Adapted from cli.py::_send_message [VERIFIED: codebase]
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from google.genai import types
from google.adk.events import Event

router = APIRouter()

async def _run_command_and_collect(
    runner: Runner,
    message: str,
    timeout: float = 120.0,
) -> dict:
    """Send command via Runner, collect final response + tool results."""
    content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=message)],
    )
    
    final_text = ""
    tool_results: list[dict] = []
    
    async def _collect():
        nonlocal final_text, tool_results
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=SESSION_ID,
            new_message=content,
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            final_text += part.text
            else:
                # Extract tool results (D-03)
                func_responses = event.get_function_responses()
                for fr in func_responses:
                    if fr.response:
                        tool_results.append(dict(fr.response))
    
    try:
        await asyncio.wait_for(_collect(), timeout=timeout)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Command execution timed out")
    
    return {
        "final_response": final_text,
        "tool_results": tool_results,
    }

@router.post("/drama/start")
async def start_drama(
    request: StartDramaRequest,
    runner=Depends(get_runner),
    lock=Depends(get_runner_lock),
):
    async with lock:  # Ensure single concurrent Runner access (STATE-03)
        # D-06: auto-save existing drama before starting new one
        drama = runner.app.state.session_service.get_session(...)
        if drama and drama.state.get("drama", {}).get("theme"):
            save_progress(tool_context=...)
            flush_state_sync()
        
        result = await _run_command_and_collect(runner, f"/start {request.theme}")
        return StartDramaResponse(**result)
```

### Query-style Endpoint Pattern
```python
# Source: Based on state_manager API [VERIFIED: codebase grep]
@router.get("/drama/status")
async def get_status(tool_context=Depends(get_tool_context)):
    state = tool_context.state.get("drama", {})
    if not state.get("theme"):
        raise HTTPException(status_code=404, detail="No active drama session")
    
    result = get_current_state(tool_context)
    return DramaStatusResponse(**result)

@router.post("/drama/save")
async def save_drama_endpoint(
    request: SaveRequest,
    tool_context=Depends(get_tool_context),
):
    result = save_progress(request.save_name, tool_context)
    # D-04: tool business errors → 200 + status: error
    return result

@router.get("/drama/list")
async def list_dramas_endpoint():
    # No tool_context needed — reads filesystem directly
    result = list_dramas()
    return DramaListResponse(**result)
```

### _current_drama_folder Migration (STATE-01)
```python
# BEFORE (state_manager.py):
_current_drama_folder: Optional[str] = None

def _get_current_theme(tool_context=None) -> str:
    if tool_context is not None:
        return tool_context.state.get("drama", {}).get("theme", "")
    return _current_drama_folder or ""

# AFTER (state_manager.py):
def _get_current_theme(tool_context=None) -> str:
    """Get the current drama theme. tool_context is required."""
    if tool_context is None:
        raise ValueError("tool_context is required — _current_drama_folder global removed")
    return tool_context.state.get("drama", {}).get("theme", "")

# Remove from init_drama_state():
#   global _current_drama_folder
#   _current_drama_folder = theme

# Remove from load_progress():
#   global _current_drama_folder
#   _current_drama_folder = save_data.get("theme", "")
```

### Lock File Management (D-07)
```python
# Source: stdlib-only PID check pattern [ASSUMED — standard Unix pattern]
import os
import signal

LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".api.lock")

def _is_pid_alive(pid: int) -> bool:
    """Check if a process with given PID is alive (Unix)."""
    try:
        os.kill(pid, 0)  # Signal 0 doesn't kill, just checks existence
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # Process exists but we can't signal it

def acquire_lock():
    """Create lock file with current PID. Raise if another instance is running."""
    if os.path.exists(LOCK_FILE):
        with open(LOCK_FILE) as f:
            try:
                pid = int(f.read().strip())
            except ValueError:
                # Corrupted lock file — remove it
                os.remove(LOCK_FILE)
            else:
                if _is_pid_alive(pid):
                    raise RuntimeError(f"Another instance is running (PID: {pid})")
                # Stale lock — owning process is dead
                os.remove(LOCK_FILE)
    
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

def release_lock():
    """Remove lock file on shutdown."""
    try:
        os.remove(LOCK_FILE)
    except FileNotFoundError:
        pass
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| FastAPI `on_event("startup")` | `lifespan` asynccontextmanager | FastAPI 0.93+ (2023) | 旧方式已废弃，lifespan 是官方推荐 |
| Pydantic v1 `BaseModel` | Pydantic v2 `BaseModel` | Pydantic 2.0 (2023-06) | 性能提升5-50x，API 微调（model_dump 替代 dict()） |
| `asyncio.run()` bridging | Native async endpoints | Always | 不要在运行中的事件循环里调 asyncio.run() |

**Deprecated/outdated:**
- FastAPI `@app.on_event("startup")` / `@app.on_event("shutdown")`: 使用 `lifespan` 参数替代 [CITED: fastapi.tiangolo.com/advanced/events]
- `trigger_storm()` sync→async bridge: 使用 `dynamic_storm()` 直接调用替代

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `os.kill(pid, 0)` works on the deployment target (Linux) for lock file stale detection | Lock File Management | 如果目标平台是 Windows，需要用其他方式检测进程存活 |
| A2 | `Event.get_function_responses()` 返回的 response 是 dict-like 对象，可以被 `dict()` 转换 | Command-style Endpoint | 如果返回类型不是 dict-like，需要额外适配 |
| A3 | state_manager 函数被 API 直接调用时，只需要 `tool_context.state` 属性 | Query-style Endpoint | 如果某些函数还需要其他 ToolContext 属性（如 invocation_id），需要扩展 MockToolContext |
| A4 | `asyncio.Lock` 足以确保 Runner 单并发访问，不需要更复杂的排队机制 | Pitfall 6 | 如果需要请求排队+超时，需要 asyncio.Queue 或类似机制 |
| A5 | FastAPI transitive dependency (via google-adk) is stable enough to use directly without pinning | Standard Stack | 如果 google-adk 升级导致 FastAPI 版本不兼容，需要显式 pin |

## Open Questions

1. **ToolContext Adapter Design**
   - What we know: state_manager functions accessed by API (save_progress, load_progress, get_current_state, get_all_actors, get_drama_folder, export_script, export_conversations, list_dramas) all accept `tool_context=None` parameter. Some use `tool_context.state["drama"]`.
   - What's unclear: Whether any of these functions access ToolContext attributes beyond `.state` (e.g., `.session`, `.invocation_id`). Need to verify by reading each function implementation.
   - Recommendation: Grep all called state_manager functions for `tool_context.` access patterns before implementing adapter.

2. **`/speak` Endpoint Semantics**
   - What we know: API-02 lists "speak" as one of 14 endpoints. The tool `actor_speak(actor_name, situation, tool_context)` calls A2A services.
   - What's unclear: Should `/speak` be a direct actor communication endpoint (bypass director), or does it go through the director agent? Direct actor speak is not a CLI command.
   - Recommendation: `/speak` 应该是一个直接向指定演员发送消息的端点，绕过 Director。这在 Android 端用于 Actor 面板交互。请求体需要 `actor_name` + `situation`。

3. **CORS Origin List**
   - What we know: API-05 requires CORS for Android app. Claude's discretion on specific origins.
   - What's unclear: Android app 的 origin 是什么？在开发阶段可能是 `http://localhost:*` 或 `*`。
   - Recommendation: 开发阶段用 `allow_origins=["*"]`，生产阶段限制为 Android app 实际 origin（通常是 `capacitor://localhost` 或自定义 scheme）。

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | Runtime | ✓ | 3.11.1 | — |
| FastAPI | REST API framework | ✓ | 0.135.3 | — |
| Pydantic v2 | Request/response models | ✓ | 2.12.5 | — |
| uvicorn | ASGI server | ✓ | 0.44.0 | — |
| google-adk | Runner + Session | ✓ | 1.28.1 | — |
| httpx | A2A calls (transitive) | ✓ | 0.28.1 | — |
| pytest | Testing | ✓ | 8.3.4+ | — |
| pytest-asyncio | Async testing | ✓ | 0.23.8+ | — |

**Missing dependencies with no fallback:**
- None — all required dependencies are available.

**Missing dependencies with fallback:**
- `psutil` (optional) — for robust PID checking in lock file. Fallback: `os.kill(pid, 0)` stdlib approach.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.4 + pytest-asyncio 0.23.8 |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/unit/test_api.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| API-01 | FastAPI app wraps DramaRouter without modifying core modules | unit | `uv run pytest tests/unit/test_api.py::test_app_wraps_router -x` | ❌ Wave 0 |
| API-02 | 14 REST endpoints map all CLI commands | unit | `uv run pytest tests/unit/test_api.py::test_all_endpoints_exist -x` | ❌ Wave 0 |
| API-03 | Pydantic v2 models define request/response schemas | unit | `uv run pytest tests/unit/test_api.py::test_pydantic_models -x` | ❌ Wave 0 |
| API-04 | API versioning via URL prefix /api/v1/ | unit | `uv run pytest tests/unit/test_api.py::test_version_prefix -x` | ❌ Wave 0 |
| API-05 | CORS middleware allows Android app origin | unit | `uv run pytest tests/unit/test_api.py::test_cors_headers -x` | ❌ Wave 0 |
| STATE-01 | _current_drama_folder migrated to session-scoped context | unit | `uv run pytest tests/unit/test_state_manager.py::test_no_global_drama_folder -x` | ❌ Wave 0 |
| STATE-02 | Debounce flush-on-push before WebSocket events | unit | `uv run pytest tests/unit/test_api.py::test_flush_before_push -x` | ❌ Wave 0 |
| STATE-03 | Single active drama session enforced | unit | `uv run pytest tests/unit/test_api.py::test_single_session_lock -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_api.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_api.py` — covers API-01~05, STATE-02, STATE-03
- [ ] `tests/unit/test_state_manager.py` — update existing tests for STATE-01 (remove _current_drama_folder references)
- [ ] Test client setup: `from httpx import AsyncClient, ASGITransport` — for testing FastAPI app without real HTTP server

*(If no gaps: "None — existing test infrastructure covers all phase requirements")*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase 15 (not this phase) |
| V3 Session Management | yes | InMemorySessionService — single session, process-bound |
| V4 Access Control | yes | asyncio.Lock — single concurrent Runner access |
| V5 Input Validation | yes | Pydantic v2 models — auto-validate request bodies |
| V6 Cryptography | no | No encryption in this phase |

### Known Threat Patterns for FastAPI

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Request body size bomb | Denial of Service | FastAPI default limits + Pydantic field constraints |
| Unrestricted CORS | Information Disclosure | Restrict allow_origins to known Android origins (API-05) |
| Path traversal via theme/save_name | Tampering | `_sanitize_name()` already sanitizes filesystem paths [VERIFIED: codebase] |
| Concurrent state mutation | Tampering | asyncio.Lock ensures serial Runner access (STATE-03) |
| Stale lock file PID reuse | Elevation of Privilege | PID reuse detection: check process start time vs lock file mtime [ASSUMED] |

## Sources

### Primary (HIGH confidence)
- Context7 `/websites/fastapi_tiangolo` — CORS middleware, APIRouter, lifespan, Pydantic v2 integration
- Codebase grep — `_current_drama_folder`, `_get_current_theme`, `Runner.run_async`, state_manager functions
- `uv pip show` / `uv run python` — FastAPI 0.135.3, Pydantic 2.12.5, google-adk 1.28.1

### Secondary (MEDIUM confidence)
- cli.py source code — Runner usage pattern, event stream processing
- app/agent.py source code — DramaRouter routing logic, root_agent definition
- app/tools.py source code — tool function signatures, return value formats

### Tertiary (LOW confidence)
- `os.kill(pid, 0)` PID detection pattern — standard Unix idiom but not verified on all target platforms

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified, FastAPI already installed as transitive dependency
- Architecture: HIGH — patterns derived from existing codebase (cli.py Runner usage) and official FastAPI docs
- Pitfalls: HIGH — event loop conflict verified by reading trigger_storm source code, debounce thread safety verified by reading _set_state source

**Research date:** 2026-04-15
**Valid until:** 2026-05-15 (stable domain — FastAPI patterns change slowly)
