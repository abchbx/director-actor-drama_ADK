# Architecture

**Analysis Date:** 2026-04-24

## Pattern Overview

**Overall:** Clean Architecture with MVVM (Model-View-ViewModel)

**Key Characteristics:**
- Unidirectional Data Flow: UI → ViewModel → Repository → API/WS → StateFlow → UI
- Dual real-time strategy: WebSocket primary + REST polling fallback
- Domain layer with repository interfaces (dependency inversion)
- Hilt dependency injection throughout all layers
- Jetpack Compose declarative UI with state hoisting

## Layers

**UI Layer (Presentation):**
- Purpose: Render UI state and capture user intent
- Location: `app/src/main/java/com/drama/app/ui/`
- Contains: Composable screens, ViewModels, UI state classes, navigation
- Depends on: Domain layer (repository interfaces, models, use cases)
- Used by: Android framework (Activity)

**Domain Layer:**
- Purpose: Define business models, repository contracts, and use cases
- Location: `app/src/main/java/com/drama/app/domain/`
- Contains: Model classes (sealed classes, enums), repository interfaces, use case classes
- Depends on: Nothing (pure Kotlin)
- Used by: UI layer (ViewModels), Data layer (implementations)

**Data Layer:**
- Purpose: Implement repository interfaces, manage API/WS/network concerns
- Location: `app/src/main/java/com/drama/app/data/`
- Contains: Repository implementations, API service interfaces, DTOs, WebSocket manager, interceptors, local storage
- Depends on: Domain layer (repository interfaces), external libraries (Retrofit, OkHttp, DataStore)
- Used by: UI layer (via Hilt-injected repository interfaces)

**DI Layer:**
- Purpose: Wire dependencies via Hilt modules
- Location: `app/src/main/java/com/drama/app/di/`
- Contains: Hilt modules (NetworkModule, DataStoreModule, DramaModule)
- Depends on: All layers
- Used by: Hilt runtime

## Data Flow

**Script Creation Flow ("开始创作"):**

1. User types theme in `DramaCreateScreen` and taps "开始创作" button
2. `DramaCreateViewModel.createDrama(theme)` invoked
3. Three parallel operations launch:
   - WebSocket connects via `WebSocketManager.connect()` → receives STORM progress events
   - REST API call `dramaRepository.startDrama(theme)` → POST `/drama/start` (blocking, minutes-long)
   - Polling loop starts: GET `/drama/status` every 2s (or 10s when WS active)
4. Timer starts tracking elapsed seconds
5. WS events (`storm_discover`, `storm_research`, `storm_outline`, `storm_cast`, `director_log`) update progress UI
6. Polling checks theme match and completion conditions (has_outline, actors ready, scene started, acting status)
7. On completion: `navigateToDetail()` emits event → UI navigates to `DramaDetailScreen`
8. Before navigation: WS disconnected, all jobs cancelled, resources cleaned up

**Chat/Conversation Flow:**

1. User types message in `ChatInputBar` (with optional @mention)
2. `DramaDetailViewModel.sendChatMessage(text, mention)` invoked
3. User message bubble immediately added to UI state
4. REST API call `dramaRepository.sendChatMessageAsBubbles(text, mention)` → POST `/drama/chat`
5. If response contains bubbles, they're appended to state
6. If response empty (WS will deliver events), reply polling starts as fallback
7. WS events (`dialogue`, `narration`, `actor_chime_in`, `tool_result`, `scene_end`) append bubbles in real-time
8. `DetectActorInteractionUseCase` determines if consecutive actor dialogues should render as `ActorInteraction` bubbles

**Connection Flow:**

1. App launch → `MainActivity` checks `ServerRepository.serverConfig` Flow
2. If null → `ConnectionGuide` route shown (first-time setup)
3. User enters IP:port or cloud URL → `ConnectionViewModel.connect()` → `AuthRepository.verifyServer()`
4. Temp Retrofit instance hits GET `/auth/verify` → returns bypass/require_token
5. If bypass → save config to DataStore → navigate to `DramaList`
6. If require_token → show token input → save with config → navigate

