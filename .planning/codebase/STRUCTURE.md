# Codebase Structure

**Analysis Date:** 2026-04-11

## Directory Layout

```
director-actor-drama/
├── app/                        # Main application package (ADK agent)
│   ├── __init__.py             # Exports ADK App instance
│   ├── agent.py                # STORM agents + StormRouter + root_agent
│   ├── tools.py                # Director tools (all callable functions)
│   ├── actor_service.py        # Actor A2A service lifecycle management
│   ├── state_manager.py        # Drama state persistence + STORM data
│   ├── .env                    # Environment config (API keys, model) — DO NOT READ
│   ├── .adk/                   # ADK session database (SQLite)
│   ├── actors/                 # Generated actor A2A service files (runtime)
│   ├── dramas/                 # Persistent drama data per theme (runtime)
│   └── app_utils/              # Utility modules
│       ├── telemetry.py        # OpenTelemetry configuration
│       └── typing.py           # Pydantic models (Feedback)
├── cli.py                      # CLI entry point (interactive REPL)
├── director_actor_drama/       # Python package stub (hatch build target)
│   └── .adk/                   # ADK config
├── tests/                      # Test suite
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── eval/                   # ADK evaluation config + evalsets
├── .planning/                  # GSD planning artifacts
├── pyproject.toml              # Project config, dependencies, tool settings
├── Makefile                    # Build/run/test targets
├── README.md                   # Project overview
├── CLAUDE.md                   # AI assistant guidance
├── DESIGN_SPEC.md              # Architecture design specification
├── CHANGELOG.md                # Version history
└── .gitignore                  # Git ignore rules
```

## Directory Purposes

**`app/`:**
- Purpose: Main application package containing all agent logic, tools, and state management
- Contains: Python modules for the ADK agent, generated actor files, persisted drama data
- Key files: `agent.py`, `tools.py`, `actor_service.py`, `state_manager.py`

**`app/actors/`:**
- Purpose: Runtime-generated actor A2A service files
- Contains: One `.py` file per actor (self-contained uvicorn server) + one `_card.json` per actor (A2A discovery metadata)
- Key files: `actor_<name>.py`, `actor_<name>_card.json`
- Generated: Yes — created dynamically by `actor_service.py::create_actor_service()`
- Committed: Yes (existing actor files are committed, though they contain hardcoded API keys — security concern)

**`app/dramas/`:**
- Purpose: Persistent storage for each drama's state, conversations, and exports
- Contains: One subdirectory per drama (sanitized theme name)
- Structure per drama:
  ```
  <theme>/
  ├── state.json              # Full drama state (actors, scenes, STORM data)
  ├── snapshot_<name>.json    # Named save snapshots
  ├── actors/                 # Actor-specific data (currently empty)
  ├── scenes/                 # Individual scene files (currently empty)
  ├── conversations/          # Conversation logs (JSON + Markdown)
  │   ├── conversation_log.json
  │   └── conversation_log.md
  └── exports/                # Exported scripts (Markdown)
      └── <theme>.md
  ```
- Generated: Yes — created by `state_manager.py::_ensure_drama_dirs()`
- Committed: No (runtime data)

**`app/app_utils/`:**
- Purpose: Shared utility modules
- Contains: Telemetry setup, type definitions
- Key files: `telemetry.py`, `typing.py`

**`app/.adk/`:**
- Purpose: ADK framework session storage
- Contains: `session.db` (SQLite database for ADK session persistence)
- Generated: Yes (ADK framework)
- Committed: Likely (contains session data)

**`tests/`:**
- Purpose: Test suite organized by type
- Contains: Unit tests, integration tests, ADK eval configurations
- Key files: `unit/test_dummy.py`, `integration/test_agent.py`, `eval/eval_config.json`

**`director_actor_drama/`:**
- Purpose: Hatch build target package (empty stub for wheel distribution)
- Contains: `.adk/` config only
- Generated: Yes (build system)
- Committed: Yes

## Key File Locations

**Entry Points:**
- `cli.py`: Interactive CLI — `uv run python cli.py` or `make cli`
- `app/__init__.py`: ADK App export — `uv run adk web .` or `make playground`
- `app/agent.py`: Agent definitions — `root_agent` and `app` are the top-level objects

