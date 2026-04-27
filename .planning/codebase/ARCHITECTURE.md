# Architecture

**Analysis Date:** 2026-04-26

## Pattern Overview

**Overall:** Client-Server with WebSocket real-time events + REST API fallback

**Key Characteristics:**
- Android (Kotlin/Jetpack Compose) frontend with Hilt DI, MVVM + unidirectional state flow
- Python (FastAPI) backend with ADK (Agent Development Kit) runner orchestrating AI agents
- WebSocket-first real-time communication with REST API for commands/queries and fallback
- Event-driven architecture: ADK tool calls → event_mapper → WS events → Android UI bubbles
- State hoisted in ViewModel as `MutableStateFlow<DramaDetailUiState>`

## Layers

**Android Presentation Layer:**
- Purpose: UI rendering and user interaction
- Location: `android/app/src/main/java/com/drama/app/ui/screens/`
- Contains: Composable screens, ViewModel, UI state classes
- Depends on: Domain layer (Repository interfaces), Data layer (WebSocketManager)
- Used by: End user

**Android Domain Layer:**
- Purpose: Business logic interfaces and models
- Location: `android/app/src/main/java/com/drama/app/domain/`
- Contains: Repository interfaces, domain models (Drama, SceneBubble, ActorInfo)
- Depends on: Nothing (pure Kotlin)
- Used by: Presentation layer

**Android Data Layer:**
- Purpose: API calls, WS connection, DTO mapping
- Location: `android/app/src/main/java/com/drama/app/data/`
- Contains: API service (Retrofit), Repository implementations, WS manager, DTOs
- Depends on: Domain layer (implements interfaces), external (Retrofit, OkHttp, kotlinx.serialization)
- Used by: Presentation layer via DI

**Backend API Layer:**
- Purpose: HTTP endpoints, WS broadcast, auth
- Location: `app/api/`
- Contains: FastAPI routers, Pydantic models, event_mapper, WS endpoint
- Depends on: Backend core (state_manager, tools, vector_memory)
- Used by: Android client

**Backend Core Layer:**
- Purpose: Drama state management, AI tool execution, agent orchestration
- Location: `app/` (state_manager.py, tools.py, agents/)
- Contains: State management, tool definitions, ADK agent configuration
- Depends on: Google ADK, ChromaDB, LLM providers
- Used by: Backend API layer

## Data Flow

**Real-time Drama Interaction (WS):**

1. User taps action → ViewModel calls `dramaRepository.sendChatMessage()`
2. Repository → Retrofit POST `/drama/chat` → Backend
3. Backend routes to ADK runner → tool calls execute (narrate, actor_speak, etc.)
4. `event_mapper.py` converts each ADK `function_call`/`function_response` to business events
5. Business events broadcast via WebSocket as `WsEvent(type, timestamp, data)`
6. `WebSocketManager.onMessage()` → deserializes `WsEventDto` → emits to `SharedFlow`
7. ViewModel `handleWsEvent()` → pattern-matches event type → updates `MutableStateFlow<UiState>`
8. Compose recomposes UI (bubbles, typing indicators, etc.)

**REST Fallback Flow:**

1. WS connection fails after MAX_RETRIES → `onPermanentFailure` callback
2. ViewModel switches to REST-only mode
3. Each user action still calls REST API → but must manually poll `getDramaStatus()` + `getSceneBubbles()` for updates

**Export Flow (backend only, no Android integration):**

1. Backend: `POST /drama/export` → `export_drama()` tool → `export_script()` + `export_conversations()`
2. Generates Markdown files in `{drama_folder}/exports/`
3. Returns `{status, message, export_path}` — file stays server-side
4. Android: API endpoint exists in `DramaApiService.exportDrama()` but NO Repository/ViewModel/Screen code

**State Management:**
- Single `MutableStateFlow<DramaDetailUiState>` in ViewModel
- All WS events and REST responses converge to state updates
- Compose observes state via `collectAsStateWithLifecycle()`

## Key Abstractions

**SceneBubble (sealed class):**
- Purpose: Union type for all chat-bubble renderable content
- Examples: `android/app/src/main/java/com/drama/app/domain/model/SceneBubble.kt`
- Pattern: Sealed class hierarchy — Narration, Dialogue, UserMessage, SceneDivider, ErrorBubble

**WsEventDto:**
- Purpose: Generic WS event envelope (type + timestamp + data map)
- Examples: `android/app/src/main/java/com/drama/app/data/remote/dto/WsEventDto.kt`
- Pattern: Single DTO for all 18+ event types; `type` field dispatches handling

**DramaRepository (interface):**
- Purpose: Clean architecture boundary between domain and data layers
- Examples: `android/app/src/main/java/com/drama/app/domain/repository/DramaRepository.kt`
- Pattern: Interface with DTO-returning and domain-model-returning methods

## Entry Points

**Android Activity:**
- Location: `android/app/src/main/java/com/drama/app/MainActivity.kt`
- Triggers: App launch
- Responsibilities: NavHost setup, Hilt entry point

**Backend API:**
- Location: `app/api/routers/commands.py`, `app/api/routers/queries.py`
- Triggers: HTTP requests from Android
- Responsibilities: Route to state_manager/tools, return JSON responses

**Backend WS:**
- Location: `app/api/routers/ws.py` (inferred)
- Triggers: WS connection from Android
- Responsibilities: Accept connection, broadcast mapped events, handle replay buffer

## Error Handling

**Strategy:** Layered error handling with graceful degradation

**Patterns:**
- Repository wraps all API calls in `Result<T>` (Kotlin runCatching)
- WS errors emit "error" event type → ViewModel shows error bubble + snackbar
- WS disconnection: exponential backoff reconnect → permanent failure → REST fallback
- Backend errors: `{"status": "error", "message": "..."}` in responses → event_mapper emits "error" event

## Cross-Cutting Concerns

**Logging:** Android uses `android.util.Log` with TAG constants; Python uses `logging.getLogger(__name__)`
**Validation:** Pydantic models on backend; DTO serialization on Android
**Authentication:** Token-based via query param on WS URL and header on REST

---

*Architecture analysis: 2026-04-26*
