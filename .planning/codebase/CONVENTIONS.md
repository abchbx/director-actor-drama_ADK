# Coding Conventions

**Analysis Date:** 2026-04-22

## Naming Patterns

**Files:**
- PascalCase matching the primary class/object: `DramaCreateViewModel.kt`, `ChatInputBar.kt`, `Route.kt`
- Screen files: `{Feature}Screen.kt` + `{Feature}ViewModel.kt` in same directory
- DTO files: `{Name}Dto.kt` or `{Name}ResponseDto.kt`
- Component files: `{ComponentName}.kt` in `components/` subdirectory

**Functions:**
- camelCase: `createDrama()`, `sendChatMessage()`, `loadInitialStatus()`
- Private helpers with descriptive names: `handleStormEvent()`, `tryDetectActorInteraction()`, `extractBubblesFromCommandResponse()`
- Composable functions: PascalCase: `ChatInputBar()`, `DramaEmptyState()`, `LogEntryItem()`

**Variables:**
- camelCase for properties: `uiState`, `focusRequester`, `keyboardController`
- Private mutable state with underscore prefix: `_uiState`, `_events`
- Public immutable expose: `val uiState: StateFlow`, `val events: SharedFlow`
- Constants in companion object: `POLL_INTERVAL_MS`, `MAX_CONSECUTIVE_ERRORS`, `STATUS_SETUP`
- Volatile fields annotated: `@Volatile private var navigated = false`

**Types:**
- UiState data classes: `{Feature}UiState` (e.g., `DramaCreateUiState`, `DramaDetailUiState`)
- Event sealed classes: `{Feature}Event` (e.g., `DramaCreateEvent`, `DramaDetailEvent`)
- DTO data classes: `{Name}Dto` suffix (e.g., `ChatRequestDto`, `DramaStatusResponseDto`)
- Domain models: Plain names (e.g., `Drama`, `ActorInfo`, `SceneBubble`)

## Code Style

**Formatting:**
- No Prettier/Ktlint config detected — follows Kotlin standard style
- 4-space indentation
- Trailing commas in parameter lists

**Linting:**
- No linting config detected (no .editorconfig, no detekt, no ktlint)
- Android Lint via Gradle (default rules)

## Import Organization

**Order:**
1. AndroidX / Jetpack imports (`androidx.compose.*`, `androidx.lifecycle.*`)
2. Kotlin standard library (`kotlinx.coroutines.*`, `kotlinx.serialization.*`)
3. Third-party (`dagger.*`, `okhttp3.*`, `retrofit2.*`)
4. Project imports (`com.drama.app.*`)

**Path Aliases:**
- None used — all imports are fully qualified

## Error Handling

**Patterns:**
- Repository methods return `Result<T>` via `runCatching { }`:
  ```kotlin
  override suspend fun startDrama(theme: String): Result<CommandResponseDto> =
      runCatching { dramaApiService.startDrama(StartDramaRequestDto(theme)) }
  ```
- ViewModel handles success/failure explicitly:
  ```kotlin
  dramaRepository.startDrama(theme)
      .onSuccess { /* update state */ }
      .onFailure { e -> /* show error */ }
  ```
- WebSocket errors caught via `.catch { }` on Flow:
  ```kotlin
  webSocketManager.connect(...)
      .catch { e -> _uiState.update { it.copy(isWsConnected = false, error = e.message) } }
      .collect { event -> handleWsEvent(event) }
  ```
- User-facing errors via Snackbar events:
  ```kotlin
  _events.emit(DramaDetailEvent.ShowSnackbar("发送失败：${e.message}"))
  ```

## Logging

**Framework:** No logging framework — console/Logcat only

**Patterns:**
- OkHttp `HttpLoggingInterceptor` at `Level.BODY` for network debugging
- `addLog()` in DramaCreateViewModel for UI-visible "Director Log" panel
- No structured logging, no crash reporting

## Comments

**When to Comment:**
- Bug fix explanations with ★ markers: `// ★★★ 关键修复：...★★★`
- Architecture decisions with D-XX references (design doc cross-references): `// D-14/D-15: 首次启动检测`
- Complex logic explanations: `// 不需要"主题匹配"防御 — 旧数据天然不满足导航条件`
- Chinese comments are common (bilingual codebase)

**JSDoc/TSDoc:**
- KDoc used sparingly, mainly for public ViewModel methods and sealed class docs
- Example: `/** 切换服务端活跃剧本上下文 — 同步等待版本（带超时） */`

## Function Design

**Size:** ViewModel methods can be long (100+ lines for `handlePollResponse`, `handleWsEvent`). Screen composables are moderate (50-150 lines). Component composables are focused (20-80 lines).

**Parameters:** Use default values for optional params: `modifier: Modifier = Modifier`, `saveName: String = ""`

**Return Values:** ViewModel methods return Unit (update StateFlow). Repository methods return `Result<T>`.

## Module Design

**Exports:** Each public class/interface is in its own file. No barrel/index files.

**Barrel Files:** Not used — direct imports by full path.

## Architecture Patterns

**Unidirectional Data Flow:**
```
UI Event → ViewModel method → Repository call → State update → UI recomposition
```

**One-time Events:** Use `SharedFlow<Event>` collected in `LaunchedEffect`:
```kotlin
LaunchedEffect(Unit) {
    viewModel.events.collect { event ->
        when (event) {
            is DramaCreateEvent.NavigateToDetail -> onNavigateToDetail(event.dramaId)
        }
    }
}
```

**Navigation:** Type-safe routes with `@Serializable` objects/data classes, passed to `navController.navigate()`

**DI:** Hilt with `@AndroidEntryPoint` on Activity, `@HiltViewModel` on ViewModels, `@Inject constructor()` on repositories

---

*Convention analysis: 2026-04-22*
