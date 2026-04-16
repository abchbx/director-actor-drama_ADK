# Architecture: FastAPI API Server + Android Client Integration

**Version:** v2.0 Draft
**Date:** 2026-04-14
**Status:** Design — Pre-implementation

---

## 1. Overview

This document describes the architecture for adding a **FastAPI API Server** and **Android client** to the existing Director-Actor Drama system. The core principle is **minimal intrusion**: the existing 12-module Python codebase remains the source of truth for all drama logic, and the API layer is a thin asynchronous wrapper that exposes the same capabilities the CLI currently provides.

```
┌──────────────┐       HTTP/REST        ┌──────────────────────────────┐
│  Android App │◄──────────────────────►│     FastAPI API Server       │
│  (Kotlin)    │       WebSocket        │                              │
│              │◄──────────────────────►│  ┌────────┐  ┌───────────┐  │
│  Jetpack     │  scene events push     │  │ Router │  │ WebSocket │  │
│  Compose     │                        │  │ Layer  │  │ Manager   │  │
│  MVVM        │                        │  └───┬────┘  └─────┬─────┘  │
│              │                        │      │             │         │
│              │                        │  ┌───▼─────────────▼─────┐  │
│              │                        │  │   Existing System     │  │
│              │                        │  │   (unchanged core)    │  │
│              │                        │  │                       │  │
│              │                        │  │  DramaRouter          │  │
│              │                        │  │  ├─ setup_agent       │  │
│              │                        │  │  └─ improv_director   │  │
│              │                        │  │                       │  │
│              │                        │  │  Actor A2A Services   │  │
│              │                        │  │  state_manager        │  │
│              │                        │  │  tools (30+)          │  │
│              │                        │  │  memory_manager       │  │
│              │                        │  │  conflict_engine      │  │
│              │                        │  └───────────────────────┘  │
└──────────────┘                        └──────────────────────────────┘
```

---

## 2. API Server Layer

### 2.1 New Module: `app/api/`

A new top-level package `app/api/` is introduced alongside the existing modules. It does **not** refactor any existing code — it wraps it.

```
app/api/
├── __init__.py
├── main.py              # FastAPI app factory, lifespan, startup/shutdown
├── router.py            # REST endpoint definitions
├── ws_manager.py        # WebSocket connection manager (pub/sub)
├── ws_schema.py         # WebSocket message schema (Pydantic models)
├── deps.py              # Dependency injection (shared Runner, SessionService)
├── auth.py              # Simple token auth
└── event_bridge.py      # Hooks that intercept tool outputs → WebSocket events
```

### 2.2 FastAPI App Factory (`app/api/main.py`)

```python
# Key responsibilities:
# 1. Create FastAPI app with lifespan
# 2. Initialize shared ADK Runner + InMemorySessionService
# 3. Start/stop actor A2A services on lifespan
# 4. Mount REST router + WebSocket endpoint
# 5. Register event_bridge hooks

from contextlib import asynccontextmanager
from fastapi import FastAPI
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from app.agent import root_agent
from app.api.ws_manager import WebSocketManager
from app.api.event_bridge import EventBridge

ws_manager = WebSocketManager()
event_bridge = EventBridge(ws_manager)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name="app", user_id="drama_user", session_id="drama_session"
    )
    runner = Runner(agent=root_agent, app_name="app", session_service=session_service)
    app.state.runner = runner
    app.state.session_service = session_service
    yield
    # Shutdown
    from app.actor_service import stop_all_actor_services
    from app.tools import close_shared_client
    stop_all_actor_services()
    await close_shared_client()
```

### 2.3 Key Design Decision: Runner as Shared State

The existing `cli.py` creates one `Runner` + one `InMemorySessionService` per process. The API server reuses this exact pattern — a single `Runner` instance stored on `app.state`. This preserves the existing single-user session model and requires **zero changes** to the agent or tool code.

**Why not one Runner per request?** The ADK `Runner` holds session state (including `drama` dict in `session.state`). Creating per-request runners would lose all in-memory state between requests. The single-runner model matches the CLI's single-session model exactly.

---

## 3. WebSocket Manager

### 3.1 Architecture (`app/api/ws_manager.py`)

The WebSocket Manager implements a **topic-based pub/sub** pattern. Each drama session is a topic; all connected clients subscribed to that topic receive the same events.

```python
class WebSocketManager:
    """Manages WebSocket connections and event broadcasting.

    Pattern: topic-based pub/sub
    - Topic = drama session ID (e.g., "drama_session")
    - All subscribers to a topic receive the same events
    - Supports multiple simultaneous connections (e.g., phone + tablet)
    """

    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = {}  # topic → ws set
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, topic: str): ...
    async def disconnect(self, ws: WebSocket, topic: str): ...
    async def broadcast(self, topic: str, event: dict): ...
    async def send_to(self, ws: WebSocket, event: dict): ...
```

### 3.2 Connection Lifecycle

