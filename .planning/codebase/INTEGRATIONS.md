# External Integrations

**Analysis Date:** 2026-04-25

## APIs & External Services

**LLM Provider:**
- OpenAI-compatible API - All AI generation (narration, dialogue, STORM)
  - SDK/Client: `google.adk.models.lite_llm.LiteLlm`
  - Auth: `OPENAI_API_KEY` + `OPENAI_BASE_URL` env vars
  - Model: Configured via `MODEL_NAME` env var (default: "openai/claude-sonnet-4-6")

## Data Storage

**Databases:**
- ChromaDB - Vector memory for actors (Tier 4 semantic retrieval)
  - Connection: Local embedded instance per drama theme
  - Client: `app/vector_memory.py` → `get_vector_store()`
  - Collections: Per-actor memory collections

**File Storage:**
- Local filesystem - All drama state, scenes, exports
  - Base path: `app/dramas/<sanitized_theme>/`
  - Structure: `state.json`, `actors/`, `scenes/`, `conversations/`, `exports/`
  - Atomic writes via tempfile + os.replace

**Caching:**
- InMemorySessionService (ADK) - Session state cache
  - Not distributed — single-process only
  - Persisted to filesystem via debounced writes

## Authentication & Identity

**Auth Provider:**
- Custom token-based (optional)
  - Implementation: `API_TOKEN` env var → Bearer token check or query param
  - Empty/missing token = auth disabled (dev mode)
  - Files: `app/api/deps.py` (require_auth), `app/api/routers/websocket.py` (_validate_ws_token)

## Monitoring & Observability

**Error Tracking:**
- None (standard Python logging only)

**Logs:**
- Python `logging` module — `[DIRECTOR-LOG]` prefix for lifecycle messages
- Android `Log.d/e/w` with TAG constants per class

## CI/CD & Deployment

**Hosting:**
- Local/self-hosted (uvicorn ASGI server)

**CI Pipeline:**
- None detected

## Environment Configuration

**Required env vars:**
- `OPENAI_API_KEY` - LLM authentication
- `OPENAI_BASE_URL` - LLM endpoint URL
- `MODEL_NAME` - LLM model identifier

**Optional env vars:**
- `API_TOKEN` - API/WS authentication token

**Secrets location:**
- `app/.env` file (NOT committed, contains API keys)
- `app/.env.example` template (committed, safe to read)

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- A2A protocol calls to actor services (localhost, per-actor ports starting at 9001)

## Inter-Process Communication

**A2A (Actor-to-Actor):**
- Each actor runs as a separate uvicorn process on its own port
- Communication via A2A SDK (ClientFactory, AgentCard)
- Actor card files: `app/actors/actor_<name>_card.json`
- Director calls actors via `a2a.client.ClientFactory` with `RemoteA2aAgent`

---

*Integration audit: 2026-04-25*
