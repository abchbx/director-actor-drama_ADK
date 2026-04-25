# Technology Stack

**Analysis Date:** 2026-04-25

## Languages

**Primary:**
- Python 3.11+ - Backend agent system, FastAPI API, tools, state management

**Secondary:**
- Kotlin - Android client (Jetpack Compose)

## Runtime

**Environment:**
- Python 3.11+ (backend)
- Android API 26+ / Kotlin JVM (client)
- Node.js not used

**Package Manager:**
- uv (Python) — lockfile: `uv.lock` (present)
- Gradle Kotlin DSL (Android) — version catalog: `libs.versions.toml`

## Frameworks

**Core:**
- Google ADK (Agent Development Kit) - Agent orchestration, Runner, A2A, session management
- FastAPI 2.0+ - REST API + WebSocket endpoints
- LiteLlm (ADK) - OpenAI-compatible LLM interface (supports Claude, GPT, etc.)

**Android:**
- Jetpack Compose - Declarative UI framework
- Hilt - Dependency injection
- Kotlin Coroutines + Flow - Async/reactive programming
- Retrofit + OkHttp - HTTP client
- kotlinx.serialization - JSON serialization (replaces Gson/Moshi)

**Testing:**
- pytest (Python) - Backend test runner
- Not detected: Android instrumented tests

**Build/Dev:**
- uvicorn - ASGI server with WatchFiles hot-reload
- Makefile - Dev command shortcuts (run, test, lint)

## Key Dependencies

**Critical:**
- google-adk - Agent framework (Runner, BaseAgent, Agent, A2A, SessionService)
- a2a-sdk - Agent-to-Agent protocol (ClientFactory, AgentCard, Message, Part)
- httpx - Async HTTP client for A2A calls
- pydantic v2 - Request/response validation, JSON schema
- chromadb - Vector memory storage (Tier 4 semantic retrieval)

**Infrastructure:**
- python-dotenv - Environment variable loading
- fastapi - Web framework (REST + WebSocket)
- uvicorn - ASGI server

**Android Critical:**
- OkHttp - WebSocket client + HTTP
- Retrofit - REST API client
- Compose Material3 - UI components
- DataStore - Local persistence (saves, preferences)

## Configuration

**Environment:**
- `OPENAI_API_KEY` - LLM API key (required)
- `OPENAI_BASE_URL` - LLM API base URL (for OpenAI-compatible endpoints)
- `MODEL_NAME` - LLM model identifier (default: "openai/claude-sonnet-4-6")
- `API_TOKEN` - Optional auth token for API/WS access (empty = auth disabled)

**Build:**
- `pyproject.toml` - Python project config + dependencies
- `android/app/build.gradle.kts` - Android build config
- `android/gradle/libs.versions.toml` - Version catalog

## Platform Requirements

**Development:**
- Python 3.11+ with uv
- Android Studio (for Android client)
- LLM API access (OpenAI-compatible endpoint)

**Production:**
- Python ASGI server (uvicorn)
- Network accessible by Android clients
- ChromaDB for vector memory (optional, degrades gracefully)

---

*Stack analysis: 2026-04-25*
