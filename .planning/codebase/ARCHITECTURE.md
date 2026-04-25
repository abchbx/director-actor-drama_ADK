# Architecture

**Analysis Date:** 2026-04-25

## Pattern Overview

**Overall:** Multi-Agent Drama Director with A2A (Agent-to-Agent) Isolation

**Key Characteristics:**
- **Director-Actor Pattern**: A central Director agent orchestrates multiple isolated Actor agents via A2A protocol
- **User-as-Protagonist**: The human user is a special "User-Controlled" actor named "你" (You), not driven by AI
- **STORM Framework**: Multi-perspective discovery and synthesis for story creation (Discovery → Research → Outline → Directing)
- **State-Centric Design**: All modules are pure functions receiving `state: dict`, ensuring testability without ToolContext dependency
- **Token-Budget Context Assembly**: Priority-based section truncation ensures LLM prompts stay within budget

## Layers

**API Layer:**
- Purpose: HTTP/WS endpoints for Android clients and web UI
- Location: `app/api/routers/`, `app/api/models.py`
- Contains: FastAPI routers, Pydantic models, WebSocket event models
- Depends on: ADK Runner, state_manager
- Used by: Android app, web clients

**Director Agent Layer:**
- Purpose: Core orchestration — scene advancement, conflict injection, STORM triggers, actor coordination
- Location: `app/tools.py`, `app/agent.py`
- Contains: Tool functions (start_drama, next_scene, actor_speak, user_action, etc.), agent definition
- Depends on: All service modules (arc_tracker, conflict_engine, dynamic_storm, context_builder, memory_manager, state_manager)
- Used by: API layer via ADK Runner

**Service Modules (Pure Functions):**
- Purpose: Domain logic as testable pure functions accepting `state: dict`
- Location: `app/arc_tracker.py`, `app/conflict_engine.py`, `app/dynamic_storm.py`, `app/coherence_checker.py`, `app/timeline_tracker.py`, `app/context_builder.py`
- Contains: Constants, validation, state mutation logic, prompt construction
- Depends on: Each other via imports (arc_tracker → conflict_engine context, etc.)
- Used by: Director agent (tools.py)

**Memory Management:**
- Purpose: 4-tier memory system for actors (working → scene summaries → arc summary → vector)
- Location: `app/memory_manager.py`, `app/semantic_retriever.py`, `app/vector_memory.py`
- Contains: Memory CRUD, compression, decay, semantic retrieval, ChromaDB vector store
- Depends on: state_manager, LLM for compression
- Used by: context_builder, tools.py

**State Persistence:**
- Purpose: Drama state save/load with debounced disk persistence
- Location: `app/state_manager.py`
- Contains: SceneContext (coreference resolution), state CRUD, scene archival, STORM state management
- Depends on: File system, vector_memory
- Used by: All layers

**Actor Service Layer:**
- Purpose: A2A agent lifecycle management — create, start, stop, restart
- Location: `app/actor_service.py`
- Contains: Process management, AgentCard generation, port allocation
- Depends on: google-adk, a2a-sdk
- Used by: tools.py

**Android UI Layer:**
- Purpose: Native Android client with Compose UI
- Location: `android/app/src/main/java/com/drama/app/`
- Contains: Screens, ViewModels, components (DialogueBubble), domain models (SceneBubble)
- Depends on: Backend API via HTTP/WebSocket
- Used by: End users

## Data Flow

**Scene Lifecycle:**

1. User sends `/next` → `next_scene()` in tools.py
2. `advance_scene()` increments current_scene, updates dynamic_storm counter
3. `_extract_scene_transition()` builds transition context from previous scene
4. Director generates narration via `director_narrate()`
5. Director calls `actor_speak()` for each actor → A2A call to isolated agent
6. `chime_in()` triggers spontaneous reactions from related actors
7. `write_scene()` records scene data to state
8. `archive_old_scenes()` archives scenes beyond threshold (20)

**User-as-Protagonist Flow:**

1. User sends chat message or `/action` → `user_action()` or `/drama/chat` endpoint
2. Chat messages without @mention route to `/action` (user acts as protagonist)
3. Chat messages with @mention route to `/speak {actor} {message}`
4. `add_conversation(speaker="主角", ...)` records user action in conversation log
5. Director responds by narrating and having actors react
6. UI: Android ViewModel creates local user bubble immediately; backend doesn't push user_message event

**Arc Tracking Flow:**

1. Director calls `create_thread()` → `create_thread_logic()` generates thread with auto-ID
2. `update_thread()` / `update_thread_logic()` adds progress notes (FIFO capped at 10)
3. `resolve_thread()` marks resolved, checks for linked conflicts
4. `set_actor_arc()` / `set_actor_arc_logic()` tracks character arc (type/stage/progress)
5. `context_builder._build_arc_tracking_section()` shows threads in director context
6. `context_builder._assemble_actor_sections()` includes actor's threads in their prompt

