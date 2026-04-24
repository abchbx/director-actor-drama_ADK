# Codebase Concerns

**Analysis Date:** 2026-04-23

## Critical Diagnostics (2026-04-23 Deep Dive)

### DIAG-1: Aggressive Polling on `/api/v1/drama/status` During Drama Creation

**Root Cause: Polling runs in parallel with WebSocket and never pauses**

- **Backend endpoint**: `app/api/routers/queries.py` line 80 — `GET /drama/status` reads `tool_context.state["drama"]` directly via `get_current_state()`. No caching, no throttle — every hit reads session state.
- **Frontend polling code**: `DramaCreateViewModel.kt` lines 216-271 — `startPolling()` creates an infinite `while (isActive && !navigated)` loop with `POLL_INTERVAL_MS = 2_000L` (2 seconds). The first poll is after 500ms.
- **Why so aggressive**:
  1. Polling starts **before** the REST `/drama/start` call returns (line 138: `startPolling()` is called before `createJob` launches). This was intentional: the comment says "后端的 /start 是阻塞式的...可能持续数分钟。如果等它返回才轮询，用户会长时间卡在'连接中'"。
  2. **Polling never pauses when WS is connected**. Even if the WebSocket is receiving `director_log` and `storm_outline` events in real-time, polling continues every 2 seconds. The only stop condition is `navigated == true`.
  3. The 2-second interval was chosen to give responsive UX during STORM (which can take 1-3 minutes), but this means ~60-90 HTTP requests per drama creation.
- **Impact**: Server load, unnecessary network traffic, battery drain on mobile. With WS connected, these polls are completely redundant — the WS events already update `stormPhase` and `handleStormEvent()` already handles navigation.
- **Fix approach**: Stop polling when WS is connected and has received at least one event. Resume polling only on WS disconnection. Example:
  ```kotlin
  // In startPolling(), add condition:
  if (_uiState.value.isWsConnected) {
      delay(POLL_INTERVAL_MS)  // Skip poll, WS is active
      continue
  }
  ```

### DIAG-2: WebSocket Connects Then Immediately Closes

**Root Cause: Heartbeat timeout triggers on FIRST ping cycle because client pong handling is text-based and fragile**

- **WebSocket endpoint**: `app/api/routers/websocket.py` line 53 — `@router.websocket("/ws")`.
- **ConnectionManager heartbeat**: `app/api/ws_manager.py` lines 69-98 — `heartbeat()` sends `{"type": "ping"}` every 15 seconds and checks `is_pong_expired()` with 30-second timeout.
- **Client pong handling**: `WebSocketManager.kt` lines 112-114 — Client responds to `{"type":"ping"}` with `{"type":"pong"}` via text matching:
  ```kotlin
  if (text.contains("\"type\"") && text.contains("\"ping\"")) {
      webSocket.send("""{"type":"pong"}""")
      return
  }
  ```
- **The actual problem — why WS connects then closes**:
  1. **`record_pong()` is only called when the client sends a JSON `{"type":"pong"}` message through `websocket.receive_json()`** (websocket.py line 79). The client DOES send pong, and the server DOES call `manager.record_pong(websocket)` when it receives `{"type":"pong"}`.
  2. **BUT** — the `_last_pong` timestamp is initialized to `time.monotonic()` at `connect()` time (ws_manager.py line 44). The first heartbeat check happens 15 seconds later. If the client's pong response arrives within 30 seconds of connection, it should work.
  3. **The REAL issue**: The `DramaCreateViewModel` calls `webSocketManager.disconnect()` in `navigateToDetail()` (line 430) which sets `isIntentionalDisconnect = true` and closes the socket. But there's a **race condition**: The `navigateToDetail()` is triggered either by:
     - `handleStormEvent()` receiving a `scene_start` event (line 488)
     - `handlePollResponse()` detecting `isComplete` (line 367)
  4. When navigation triggers, `disconnect()` is called immediately, closing the WS connection. On the **DramaDetailViewModel** side, `connectWebSocket()` is called during `performInitSync()` (line 139), which calls `disconnectWebSocketSafely()` first (line 242), then `webSocketManager.connect()` again.
  5. **Race condition**: If `DramaCreateViewModel.disconnect()` executes AFTER `DramaDetailViewModel.connectWebSocket()` has already started connecting (because they share the same `WebSocketManager` singleton), the new connection gets closed by the old ViewModel's disconnect.
  6. **Additionally**, the `onClosed` callback in WebSocketManager checks `isIntentionalDisconnect` — but since DramaCreateViewModel set it to `true` via `disconnect()`, if the close arrives after DramaDetailViewModel's `connect()` has reset `isIntentionalDisconnect = false`, the close won't trigger reconnect.
  7. **Another subtle issue**: The `WebSocketManager` is a **singleton** (`@Inject` with Hilt). Both ViewModels share the same instance. The `onReconnected` callback is overwritten by whichever ViewModel connects last.