```
Client                              Server
  │                                   │
  │── WS Connect ───────────────────►│  ws_manager.connect()
  │                                   │  Send: {type: "connected", session_id: ...}
  │                                   │
  │◄── Event: scene_start ──────────│  (triggered by next_scene tool call)
  │◄── Event: narration ────────────│  (triggered by director_narrate tool call)
  │◄── Event: dialogue ─────────────│  (triggered by actor_speak tool call)
  │◄── Event: scene_end ────────────│  (triggered by write_scene tool call)
  │◄── Event: tension_update ───────│  (triggered by evaluate_tension tool call)
  │                                   │
  │── WS Close ─────────────────────►│  ws_manager.disconnect()
```

### 3.3 Reconnection Strategy

- **Client-side**: Android app stores last received `event_id`. On reconnect, sends `last_event_id` in connection handshake.
- **Server-side**: Recent events (last 100) are buffered per topic. On reconnect, replay missed events.
- **Why not server-sent resume state?** The REST API already provides full state via `GET /api/drama/status`. On reconnect, client calls REST + WS, getting full state + live stream.

---

## 4. API Endpoint Design

### 4.1 REST Endpoints

All REST endpoints map to existing tool functions. The API layer translates HTTP requests to `runner.run_async()` calls and returns structured JSON.

#### Drama Lifecycle

| Method | Path | Maps To | Description |
|--------|------|---------|-------------|
| `POST` | `/api/drama/start` | `start_drama(theme)` | Start new drama |
| `POST` | `/api/drama/end` | `end_drama()` | End drama (finale) |
| `POST` | `/api/drama/save` | `save_drama(save_name?)` | Save progress |
| `POST` | `/api/drama/load` | `load_drama(save_name)` | Load saved drama |
| `GET` | `/api/drama/status` | `show_status()` | Current state summary |
| `GET` | `/api/drama/list` | `list_all_dramas()` | List all saved dramas |
| `POST` | `/api/drama/export` | `export_drama()` | Export to Markdown |

#### Scene Control

| Method | Path | Maps To | Description |
|--------|------|---------|-------------|
| `POST` | `/api/scene/next` | `next_scene()` | Advance to next scene |
| `POST` | `/api/scene/action` | `user_action(desc)` | Inject event |
| `POST` | `/api/scene/steer` | `steer_drama(direction)` | Set direction hint |
| `POST` | `/api/scene/auto` | `auto_advance(n)` | Auto-advance N scenes |

#### Actor Management

| Method | Path | Maps To | Description |
|--------|------|---------|-------------|
| `POST` | `/api/actor/create` | `create_actor(...)` | Create A2A actor service |
| `GET` | `/api/actor/cast` | `show_cast()` | List actors + A2A status |
| `POST` | `/api/actor/emotion` | `update_emotion(...)` | Update actor emotion |

#### STORM & Analysis

| Method | Path | Maps To | Description |
|--------|------|---------|-------------|
| `POST` | `/api/storm/discover` | `storm_discover_perspectives(theme)` | Multi-perspective discovery |
| `POST` | `/api/storm/synthesize` | `storm_synthesize_outline(theme)` | Synthesize outline |
| `POST` | `/api/storm/dynamic` | `dynamic_storm(focus?)` | Trigger dynamic STORM |
| `POST` | `/api/tension/evaluate` | `evaluate_tension()` | Score current tension |

#### WebSocket

| Method | Path | Description |
|--------|------|-------------|
| `WS` | `/ws/drama` | Real-time scene event stream |

### 4.2 REST Request/Response Pattern

The API server sends user commands to the `DramaRouter` via `runner.run_async()`, the same mechanism the CLI uses. The key difference: instead of printing to terminal, the API collects events and returns structured JSON + pushes WebSocket events.

```python
# Example: POST /api/scene/next
@router.post("/scene/next")
async def scene_next(request: Request):
    runner = request.app.state.runner
    result = await _run_agent_command(runner, "/next")

    # result contains the full final response text from the director
    return {
        "status": "success",
        "scene_number": result.get("current_scene"),
        "transition": result.get("transition"),
        "director_response": result.get("text"),  # LLM's narrative output
    }
```

### 4.3 The `_run_agent_command` Bridge

This is the critical integration function. It mirrors `cli.py::_send_message()` but returns structured data instead of printing:

```python
async def _run_agent_command(runner: Runner, message: str) -> dict:
    """Send a command to DramaRouter and collect structured response.

    Mirrors cli.py::_send_message() but:
    1. Returns dict instead of printing
    2. Triggers event_bridge for each tool call (WebSocket push)
    3. Collects tool responses for structured API return
    """
    content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=message)],
    )

    result = {"text": "", "tool_calls": [], "tool_responses": []}

    async for event in runner.run_async(
        user_id=USER_ID, session_id=SESSION_ID, new_message=content,
    ):
        if event.is_final_response():
            # Director's final text output
            for part in event.content.parts:
                if part.text:
                    result["text"] += part.text
        elif event.content and event.content.parts:
            for part in event.content.parts:
                if part.function_call:
                    # Track tool invocation → trigger WebSocket event
                    result["tool_calls"].append({
                        "name": part.function_call.name,
                        "args": part.function_call.args,
                    })
                    await event_bridge.on_tool_call(part.function_call)
                if part.function_response:
                    resp = part.function_response.response or {}
                    result["tool_responses"].append({
                        "name": part.function_response.name,
                        "response": resp,
                    })
                    await event_bridge.on_tool_response(
                        part.function_response.name, resp
                    )

    return result
```

