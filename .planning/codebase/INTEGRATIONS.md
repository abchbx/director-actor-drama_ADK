# External Integrations

**Analysis Date:** 2026-04-11

## APIs & External Services

**LLM Provider (OpenAI-Compatible API):**
- Purpose: Powers all agent reasoning — director, discoverer, researcher, outliner, and dynamically created actor agents
- SDK/Client: `google.adk.models.lite_llm.LiteLlm` (ADK's OpenAI-compatible wrapper)
- Auth: `OPENAI_API_KEY` env var
- Base URL: `OPENAI_BASE_URL` env var (configurable endpoint)
- Default model: `openai/claude-sonnet-4-6`
- Integration pattern: Each agent is configured with `LiteLlm(model=MODEL_NAME)` in `app/agent.py`; actor agents embed the same config at code-generation time in `app/actor_service.py`
- Timeout: 120s for A2A actor calls (configured in `httpx.AsyncClient` within `_call_a2a_sdk()` in `app/tools.py`)

## Agent-to-Agent (A2A) Protocol

**A2A SDK (`a2a-sdk~=0.3.22`):**
- Purpose: Inter-agent communication between director and actor agents
- Protocol: HTTP-based JSON-RPC, each agent exposes an A2A-compatible HTTP endpoint
- SDK components used:
  - `a2a.client.ClientFactory` + `ClientConfig` — Create A2A client for sending messages
  - `a2a.types.AgentCard` — Service metadata/discovery document (JSON)
  - `a2a.types.Message` — Message envelope with `messageId`, `parts`, `role`
  - `a2a.types.Part` — Content parts (text + optional metadata)
  - `a2a.types.Task` — Task object in A2A responses (contains `artifacts`, `status`)
- ADK integration: `google.adk.a2a.utils.agent_to_a2a.to_a2a()` converts an ADK `Agent` into an A2A-compatible ASGI app
- ADK remote agent: `google.adk.agents.remote_a2a_agent.RemoteA2aAgent` (imported but not actively used in current tools; director calls actors directly via A2A client)

**Director → Actor Communication:**
- Director calls `actor_speak()` tool in `app/tools.py`
- `actor_speak()` calls `_call_a2a_sdk()` which:
  1. Reads actor's `AgentCard` JSON from `app/actors/actor_<name>_card.json`
  2. Creates `httpx.AsyncClient` with 120s timeout
  3. Creates `ClientFactory` with `streaming=False, polling=False`
  4. Sends `Message` with situation prompt as `Part(text=...)`
  5. Iterates async response events, extracts text from `Message` or `Task` artifacts
  6. Filters out `adk_thought` metadata (agent's internal reasoning)

**Actor → Actor Communication:**
- Each generated actor script includes a `call_actor()` async tool
- Uses same A2A client pattern (read card file → create client → send message)
- Enables direct inter-actor dialogue without going through the director

**Actor Service Lifecycle:**
- `create_actor_service()` in `app/actor_service.py`:
  1. Generates Python code for actor agent via `generate_actor_agent_code()`
  2. Writes `app/actors/actor_<name>.py` (standalone A2A service script)
  3. Writes `app/actors/actor_<name>_card.json` (A2A Agent Card)
  4. Launches as subprocess via `subprocess.Popen([sys.executable, actor_file])`
  5. Waits 2s for startup, checks if process is alive
- Port assignment: Deterministic via `hashlib.md5(name) % 100 + 9001` (ports 9001–9100)
- Process tracking: `_actor_processes` dict maps actor name → `subprocess.Popen` object
- Cleanup: `stop_actor_service()` / `stop_all_actor_services()` with `terminate()` + 5s timeout, then `kill()`

**A2A Agent Card Schema:**
```json
{
  "name": "actor_<角色名>",
  "description": "演员 <角色名>，角色：<身份>",
  "url": "http://localhost:<port>/",
  "version": "1.0.0",
  "capabilities": {"streaming": false},
  "defaultInputModes": ["text/plain"],
  "defaultOutputModes": ["text/plain"],
  "skills": [{"id": "act_<name>", "name": "扮演<角色名>", "tags": ["acting", "roleplay"]}]
}
```
- Discovery endpoint: `http://localhost:<port>/.well-known/agent.json`
- RPC endpoint: `http://localhost:<port>/`

## Google ADK Integration

**Core ADK Components Used:**
- `google.adk.agents.Agent` — Sub-agent definitions (discoverer, researcher, outliner, director)
- `google.adk.agents.BaseAgent` — Base class for `StormRouter` custom router agent
- `google.adk.agents.invocation_context.InvocationContext` — Context passed to agent `_run_async_impl()`
- `google.adk.apps.App` — Root application wrapper; `app = App(root_agent=root_agent, name="app")`
- `google.adk.events.Event`, `EventActions` — Event system for agent communication
- `google.adk.models.lite_llm.LiteLlm` — OpenAI-compatible model wrapper
- `google.adk.runners.Runner` — Orchestrates agent execution with session management
- `google.adk.sessions.InMemorySessionService` — In-memory session state storage
- `google.adk.tools.ToolContext` — Provides `state` dict for tool state management
- `google.adk.a2a.utils.agent_to_a2a.to_a2a` — Converts ADK Agent to A2A-compatible ASGI app
- `google.genai.types.Content`, `Part` — Message content types for Runner interaction

**Agent Architecture (STORM Framework):**
- `StormRouter(BaseAgent)` — Custom router that delegates to sub-agents based on `drama.status` state:
  - `brainstorming` / `storm_discovering` / `""` → `storm_discoverer`
  - `storm_researching` → `storm_researcher`
  - `storm_outlining` → `storm_outliner`
  - `acting` / others → `storm_director`
  - `/save`, `/load`, `/export`, `/cast`, `/status`, `/list` → always routed to `storm_director`

## Data Storage

**Databases:**
- SQLite (via ADK)
  - `app/.adk/session.db` (~3.5 MB) — ADK web playground session persistence
  - `director_actor_drama/.adk/session.db` (~36 KB) — Alternate/legacy session DB
  - Not directly accessed by application code; managed by ADK internals

**File Storage:**
- Local filesystem — Primary persistence mechanism
  - `app/dramas/<theme>/state.json` — Drama state (theme, status, actors, scenes, STORM data)
  - `app/dramas/<theme>/snapshot_<name>.json` — Named save snapshots
  - `app/dramas/<theme>/conversations/conversation_log.json` — Conversation log
  - `app/dramas/<theme>/conversations/conversation_log.md` — Markdown conversation export
  - `app/dramas/<theme>/exports/<theme>.md` — Full script Markdown export
  - `app/actors/actor_<name>.py` — Generated actor agent scripts
  - `app/actors/actor_<name>_card.json` — A2A Agent Cards
  - `app/saves/` — Legacy save directory (contains at least one save file)

**Caching:**
- None — No caching layer; all state reads are from in-memory `tool_context.state` or file I/O

## Authentication & Identity

**Auth Provider:**
- Custom (API key-based)
  - LLM API auth: `OPENAI_API_KEY` env var
  - No user authentication system — single-user CLI application
  - No A2A authentication between agents — all communication on localhost

## Monitoring & Observability

**Error Tracking:**
- None configured (no Sentry, etc.)

**Logs:**
- Python `logging` module — Used in `app/actor_service.py`
- `google-cloud-logging>=3.12.0` — Available for Google Cloud structured logging
- OpenTelemetry GenAI instrumentation — Configured in `app/app_utils/telemetry.py`
  - Enabled when `LOGS_BUCKET_NAME` env var is set
  - Uploads telemetry to GCS bucket (`gs://<bucket>/completions`)
  - Content capture mode: `NO_CONTENT` (metadata only, no prompts/responses)

**CLI Output:**
- Tool calls displayed with `⚙️` prefix
- Tool responses (dialogue, narration, scene) displayed inline
- Final agent response displayed with `🎭 导演:` prefix

## CI/CD & Deployment

**Hosting:**
- Local development only (no deployment target; `deployment_target = "none"` in metadata)

**CI Pipeline:**
- None configured (no GitHub Actions, no CI config files)
- Manual quality checks via `make lint` (ruff check + format, ty type check, codespell)

## Environment Configuration

**Required env vars:**
- `OPENAI_API_KEY` — LLM API authentication key
- `OPENAI_BASE_URL` — LLM API base URL (OpenAI-compatible endpoint)
- `MODEL_NAME` — Model identifier (default: `openai/claude-sonnet-4-6`)

**Optional env vars:**
- `LOGS_BUCKET_NAME` — GCS bucket for telemetry upload
- `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` — Toggle content capture (default: `false`)
- `COMMIT_SHA` — Version identifier for telemetry (default: `dev`)

**Secrets location:**
- `app/.env` — Contains API keys and configuration (DO NOT commit or read)
- ⚠️ SECURITY CONCERN: Generated actor scripts in `app/actors/` embed `OPENAI_API_KEY` and `OPENAI_BASE_URL` as string literals in source code — these are written to disk and should not be committed to version control

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None (all A2A communication is synchronous request-response on localhost)

## File System Integration

**Drama Save/Load System:**
- Save: `save_progress()` in `app/state_manager.py` writes `state.json` + optional snapshot
- Load: `load_progress()` reads `state.json` or snapshot, restores to `tool_context.state`, then `load_drama()` tool in `app/tools.py` restarts all actor A2A services
- Auto-save: `_set_state()` auto-persists state to disk whenever state changes

**Export System:**
- Script export: `export_script()` generates full Markdown script with cast table, STORM outline, scenes, narration log
- Conversation export: `export_conversations()` supports JSON, Markdown, and plain text formats
- Both triggered via `/export` command or automatically during `/save`

**Directory Structure per Drama:**
```
app/dramas/<sanitized_theme>/
├── state.json              # Main state (actors, scenes, STORM data, narration)
├── snapshot_<name>.json    # Named save snapshots
├── actors/                 # Actor-specific data (currently empty)
├── scenes/                 # Individual scene files (currently unused)
├── conversations/          # Conversation logs (JSON + Markdown)
└── exports/                # Exported scripts (Markdown)
```

---

*Integration audit: 2026-04-11*
