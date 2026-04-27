# Codebase Concerns

**Analysis Date:** 2026-04-26

## Tech Debt

**DramaDetailViewModel — God Object (1665 lines):**
- Issue: Single ViewModel handles 10+ distinct responsibilities: init sync, WebSocket lifecycle, REST polling, WS event handling (15+ event types), scene bubble loading, scene history, save/load, actor panel, status refresh, reconnection merge, command sending, chat messaging, reply polling, export. This makes the class extremely difficult to test, modify, or reason about.
- Files: `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt`
- Impact: Any change to any feature risks breaking unrelated features; impossible to unit test in isolation; merge conflicts in team development
- Fix approach: Extract responsibilities into focused UseCases or sub-ViewModels (e.g., `WebSocketOrchestrator`, `BubbleMerger`, `CommandDispatcher`, `SaveLoadManager`, `ActorPanelManager`)

**SceneBubble — Fat Sealed Class (252 lines, 7 subclasses):**
- Issue: The sealed class has 7 subclasses (`Narration`, `Dialogue`, `UserMessage`, `ActorInteraction`, `SceneDivider`, `SystemError`, `PlotGuidance`), each with custom `equals`/`hashCode` overrides based on `contentFingerprint`. Adding new bubble types requires modifying this central class and all `when` exhaustiveness points. The fingerprint-based equality is unusual and can cause subtle bugs (two bubbles with different `id` but similar text are considered equal).
- Files: `android/app/src/main/java/com/drama/app/domain/model/SceneBubble.kt`
- Impact: Risk of incorrect deduplication (e.g., two different actors saying the same short line); every new bubble type modifies this file; `when` branches must be updated everywhere
- Fix approach: Consider separating identity (`id`-based equality) from deduplication (`contentFingerprint`-based matching); extract bubble type registry or use a discriminator + data map pattern for extensibility

**WebSocketManager — Hilt Singleton with Manual Lifecycle:**
- Issue: `WebSocketManager` is `@Inject` constructed and provided as `@Singleton` via Hilt, but manages its own `reconnectScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)` which is completely detached from Android lifecycle. The `reconnectScope` is never cancelled — even when `disconnect()` is called, only the `reconnectJob` is cancelled, not the scope itself. This scope leaks when the app process lives but the Activity is destroyed.
- Files: `android/app/src/main/java/com/drama/app/data/remote/ws/WebSocketManager.kt` (lines 35-39, 48, 344-349)
- Impact: Potential coroutine leaks; reconnect attempts may fire after ViewModel is cleared; deprecated `isConnected`/`isReconnecting` properties each create a new `MutableStateFlow` + coroutine per access (line 82-97)
- Fix approach: Inject `ProcessLifecycleOwner` scope or use `Closeable` integration; cancel `reconnectScope` in `disconnect()`; remove deprecated compatibility properties

**runBlocking in NetworkModule:**
- Issue: `provideRetrofit()` uses `runBlocking { serverPreferences.serverConfig.first() }` to read DataStore during DI graph creation. This blocks the calling thread (typically the main thread during Activity creation) and can cause ANR if DataStore is slow on first read. The comment at line 66 acknowledges this is a pitfall.
- Files: `android/app/src/main/java/com/drama/app/di/NetworkModule.kt` (line 76)
- Impact: Potential ANR on cold start; freezes UI during Hilt initialization
- Fix approach: Use a lazy Retrofit proxy/wrapper that resolves baseUrl on first actual API call, or use `@ApplicationContext` + `SharedPreferences` for the initial URL and migrate to DataStore asynchronously

