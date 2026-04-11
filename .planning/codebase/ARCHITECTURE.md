# Architecture

**Analysis Date:** 2026-04-11

## Pattern Overview

**Overall:** Director-Actor Multi-Agent Architecture with STORM Framework Pipeline

**Key Characteristics:**
- **Hierarchical multi-agent orchestration**: A central Director (root agent) routes to phase-specific sub-agents, while Actor agents run as physically isolated A2A services
- **Phase-based state machine (STORM)**: Drama creation follows a strict 4-phase pipeline — Discovery → Research → Outline → Directing — with routing enforced by a custom `BaseAgent` subclass
- **A2A protocol for actor isolation**: Each actor is an independent HTTP service (uvicorn + A2A SDK) on a dedicated port, ensuring cognitive boundary enforcement via process-level isolation
- **Dual state management**: In-memory ADK session state (`tool_context.state["drama"]`) is the primary source of truth; filesystem (`app/dramas/<theme>/state.json`) is the persistence layer with auto-save on every mutation

## Layers

**Routing Layer (StormRouter):**
- Purpose: Routes user messages to the correct STORM phase agent based on drama status
- Location: `app/agent.py` (class `StormRouter`)
- Contains: Phase routing logic, sub-agent delegation
- Depends on: All four STORM phase agents
- Used by: ADK Runner (as root_agent)

**STORM Phase Agents (4 sub-agents):**
- Purpose: Each agent handles one phase of the STORM drama creation pipeline
- Location: `app/agent.py` (module-level `_storm_discoverer`, `_storm_researcher`, `_storm_outliner`, `_storm_director`)
- Contains: System instructions, tool assignments per phase
- Depends on: `app/tools.py` (tool functions), `app/state_manager.py` (state access)
- Used by: StormRouter (sub-agent delegation)

**Tool Layer:**
- Purpose: Implements all callable tools for the Director and STORM agents
- Location: `app/tools.py`
- Contains: Drama lifecycle tools, STORM tools, A2A communication bridge
- Depends on: `app/state_manager.py`, `app/actor_service.py`, `a2a` SDK, `google.adk`
- Used by: STORM phase agents (via ADK tool mechanism)

**Actor Service Layer:**
- Purpose: Manages the lifecycle of actor A2A services (create, start, stop, reconnect)
- Location: `app/actor_service.py`
- Contains: Code generation, subprocess management, agent card creation, port allocation
- Depends on: `a2a` SDK, `google.adk`, `uvicorn`, `subprocess`
- Used by: `app/tools.py` (create_actor, load_drama)

**State Management Layer:**
- Purpose: Manages all drama state (scenes, actors, STORM data, conversations) with dual persistence
- Location: `app/state_manager.py`
- Contains: State CRUD functions, conversation logging, STORM data management, export/import
- Depends on: `json`, `os` (filesystem), ADK `ToolContext` (in-memory state)
- Used by: `app/tools.py` (all tool functions)

**Actor Runtime (per-actor):**
- Purpose: Each actor runs as an independent A2A service with its own LLM session
- Location: `app/actors/actor_<name>.py` (generated at runtime)
- Contains: Actor Agent definition, A2A server setup, optional `call_actor` tool for inter-actor communication
- Depends on: `a2a` SDK, `google.adk`, `uvicorn`
- Used by: Director (via A2A protocol), other actors (via `call_actor` tool)

## Data Flow

**STORM Drama Creation Flow:**

```
User: /start <theme>
  │
  ▼
StormRouter ──(status="" / "brainstorming")──► _storm_discoverer
  │                                              │
  │                                    start_drama(theme)
  │                                    storm_discover_perspectives(theme)
  │                                              │
  │                                    state.status → "storm_researching"
  ▼
User: /next
  │
  ▼
StormRouter ──(status="storm_researching")──► _storm_researcher
  │                                              │
  │                                    storm_ask_perspective_questions()
  │                                    storm_research_perspective() × N
  │                                              │
  │                                    state.status → "storm_outlining"
  ▼
User: /next
  │
  ▼
StormRouter ──(status="storm_outlining")──► _storm_outliner
  │                                              │
  │                                    storm_synthesize_outline()
  │                                    create_actor() × N
  │                                              │
  │                                    state.status → "acting"
  ▼
User: /next (loop for each scene)
  │
  ▼
StormRouter ──(status="acting")──► _storm_director
  │                                         │
  │                               next_scene()
  │                               director_narrate() ──► add_narration()
  │                               actor_speak() × N ──► A2A call ──► Actor service
  │                               write_scene() ──► update_script()
  │                               update_emotion() (optional)
```

**A2A Communication Flow (Director → Actor):**

```
_storm_director calls actor_speak(actor_name, situation)
  │
  ▼
tools.py::actor_speak()
  ├── get_actor_info() ──► state_manager (read from tool_context.state)
  ├── get_actor_remote_config() ──► actor_service (read agent card JSON)
  ├── update_actor_memory() ──► state_manager (write situation to actor's memory)
  ├── Build prompt with situation + memory
  │
  ▼
_call_a2a_sdk(card_file, prompt, actor_name, port)
  ├── Load agent card JSON from app/actors/actor_<name>_card.json
  ├── Create AgentCard → ClientFactory → Client
  ├── Send Message via client.send_message()
  ├── Parse response (handle Task/Message/ClientEvent tuples)
  ├── Filter out adk_thought parts
  │
  ▼
Return actor's dialogue text
  │
  ▼
add_dialogue() ──► state_manager (log to conversation)
Return formatted result to director agent
```

