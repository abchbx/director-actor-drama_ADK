# Architecture

**Analysis Date:** 2026-04-22

## Pattern Overview

**Overall:** Clean Architecture with MVVM (Model-View-ViewModel) using Jetpack Compose + Hilt DI

**Key Characteristics:**
- Unidirectional data flow: UI → ViewModel → Repository → API/WS → StateFlow → UI
- Single-Activity architecture with Jetpack Navigation Compose (type-safe routes)
- Global WebSocket singleton with per-screen event subscriptions
- Edge-to-edge display with manual IME inset handling
- REST API + WebSocket dual-channel: WebSocket for real-time events, REST for commands with polling fallback

## Layers

**UI Layer (Compose Screens):**
- Purpose: Declarative UI rendering, user interaction handling
- Location: `android/app/src/main/java/com/drama/app/ui/`
- Contains: Screen composables, UI state classes, one-time event sealed classes
- Depends on: ViewModel layer
- Used by: Navigation host (`DramaNavHost.kt`)

**ViewModel Layer:**
- Purpose: Business logic, state management, orchestration of repo + WS calls
- Location: `android/app/src/main/java/com/drama/app/ui/screens/*/`
- Contains: HiltViewModel classes, UiState data classes, Event sealed classes
- Depends on: Domain repository interfaces, WebSocketManager, ServerPreferences
- Used by: UI layer via `hiltViewModel()` and `collectAsStateWithLifecycle()`

**Domain Layer:**
- Purpose: Repository interfaces, domain models
- Location: `android/app/src/main/java/com/drama/app/domain/`
- Contains: Repository interfaces (`DramaRepository`, `AuthRepository`, `ServerRepository`), model classes (`Drama`, `SceneBubble`, `ActorInfo`, etc.)
- Depends on: Nothing (pure Kotlin)
- Used by: ViewModel layer

**Data Layer:**
- Purpose: Repository implementations, API services, DTOs, WebSocket management
- Location: `android/app/src/main/java/com/drama/app/data/`
- Contains: `DramaRepositoryImpl`, `DramaApiService` (Retrofit), DTOs, `WebSocketManager`
- Depends on: Domain layer (implements interfaces), Retrofit, OkHttp, kotlinx.serialization
- Used by: ViewModel layer (via Hilt DI)

## Data Flow

**Drama Creation Flow:**

1. User enters theme → `DramaCreateScreen` calls `viewModel.createDrama(theme)`
2. ViewModel starts 3 parallel operations:
   - **WebSocket connection** for STORM progress events (storm_discover, storm_research, storm_cast, scene_start)
   - **REST POST /drama/start** (blocking on backend — takes minutes for LLM STORM)
   - **Polling GET /drama/status** every 2s to detect completion
3. On completion detection (actors >0, scene≥1, or status=acting), ViewModel emits `DramaCreateEvent.NavigateToDetail(dramaId)`
4. Screen collects event → calls `onNavigateToDetail(dramaId)` → `navController.navigate(DramaDetail(dramaId))`
5. Navigation pops up to DramaList (not inclusive), so back from detail returns to list

**Drama Detail / Chat Flow:**

1. `DramaDetailViewModel.init` → `resetAllState(dramaId)` → `switchToDramaAndWait(dramaId)` (POST /drama/load)
2. After load completes: `loadInitialStatus()` + `connectWebSocket()` + `startPolling()`
3. User types message in `ChatInputBar` → `onSend(text, mention)` → `viewModel.sendChatMessage()`
4. ViewModel immediately adds `UserMessage` bubble, then calls POST /drama/chat
5. If WebSocket connected: real-time dialogue/narration events arrive as `SceneBubble.Dialogue`/`SceneBubble.Narration`
6. If WS disconnected: falls back to REST polling (`startReplyPolling()`, up to 20 attempts × 1s)

**State Management:**
- Each ViewModel owns a `MutableStateFlow<UiState>` exposed as `StateFlow`
- One-time events use `MutableSharedFlow<Event>` (Snackbar, navigation)
- No shared state between screens — each ViewModel is independent
- `WebSocketManager` is a global `@Singleton` but each ViewModel creates its own collection job

## Key Abstractions

**SceneBubble Sealed Class:**
- Purpose: Type-safe representation of all chat message types
- Examples: `android/app/src/main/java/com/drama/app/domain/model/SceneBubble.kt`
- Pattern: Sealed class hierarchy (Narration, Dialogue, UserMessage, ActorInteraction, SceneDivider)

**Navigation Routes:**
- Purpose: Type-safe navigation with serialized data classes
- Examples: `android/app/src/main/java/com/drama/app/ui/navigation/Route.kt`
- Pattern: `@Serializable` objects for parameterless routes, `@Serializable data class` for parameterized routes

**DramaRepository Interface:**
- Purpose: Clean Architecture boundary — ViewModels depend on interface, not implementation
- Examples: `android/app/src/main/java/com/drama/app/domain/repository/DramaRepository.kt`
- Pattern: Interface + `DramaRepositoryImpl` bound via Hilt `@Binds`

## Entry Points

**MainActivity:**
- Location: `android/app/src/main/java/com/drama/app/MainActivity.kt`
- Triggers: Android launcher intent
- Responsibilities: `enableEdgeToEdge()`, sets up `NavController`, `Scaffold` with bottom bar, determines `startDestination` based on server config

**DramaApplication:**
- Location: `android/app/src/main/java/com/drama/app/DramaApplication.kt`
- Triggers: Process start
- Responsibilities: Hilt application entry point (`@HiltAndroidApp` implied)

## Error Handling

**Strategy:** Result-based with user-facing Snackbar messages

**Patterns:**
- Repository methods return `Result<T>` using `runCatching { }`
- ViewModel handles `.onSuccess` / `.onFailure` with UI state updates
- Non-fatal errors update `uiState.error` field (shown inline)
- Fatal errors + user-facing messages use `_events.emit(ShowSnackbar(msg))`
- WebSocket errors update `isWsConnected = false` and trigger REST polling fallback

## Cross-Cutting Concerns

**Logging:** No structured logging framework. Uses `addLog()` in DramaCreateViewModel for UI-visible director log. No persistent app logs.

**Validation:** Input validation is minimal — theme must be non-blank, text must be non-blank for sending. No server-side error code mapping.

**Authentication:** `AuthInterceptor` adds token from `ServerPreferences` to all Retrofit requests. Token is stored in DataStore via `ServerPreferences`.

**Keyboard/IME Handling:** Dual approach:
1. `DramaDetailScreen` uses manual `WindowInsets.ime.getBottom(density)` → `.padding(bottom = imeHeightPx.toDp())` for animated keyboard following
2. `ChatInputBar` additionally applies `.imePadding()` + `.navigationBarsPadding()` directly on the input Column
3. **Note:** This creates double-padding potential — the screen applies IME padding to the whole Column, and ChatInputBar applies its own imePadding. This is a known issue area.
4. `AndroidManifest.xml` has NO `windowSoftInputMode` attribute (defaults to `adjustUnspecified`/`stateUnspecified`)
5. `enableEdgeToEdge()` is called in `MainActivity.onCreate()` — this makes the app draw behind system bars

---

*Architecture analysis: 2026-04-22*
