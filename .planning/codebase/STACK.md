# Technology Stack

**Analysis Date:** 2026-04-11

## Languages

**Primary:**
- Python 3.10–3.13 (required: `>=3.10,<3.14`) - All application logic, agent definitions, tools, state management

**Secondary:**
- JSON - State persistence, agent cards, conversation logs
- Markdown - Exported scripts and conversation logs

## Runtime

**Environment:**
- Python 3.10+ (target version specified as `py310` in ruff config and ty config)

**Package Manager:**
- uv (Astral's Python package manager) - configured via `uv.lock`
- Build system: hatchling (`pyproject.toml` → `[build-system]`)
- Lockfile: `uv.lock` (present, ~1 MB)

## Frameworks

**Core:**
- Google ADK (Agent Development Kit) `>=1.15.0,<2.0.0` with `[extensions]` - Agent framework, provides `Agent`, `BaseAgent`, `Runner`, `SessionService`, `LiteLlm`, `ToolContext`, `App`
- a2a-sdk `~=0.3.22` - Agent-to-Agent protocol SDK for inter-agent communication; provides `ClientFactory`, `ClientConfig`, `AgentCard`, `Message`, `Part`, `Task`

**Testing:**
- pytest `>=8.3.4,<9.0.0` - Test runner
- pytest-asyncio `>=0.23.8,<1.0.0` - Async test support (`asyncio_default_fixture_loop_scope = "function"`)
- nest-asyncio `>=1.6.0,<2.0.0` - Nested event loop support for testing
- google-adk[eval] `>=1.15.0,<2.0.0` (optional) - Agent evaluation framework

**Build/Dev:**
- ruff `>=0.4.6,<1.0.0` (optional lint) - Linter and formatter (line-length: 88, target: py310)
- ty `>=0.0.1a0` (optional lint) - Astral's Rust-based type checker
- codespell `>=2.2.0,<3.0.0` (optional lint) - Spell checker
- uvicorn `>=0.30.0` - ASGI server for actor A2A services

## Key Dependencies

**Critical:**
- `google-adk[extensions]` - Core agent framework; provides `Agent`, `BaseAgent`, `Runner`, `InMemorySessionService`, `LiteLlm`, `ToolContext`, `RemoteA2aAgent`, `to_a2a` utility, `App`, `Event`, `EventActions`
- `a2a-sdk` - A2A protocol implementation; `ClientFactory`, `ClientConfig`, `AgentCard`, `Message`, `Part`, `Role`, `Task` types for inter-agent messaging
- `LiteLlm` - OpenAI-compatible LLM wrapper within ADK; uses `OPENAI_API_KEY` and `OPENAI_BASE_URL` env vars; default model: `openai/claude-sonnet-4-6`

**Infrastructure:**
- `python-dotenv>=1.0.0` - `.env` file loading for configuration
- `httpx` (transitive via a2a-sdk) - Async HTTP client for A2A communication; timeout: 120s
- `uvicorn>=0.30.0` - ASGI server that runs each actor as a standalone HTTP service
- `pydantic` (transitive) - Data models for feedback typing (`app/app_utils/typing.py`)

**Observability:**
- `opentelemetry-instrumentation-google-genai>=0.1.0,<1.0.0` - GenAI telemetry instrumentation
- `gcsfs>=2024.11.0` - Google Cloud Storage filesystem (for telemetry upload)
- `google-cloud-logging>=3.12.0,<4.0.0` - Google Cloud structured logging

## Configuration

**Environment:**
- `.env` file at `app/.env` (loaded via `python-dotenv` at runtime)
- Key env vars: `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `MODEL_NAME`
- Telemetry env vars: `LOGS_BUCKET_NAME`, `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`
- ADK session database: `app/.adk/session.db` (SQLite, used by ADK web playground)

**Build:**
- `pyproject.toml` - Project metadata, dependencies, tool configs
- `Makefile` - Dev commands: `install`, `playground`, `cli`, `test`, `eval`, `lint`
- Ruff config embedded in `pyproject.toml` (`[tool.ruff]`, `[tool.ruff.lint]`, `[tool.ruff.lint.isort]`)
- Ty config in `pyproject.toml` (`[tool.ty]`)
- Pytest config in `pyproject.toml` (`[tool.pytest.ini_options]`)

## LLM Configuration

**Model Access Pattern:**
- Uses `google.adk.models.lite_llm.LiteLlm` as the model interface
- Supports any OpenAI-compatible API endpoint via `OPENAI_BASE_URL`
- Default model identifier: `openai/claude-sonnet-4-6`
- Model resolution: `LiteLlm(model=MODEL_NAME)` where `MODEL_NAME` comes from env var
- All sub-agents (discoverer, researcher, outliner, director) and dynamically generated actor agents share the same model configuration

**API Pattern:**
- OpenAI-compatible chat completion API
- Base URL configurable via `OPENAI_BASE_URL` env var
- Authentication via `OPENAI_API_KEY` env var
- Actor subprocess agents embed API key and base URL at generation time (from `generate_actor_agent_code()` in `app/actor_service.py`)

## Data Storage

**Session State:**
- `InMemorySessionService` - Director agent session state (used in CLI mode)
- ADK `session.db` - SQLite database for ADK web playground session persistence
- State is also stored in `tool_context.state["drama"]` dict during runtime

**Drama Persistence:**
- JSON files on local filesystem under `app/dramas/<sanitized_theme>/`
- `state.json` - Main drama state (theme, status, actors, scenes, STORM data, narration log)
- `snapshot_<name>.json` - Named save snapshots
- `conversations/conversation_log.json` - Full conversation log
- `conversations/conversation_log.md` - Markdown export of conversations
- `exports/<sanitized_theme>.md` - Full script export as Markdown

**Actor Data:**
- `app/actors/actor_<name>.py` - Dynamically generated actor agent Python scripts
- `app/actors/actor_<name>_card.json` - A2A Agent Card JSON for service discovery
- Actor processes run as subprocesses (tracked in `_actor_processes` dict in `app/actor_service.py`)

## CLI Framework

**Implementation:**
- Custom async CLI built with `asyncio` (`cli.py`)
- No external CLI framework (no click, argparse, typer)
- Interactive REPL loop: reads `input()`, sends to ADK `Runner`, prints responses
- Command routing: `/start`, `/next`, `/action`, `/save`, `/load`, `/export`, `/list`, `/cast`, `/status`, `/quit`, `/help`
- Entry point: `python cli.py` or `uv run python cli.py`

**ADK Web Playground:**
- Run via `uv run adk web . --port 8501 --reload_agents` (Makefile target: `make playground`)
- Uses ADK's built-in web server with SSE streaming

## Testing Framework

**Runner:**
- pytest >=8.3.4 - Config: `pythonpath = "."`, `asyncio_default_fixture_loop_scope = "function"`

**Test Organization:**
- `tests/unit/` - Unit tests (currently only `test_dummy.py` placeholder)
- `tests/integration/` - Integration tests (currently `test_agent.py` with streaming test)
- `tests/eval/` - Agent evaluation configs (`eval_config.json` with rubric-based evaluation)
- `tests/eval/evalsets/` - Evaluation datasets

**Run Commands:**
```bash
uv run pytest tests/unit           # Run unit tests
uv run pytest tests/integration    # Run integration tests
make test                          # Run both unit and integration
make eval                          # Run ADK agent evaluation
make eval-all                      # Run all evalsets
```

## Platform Requirements

**Development:**
- Python 3.10–3.13
- uv package manager
- OpenAI-compatible LLM API endpoint with API key

**Production:**
- Local development only (no deployment target configured; `deployment_target = "none"` in agent-starter-pack metadata)
- Actor services run on localhost ports 9001–9100 (deterministic hash-based port assignment)
- Director CLI runs as single process; actors spawn as subprocesses

---

*Stack analysis: 2026-04-11*