**Dynamic STORM Flow:**

1. `dynamic_storm()` called on interval (every 8 scenes) or tension-low trigger
2. `discover_perspectives_prompt()` builds LLM prompt from state
3. LLM generates 1-2 new perspectives
4. `check_keyword_overlap()` deduplicates against existing perspectives
5. `suggest_conflict_types()` maps perspective keywords to conflict types
6. `parse_llm_perspectives()` validates and structures response
7. `update_dynamic_storm_state()` updates counter, records trigger history

**State Management:**
- All state lives in `tool_context.state["drama"]` (in-memory)
- `_set_state()` writes to context immediately, persists to disk via 5-second debounce
- `flush_state_sync()` forces immediate write (called at exit, save, load)
- Atomic file writes via temp-file + rename pattern

## Key Abstractions

**SceneContext (Coreference Resolution):**
- Purpose: Maintains shared cognitive state of the current scene — tracks entities, pronoun mappings
- Examples: `app/state_manager.py` (class SceneContext)
- Pattern: Singleton per drama state, mutated by director, consumed by `resolve_coreferences()` before actor prompts
- Resolution order: speaker-specific → global pronoun_map → last_mentioned → unresolvable

**User Protagonist ("你"):**
- Purpose: The human user is a special actor with `is_user_protagonist: True` and `control_type: "User-Controlled"`
- Examples: `app/state_manager.py` (init_drama_state, load_progress), `app/tools.py` (actor_speak, create_actor)
- Pattern: Auto-injected on drama init, cannot be deleted/overwritten, excluded from A2A calls, excluded from chime_in
- Backward compat: `load_progress()` auto-injects user protagonist into old saves missing it

**Arc Progress:**
- Purpose: Track character arc for each actor
- Examples: `app/arc_tracker.py` (set_actor_arc_logic), `app/state_manager.py` (actor data)
- Pattern: Dict on each actor with arc_type (growth/fall/transformation/redemption), arc_stage (setup/development/climax/resolution), progress (0-100), related_threads

**Plot Threads:**
- Purpose: Track story arcs as first-class entities
- Examples: `app/arc_tracker.py` (create_thread_logic, update_thread_logic, resolve_thread_logic)
- Pattern: Auto-generated thread IDs (thread_{scene}_{keyword}_{index}), status lifecycle (active → dormant → resolving → resolved), FIFO progress_notes

## Entry Points

**Backend API:**
- Location: `app/api/routers/commands.py`
- Triggers: HTTP POST endpoints (/drama/start, /next, /action, /speak, /steer, /auto, /end, /storm, /chat)
- Responsibilities: Acquire asyncio lock, validate active drama, route to ADK Runner, return CommandResponse

**WebSocket:**
- Location: `app/api/routers/` (WS connection manager)
- Triggers: Real-time scene events pushed to Android clients
- Responsibilities: Broadcast director_log, actor_dialogue, narration events

**ADK Agent:**
- Location: `app/agent.py`
- Triggers: Runner.run_async() called by API endpoints
- Responsibilities: LLM-powered director agent with tool access

**Android App:**
- Location: `android/app/src/main/java/com/drama/app/`
- Triggers: User interactions (chat input, scene navigation)
- Responsibilities: Display drama UI, manage local state, communicate with backend

## Error Handling

**Strategy:** Graceful degradation with auto-recovery

**Patterns:**
- **Crash Recovery (D-16~D-19)**: Passive detection when A2A call fails → auto-restart actor (max 3 crashes), retry once after restart
- **State Corruption Protection**: Atomic file writes (temp + rename), backward-compatible migration on load
- **LLM Parse Failures**: `parse_llm_perspectives()` returns empty list on JSON decode failure; `parse_contradictions()` returns empty on malformed LLM output
- **Actor Validation**: `create_thread_logic()` checks actors exist; `set_actor_arc_logic()` validates arc_type/stage enums; `register_actor()` prevents overwriting user protagonist

## Cross-Cutting Concerns

**Logging:** Python `logging` module, `[DIRECTOR-LOG]` prefix for server console, optional WS push as 'director_log' events for Android

**Validation:** Pydantic v2 models for API layer, manual validation in pure functions (arc_tracker, conflict_engine)

**Authentication:** Token-based auth via `require_auth` dependency; bypass mode available

**Debounced Persistence:** 5-second debounce timer for state writes; `flush_state_sync()` for immediate writes

**Token Budget Control:** Priority-based section truncation in `context_builder.py` — actor budget 8000 tokens, director budget 30000 tokens

---

*Architecture analysis: 2026-04-25*