**Agent Definitions:**
- `app/agent.py`: All STORM phase agents + StormRouter + root_agent
  - `_storm_discoverer` (Agent): Phase 1 — perspective discovery
  - `_storm_researcher` (Agent): Phase 2 — deep research per perspective
  - `_storm_outliner` (Agent): Phase 3 — outline synthesis
  - `_storm_director` (Agent): Phase 4 — scene execution
  - `StormRouter` (BaseAgent): Routes to correct phase agent
  - `root_agent`: StormRouter instance with all 4 sub-agents

**Tools:**
- `app/tools.py`: All tool functions exposed to agents
  - Drama lifecycle: `start_drama`, `next_scene`, `user_action`
  - Actor management: `create_actor`, `actor_speak`, `update_emotion`
  - Narration: `director_narrate`, `write_scene`
  - Persistence: `save_drama`, `load_drama`, `export_drama`
  - Query: `show_cast`, `show_status`, `list_all_dramas`
  - STORM: `storm_discover_perspectives`, `storm_ask_perspective_questions`, `storm_research_perspective`, `storm_synthesize_outline`

**Actor Service Management:**
- `app/actor_service.py`: Actor lifecycle
  - `create_actor_service()`: Generate code + write files + launch subprocess
  - `generate_actor_agent_code()`: Template-based code generation for actor services
  - `stop_actor_service()` / `stop_all_actor_services()`: Process termination
  - `get_actor_remote_config()`: Read agent card for A2A connection
  - `list_running_actors()`: Show running subprocess info

**State Management:**
- `app/state_manager.py`: All state CRUD + persistence
  - Drama lifecycle: `init_drama_state`, `save_progress`, `load_progress`, `list_dramas`
  - Scene management: `advance_scene`, `update_script`, `add_narration`
  - Actor state: `register_actor`, `update_actor_memory`, `update_actor_emotion`, `get_actor_info`, `get_all_actors`
  - Conversation: `add_conversation`, `add_dialogue`, `add_action`, `add_system_message`, `export_conversations`
  - STORM: `storm_add_perspective`, `storm_get_perspectives`, `storm_add_research_result`, `storm_get_research_results`, `storm_set_outline`, `storm_get_outline`
  - Internal: `_get_state`, `_set_state`, `_save_state_to_file`, `_load_state_from_file`

**Configuration:**
- `pyproject.toml`: Dependencies, ruff/ty/pytest config, build settings
- `Makefile`: CLI targets (install, playground, cli, test, eval, lint)
- `app/.env`: Environment variables (API keys, base URL, model name) — DO NOT READ CONTENTS

**Design Documentation:**
- `DESIGN_SPEC.md`: Detailed architecture specification
- `CLAUDE.md`: AI assistant guidance for working on this project

## Naming Conventions

**Files:**
- Agent modules: `agent.py` (singular, top-level agent definitions)
- Service modules: `actor_service.py` (snake_case, one concern per file)
- Utility modules: `app_utils/telemetry.py` (snake_case in utility package)
- Actor generated files: `actor_<name>.py` and `actor_<name>_card.json` (Chinese names preserved in filenames, sanitized with `_` for special chars)
- Test files: `test_<module>.py` (pytest convention)

**Directories:**
- Application code: `app/` (flat, no nested packages except `app_utils/`)
- Runtime data: `app/actors/`, `app/dramas/` (generated, lower-case)
- Tests: `tests/unit/`, `tests/integration/`, `tests/eval/` (standard Python test layout)

**Agent Names:**
- STORM agents: `storm_discoverer`, `storm_researcher`, `storm_outliner`, `storm_director`
- Actor agents: `actor_<character_name>` (e.g., `actor_朱棣`)
- Root agent: `storm_director_root`

## Module Dependency Graph