**AuthRepositoryImpl — New Retrofit Instance Per Validation:**
- Issue: Every call to `verifyServer()` creates a brand new `OkHttpClient` (via `okHttpClient.newBuilder().addInterceptor(...).build()`) and `Retrofit` instance. While the `newBuilder()` shares the connection pool, the `addInterceptor` at line 25 adds a pass-through interceptor on top of the existing interceptors (including `AuthInterceptor`), potentially double-processing auth. The Retrofit instance is never reused or cached.
- Files: `android/app/src/main/java/com/drama/app/data/repository/AuthRepositoryImpl.kt` (lines 23-38)
- Impact: Unnecessary object creation per validation; interceptor stacking may cause unexpected auth behavior; no connection reuse for repeated validations to the same server
- Fix approach: Create a dedicated `@NoAuth` qualified OkHttpClient without AuthInterceptor; optionally cache Retrofit instances by baseUrl using a LRU map

## Known Bugs

**Deprecated WebSocketManager properties leak coroutines:**
- Symptoms: Each access to `isConnected` or `isReconnecting` creates a new `MutableStateFlow` and launches a collecting coroutine in `reconnectScope` that never completes
- Files: `android/app/src/main/java/com/drama/app/data/remote/ws/WebSocketManager.kt` (lines 80-97)
- Trigger: Any code that reads `webSocketManager.isConnected` or `webSocketManager.isReconnecting`
- Workaround: Use `connectionState` StateFlow instead (the deprecated properties already suggest this)

**SceneBubble fingerprint collision risk:**
- Symptoms: Two genuinely different messages with similar first-N characters get deduplicated incorrectly during reconnect merge
- Files: `android/app/src/main/java/com/drama/app/domain/model/SceneBubble.kt` (e.g., line 74: `"N|${text.take(80)}"`, line 99: `"D|$actorName|${text.take(60)}"`)
- Trigger: Two narrations with identical first 80 characters, or two dialogues by the same actor with identical first 60 characters
- Workaround: None currently; the fingerprint truncation is a deliberate trade-off for merge stability

## Security Considerations

**usesCleartextTraffic="true" in Production Manifest:**
- Risk: Allows unencrypted HTTP traffic to any server. Combined with the WebSocket `ws://` protocol (non-TLS), all communication including auth tokens can be intercepted on the network.
- Files: `android/app/src/main/AndroidManifest.xml` (line 14)
- Current mitigation: App is designed for local network usage (connects to `ip:port` on LAN), making this somewhat expected for development
- Recommendations: Use `android:networkSecurityConfig` with a `domain-config` that allows cleartext only for local/private IP ranges; enforce `https://`/`wss://` for non-local connections

**isMinifyEnabled = false in Release Build:**
- Risk: Release APK ships with full class/method/field names, making reverse engineering trivial. No code shrinking means unused code is included, increasing APK size and attack surface.
- Files: `android/app/build.gradle.kts` (line 26)
- Current mitigation: ProGuard rules file exists but is never applied
- Recommendations: Enable `isMinifyEnabled = true` and `isShrinkResources = true` for release builds; test ProGuard rules thoroughly; consider adding obfuscation for sensitive logic

**Token in WebSocket URL Query Parameter:**
- Risk: Auth token is passed as a URL query parameter (`?token=$token`) when connecting via WebSocket. This is visible in server logs, proxy logs, and browser history equivalents.
- Files: `android/app/src/main/java/com/drama/app/data/remote/ws/WebSocketManager.kt` (lines 132-139)
- Current mitigation: App uses local network only
- Recommendations: Migrate to a WebSocket connection that sends the token in the first message after connection (e.g., as an `auth` message)

## Performance Bottlenecks

**3-second REST polling always running:**
- Problem: `startPolling()` runs an infinite loop with 3-second intervals, making `getDramaStatus()` REST calls even when WebSocket is connected and healthy. This doubles network traffic.
- Files: `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt` (lines 404-434)
- Cause: Polling is used for `outlineSummary` which isn't pushed via WS; the comment at line 409 acknowledges this but doesn't solve it
- Improvement path: Add `outlineSummary` updates to WS events and stop polling when WS is connected; or use conditional polling (poll every 10s when WS connected, 3s when not)

