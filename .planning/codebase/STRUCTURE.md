# Codebase Structure

**Analysis Date:** 2026-04-25

## Directory Layout

```
director-actor-drama/
├── app/                          # Python backend (FastAPI + ADK agent)
│   ├── agent.py                  # Director agent definition
│   ├── tools.py                  # Tool functions for the director agent (~2880 lines)
│   ├── state_manager.py          # State persistence + SceneContext + STORM state
│   ├── arc_tracker.py            # Plot thread + character arc tracking (pure functions)
│   ├── conflict_engine.py        # Tension calculation + conflict injection
│   ├── dynamic_storm.py          # Dynamic STORM perspective discovery
│   ├── context_builder.py        # LLM context assembly with token budget
│   ├── memory_manager.py         # 4-tier memory CRUD + compression + decay
│   ├── semantic_retriever.py     # Tag-based scene retrieval
│   ├── vector_memory.py          # ChromaDB vector store (Tier 4)
│   ├── coherence_checker.py      # Fact tracking + contradiction detection
│   ├── timeline_tracker.py       # Time progression + jump detection
│   ├── actor_service.py          # A2A agent lifecycle (create/start/stop)
│   ├── api/                      # REST + WebSocket API layer
│   │   ├── models.py             # Pydantic v2 request/response models
│   │   ├── deps.py               # FastAPI dependencies (runner, lock, auth)
│   │   ├── runner_utils.py       # ADK Runner interaction utilities
│   │   └── routers/
│   │       ├── commands.py       # POST endpoints (/start, /next, /action, etc.)
│   │       └── queries.py        # GET endpoints (status, cast, scenes)
│   ├── dramas/                   # Runtime drama data (auto-generated)
│   │   ├── {theme}/              # Per-drama folder
│   │   │   ├── state.json        # Main drama state
│   │   │   ├── actors/           # Vector memory backups
│   │   │   ├── scenes/           # Archived scene files
│   │   │   ├── conversations/    # Conversation logs (deprecated)
│   │   │   └── exports/          # Exported scripts
│   │   └── _active_theme         # Hot-reload recovery marker
│   └── saves/                    # Legacy save files
├── android/                      # Android app (Kotlin + Jetpack Compose)
│   └── app/src/main/java/com/drama/app/
│       ├── ui/
│       │   ├── screens/
│       │   │   └── dramadetail/
│       │   │       └── components/
│       │   │           └── DialogueBubble.kt  # Chat-style dialogue bubble
│       │   ├── components/        # Shared UI components (MarkdownText, etc.)
│       │   └── theme/             # ActorPalette colors, theme config
│       ├── domain/model/          # SceneBubble and other domain models
│       └── ...                    # ViewModels, navigation, DI
└── .planning/                     # Planning documents (GSD output)
```

## Directory Purposes

**`app/`:**
- Purpose: Core Python backend — director agent, tools, state management, service modules
- Contains: Python modules for the drama engine
- Key files: `tools.py`, `state_manager.py`, `arc_tracker.py`, `dynamic_storm.py`

**`app/api/`:**
- Purpose: HTTP/WS API layer for client communication
- Contains: FastAPI routers, Pydantic models, dependencies
- Key files: `routers/commands.py`, `models.py`

**`app/dramas/`:**
- Purpose: Runtime drama data — each drama gets its own isolated folder
- Contains: state.json, actor backups, scene archives, exports
- Key files: Generated at runtime; `_active_theme` marker for recovery

**`android/`:**
- Purpose: Native Android client
- Contains: Compose UI screens, ViewModels, domain models, networking
- Key files: `DialogueBubble.kt`, domain models

## Key File Locations

**Entry Points:**
- `app/api/routers/commands.py`: All REST command endpoints
- `app/agent.py`: Director agent definition (ADK)
- `app/tools.py`: All tool functions available to the director agent

**Arc/Thread Tracking:**
- `app/arc_tracker.py`: Pure functions for plot thread CRUD + character arc tracking
- `app/context_builder.py`: `_build_arc_tracking_section()`, `_build_global_arc_section()`, actor thread assembly
- `app/dynamic_storm.py`: `discover_perspectives_prompt()` includes arc progress in LLM prompt

**Scene Management:**
- `app/state_manager.py`: `advance_scene()`, `update_script()`, `archive_old_scenes()`, `get_scene_summaries()`, `get_scene_detail()`
- `app/context_builder.py`: `_extract_scene_transition()`, `_build_recent_scenes_section()`, `_build_last_scene_transition_section()`
- `app/tools.py`: `next_scene()`, `write_scene()`, `director_narrate()`

**User Protagonist:**
- `app/state_manager.py`: `init_drama_state()` (creates "你" actor), `load_progress()` (backward compat injection)
- `app/tools.py`: `user_action()`, `actor_speak()` (special user protagonist handling), `create_actor()` (prevents overwrite)
- `app/api/routers/commands.py`: `/drama/chat` (routes user messages to /action or /speak)

**Memory System:**
- `app/memory_manager.py`: 4-tier memory (working, scene summaries, arc summary, vector), compression, decay
- `app/semantic_retriever.py`: Tag-based semantic scene retrieval
- `app/vector_memory.py`: ChromaDB vector store integration