### 4.4 Long-Running Operations

LLM calls take 5-30+ seconds. The API handles this with two patterns:

1. **REST + WebSocket hybrid**: REST request blocks until completion (with timeout), while WebSocket pushes intermediate events in real-time. The Android app shows a loading state and renders events as they arrive via WebSocket.

2. **Optional SSE mode**: For clients without WebSocket support, `POST` endpoints accept `?stream=true` to return Server-Sent Events instead of waiting for completion.

---

## 5. WebSocket Message Schema

### 5.1 Event Types (`app/api/ws_schema.py`)

All events follow a consistent envelope:

```python
class WSEvent(BaseModel):
    """Base WebSocket event envelope."""
    type: str               # Event type identifier
    event_id: str           # Unique event ID (UUID)
    timestamp: str          # ISO 8601
    session_id: str         # Drama session ID
    data: dict              # Event-specific payload
```

### 5.2 Event Catalog

| Event Type | Trigger | Data Payload |
|------------|---------|--------------|
| `connected` | WS connection established | `{session_id, drama_status}` |
| `scene_start` | `next_scene()` tool call | `{scene_number, is_first_scene, transition_text, auto_remaining, actors_available}` |
| `narration` | `director_narrate()` tool call | `{narration, formatted_narration}` |
| `dialogue` | `actor_speak()` tool call | `{actor_name, role, emotion, dialogue, formatted_dialogue}` |
| `scene_end` | `write_scene()` tool call | `{scene_number, scene_title, scene_description, dialogue_content, formatted_scene}` |
| `tension_update` | `evaluate_tension()` tool call | `{tension_score, is_boring, active_conflicts, suggestion}` |
| `conflict_inject` | `inject_conflict()` tool call | `{conflict_type, description, prompt_hint}` |
| `actor_created` | `create_actor()` tool call | `{actor_name, role, port, card_url}` |
| `emotion_update` | `update_emotion()` tool call | `{actor_name, emotion}` |
| `drama_started` | `start_drama()` tool call | `{theme, drama_folder}` |
| `drama_ended` | `end_drama()` tool call | `{status, message}` |
| `drama_saved` | `save_drama()` tool call | `{save_name, state_file}` |
| `drama_loaded` | `load_drama()` tool call | `{theme, current_scene, actors_list}` |
| `storm_discover` | `storm_discover_perspectives()` | `{perspectives: [...]}` |
| `storm_synthesize` | `storm_synthesize_outline()` | `{outline: {...}}` |
| `dynamic_storm` | `dynamic_storm()` tool call | `{focus_area, discovered_perspectives}` |
| `director_response` | Final LLM text response | `{text}` — the director's complete formatted output |
| `auto_advance_status` | `auto_advance()` state change | `{remaining, is_active}` |
| `error` | Any tool/API error | `{error_type, message, tool_name?}` |

### 5.3 Event Flow Example: One Complete Scene

```
User: POST /api/scene/next

WS → {type: "scene_start", data: {scene_number: 5, transition_text: "...", actors_available: ["李明", "苏念瑶"]}}
WS → {type: "narration", data: {narration: "暮色笼罩着古老的城墙..."}}
WS → {type: "dialogue", data: {actor_name: "李明", emotion: "焦虑", dialogue: "我们必须在天亮前离开..."}}
WS → {type: "dialogue", data: {actor_name: "苏念瑶", emotion: "决绝", dialogue: "我不会走的。"}}
WS → {type: "scene_end", data: {scene_number: 5, scene_title: "城门之夜"}}
WS → {type: "tension_update", data: {tension_score: 65, is_boring: false}}
WS → {type: "director_response", data: {text: "━━━━━━━━━\n第 5 场：「城门之夜」\n━━━━━━━━━\n..."}}

HTTP Response: {status: "success", director_response: "..."}
```

---

## 6. Integration Points

### 6.1 What's NEW vs What's MODIFIED

#### NEW (no existing code changes)

| Component | File | Purpose |
|-----------|------|---------|
| FastAPI app | `app/api/main.py` | App factory, lifespan, startup |
| REST router | `app/api/router.py` | HTTP endpoint definitions |
| WebSocket manager | `app/api/ws_manager.py` | Connection lifecycle, pub/sub |
| WS schema | `app/api/ws_schema.py` | Pydantic models for events |
| Dependencies | `app/api/deps.py` | Shared Runner injection |
| Auth | `app/api/auth.py` | Simple token auth |
| Event bridge | `app/api/event_bridge.py` | Tool output → WS event translation |
| Server entry | `server.py` (project root) | `uvicorn` entry point |
| API deps | `pyproject.toml` additions | `fastapi`, `uvicorn[standard]`, `websockets` |