**DramaDetailUiState — Monolithic State Object:**
- Problem: Single `data class` with 20+ fields means every `update {}` triggers Compose recomposition for all observers, even if only one field changed. This causes unnecessary recompositions throughout the entire detail screen.
- Files: `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt` (lines 43-99)
- Cause: All UI state in one flat `data class` with no granularity
- Improvement path: Split into multiple StateFlows (e.g., `connectionState`, `bubbles`, `actorPanel`, `saveState`) so Compose can subscribe to only what it needs

## Fragile Areas

**WebSocket reconnection and bubble merge:**
- Files: `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt` (lines 1083-1208)
- Why fragile: The merge algorithm depends on `contentFingerprint` equality which truncates text; the reconnection flow has 5 sequential steps each of which can fail independently; `onWsReconnected` callback is set as a mutable `var` on `WebSocketManager` (not thread-safe)
- Safe modification: Add comprehensive unit tests before modifying merge logic; use atomic reference for callback
- Test coverage: Zero — no unit tests exist

**Command dispatch in ViewModel:**
- Files: `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt` (lines 1230-1444)
- Why fragile: `sendCommand()` is a 200+ line method with nested `when` expressions for CommandType routing, display text formatting, bubble creation, and network dispatch. Adding a new command type requires modifications in 3 different `when` blocks within this method.
- Safe modification: Extract command handling into a `CommandDispatcher` with a registry pattern
- Test coverage: Zero

## Scaling Limits

**Retrofit baseUrl fixed at DI time:**
- Current capacity: Single server URL, set once during Hilt initialization
- Limit: User cannot switch servers without restarting the Activity (comment at line 68 confirms: "当用户切换服务器时，需要重启 Activity 让 Hilt 重建 DI graph")
- Scaling path: Implement a dynamic baseUrl provider (e.g., using OkHttp's `Interceptor` to rewrite URLs, or a factory pattern that creates Retrofit instances on demand)

## Dependencies at Risk

**security-crypto alpha version:**
- Risk: `androidx.security:security-crypto:1.1.0-alpha06` is an alpha release used for encrypted token storage. Alpha libraries may have breaking API changes or unresolved bugs.
- Impact: Token storage could fail on certain Android versions or after library updates
- Migration plan: Monitor for stable release; test on all supported API levels (26-35)

**No test libraries declared:**
- Risk: Zero test dependencies in `build.gradle.kts` or `libs.versions.toml`. No JUnit, no Mockito, no Turbine, no Compose testing.
- Impact: Cannot write tests without first adding infrastructure
- Migration plan: Add `junit`, `mockk`/`mockito`, `turbine`, `compose-ui-test-junit4`, `kotlinx-coroutines-test`, `hilt-android-testing` to version catalog and build file

## Missing Critical Features

**Zero unit tests:**
- Problem: No `src/test/` directory exists. No test files found anywhere in the Android module (`*Test.kt` search returns 0 results). No test dependencies declared in build configuration.
- Blocks: Any refactoring of the 1665-line ViewModel is extremely risky without test coverage; cannot verify bug fixes don't regress

**No ProGuard/R8 in release:**
- Problem: `isMinifyEnabled = false` means release builds are unoptimized. ProGuard rules file exists but is never activated.
- Blocks: Production deployment best practices; APK size optimization; code obfuscation

## Test Coverage Gaps

**All areas untested:**
- What's not tested: Everything — no test infrastructure exists at all
- Files: All source files under `android/app/src/main/java/com/drama/app/`
- Risk: Any change can break any functionality without detection
- Priority: **Critical** — Start with:
  1. `SceneBubble` model tests (pure data classes, easy to test)
  2. `mergeBubblesAfterReconnect` algorithm tests (complex logic, currently untested)
  3. `WebSocketManager` connection lifecycle tests
  4. `DramaDetailViewModel` command dispatch tests (after extraction to UseCases)

---

*Concerns audit: 2026-04-26*
