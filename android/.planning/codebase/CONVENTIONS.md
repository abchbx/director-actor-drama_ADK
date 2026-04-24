# Coding Conventions

**Analysis Date:** 2026-04-24

## Naming Patterns

**Files:**
- Screen composables: `{Feature}Screen.kt` — e.g., `DramaCreateScreen.kt`
- ViewModels: `{Feature}ViewModel.kt` — e.g., `DramaCreateViewModel.kt`
- DTOs: `{Entity}Dto.kt` or `{Entity}{Action}Dto.kt` — e.g., `WsEventDto.kt`, `StartDramaRequestDto`
- Repository interfaces: `{Entity}Repository.kt`
- Repository implementations: `{Entity}RepositoryImpl.kt`
- API services: `{Entity}ApiService.kt`
- DI modules: `{Concern}Module.kt` — e.g., `NetworkModule.kt`
- Use cases: `{Verb}{Noun}UseCase.kt` — e.g., `DetectActorInteractionUseCase.kt`
- Domain models: `{Noun}.kt` — e.g., `SceneBubble.kt`, `CommandType.kt`

**Functions:**
- ViewModel public methods: camelCase, verb-first — `createDrama()`, `sendChatMessage()`, `connectWebSocket()`
- Repository methods: camelCase, verb-first — `startDrama()`, `listDramas()`, `getSceneBubbles()`
- Composable functions: PascalCase — `DramaCreateScreen()`, `ChatInputBar()`, `MentionChip()`
- Private helpers: camelCase — `handleStormEvent()`, `addLog()`, `normalizeLineBreaks()`

**Variables:**
- StateFlow: underscore prefix for private mutable — `_uiState`, `_events`
- Public immutable: no prefix — `uiState`, `events`
- Local variables: camelCase — `navTarget`, `isThemeMatch`, `currentDelayMs`
- Constants: SCREAMING_SNAKE_CASE — `POLL_INTERVAL_MS`, `MAX_CONSECUTIVE_ERRORS`, `TAG`

**Types:**
- UI State: `{Feature}UiState` data class — e.g., `DramaCreateUiState`, `DramaDetailUiState`
- Events: `{Feature}Event` sealed class — e.g., `DramaCreateEvent`, `DramaDetailEvent`
- DTOs: `{Name}Dto` suffix — e.g., `WsEventDto`, `CommandResponseDto`
- Domain models: No suffix — e.g., `SceneBubble`, `Drama`, `ActorInfo`

## Code Style

**Formatting:**
- No Prettier/Ktlint config detected
- Kotlin standard formatting (4-space indent, trailing commas)
- Compose functions with `Modifier` as first optional parameter

**Linting:**
- No dedicated lint config detected (relies on Android Studio defaults)
- Comment annotations: `★` for important fixes/notes, `D-XX` for design spec references

## Import Organization

**Order:**
1. Android framework (`android.*`, `androidx.*`)
2. Third-party libraries (`okhttp3.*`, `retrofit2.*`, `dagger.*`, `kotlinx.*`)
3. Project imports (`com.drama.app.*`)

**Path Aliases:**
- None (full package paths used)

## Error Handling

**Patterns:**
- Repository methods return `Result<T>` using `runCatching { }` — all exceptions caught
- `NetworkExceptionInterceptor` converts OkHttp exceptions to HTTP error responses (prevents Retrofit crashes)
- `AuthRepositoryImpl` maps exceptions to domain-specific error strings (`"TIMEOUT"`, `"NETWORK_UNREACHABLE"`)
- WebSocket failures: exponential backoff reconnect, then REST degradation after threshold
- ViewModel error state: `error: String?` field in UiState, shown in UI with dismiss/retry

**Anti-patterns to avoid:**
- Do NOT throw exceptions from Repository methods — always return `Result`
- Do NOT let network exceptions propagate uncaught — `NetworkExceptionInterceptor` handles them

## Logging

**Framework:** Android `android.util.Log`

**Patterns:**
- Each class defines `companion object { private const val TAG = "ClassName" }`
- `Log.d()` for debug, `Log.i()` for info, `Log.w()` for warnings, `Log.e()` for errors with stack traces
- OkHttp logging at `BODY` level with `Authorization` header redacted
- Never log tokens or secrets

## Comments

**When to Comment:**
- Bug fixes: `★ 修复：` prefix explaining what was wrong and why the fix works
- Design spec references: `D-XX` prefix linking to requirement IDs (e.g., `D-14`, `APP-14`)
- Architecture decisions: Explain "why" not "what"
- Pitfall documentation: `Pitfall N:` prefix for known gotchas

**JSDoc/TSDoc:**
- KDoc used sparingly, mainly on public domain model classes and key ViewModel methods
- Most documentation is inline comments (Chinese) explaining business logic

## Function Design

**Size:** ViewModel methods can be 50-80 lines; repository mapping methods 20-40 lines; composable functions 20-60 lines

**Parameters:** ViewModel methods take minimal params (user input strings); composable functions follow Compose conventions (state + callbacks)

**Return Values:** Repository returns `Result<T>`; ViewModel updates StateFlow; Composables are Unit

## Module Design

**Exports:** Each public class/interface is in its own file; no barrel files

**Barrel Files:** Not used — direct imports from specific files

## State Management Pattern

**ViewModel:**
```kotlin
private val _uiState = MutableStateFlow(FeatureUiState())
val uiState: StateFlow<FeatureUiState> = _uiState.asStateFlow()

private val _events = MutableSharedFlow<FeatureEvent>()
val events: SharedFlow<FeatureEvent> = _events.asSharedFlow()
```

**UI Collection:**
```kotlin
val uiState by viewModel.uiState.collectAsStateWithLifecycle()
```

**State Updates:**
```kotlin
_uiState.update { it.copy(field = newValue) }
```

**One-time Events:**
```kotlin
viewModelScope.launch { _events.emit(FeatureEvent.NavigateToDetail(id)) }
```

**Event Collection in UI:**
```kotlin
LaunchedEffect(Unit) {
    viewModel.events.collect { event ->
        when (event) {
            is FeatureEvent.NavigateToDetail -> onNavigateToDetail(event.dramaId)
        }
    }
}
```

## Compose Patterns

**Screen signature:**
```kotlin
@Composable
fun FeatureScreen(
    onNavigateSomewhere: (String) -> Unit = {},
    viewModel: FeatureViewModel = hiltViewModel(),
)
```

**Hilt ViewModel injection:** Always use `hiltViewModel()` default parameter

**Navigation:** Type-safe routes with `@Serializable` objects/data classes in `Route.kt`

## Chinese/English Convention

- UI text: Chinese (e.g., "开始创作", "戏剧", "设置")
- Code identifiers: English (e.g., `createDrama`, `DramaListScreen`)
- Comments: Mix of Chinese (business logic) and English (technical notes)
- Design spec references: `D-XX` format

---

*Convention analysis: 2026-04-24*