#### MODIFIED (minimal changes to existing code)

| File | Change | Why |
|------|--------|-----|
| `pyproject.toml` | Add `fastapi>=0.115.0`, `uvicorn[standard]>=0.30.0`, `websockets>=13.0` | New dependencies |
| `Makefile` | Add `make api` target | Convenience start command |
| `app/actor_service.py` | None | — |
| `app/state_manager.py` | None | — |
| `app/tools.py` | None | — |
| `app/agent.py` | None | — |
| `cli.py` | None | — |

**Key principle: Zero modifications to the 12 core modules.** The event bridge intercepts ADK `Event` objects in the `_run_agent_command` function — it never touches tool code.

### 6.2 Event Bridge: How It Hooks In Without Modifying Tools

The `EventBridge` class receives ADK `Event` objects after they're emitted by the runner. It inspects `function_call.name` and `function_response.response` to determine which WebSocket event to emit:

```python
class EventBridge:
    """Translates ADK tool call/response events into WebSocket events.

    This is a pure observer — it never modifies tool behavior.
    It reads the same event stream that cli.py prints to terminal.
    """

    # Mapping: tool function name → WS event type
    TOOL_EVENT_MAP = {
        "next_scene": "scene_start",
        "director_narrate": "narration",
        "actor_speak": "dialogue",
        "write_scene": "scene_end",
        "evaluate_tension": "tension_update",
        "inject_conflict": "conflict_inject",
        "create_actor": "actor_created",
        "update_emotion": "emotion_update",
        "start_drama": "drama_started",
        "end_drama": "drama_ended",
        "save_drama": "drama_saved",
        "load_drama": "drama_loaded",
        "storm_discover_perspectives": "storm_discover",
        "storm_synthesize_outline": "storm_synthesize",
        "dynamic_storm": "dynamic_storm",
        "auto_advance": "auto_advance_status",
    }

    async def on_tool_call(self, function_call) -> None:
        """Called when a tool is invoked. Emits 'started' if needed."""
        pass  # Most events fire on response, not call

    async def on_tool_response(self, tool_name: str, response: dict) -> None:
        """Called when a tool returns. Emits the corresponding WS event."""
        event_type = self.TOOL_EVENT_MAP.get(tool_name)
        if event_type:
            await self.ws_manager.broadcast(
                topic="drama_session",
                event={
                    "type": event_type,
                    "event_id": str(uuid.uuid4()),
                    "timestamp": datetime.now().isoformat(),
                    "session_id": "drama_session",
                    "data": response,
                }
            )
```

### 6.3 State Access Without Refactoring

The API layer needs to read drama state for `GET` endpoints. Rather than modifying `state_manager.py`, it accesses state through the ADK session:

```python
async def _get_drama_state(request: Request) -> dict:
    """Read current drama state from ADK session (read-only)."""
    session_service = request.app.state.session_service
    session = await session_service.get_session(
        app_name="app", user_id="drama_user", session_id="drama_session"
    )
    return session.state.get("drama", {})
```

For `GET /api/drama/status`, `GET /api/actor/cast`, etc., the API reads `session.state["drama"]` directly — the same data `show_status()` and `show_cast()` read from `ToolContext.state`.

---

## 7. Data Flow

### 7.1 Command Flow (Android → Server → Drama → Android)

```
┌──────────┐  1. POST /api/scene/next  ┌────────────┐
│  Android │──────────────────────────► │  FastAPI    │
│  App     │                            │  Router     │
│          │                            │             │
│          │  2. WS: scene_start ────── │  _run_agent │
│          │◄────────────────────────── │  _command() │
│          │  3. WS: narration ──────── │             │
│          │◄────────────────────────── │  ┌─────────┐│
│          │  4. WS: dialogue ×N ────── │  │ Runner  ││
│          │◄────────────────────────── │  │ .run_   ││
│          │  5. WS: scene_end ──────── │  │ async() ││
│          │◄────────────────────────── │  └────┬────┘│
│          │  6. WS: tension_update ─── │       │     │
│          │◄────────────────────────── │  ┌────▼────┐│
│          │  7. WS: director_response │  │DramaRtr ││
│          │◄────────────────────────── │  │ ├setup  ││
│          │                            │  │ └improv ││
│          │  8. HTTP 200 Response ──── │  └────┬────┘│
│          │◄────────────────────────── │       │     │
└──────────┘                            └───────┴─────┘
                                              │
                                    ┌─────────▼──────────┐
                                    │  Tool Functions     │
                                    │  next_scene()       │
                                    │  director_narrate() │
                                    │  actor_speak()      │──► A2A Actor Services
                                    │  write_scene()      │    (independent processes)
                                    │  evaluate_tension() │
                                    └────────────────────┘
```