- **Fix approach**:
  1. **Don't use a shared singleton for WebSocketManager** — or use reference counting for connect/disconnect.
  2. In `DramaCreateViewModel.navigateToDetail()`, disconnect WS BEFORE navigation (already done at line 430, but navigation at line 432-434 happens asynchronously via `_events.emit()`). Ensure the disconnect completes before DramaDetailViewModel initiates its connection.
  3. Replace `onReconnected` callback with a SharedFlow to allow multiple subscribers.

### DIAG-3: Director Script Outline Generation and WebSocket Delivery

**How the director writes the script outline:**

1. **DramaRouter routes `/start` to `setup_agent`** (`app/agent.py` lines 458-459):
   ```python
   if is_start_command:
       agent = self._sub_agents_map.get("setup_agent")
   ```

2. **setup_agent executes 4 steps** (`app/agent.py` lines 89-117):
   - Step 1: `start_drama(theme)` — initializes drama state (`app/tools.py` line 189)
   - Step 2: `storm_discover_perspectives(theme)` — discovers narrative perspectives
   - Step 3: `storm_research_perspective(perspective_name, theme)` — researches each perspective (at least 2-3)
   - Step 4: `storm_synthesize_outline(theme)` — merges all perspectives into a drama outline with 4 acts (`app/tools.py` line 2052)

3. **The outline is stored in state** via `storm_set_outline(outline, tool_context)` at `app/tools.py` line 2139, and **status transitions to "acting"** via `set_drama_status("acting", tool_context)` at line 2142.

**How the outline is supposed to be sent to the frontend via WebSocket:**

4. **Event flow from Runner → WebSocket**:
   - `run_command_and_collect()` in `app/api/runner_utils.py` iterates over `runner.run_async()` events (line 70).
   - For each event, if `event_callback` is provided, it calls `await event_callback(event)` (line 87).
   - The `event_callback` is created by `ConnectionManager.create_broadcast_callback()` (`app/api/ws_manager.py` line 116).
   - The callback calls `map_runner_event(event)` (`app/api/event_mapper.py` line 188) which maps ADK events to business events.

5. **Event mapping for STORM tools** (`app/api/event_mapper.py` lines 19-34):
   ```python
   "storm_discover_perspectives": ["storm_discover"],
   "storm_research_perspective": ["storm_research"],
   "storm_synthesize_outline": ["storm_outline"],
   ```
   Plus, these tools are in `DIRECTOR_LOG_TOOLS` (lines 38-42), so rich `director_log` events are emitted for both function_call and function_response phases.

6. **The problem with outline delivery**:
   - When `storm_synthesize_outline` is called as a `function_call`, the event mapper emits `storm_outline` + `director_log`. **But the outline content is NOT included in the WS event** — only `{"tool": "storm_synthesize_outline"}` is sent for the call phase (line 49-50: `_extract_call_data("storm_outline", ...)` returns `{"tool": fn_name}`).
   - When `storm_synthesize_outline` returns as a `function_response`, the mapper emits another `storm_outline` event, but `_extract_response_data("storm_outline", ...)` returns `{}` (line 87: falls through to the `else` branch).
   - **The actual outline data is in the `function_response` dict** (which includes `outline`, `message`, `phase`, `next_phase`), but `TOOL_EVENT_MAP["storm_synthesize_outline"]` maps to `["storm_outline"]`, and `_extract_response_data` doesn't have a case for `storm_outline` — so the outline content is **lost in WS transit**.
   - The frontend only receives `{"type": "storm_outline", "data": {}}` — a signal that the outline is ready, but **no outline content**.

7. **How the frontend gets the outline**: The Android client polls `GET /drama/status` which returns `has_outline: bool` and `outline_summary: str` (from `get_current_state()` in `app/state_manager.py` lines 1123-1155). This is a **text summary**, not the structured outline.

- **Fix approach**: Add outline data extraction in `event_mapper.py`:
  ```python
  # In _extract_response_data():
  elif event_type == "storm_outline":
      return {
          "acts_count": response.get("acts_count", len(response.get("outline", {}).get("acts", []))),
          "message": response.get("message", ""),
          "new_status": response.get("new_status", ""),
      }
  ```
  And on the frontend, use the `storm_outline` WS event to update UI immediately instead of waiting for the next poll cycle.

### DIAG-4: Drama Creation Flow — End-to-End Analysis

**Complete flow from POST /drama/start to client display:**

**Phase A: Backend Init (0-2 seconds)**
1. Android calls `POST /api/v1/drama/start` with `{theme: "新三国"}`.
2. `commands.py:start_drama()` (line 90) acquires `runner_lock`.
3. Auto-saves existing drama if any (line 112-120).
4. Calls `init_drama_state(theme, tool_context)` (line 124) — **synchronously** initializes state: `status="setup"`, `current_scene=0`, `actors={}`, `storm={}`.
5. Calls `flush_state_sync()` (line 125) — writes state to disk immediately.
6. **Releases `runner_lock`** (line 110 exits `async with lock`).
7. Spawns **background task** `_run_storm_setup()` (line 132) — this runs the full STORM pipeline.
8. **Returns immediately** to the Android client with `CommandResponse(status="success")`.