```
cli.py
  ├── app.agent (root_agent, app)
  └── app.actor_service (stop_all_actor_services)

app/__init__.py
  └── app.agent (app)

app/agent.py
  ├── google.adk.agents (Agent, BaseAgent)
  ├── google.adk.apps (App)
  ├── google.adk.models.lite_llm (LiteLlm)
  └── app.tools (all tool functions)

app/tools.py
  ├── google.adk.agents.remote_a2a_agent (RemoteA2aAgent)
  ├── google.adk.tools (ToolContext)
  ├── app.state_manager (all state functions)
  ├── app.actor_service (create_actor_service, get_actor_remote_config, stop_*, list_*)
  ├── a2a.client (ClientFactory, ClientConfig)
  ├── a2a.types (AgentCard, Message, Part, Task)
  └── httpx (AsyncClient)

app/actor_service.py
  ├── a2a.client / a2a.types (for generated call_actor code)
  ├── google.adk.agents (Agent — in generated code only)
  ├── google.adk.a2a.utils.agent_to_a2a (to_a2a — in generated code)
  ├── google.adk.models.lite_llm (LiteLlm — in generated code)
  └── uvicorn (in generated code)

app/state_manager.py
  └── (stdlib only: json, os, datetime)

app/app_utils/telemetry.py
  └── (stdlib only: logging, os)

app/app_utils/typing.py
  └── pydantic (BaseModel, Field)

app/actors/actor_<name>.py (each, generated)
  ├── google.adk.agents (Agent)
  ├── google.adk.a2a.utils.agent_to_a2a (to_a2a)
  ├── google.adk.models.lite_llm (LiteLlm)
  ├── a2a.client / a2a.types (for call_actor tool)
  ├── httpx (for call_actor tool)
  └── uvicorn (HTTP server)
```

## Where to Add New Code

**New STORM Phase / Agent:**
- Agent definition: `app/agent.py` — add new `Agent()` instance and register it in `StormRouter.sub_agents`
- Agent tools: `app/tools.py` — add new tool functions, import them in `agent.py`
- Routing logic: `app/agent.py` `StormRouter._run_async_impl()` — add new status → agent mapping

**New Director Tool:**
- Implementation: `app/tools.py` — add function with `tool_context: ToolContext` parameter
- State operations: `app/state_manager.py` — add corresponding state CRUD functions if needed
- Registration: `app/agent.py` — import and add to the relevant agent's `tools=[]` list

**New Actor Capability:**
- Tool for actors: `app/actor_service.py` `generate_actor_agent_code()` — add tool code to the generated template
- Actor template: The generated code in `generate_actor_agent_code()` — modify the instruction template or add new tools

**New State Fields:**
- State structure: `app/state_manager.py` `init_drama_state()` — add new fields to the initial state dict
- State access: `app/state_manager.py` — add getter/setter functions following existing pattern (e.g., `storm_add_perspective`)
- Persistence: Automatic — `_set_state()` handles JSON serialization of the full state dict

**New CLI Command:**
- Command handling: `cli.py` `run_interactive()` — add to the local command check block
- Agent command: Add corresponding tool in `app/tools.py` and reference in agent instructions

**New Export Format:**
- Export logic: `app/state_manager.py` `export_script()` or `export_conversations()` — add new format branch

**New Test:**
- Unit tests: `tests/unit/test_<module>.py`
- Integration tests: `tests/integration/test_<feature>.py`
- Eval sets: `tests/eval/evalsets/<name>.evalset.json`

## Special Directories

**`app/actors/`:**
- Purpose: Contains generated actor A2A service files (one .py + one _card.json per actor)
- Generated: Yes — by `actor_service.py::create_actor_service()` at runtime
- Committed: Yes (contains historical actor instances with embedded API keys — security concern)
- Cleanup: Not automatic — old actor files accumulate. `stop_actor_service()` kills the process but does not delete the files.

**`app/dramas/`:**
- Purpose: Persistent drama data — state, conversations, exports per drama theme
- Generated: Yes — by `state_manager.py::_ensure_drama_dirs()` on drama initialization
- Committed: No (runtime data, though some sample dramas are in the repo)
- Structure: Each drama gets its own subdirectory with `state.json`, `conversations/`, `exports/`, `actors/`, `scenes/`

**`app/.adk/`:**
- Purpose: ADK session database
- Generated: Yes (ADK framework manages this)
- Committed: Likely (contains `session.db` — a SQLite database)
- Size: Can grow large (observed: 3.47 MB)

**`tests/eval/`:**
- Purpose: ADK agent evaluation configuration and datasets
- Contains: `eval_config.json` and `evalsets/*.evalset.json`
- Generated: No (manually created)
- Committed: Yes

**`.planning/`:**
- Purpose: GSD workflow artifacts (roadmap, phases, codebase analysis)
- Generated: By GSD commands
- Committed: Yes

---

*Structure analysis: 2026-04-11*