### 7.2 Setup Flow (Create New Drama)

```
Android                           Server                              A2A Actors
  │                                 │                                    │
  │─ POST /api/drama/start ───────►│                                    │
  │  {theme: "太空探险"}            │─ runner.run_async("/start 太空探险")│
  │                                 │  → setup_agent routes              │
  │                                 │  → start_drama()                   │
  │◄─ WS: drama_started ──────────│  → storm_discover_perspectives()   │
  │◄─ WS: storm_discover ─────────│  → storm_synthesize_outline()      │
  │◄─ WS: storm_synthesize ───────│  → create_actor() × N              │
  │◄─ WS: actor_created ──────────│                                    │
  │  {name: "指挥官", port: 9042}  │                          ┌─────────┤
  │◄─ WS: actor_created ──────────│                          │ uvicorn │
  │  {name: "工程师", port: 9067}  │                          │ :9042   │
  │                                 │                          ├─────────┤
  │◄─ WS: director_response ──────│                          │ uvicorn │
  │  (full setup output)           │                          │ :9067   │
  │                                 │                          └─────────┘
  │◄─ HTTP 200 ───────────────────│
  │  {status: "success", ...}      │
```

### 7.3 Auto-Advance Flow

```
Android                           Server
  │                                 │
  │─ POST /api/scene/auto ────────►│  {scenes: 3}
  │                                 │
  │◄─ WS: scene_start (scene N) ──│
  │◄─ WS: narration ──────────────│
  │◄─ WS: dialogue ×M ────────────│
  │◄─ WS: scene_end ──────────────│
  │◄─ WS: tension_update ─────────│
  │◄─ WS: director_response ──────│
  │                                 │  ← Scene N complete, auto-continue
  │◄─ WS: scene_start (scene N+1) │  ← Auto-advance continues
  │◄─ WS: narration ──────────────│
  │◄─ WS: dialogue ×M ────────────│
  │◄─ WS: scene_end ──────────────│
  │◄─ WS: tension_update ─────────│
  │◄─ WS: director_response ──────│
  │                                 │
  │─ POST /api/scene/steer ───────►│  {direction: "让指挥官变偏执"}
  │                                 │  ← This interrupts auto-advance
  │                                 │  ← (DramaRouter clears remaining_auto_scenes)
  │◄─ WS: director_response ──────│
  │◄─ HTTP 200 ───────────────────│
```

**Important**: The auto-advance interruption logic already exists in `DramaRouter._run_async_impl()` (lines 437-440 of `agent.py`). Any non-`/auto` input automatically clears `remaining_auto_scenes`. The API server leverages this existing safety net.

---

## 8. Android App Architecture

### 8.1 Tech Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Kotlin | First-class Android language |
| UI | Jetpack Compose + Material 3 | Modern declarative UI, consistent theming |
| Architecture | MVVM + Repository | Separation of concerns, testability |
| Networking | Retrofit (REST) + OkHttp WebSocket | Mature, well-documented |
| Serialization | Kotlinx Serialization | Native Kotlin, no reflection |
| DI | Hilt | Standard Android DI |
| State | StateFlow + SharedFlow | Reactive state, lifecycle-aware |
| Navigation | Compose Navigation | Type-safe, integrated with Compose |

### 8.2 Module Structure

```
app/
├── di/                         # Hilt modules
│   ├── NetworkModule.kt        # Retrofit, OkHttp, WebSocket instance
│   └── RepositoryModule.kt     # Repository bindings
├── data/
│   ├── remote/
│   │   ├── DramaApiService.kt      # Retrofit interface for REST
│   │   ├── WsEvent.kt              # WebSocket event models
│   │   └── DramaWebSocket.kt       # WebSocket lifecycle manager
│   ├── repository/
│   │   ├── DramaRepository.kt      # Single source of truth
│   │   └── DramaRepositoryImpl.kt  # REST + WS orchestration
│   └── local/                      # (Optional: Room for offline cache)
├── domain/
│   └── model/
│       ├── DramaState.kt           # Domain models
│       ├── Scene.kt
│       ├── Actor.kt
│       └── TensionReport.kt
├── ui/
│   ├── theme/                      # Material 3 theme
│   ├── screen/
│   │   ├── home/HomeScreen.kt      # Drama list + create
│   │   ├── drama/DramaScreen.kt    # Main drama interaction
│   │   ├── cast/CastScreen.kt      # Actor roster + status
│   │   └── export/ExportScreen.kt  # Script export + share
│   └── component/
│       ├── SceneCard.kt            # Scene display card
│       ├── DialogueBubble.kt       # Actor dialogue bubble
│       ├── NarrationBlock.kt       # Director narration block
│       ├── TensionGauge.kt         # Tension score indicator
│       └── CommandBar.kt           # /next, /action, /steer input
└── MainActivity.kt
```