**Phase B: Android Polling + WebSocket (0-120 seconds)**
9. Meanwhile, `DramaCreateViewModel` has already started:
   - **WebSocket connection** (line 120-132): connects to `/api/v1/ws`, receives `director_log` events during STORM.
   - **Polling loop** (line 216-271): hits `GET /drama/status` every 2 seconds.
   - **REST call** (line 141-161): `dramaRepository.startDrama(theme)` — this is the `POST /drama/start` that already returned quickly, so it completes fast.

**Phase C: Backend STORM (10-180 seconds, in background task)**
10. `_run_storm_setup()` re-acquires `runner_lock` (line 75) — **this blocks ALL other commands** until STORM completes.
11. `run_command_and_collect()` sends `/start {theme}` through the ADK Runner.
12. `DramaRouter._run_async_impl()` routes to `setup_agent` because `/start` is detected.
13. `setup_agent` (LLM-driven) executes:
    - `start_drama(theme)` — **re-initializes state** (duplicate of step 4! The init already happened in Phase A, but the tool does it again). This is because the background task runs `/start {theme}` as if it's a fresh CLI command, and the agent always calls `start_drama()` first.
    - `storm_discover_perspectives(theme)` — LLM discovers 2-5 perspectives.
    - `storm_research_perspective()` × N — LLM researches each perspective.
    - `storm_synthesize_outline(theme)` — LLM synthesizes outline, sets `status="acting"`.
    - **Agent outputs outline summary text** and **stops** (instruction: "完成后必须向用户输出一份清晰的大纲摘要...然后停止，等待用户确认后再继续创建演员").

**Phase D: Navigation Decision (variable timing)**
14. Android detects completion via polling or WS events:
    - **Via polling** (`handlePollResponse()`): When `drama_status == "acting"` and `num_actors > 0` → `isComplete = true`. **BUT** — the setup_agent does NOT create actors (instruction says "绝对不要调用 create_actor！"). So `num_actors` is 0 after STORM completes, and `isComplete` won't be true via condition B or C.
    - **Via WS** (`handleStormEvent()`): When `storm_outline` event is received → logs "📋 收到大纲完成信号，等待演员创建..." and does NOT navigate (line 481-484). When `scene_start` event is received → navigates. But `scene_start` is only emitted when `next_scene()` is called, which hasn't happened yet.
    - **The gap**: After STORM completes, `drama_status` transitions to `"acting"` (from `storm_synthesize_outline`), but `num_actors == 0` and `current_scene == 0`. The only `isComplete` condition that matches is:
      ```kotlin
      ds == STATUS_SETUP && status.has_outline && status.num_actors > 0  // Fails: num_actors=0
      // OR
      currentElapsed >= 60 && status.num_actors > 0 && ds.isNotBlank()  // Fails: num_actors=0
      ```
    - **Result**: The app **gets stuck** after STORM completes with `status="acting"`, `num_actors=0`, `current_scene=0`. No `isComplete` condition is satisfied. The user sees "创作中..." indefinitely until the 120-second force timeout.

**Phase E: Force Timeout (at 120 seconds)**
15. `startForceNavigateTimeout()` fires (line 175-199).
16. If `hasConfirmedThemeMatch` is true (which it should be after a successful poll that returns the new theme), it force-navigates to the detail page with `creatingTheme` as the dramaId.
17. If `hasConfirmedThemeMatch` is false (unlikely but possible if backend hasn't initialized yet), it shows an error.

**The fundamental design flaw**:
- The backend's `setup_agent` is designed to **stop after outline synthesis** and wait for user confirmation before creating actors.
- But the Android `DramaCreateViewModel` expects actors to be created as part of the setup flow (all `isComplete` conditions require `num_actors > 0`).
- There's no WS event or poll response that signals "outline ready, awaiting user confirmation" in a way the Android client handles gracefully.
- The `has_outline` field IS returned in `DramaStatusResponse` (line 109: `has_outline: bool`), and the Android DTO does have this field (`DramaStatusResponseDto.kt` line 16: `val has_outline: Boolean = false`). The `handlePollResponse()` does have a condition for outline + actors (line 311), but NOT for outline WITHOUT actors.

**Fix approach**:
1. Add a new `isComplete` condition in `handlePollResponse()` for when `has_outline == true` and `drama_status == "acting"` (outline synthesized, ready for user to confirm):
   ```kotlin
   ds == STATUS_ACTING && status.has_outline && status.current_scene == 0 -> true
   ```
2. On the backend, `storm_synthesize_outline` sets `status="acting"`, which is misleading — it should set a transitional status like `"outline_ready"` that the frontend can recognize.
3. Alternatively, emit a specific WS event `outline_ready` that the frontend can handle to navigate to a "confirm outline" state instead of waiting for actors.

---

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
