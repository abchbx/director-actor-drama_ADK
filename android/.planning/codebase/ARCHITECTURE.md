# Architecture

**Analysis Date:** 2026-04-25

## Pattern Overview

**Overall:** Clean Architecture with MVVM (Model-ViewModel-View)

**Key Characteristics:**
- Unidirectional data flow: ViewModel emits `StateFlow<UiState>` → Compose UI collects and renders
- Sealed class hierarchy for message types (`SceneBubble`) enables exhaustive `when` dispatch
- Dual data source strategy: WebSocket (primary) + REST polling (fallback/degradation)
- Repository layer maps DTOs → domain models, encapsulating business logic (bubble mapping, cast merging)
- Single Activity, Compose Navigation with type-safe routes (`@Serializable` objects/data classes)

## Layers

**UI Layer (Compose Screens + ViewModels):**
- Purpose: Render UI state and handle user interactions
- Location: `app/src/main/java/com/drama/app/ui/`
- Contains: Screen composables, ViewModels, UI state classes, event sealed classes
- Depends on: Domain layer (models, repositories, use cases), Data layer (ConnectionState)
- Used by: Nothing — this is the top layer

**Domain Layer (Models + Repository Interfaces + Use Cases):**
- Purpose: Define business models and contracts
- Location: `app/src/main/java/com/drama/app/domain/`
- Contains: `SceneBubble` sealed class, `ActorInfo`, `CommandType`, repository interfaces, `DetectActorInteractionUseCase`
- Depends on: Nothing (pure Kotlin)
- Used by: UI layer, Data layer (implements interfaces)

**Data Layer (Repository Implementations + Remote/Local Data Sources):**
- Purpose: Implement repository interfaces, manage API calls and local storage
- Location: `app/src/main/java/com/drama/app/data/`
- Contains: `DramaRepositoryImpl`, DTOs, `WebSocketManager`, `DramaSaveRepository`, API services
- Depends on: Domain layer (implements interfaces), external libs (Retrofit, OkHttp, DataStore)
- Used by: UI layer (via DI)

**DI Layer (Hilt Modules):**
- Purpose: Provide dependency injection bindings
- Location: `app/src/main/java/com/drama/app/di/`
- Contains: `NetworkModule`, `DramaModule`, `DataStoreModule`, `SavesDataStore`
- Depends on: Data + Domain layers

## Data Flow

**Chat Message Flow (WebSocket path — primary):**

1. User types message in `ChatInputBar` → calls `viewModel.sendChatMessage(text, mention)`
2. ViewModel appends `SceneBubble.UserMessage` to `bubbles` list immediately (optimistic)
3. ViewModel calls `dramaRepository.sendChatMessageAsBubbles(text, mention)` (REST POST)
4. REST response bubbles are **discarded** when WS is connected (WS is the single source of truth)
5. Server processes via ADK Runner → `event_mapper.py` maps tool calls to business events
6. WebSocket pushes `WsEventDto` events (narration, dialogue, actor_chime_in, etc.)
7. `WebSocketManager.events` Flow emits events → `handleWsEvent()` in ViewModel
8. Each event type creates the appropriate `SceneBubble` subclass and appends to state

**Chat Message Flow (REST fallback path — WS disconnected):**

1. Same steps 1-3 as above
2. REST response bubbles are **used** when WS is disconnected
3. If REST response is empty, `startReplyPolling()` begins polling `getDramaStatus()` + `getSceneBubbles()`
4. Polling continues for up to 20 attempts (1s interval) until new data appears

**WS Event → Bubble Mapping:**

| WS Event Type | Bubble Created | Notes |
|---|---|---|
| `narration` (text non-empty) | `SceneBubble.Narration` | Call phase (text empty) → typing indicator only |
| `dialogue` (text non-empty) | `SceneBubble.Dialogue` or `ActorInteraction` | `DetectActorInteractionUseCase` decides |
| `actor_chime_in` (text non-empty) | `SceneBubble.Dialogue` or `ActorInteraction` | Same detection logic |
| `end_narration` | `SceneBubble.Narration` | Drama ending narration |
| `scene_end` | `SceneBubble.SceneDivider` | Shows "第 N 场 · 标题" |
| `tension_update` | Updates `tensionScore` in UiState | No bubble |
| `typing` | Updates `isTyping` + `typingText` | No bubble |
| `error` | `SceneBubble.SystemError` + snackbar | Inline error + toast |
| `director_log` | Updates `stormPhase` | Progress display, no bubble |
| `command_echo` | Updates `stormPhase` | Confirmation only |
| `user_message` | `SceneBubble.UserMessage` (deduped) | Backup channel |

**State Management:**
- `MutableStateFlow<DramaDetailUiState>` in ViewModel — single source of truth
- Compose UI collects via `collectAsStateWithLifecycle()`
- No shared ViewModel state across screens — each screen has its own ViewModel

## Key Abstractions

**SceneBubble (sealed class):**
- Purpose: Represents all renderable message types in the chat interface
- Examples: `app/src/main/java/com/drama/app/domain/model/SceneBubble.kt`
- Pattern: Type-safe discriminated union with `when` exhaustive matching
- Subtypes: `Narration`, `Dialogue`, `UserMessage`, `ActorInteraction`, `SceneDivider`, `SystemError`
- Each subtype carries: `id`, `avatarType`, `senderType`, `senderName` — enabling the three-party messaging system (director/actor/user)

**ConnectionState (sealed class):**
- Purpose: Represent WebSocket connection lifecycle states
- Examples: `app/src/main/java/com/drama/app/data/remote/ws/ConnectionState.kt`
- Pattern: State machine: `Disconnected → Connecting → Connected`, `Connected → Reconnecting → Connected`

**CommandType (enum):**
- Purpose: Parse user input into command types for routing
- Examples: `app/src/main/java/com/drama/app/domain/model/CommandType.kt`
- Pattern: Prefix matching (`/next`, `/action`, `/speak`, etc.) with `FREE_TEXT` as default

## Entry Points

**MainActivity:**
- Location: `app/src/main/java/com/drama/app/MainActivity.kt`
- Triggers: Android launcher
- Responsibilities: Sets up `DramaTheme`, `NavController`, `DramaNavHost`, bottom navigation bar

**DramaDetailScreen:**
- Location: `app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailScreen.kt`
- Triggers: Navigation from DramaList or DramaCreate
- Responsibilities: Orchestrates the drama chat interface — bubble list, input bar, actor drawer, connection status

## Error Handling

**Strategy:** Multi-layer error handling with graceful degradation

**Patterns:**
- **Inline error bubbles:** Server errors become `SceneBubble.SystemError` displayed in the chat flow
- **Snackbar events:** User-facing errors emit `DramaDetailEvent.ShowSnackbar` via SharedFlow
- **WS degradation:** On permanent WS failure, app falls back to REST polling with banner notification
- **Init error blocking:** If `switchToDramaAndWait()` fails during init, `initError` blocks the UI with retry button
- **Deduplication:** `addedErrorIds` set prevents the same error message from creating duplicate bubbles

## Cross-Cutting Concerns

**Logging:** Android `Log` with TAG constants (e.g., `TAG = "DramaDetailViewModel"`)

**Validation:** Input validation in ViewModel (`text.isBlank()` checks before sending)

**Authentication:** Token-based via `AuthInterceptor`, stored in `SecureStorage`, passed through `ServerConfig.token`

**Local Saves:** DataStore-based local save/load system (independent of server saves), with `/save`, `/load`, `/list`, `/delete` commands handled entirely client-side

---

*Architecture analysis: 2026-04-25*