### 8.3 MVVM Data Flow

```
┌──────────────────────────────────────────────────────────┐
│                      UI Layer (Compose)                  │
│                                                          │
│  DramaScreen                                            │
│  ├─ SceneList (LazyColumn of SceneCard)                 │
│  ├─ LiveFeed (real-time narration + dialogue)           │
│  ├─ TensionGauge                                        │
│  └─ CommandBar (/next, /action, /steer)                 │
│          │                          ▲                    │
│          │ events                   │ state              │
│          ▼                          │                    │
│  ┌──────────────────────────────────────────────────┐   │
│  │              DramaViewModel                      │   │
│  │                                                  │   │
│  │  _dramaState: StateFlow<DramaState>             │   │
│  │  _liveEvents: SharedFlow<WSEvent>               │   │
│  │  _isLoading: StateFlow<Boolean>                 │   │
│  │                                                  │   │
│  │  fun nextScene()                                 │   │
│  │  fun injectAction(description: String)           │   │
│  │  fun steerDrama(direction: String)               │   │
│  │  fun startDrama(theme: String)                   │   │
│  └──────────┬──────────────────────┬────────────────┘   │
│             │                      │                     │
└─────────────┼──────────────────────┼─────────────────────┘
              │                      │
              ▼                      ▼
┌──────────────────────────────────────────────────────────┐
│                  Repository Layer                        │
│                                                          │
│  DramaRepositoryImpl                                    │
│  ├─ REST: POST commands via Retrofit                   │
│  ├─ WS:  Receive events via OkHttp WebSocket           │
│  └─ Merge: REST response + WS events → unified state   │
│                                                          │
│  dramaState = merge(                                     │
│    REST GET /api/drama/status,        ← full state      │
│    WS events (dialogue, narration, etc) ← live updates  │
│  )                                                       │
└──────────────────────────────────────────────────────────┘
```

### 8.4 WebSocket Lifecycle on Android

```kotlin
class DramaWebSocket(
    private val okHttpClient: OkHttpClient,
    private val baseUrl: String,
) {
    private var webSocket: WebSocket? = null
    private val _events = MutableSharedFlow<WSEvent>()
    val events: SharedFlow<WSEvent> = _events.asSharedFlow()

    fun connect(token: String) {
        val request = Request.Builder()
            .url("ws://$baseUrl/ws/drama")
            .header("Authorization", "Bearer $token")
            .build()

        webSocket = okHttpClient.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(ws: WebSocket, response: Response) { /* connected */ }
            override fun onMessage(ws: WebSocket, text: String) {
                val event = Json.decodeFromString<WSEvent>(text)
                _events.tryEmit(event)
            }
            override fun onFailure(ws: WebSocket, t: Throwable, response: Response?) {
                // Schedule reconnection with exponential backoff
                scheduleReconnect()
            }
            override fun onClosed(ws: WebSocket, code: Int, reason: String) {
                // Clean disconnect
            }
        })
    }

    fun disconnect() {
        webSocket?.close(1000, "Client disconnect")
        webSocket = null
    }
}
```

### 8.5 Key UI Screens

#### DramaScreen (Main Interaction)

The primary screen during active drama. It displays a real-time stream of scenes and provides command input.

```
┌─────────────────────────────────┐
│ 🎭 全宗恋爱脑              ⋮   │  ← Title + menu
├─────────────────────────────────┤
│ 📊 张力: 65 ████████░░         │  ← TensionGauge
│ ⏱ 时间: 第三天·黄昏            │  ← Timeline
│ 🔄 模式: 手动                  │  ← Auto/Manual indicator
├─────────────────────────────────┤
│ ┌─ 第5场：城门之夜 ──────────┐ │
│ │                             │ │
│ │ 🎬 暮色笼罩着古老的城墙... │ │  ← NarrationBlock
│ │                             │ │
│ │ 🎭 李明（指挥官·焦虑）：   │ │  ← DialogueBubble
│ │    我们必须在天亮前离开...  │ │
│ │                             │ │
│ │ 🎭 苏念瑶（医者·决绝）：   │ │
│ │    我不会走的。             │ │
│ │                             │ │
│ │ 📝 场景已保存               │ │
│ └─────────────────────────────┘ │
│ ┌─ 第4场：密室 ──────────────┐ │  ← Collapsed previous scene
│ │ ...                         │ │
│ └─────────────────────────────┘ │
├─────────────────────────────────┤
│ > 🎯 接下来你想...             │  ← Director's choice prompts
│   A. 指挥官的回忆              │
│   B. 医者的秘密                │
│   C. /action · /steer · /end   │
├─────────────────────────────────┤
│ ┌──────────────────┐ ┌───────┐ │
│ │ 输入命令或事件... │ │ ▶ 下场 │ │  ← CommandBar
│ └──────────────────┘ └───────┘ │
│ [/next] [/action] [/steer]     │  ← Quick actions
│ [/auto] [/storm] [/end]        │
└─────────────────────────────────┘
```

