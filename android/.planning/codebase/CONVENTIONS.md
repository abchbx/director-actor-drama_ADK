# Coding Conventions

**Analysis Date:** 2026-04-25

## Naming Patterns

**Files:**
- PascalCase matching class/object name: `DramaDetailViewModel.kt`, `SceneBubble.kt`, `WebSocketManager.kt`
- Suffix conventions:
  - `*Dto.kt` — Data Transfer Objects (network layer)
  - `*Repository.kt` — Repository interfaces and implementations
  - `*Screen.kt` — Compose screen composables
  - `*ViewModel.kt` — ViewModel classes
  - `*Bubble.kt` — Chat bubble composables
  - `*Bar.kt` — Input bar composables
  - `*Indicator.kt` — Status/progress indicators
  - `*Module.kt` — Hilt DI modules
  - `*Interceptor.kt` — OkHttp interceptors
  - `*UseCase.kt` — Domain use cases

**Functions:**
- camelCase: `sendChatMessage()`, `handleWsEvent()`, `loadSceneBubbles()`
- Private helper prefix with underscore conceptually: `_extract_call_data` (backend Python)
- Composable functions are PascalCase: `DialogueBubble()`, `SceneBubbleList()`, `TypingIndicator()`
- Boolean getters use `is` prefix: `isWsConnected`, `isReconnecting`, `isTyping`, `isProcessing`

**Variables:**
- camelCase: `bubbleCounter`, `lastKnownScene`, `activeDramaId`
- Private MutableStateFlow prefixed with underscore: `_uiState`, `_events`
- Public StateFlow without underscore: `uiState`, `events`
- Constants: `SCREAMING_SNAKE_CASE` in companion object: `TAG`, `TYPING_ROW_HEIGHT`
- DTO fields: snake_case matching JSON: `current_scene`, `actor_name`, `tension_score`

**Types:**
- Sealed class for type hierarchies: `SceneBubble`, `ConnectionState`, `DramaDetailEvent`
- Enum classes for fixed sets: `CommandType`, `InteractionType`, `SenderType`, `AvatarType`
- Data classes for state and DTOs: `DramaDetailUiState`, `WsEventDto`, `ChatRequestDto`
- `@Serializable` annotation on all DTOs and sealed class subtypes
- `@SerialName("snake_case")` for sealed class polymorphic serialization

## Code Style

**Formatting:**
- Kotlin standard formatting (4-space indent)
- Trailing commas in parameter lists
- Consistent use of `Modifier.` chain pattern in Compose

**Linting:**
- Not detected — no `.eslintrc`, `detekt.yml`, or `ktlint` config found

## Import Organization

**Order:**
1. Android framework (`android.*`, `androidx.*`)
2. Third-party libraries (`dagger.*`, `kotlinx.*`, `okhttp3.*`)
3. Project imports (`com.drama.app.*`)

**Path Aliases:**
- None used

## Error Handling

**Patterns:**
- `Result<T>` from Kotlin stdlib for repository return types: `suspend fun getDramaStatus(): Result<DramaStatusResponseDto>`
- `.onSuccess { }` / `.onFailure { }` chaining for result handling
- Inline error bubbles via `SceneBubble.SystemError` for server errors in chat
- `SharedFlow<DramaDetailEvent>` for one-time UI events (snackbars)
- Error deduplication via `addedErrorIds` set to prevent duplicate error bubbles
- WS permanent failure degrades to REST polling with user-visible banner

## Logging

**Framework:** Android `android.util.Log`

**Patterns:**
- TAG defined in companion object: `companion object { private const val TAG = "DramaDetailViewModel" }`
- `Log.i()` for info, `Log.w()` for warnings
- Sparse logging — only in ViewModel and WebSocketManager

## Comments

**When to Comment:**
- ★ markers for important design decisions and fixes: `// ★ 核心修复：...`
- Section headers with `// ============================================================` dividers
- KDoc on public APIs (inconsistent — mostly on key functions)

**JSDoc/TSDoc:**
- KDoc used selectively on important classes and functions
- Chinese comments for business logic explanations
- `@Serializable` and `@SerialName` annotations serve as implicit documentation for DTOs

## Function Design

**Size:** ViewModel methods range from 5 to 50 lines; `handleWsEvent()` is the largest at ~240 lines

**Parameters:** Named parameters with default values are standard pattern:
```kotlin
fun SceneBubbleList(
    bubbles: List<SceneBubble>,
    isTyping: Boolean,
    typingText: String = "AI 正在思考...",
    modifier: Modifier = Modifier,
)
```

**Return Values:**
- Repository methods return `Result<T>`
- ViewModel methods return Unit (update `_uiState` as side effect)
- Composable functions return Unit

## Module Design

**Exports:**
- Each screen exports a `*Screen` composable (public API)
- ViewModel exposed via `uiState: StateFlow` and action methods (`sendCommand`, `sendChatMessage`, etc.)
- Repository interfaces define public contracts; implementations are internal

**Barrel Files:**
- Not used — imports reference specific files directly

## Compose Patterns

**State Hoisting:**
- UI state hoisted to ViewModel via `StateFlow<UiState>`
- Local UI state (menu expanded, input text) uses `remember`/`rememberSaveable`

**Side Effects:**
- `LaunchedEffect` for collecting flows and responding to state changes
- `DisposableEffect` for WS lifecycle (connect on enter, disconnect on leave)
- `SharedFlow` for one-time events (snackbars) — prevents re-consumption on recomposition

**Animation:**
- `AnimatedVisibility` for enter/exit transitions on bubbles
- `rememberInfiniteTransition` for pulsing/typing indicators
- Consistent easing: `FastOutSlowInEasing` for enter, `LinearOutSlowInEasing` for exit

---

*Convention analysis: 2026-04-25*