**Configuration:**
- `app/arc_tracker.py`: `ARC_TYPES`, `ARC_STAGES`, `DORMANT_THRESHOLD`, `MAX_PROGRESS_NOTES`
- `app/dynamic_storm.py`: `STORM_INTERVAL`, `OVERLAP_THRESHOLD`, `CONFLICT_KEYWORD_MAP`
- `app/state_manager.py`: `SCENE_ARCHIVE_THRESHOLD`, `DEBOUNCE_SECONDS`
- `app/context_builder.py`: `DEFAULT_ACTOR_TOKEN_BUDGET`, `DEFAULT_DIRECTOR_TOKEN_BUDGET`, section priorities

**Core Logic:**
- `app/conflict_engine.py`: Tension calculation, conflict generation, conflict resolution
- `app/coherence_checker.py`: Fact management, consistency validation, contradiction repair
- `app/timeline_tracker.py`: Time progression, period tracking, jump detection

**Testing:**
- `app/tests/` or `tests/`: Test files (location TBD based on project convention)

## Naming Conventions

**Files:**
- Snake_case Python modules: `arc_tracker.py`, `conflict_engine.py`, `dynamic_storm.py`
- PascalCase Kotlin files: `DialogueBubble.kt`, `SceneBubble.kt`

**Functions:**
- Pure logic functions: `snake_case_logic` suffix — e.g., `create_thread_logic`, `set_actor_arc_logic`, `resolve_thread_logic`
- Tool functions (exposed to LLM): `snake_case` — e.g., `next_scene`, `actor_speak`, `user_action`
- Internal helpers: `_leading_underscore` — e.g., `_extract_scene_transition`, `_build_global_arc_section`

**Constants:**
- UPPER_SNAKE_CASE: `STORM_INTERVAL`, `ARC_TYPES`, `DORMANT_THRESHOLD`, `MAX_PROGRESS_NOTES`
- Module-level defaults: `_DEFAULT_ARC_PROGRESS`, `_CHAR_TOKEN_RATIO`

**State dict keys:**
- snake_case: `current_scene`, `plot_threads`, `conflict_engine`, `dynamic_storm`, `arc_progress`
- Actor data keys: `is_user_protagonist`, `control_type`, `working_memory`, `scene_summaries`, `arc_summary`

## Where to Add New Code

**New Plot Thread Feature:**
- Primary logic: `app/arc_tracker.py` — add new pure function
- Tool wrapper: `app/tools.py` — add tool function calling the pure logic
- Context integration: `app/context_builder.py` — add section builder
- State migration: `app/state_manager.py` — add backward compat in `load_progress()`

**New Scene Lifecycle Hook:**
- Scene advance: `app/state_manager.py` — `advance_scene()`
- Scene transition: `app/context_builder.py` — `_extract_scene_transition()` or `_build_last_scene_transition_section()`
- Tool layer: `app/tools.py` — `next_scene()`

**New Actor/Arc Feature:**
- Arc tracking: `app/arc_tracker.py` — extend `set_actor_arc_logic()` or add new function
- Actor context: `app/context_builder.py` — `_assemble_actor_sections()`
- Actor data model: `app/state_manager.py` — `register_actor()`, `init_drama_state()`

**New User Interaction Pattern:**
- API endpoint: `app/api/routers/commands.py` — add new POST endpoint
- Request model: `app/api/models.py` — add Pydantic model
- Tool function: `app/tools.py` — add tool
- Android UI: `android/app/src/main/java/com/drama/app/ui/`

**New Conflict/Tension Feature:**
- Conflict logic: `app/conflict_engine.py` — add pure function
- Tool wrapper: `app/tools.py` — add tool function
- Context: `app/context_builder.py` — `_build_conflict_section()`, `_build_tension_section()`

**Utilities:**
- Shared helpers: Module-level `_helper_function` pattern in relevant module
- LLM utilities: `app/memory_manager.py` (`_call_llm`)

## Special Directories

**`app/dramas/`:**
- Purpose: Runtime drama data folders (one per drama theme)
- Generated: Yes — created by `init_drama_state()` / `_ensure_drama_dirs()`
- Committed: Partially — `综艺犯罪嫌疑人/` is a sample drama; `Phase5InitTest_*/` are test artifacts

**`app/dramas/{theme}/scenes/`:**
- Purpose: Archived scene JSON files (scene_0001.json, etc.)
- Generated: Yes — created by `archive_old_scenes()` when scenes exceed threshold (20)
- Committed: No — runtime data only

**`app/dramas/_active_theme`:**
- Purpose: Marker file for hot-reload recovery (uvicorn WatchFiles restart)
- Generated: Yes — written by `_write_active_theme()`
- Committed: No — runtime marker

**`app/saves/`:**
- Purpose: Legacy save file directory
- Generated: Yes
- Committed: No

**`.planning/`:**
- Purpose: GSD planning documents (codebase analysis, roadmap, phases)
- Generated: Yes — created by GSD commands
- Committed: Yes — part of project documentation

---

*Structure analysis: 2026-04-25*