### 8.6 Offline Cache (Optional — Future Enhancement)

Not in v2.0 scope, but the Repository pattern prepares for it:
- **Room database** stores last-known drama state, scenes, actors
- On app start, Room provides immediate UI while REST fetches fresh state
- WebSocket events update Room in real-time
- This is purely an Android-side concern; no server changes needed

---

## 9. Authentication

### 9.1 Simple Token Auth (`app/api/auth.py`)

Designed for **single-user / LAN** scenarios. No OAuth, no registration.

```python
# Flow:
# 1. First connection: client requests token
# 2. Server generates random token, stores in memory
# 3. All subsequent requests: client sends Authorization: Bearer <token>
# 4. WebSocket: token sent as query param or first message

AUTH_TOKEN: str | None = None

@router.post("/auth/token")
async def get_token():
    """Generate or return the single auth token."""
    global AUTH_TOKEN
    if AUTH_TOKEN is None:
        AUTH_TOKEN = secrets.token_urlsafe(32)
    return {"token": AUTH_TOKEN}

async def verify_token(token: str) -> bool:
    """Verify token against the stored single token."""
    return token == AUTH_TOKEN
```

**Security properties:**
- Token is generated on first request (no hardcoded secret)
- Token is valid for the server process lifetime
- No HTTPS required on LAN (but recommended for remote access)
- Single token = single user; concurrent connections share the same token

---

## 10. Build Order

### 10.1 Phase Dependencies

```
Phase 13: API Server Foundation
    │  FastAPI app, Runner integration, _run_agent_command bridge
    │  No WebSocket yet — just REST endpoints returning JSON
    │
    ├──► Phase 14: WebSocket Real-Time Layer
    │       WebSocket manager, event bridge, message schema
    │       REST + WS working together
    │
    ├──► Phase 15: Auth & Polish
    │       Simple token auth, error handling, CORS
    │       Server ready for Android consumption
    │
    └──► Phase 16: Android App — Foundation
            Project setup, Retrofit + WS client, MVVM skeleton
            Home screen + drama creation
            
            ├──► Phase 17: Android App — Drama Interaction
            │       DramaScreen, live feed, command bar
            │       Scene rendering, dialogue bubbles
            │
            └──► Phase 18: Android App — Polish & Integration
                    Cast screen, export, error states
                    Reconnection handling, loading states
                    End-to-end testing
```

### 10.2 Phase Details

#### Phase 13: API Server Foundation
- **NEW**: `app/api/main.py`, `app/api/router.py`, `app/api/deps.py`
- **NEW**: `server.py` (uvicorn entry point)
- **MODIFIED**: `pyproject.toml` (add FastAPI + uvicorn deps)
- **MODIFIED**: `Makefile` (add `make api` target)
- **Tests**: Unit tests for each REST endpoint using `TestClient`
- **Verification**: `curl` commands to start drama, create actor, advance scene

**Key deliverable**: Every CLI command works via REST. Response is structured JSON containing the same data the CLI prints.

#### Phase 14: WebSocket Real-Time Layer
- **NEW**: `app/api/ws_manager.py`, `app/api/ws_schema.py`, `app/api/event_bridge.py`
- **MODIFIED**: `app/api/main.py` (mount WS endpoint)
- **MODIFIED**: `app/api/router.py` (integrate event_bridge into `_run_agent_command`)
- **Tests**: WS connection test, event broadcast test, reconnection buffer test
- **Verification**: `websocat` CLI to observe live events during scene progression

**Key deliverable**: Real-time scene events pushed during REST-triggered operations.

#### Phase 15: Auth & Polish
- **NEW**: `app/api/auth.py`
- **MODIFIED**: `app/api/router.py` (add auth dependency), `app/api/main.py` (CORS)
- **Tests**: Auth flow test, unauthorized access test, CORS test
- **Verification**: Token-based access from external machine

**Key deliverable**: Secured API server ready for mobile client.

#### Phase 16: Android App — Foundation
- **NEW**: Android project with Kotlin + Compose + Hilt
- **NEW**: Retrofit service, WS client, repository, view models
- **NEW**: Home screen (drama list + create)
- **Verification**: Create drama from app, see it in drama list

#### Phase 17: Android App — Drama Interaction
- **NEW**: DramaScreen, SceneCard, DialogueBubble, NarrationBlock
- **NEW**: CommandBar, TensionGauge, LiveFeed
- **NEW**: ViewModel with WS event → state merge
- **Verification**: Full scene cycle from app

#### Phase 18: Android App — Polish & Integration
- **NEW**: CastScreen, ExportScreen
- **NEW**: Reconnection logic, error states, loading skeletons
- **NEW**: Settings screen (server URL configuration)
- **Verification**: End-to-end test on physical device

---

## 11. Technical Considerations

### 11.1 Concurrency Model

The existing system is **single-user, single-session**. The API server preserves this:

- One `Runner` instance, one `InMemorySessionService`, one session
- All REST requests are serialized through the same `Runner` — concurrent requests wait
- WebSocket broadcasts to multiple connections (phone + tablet), but they're all observing the same session

If multi-user support is needed in the future, the architecture would need:
- Per-user `Runner` + `SessionService` instances
- Session-scoped state (replace global `_current_drama_folder`)
- Actor A2A service multiplexing or isolation per session

This is explicitly **out of scope** for v2.0.

### 11.2 State Consistency

The existing debounce save mechanism (`state_manager.py` lines 148-287) works unchanged. The API server reads state from `session.state["drama"]` (in-memory) which is always current, even before the debounce timer flushes to disk.

**Potential issue**: If the server crashes before debounce flushes, up to 5 seconds of state changes could be lost. This is the same risk the CLI has today. Mitigation: the API server calls `flush_state_sync()` in the lifespan shutdown handler.

### 11.3 Actor A2A Service Lifecycle

Actor services are managed by `actor_service.py` using `subprocess.Popen`. The API server inherits this lifecycle:

- **Startup**: Actors are created on demand when `create_actor` tool is called (same as CLI)
- **Runtime**: Actor processes run independently; the API server communicates via A2A protocol
- **Shutdown**: `stop_all_actor_services()` is called in the FastAPI lifespan shutdown handler
- **Crash recovery**: Existing passive detection + auto-restart works unchanged

**No changes needed** to `actor_service.py`.

### 11.4 CORS Configuration

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # LAN access; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

For Android app access on the same LAN, CORS must allow the app's origin. In development, `allow_origins=["*"]` is acceptable. For production, restrict to known origins.

### 11.5 Server Discovery (Android → Server)

The Android app needs to find the server on the LAN. Options:

1. **Manual IP entry**: User types `http://192.168.1.100:8000` in settings
2. **mDNS/Bonjour**: Server advertises `_drama._tcp` service; Android discovers automatically
3. **QR code**: Server displays QR with `http://<ip>:<port>?token=<token>`; Android scans

**Recommendation for v2.0**: Manual IP entry + QR code fallback. mDNS is a nice-to-have for later.

### 11.6 Error Handling

```python
# API-level error responses mirror the tool-level error format
{
    "status": "error",
    "error_type": "rate_limit" | "timeout" | "auth" | "not_found" | "internal",
    "message": "Human-readable error description",
    "suggestion": "Optional fix suggestion"
}
```

Errors from the LLM/A2A layer are caught in `_run_agent_command` and translated to both:
1. HTTP error response (for the requesting client)
2. WebSocket `error` event (for all connected clients)

---

## 12. File Structure Summary

### New Files

```
director-actor-drama/
├── server.py                          # uvicorn entry point (NEW)
├── app/
│   └── api/                           # NEW package
│       ├── __init__.py
│       ├── main.py                    # FastAPI app + lifespan
│       ├── router.py                  # REST endpoints
│       ├── ws_manager.py              # WebSocket pub/sub
│       ├── ws_schema.py               # Event models (Pydantic)
│       ├── deps.py                    # Dependency injection
│       ├── auth.py                    # Token auth
│       └── event_bridge.py            # Tool → WS event bridge
```

### Modified Files

```
director-actor-drama/
├── pyproject.toml                     # Add: fastapi, uvicorn[standard], websockets
├── Makefile                           # Add: api target
```

### Unchanged Files (Core System — Zero Modifications)

```
app/agent.py                           # DramaRouter, setup_agent, improv_director
app/actor_service.py                   # A2A service launcher
app/state_manager.py                   # State persistence + debounce
app/tools.py                           # 30+ tool functions
app/context_builder.py                 # Context assembly + token budget
app/memory_manager.py                  # 3-tier memory + coreference resolution
app/conflict_engine.py                 # Tension scoring + conflict injection
app/arc_tracker.py                     # Arc + thread tracking
app/coherence_checker.py               # Consistency validation
app/timeline_tracker.py                # Time tracking + jump detection
app/dynamic_storm.py                   # Dynamic STORM perspective discovery
app/semantic_retriever.py              # Tag-based scene retrieval
app/tutorial.py                        # Tutorial system
cli.py                                 # CLI interface (continues to work)
```

---

## 13. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| ADK `Runner.run_async()` not safe for concurrent calls | Medium | High | Serialize requests via asyncio.Lock |
| WebSocket disconnection during scene generation | Medium | Low | Client reconnects + REST state sync |
| LLM timeout (30s+) causing HTTP timeout | High | Medium | REST returns immediately with `task_id`; client polls or uses WS for result |
| Actor A2A service crash during mobile session | Low | Medium | Existing auto-restart handles this; WS pushes error event |
| Large state JSON (>1MB) slow to serialize | Low | Low | Scene archival already limits state size (20 scenes max) |

---

*This architecture is designed for minimal invasion into the existing codebase. The entire API layer is additive — if removed, the system reverts to CLI-only with zero code changes.*
