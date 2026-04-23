# Codebase Concerns

**Analysis Date:** 2026-04-22

## Tech Debt

**Double IME Padding (Keyboard Overlap Bug):**
- Issue: `DramaDetailScreen` applies manual `WindowInsets.ime.getBottom()` padding to the entire Column (line 150), while `ChatInputBar` independently applies `.imePadding()` + `.navigationBarsPadding()` on its own Column (lines 104-105). This double-applies IME padding, likely causing the input bar to be pushed too far up or creating layout jumps when the keyboard appears.
- Files: `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailScreen.kt` (line 121, 150), `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/components/ChatInputBar.kt` (lines 104-105)
- Impact: Keyboard likely doesn't behave smoothly — input bar may jump, overlap content, or have excessive spacing. The comment at line 148-149 says "not using .imePadding() (it's instantaneous, no animation)" but ChatInputBar still uses it.
- Fix approach: Remove `.imePadding()` from ChatInputBar and rely solely on the parent Column's manual `imeHeightPx` padding, OR remove the manual padding from DramaDetailScreen and use only `.imePadding()` on ChatInputBar. The manual approach gives animation control but must be the sole source of IME offset.

**Missing windowSoftInputMode in AndroidManifest:**
- Issue: `AndroidManifest.xml` has no `android:windowSoftInputMode` attribute on the Activity. With `enableEdgeToEdge()`, the default is `adjustUnspecified` which may cause unpredictable keyboard behavior.
- Files: `android/app/src/main/java/com/drama/app/src/main/AndroidManifest.xml`
- Impact: Keyboard resize behavior is undefined — may adjust or not adjust depending on API level. Should explicitly set `adjustResize` (which enableEdgeToEdge typically needs) or `adjustNothing` with manual inset handling.
- Fix approach: Add `android:windowSoftInputMode="adjustResize"` to the Activity element, consistent with the edge-to-edge + manual IME inset approach used in the code.

**WebSocketManager is a Global Singleton with Shared Mutable State:**
- Issue: `WebSocketManager` is `@Singleton` and shared across all ViewModels. It has mutable `onReconnected` callback, a single `_events` SharedFlow, and a single `_connectionState` StateFlow. When DramaCreateViewModel disconnects before navigating, it calls `webSocketManager.disconnect()` which closes the WS for ALL consumers (including any potential concurrent listeners).
- Files: `android/app/src/main/java/com/drama/app/data/remote/ws/WebSocketManager.kt`, `android/app/src/main/java/com/drama/app/ui/screens/dramacreate/DramaCreateViewModel.kt` (line 366)
- Impact: If two screens share the WS (e.g., DramaList polling while DramaCreate creates), one disconnecting kills the other. The `onReconnected` callback can only have one subscriber (overwrites previous).
- Fix approach: Use reference counting or subscription-based lifecycle for WS connections. Replace `onReconnected` callback with a SharedFlow. Consider not calling `disconnect()` in `navigateToDetail()` — let the new ViewModel's `connect()` reconnect.

**Hardcoded "南阳三子" as Test Data:**
- Issue: "南阳三子" appears as a sample drama stored at `app/dramas/南阳三子/state.json`. While not hardcoded in logic, it appears in code comments explaining race conditions (DramaCreateViewModel line 251, DramaDetailViewModel line 118). The state.json file is a 500-line fixture that could accidentally be shipped.
- Files: `app/dramas/南阳三子/state.json`, comments in `DramaCreateViewModel.kt` (line 251), `DramaDetailViewModel.kt` (line 118)
- Impact: Low — comments are fine, but the fixture data should be excluded from production builds. If the backend defaults to this drama, new users may see stale data.
- Fix approach: Add `app/dramas/` to `.gitignore` or move to test resources. The code comments serve as useful documentation of a real race condition.

## Known Bugs

**Race Condition: Drama Creation Shows Old Drama Data:**
- Symptoms: After creating a new drama, navigating to detail shows the previous drama's actors/bubbles
- Files: `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt` (init block, lines 112-134)
- Trigger: POST /drama/start is blocking on backend. Polling GET /drama/status during creation may return old drama data. Even after navigation, if `switchToDramaAndWait()` fails, `loadInitialStatus()` gets wrong data.
- Workaround: The `switchToDramaAndWait()` method calls POST /drama/load before loading status, which partially mitigates this. But there's still a window where the backend hasn't fully switched contexts.

## Security Considerations

**Token in WebSocket URL:**
- Risk: Auth token is passed as a query parameter in the WebSocket URL (`?token=$token`). This may be logged in server access logs or proxy caches.
- Files: `android/app/src/main/java/com/drama/app/data/remote/ws/WebSocketManager.kt` (lines 85-88)
- Current mitigation: HTTPS/WSS would encrypt the URL, but the code supports plain WS (line 87: `ws://`)
- Recommendations: Use WebSocket subprotocol for auth instead of query param. Ensure production uses WSS only.

**Cleartext Traffic Enabled:**
- Risk: `android:usesCleartextTraffic="true"` in AndroidManifest allows unencrypted HTTP/WS connections
- Files: `android/app/src/main/AndroidManifest.xml` (line 14)
- Current mitigation: None — needed for local development
- Recommendations: Use network security config to restrict cleartext to specific domains (e.g., local IP addresses only), disable for production