**A2A Communication Flow (Actor → Actor):**

```
Actor A's call_actor(actor_name, message)
  ├── Load actor B's card JSON from app/actors/
  ├── Create A2A client with card
  ├── Send message to actor B's A2A service
  ├── Parse response, filter thoughts
  └── Return dialogue text to actor A
```

**State Persistence Flow:**

```
Tool call modifies state
  │
  ▼
state_manager::_set_state(state, tool_context)
  ├── tool_context.state["drama"] = state  (in-memory, for ADK session)
  └── _save_state_to_file(theme, state)    (filesystem, for durability)
       └── app/dramas/<theme>/state.json   (JSON serialization)
```

**State Management:**
- Primary: ADK `ToolContext.state["drama"]` — dict holding all runtime state
- Persistence: `app/dramas/<sanitized_theme>/state.json` — auto-saved on every `_set_state()` call
- Snapshots: Named saves at `app/dramas/<theme>/snapshot_<name>.json`
- Conversation log: In-memory `_conversation_log` list, persisted to `app/dramas/<theme>/conversations/conversation_log.json`
- On load: `load_progress()` reads state.json → writes to `tool_context.state["drama"]` → restarts all actor A2A services

## Key Abstractions

**StormRouter (BaseAgent):**
- Purpose: Custom routing agent that delegates to phase-specific sub-agents based on drama status
- Examples: `app/agent.py` class `StormRouter`
- Pattern: State-driven router — reads `ctx.session.state["drama"]["status"]` and selects sub-agent accordingly
- Special: Commands `/save`, `/load`, `/export`, `/cast`, `/status`, `/list` are always routed to `_storm_director` regardless of current phase

**Actor A2A Service (per-actor):**
- Purpose: Represents a character as an independent agent with isolated cognition
- Examples: `app/actors/actor_朱棣.py`, `app/actors/actor_沈博士.py`
- Pattern: Code-generated subprocess — each actor is a standalone Python script with uvicorn HTTP server, launched as `subprocess.Popen`

**Agent Card (A2A Discovery):**
- Purpose: JSON descriptor for A2A service discovery and connection
- Examples: `app/actors/actor_朱棣_card.json`
- Pattern: Standard A2A `AgentCard` schema with name, URL, capabilities, skills

**Drama State (central data model):**
- Purpose: Single dict holding all drama data: theme, status, current_scene, scenes[], actors{}, narration_log[], storm{}
- Examples: `tool_context.state["drama"]` in all tool functions
- Pattern: Nested dict with JSON serialization, managed through `state_manager` functions

## Entry Points

**CLI (primary):**
- Location: `cli.py`
- Triggers: `uv run python cli.py` or `make cli`
- Responsibilities: Interactive REPL loop, sends user messages to root_agent via ADK Runner, displays tool call progress and formatted output, cleanup on exit

**ADK Web Playground:**
- Location: `app/__init__.py` exports `app` (ADK App instance)
- Triggers: `uv run adk web .` or `make playground`
- Responsibilities: Web UI for agent interaction via ADK's built-in playground

**Actor Services (subprocess):**
- Location: `app/actors/actor_<name>.py` (each is self-contained)
- Triggers: `create_actor_service()` spawns `subprocess.Popen([sys.executable, actor_file])`
- Responsibilities: Run as uvicorn HTTP server exposing A2A protocol endpoints, respond to messages in character

## Error Handling

**Strategy:** Defensive with graceful degradation

**Patterns:**
- **A2A call failures** (`app/tools.py` `_call_a2a_sdk`): Try/except wrapping with categorized error messages — connection refused, timeout, or generic exception. Returns bracketed error text (e.g., `[朱棣连接失败(端口:9030)]`) so the director can display it in the script format
- **Actor service startup** (`app/actor_service.py` `create_actor_service`): Checks `process.poll()` after 2-second startup delay; returns error dict with stderr if process exited early
- **State loading** (`app/state_manager.py` `load_progress`): Falls back to snapshot search if main state.json not found; lists available dramas in error message
- **Missing actors** (`app/tools.py` `actor_speak`): Returns error dict if actor not found in state or card file missing
- **JSON corruption** (`app/state_manager.py` `list_dramas`): Catches `json.JSONDecodeError` and marks drama as "Corrupted" rather than crashing

## Cross-Cutting Concerns

**Logging:** Python `logging` module used in `actor_service.py`. CLI prints tool call names and formatted content to stdout. No structured logging framework.

**Validation:** Actor count capped at 10 (enforced in `state_manager.py::register_actor`). Input sanitization via `_sanitize_name()` for filesystem paths. No schema validation on state structure.

**Authentication:** Environment-based API key configuration (`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `MODEL_NAME`). Keys are injected into generated actor service code at creation time. No user authentication for the CLI.

**Telemetry:** Optional OpenTelemetry setup via `app/app_utils/telemetry.py` — configurable via `LOGS_BUCKET_NAME` env var. Default: disabled.

**Concurrency:** Actor services run as separate processes (subprocess.Popen). The CLI runs a single asyncio event loop. A2A calls use `httpx.AsyncClient`. No database locking needed — filesystem-based persistence with sequential writes.

---

*Architecture analysis: 2026-04-11*