**State Management:**
- Each ViewModel holds a `MutableStateFlow<UiState>` exposed as `StateFlow<UiState>`
- UI collects via `collectAsStateWithLifecycle()`
- One-time events use `SharedFlow<SealedEvent>` (navigation, snackbars)
- No shared global state — each screen owns its own ViewModel

## Key Abstractions

**SceneBubble (sealed class):**
- Purpose: Represents all message types in the chat/conversation UI
- Examples: `app/src/main/java/com/drama/app/domain/model/SceneBubble.kt`
- Pattern: Sealed class hierarchy with 5 subtypes: Narration, Dialogue, UserMessage, ActorInteraction, SceneDivider
- Each subtype has an `id: String` for LazyColumn keys

**DramaRepository (interface):**
- Purpose: Abstraction over backend API, enables testing and implementation swapping
- Examples: `app/src/main/java/com/drama/app/domain/repository/DramaRepository.kt`
- Pattern: Interface in domain layer, implementation in data layer via `DramaRepositoryImpl`
- Two tiers of methods: DTO-level (return raw DTOs) and domain-level (return `SceneBubble`, `ActorInfo`)

**WebSocketManager:**
- Purpose: Manage persistent WebSocket connection with auto-reconnect and REST fallback
- Examples: `app/src/main/java/com/drama/app/data/remote/ws/WebSocketManager.kt`
- Pattern: Singleton (Hilt), exposes `events: Flow<WsEventDto>` and `connectionState: StateFlow<Boolean>`
- Features: exponential backoff reconnect, ConnectivityManager NetworkCallback, generation counter for stale callbacks, replay message support, permanent failure degradation

**CommandType (enum):**
- Purpose: Parse user input to determine which drama command to send
- Examples: `app/src/main/java/com/drama/app/domain/model/CommandType.kt`
- Pattern: Enum with `fromInput()` factory, maps `/next`, `/action`, `/speak`, `/end` prefixes

## Entry Points

**MainActivity:**
- Location: `app/src/main/java/com/drama/app/MainActivity.kt`
- Triggers: Android framework (launcher activity)
- Responsibilities: Sets up `DramaApp` composable, determines start destination based on saved server config

**DramaApplication:**
- Location: `app/src/main/java/com/drama/app/DramaApplication.kt`
- Triggers: Android framework (application start)
- Responsibilities: `@HiltAndroidApp` annotation triggers Hilt code generation

**DramaNavHost:**
- Location: `app/src/main/java/com/drama/app/ui/navigation/DramaNavHost.kt`
- Triggers: Compose recomposition from `DramaApp`
- Responsibilities: Defines navigation graph with 5 routes, wires screens to navController

## Error Handling

**Strategy:** Result-based with graceful degradation

**Patterns:**
- Repository methods return `Result<T>` (Kotlin stdlib), catching all exceptions
- `NetworkExceptionInterceptor` catches OkHttp-level network errors and converts to HTTP error responses (504 timeout, 503 unreachable) so Retrofit doesn't throw
- `AuthRepositoryImpl` maps specific exceptions to domain error types (`TIMEOUT`, `NETWORK_UNREACHABLE`, `AUTH_FAILED`)
- WebSocket failures trigger exponential backoff reconnect; after 5 consecutive failures, `onPermanentFailure` callback degrades to REST-only mode
- UI shows `ConnectionBanner` when WS is disconnected and not reconnecting
- `DramaDetailScreen` shows init error with retry button when `switchToDrama` fails

## Cross-Cutting Concerns

**Logging:** Android `Log` with TAG constants; OkHttp `HttpLoggingInterceptor` with `Authorization` header redacted

**Validation:** Input validated in UI (theme blank check, command prefix parsing); backend validates via HTTP status codes

**Authentication:** Token-based via `AuthInterceptor` (injects `Authorization: Bearer` header from `SecureStorage`); token stored encrypted via `EncryptedSharedPreferences`; WebSocket passes token as query parameter

**Threading:** Coroutines throughout (`viewModelScope.launch`); WebSocket callbacks use `Dispatchers.IO` via `SupervisorJob` scope; Flow collection on Main for UI updates