**No Certificate Pinning:**
- Risk: No certificate pinning or network security config — vulnerable to MITM
- Files: N/A (not implemented)
- Current mitigation: None
- Recommendations: Add network security config for production

## Performance Bottlenecks

**DramaCreateViewModel Polling Loop:**
- Problem: Polls GET /drama/status every 2 seconds for up to 2 minutes (force timeout), even when WS is connected
- Files: `android/app/src/main/java/com/drama/app/ui/screens/dramacreate/DramaCreateViewModel.kt` (lines 188-243)
- Cause: Polling starts immediately and never stops (only stops on `navigated` flag). When WS is connected and receiving events, polling is redundant.
- Improvement path: Stop polling when WS connects successfully and receives first event. Resume polling only on WS failure.

**DramaDetailViewModel: 39KB Single File:**
- Problem: DramaDetailViewModel is 950 lines / 39KB — handles WS events, scene history, actor panel, chat, polling, save, status refresh
- Files: `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt`
- Cause: All drama detail logic centralized in one ViewModel
- Improvement path: Extract use cases: `ChatUseCase`, `SceneHistoryUseCase`, `ActorPanelUseCase`, `DramaStatusUseCase`

## Fragile Areas

**Drama Creation → Detail Navigation:**
- Files: `android/app/src/main/java/com/drama/app/ui/screens/dramacreate/DramaCreateViewModel.kt` (navigateToDetail), `android/app/src/main/java/com/drama/app/ui/navigation/DramaNavHost.kt` (line 46)
- Why fragile: The `dramaId` passed to navigation is constructed from multiple fallback sources: `status.theme` → `status.drama_folder` → `creatingTheme` → hardcoded "current" (lines 312-317). If any of these is wrong, the detail screen loads the wrong drama or fails to load.
- Safe modification: Ensure the `dramaId` matches what POST /drama/load expects (it expects `save_name` = theme name, not folder path). The split("/").last() logic (line 316) is a workaround for folder paths.
- Test coverage: No unit tests for this flow

**DramaDetailScreen IME/Keyboard Handling:**
- Files: `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailScreen.kt` (lines 119-150), `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/components/ChatInputBar.kt` (lines 104-105)
- Why fragile: As noted in Tech Debt, dual IME padding sources create unpredictable behavior. The manual `imeHeightPx` approach reads WindowInsets.ime which may not animate smoothly on all devices.
- Safe modification: Test on multiple API levels (especially 30+ where WindowInsets.ime behavior changed). Use only one IME padding strategy consistently.
- Test coverage: No automated tests for keyboard behavior

## Scaling Limits

**Single Drama Context on Backend:**
- Current capacity: Backend appears to support only one "active" drama at a time (all APIs like /drama/status, /drama/cast return data for the current drama without a drama_id parameter)
- Limit: Cannot view or interact with multiple dramas simultaneously
- Scaling path: Backend needs drama_id parameter on all endpoints, or client needs to call POST /drama/load before any query

**Retrofit BaseUrl is Fixed at Startup:**
- Current capacity: Retrofit baseUrl is determined once from DataStore at Hilt module creation time (`runBlocking { serverPreferences.serverConfig.first() }`)
- Limit: Changing server requires app restart (Activity recreation for Hilt DI graph)
- Scaling path: Use dynamic URL override via OkHttp interceptor, or recreate Retrofit instance on server change

## Dependencies at Risk

**OkHttp WebSocket (No Dedicated Library):**
- Risk: Using raw OkHttp WebSocket without a dedicated socket library (like Socket.IO or Scarlet)
- Impact: Manual reconnect logic, no automatic heartbeat, no room/channel abstraction
- Migration plan: Consider Scarlet or similar for type-safe WS event handling with reconnection

**Retrofit baseUrl Fixed at Build Time:**
- Risk: `runBlocking` in Hilt provider to read DataStore (NetworkModule line 69)
- Impact: Blocks main thread during DI initialization; cannot change server without restart
- Migration plan: Use lazy Retrofit creation or OkHttp interceptor to rewrite URLs dynamically

## Missing Critical Features

**No Offline Support:**
- Problem: All data comes from the server. No local database or cache. If server is unreachable, the app shows nothing.
- Blocks: Offline usage, faster startup, data persistence across sessions

**No Push Notifications:**
- Problem: All real-time updates require active WebSocket connection. When app is backgrounded, user gets no notifications.
- Blocks: Timely user engagement when drama events happen

## Test Coverage Gaps

**No Unit Tests for ViewModels:**
- What's not tested: All ViewModel logic (DramaCreateViewModel, DramaDetailViewModel, DramaListViewModel)
- Files: `android/app/src/main/java/com/drama/app/ui/screens/dramacreate/DramaCreateViewModel.kt`, `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt`
- Risk: Refactoring ViewModel logic (especially navigation triggers, WS event handling, polling) can silently break
- Priority: High — DramaCreateViewModel has complex async orchestration

**No UI Tests:**
- What's not tested: Any Compose UI behavior (keyboard handling, navigation, input validation)
- Files: All Screen composables
- Risk: Layout regressions, keyboard overlap bugs go undetected
- Priority: Medium — especially for ChatInputBar and keyboard behavior

**No Integration Tests for API Layer:**
- What's not tested: Retrofit service calls, WebSocket event parsing
- Files: `android/app/src/main/java/com/drama/app/data/remote/`
- Risk: API contract changes break silently
- Priority: Medium

---

*Concerns audit: 2026-04-22*
