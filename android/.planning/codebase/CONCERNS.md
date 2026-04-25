# Codebase Concerns

**Analysis Date:** 2026-04-25

## Tech Debt

**DramaDetailViewModel.kt — God Object (1227 lines, 51KB):**
- Issue: Single ViewModel handles WS events, REST calls, state management, command parsing, local saves, actor panel, history, and error handling
- Files: `app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt`
- Impact: Difficult to understand, modify, and test. Any change risks side effects across unrelated features.
- Fix approach: Extract responsibilities into separate classes:
  - `WsEventHandler` — Parse WS events and create bubbles
  - `CommandRouter` — Parse and route commands (already partially separated in `CommandType`)
  - `LocalSaveManager` — Handle local save/load/list/delete
  - `DramaStateManager` — Handle status polling and state sync

**handleWsEvent() — Monolithic when block (~240 lines):**
- Issue: Single function handles 15+ event types with complex branching logic
- Files: `app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt` (lines 417-655)
- Impact: High cyclomatic complexity, easy to introduce bugs when adding new event types
- Fix approach: Extract each event type handler into a separate private function or use a map of event type → handler function

**DramaRepositoryImpl.kt — Dual Concern (10.76KB):**
- Issue: Implements both REST API calls and DTO→domain mapping logic
- Files: `app/src/main/java/com/drama/app/data/repository/DramaRepositoryImpl.kt`
- Impact: Mapping logic is tightly coupled to API implementation, making it hard to test independently
- Fix approach: Extract `SceneBubbleMapper` class for DTO→domain conversion, testable in isolation

## Known Bugs

**None confirmed — but potential issues observed:**

**Bubble counter race condition:**
- Symptoms: Potential duplicate IDs if `bubbleCounter++` is called from multiple coroutines
- Files: `app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt`
- Trigger: Multiple WS events arriving simultaneously could interleave `bubbleCounter++` operations
- Workaround: Currently safe because WS events are collected on a single coroutine, but `addErrorBubble()` is called from multiple coroutine scopes

**WS reconnection during scene transition:**
- Symptoms: After `returnToCurrentScene()`, `disconnectWebSocketSafely()` resets `hasCalledConnectWebSocket = false`, then `connectWebSocket()` is called — but if the reconnection is slow, the user might see stale state
- Files: `app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt` (lines 707-714)
- Trigger: Rapid switching between history view and current scene
- Workaround: None — user must wait for reconnection

## Security Considerations

**Token in WebSocket URL:**
- Risk: Auth token passed as query parameter in WS connection URL — may be logged by proxies/servers
- Files: `app/src/main/java/com/drama/app/data/remote/ws/WebSocketManager.kt`
- Current mitigation: HTTPS/WSS would encrypt the URL (but current setup may use plain HTTP)
- Recommendations: Consider using WebSocket subprotocol for auth or first-message auth instead of URL query param

**No certificate pinning:**
- Risk: MITM attacks could intercept REST or WS traffic
- Files: `app/src/main/java/com/drama/app/di/NetworkModule.kt`
- Current mitigation: None
- Recommendations: Add certificate pinning for production deployments

**SecureStorage implementation:**
- Risk: EncryptedSharedPreferences is used but implementation not audited
- Files: `app/src/main/java/com/drama/app/data/local/SecureStorage.kt`
- Current mitigation: Android Keystore-backed encryption
- Recommendations: Verify key alias uniqueness and encryption parameters

## Performance Bottlenecks

**Full bubble list replacement on every update:**
- Problem: `_uiState.update { it.copy(bubbles = it.bubbles + bubble) }` creates a new list on every bubble addition
- Files: `app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt`
- Cause: Immutable state + List concatenation creates O(n) copies on each update
- Improvement path: Use `MutableList` internally and only expose immutable snapshot, or use a persistent data structure (e.g., `kotlinx.collections.immutable`)

**ReverseLayout + reversed list:**
- Problem: `bubbles.reversed()` creates a new list on every recomposition
- Files: `app/src/main/java/com/drama/app/ui/screens/dramadetail/components/SceneBubbleList.kt` (line 71)
- Cause: `remember(bubbles)` caches, but still creates a new reversed list whenever `bubbles` reference changes
- Improvement path: Maintain bubbles in reverse order in ViewModel, or use `LazyColumn` without `reverseLayout`

**SceneBubbleList key stability:**
- Problem: Bubble IDs use counter-based IDs like `"b_0"`, `"b_1"` — if bubbles are reloaded, IDs may conflict with existing ones
- Files: `app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt`
- Cause: `bubbleCounter` resets to 0 in `resetAllState()`, but scene loading uses different prefixes
- Improvement path: Use UUID-based IDs or ensure prefix uniqueness across all bubble creation paths

## Fragile Areas

**WS event handling — message source deduplication:**
- Files: `app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt` (lines 1131-1171)
- Why fragile: The dedup logic assumes WS events arrive after REST response, but timing is non-deterministic. The `isWsConnected` check at send time may not reflect WS state at response time.
- Safe modification: Test thoroughly with rapid connect/disconnect cycles; consider adding sequence numbers or timestamps for dedup
- Test coverage: None

**Three-party message system (director/actor/user):**
- Files: `app/src/main/java/com/drama/app/domain/model/SceneBubble.kt`, `event_mapper.py`
- Why fragile: `senderType` and `senderName` must match between backend event_mapper and frontend ViewModel handling. Any mismatch in naming convention (e.g., "旁白" vs "narrator") will break avatar display
- Safe modification: Keep a shared enum/mapping between backend and frontend; add integration tests
- Test coverage: None

## Scaling Limits

**Bubble list size:**
- Current capacity: No limit — bubbles accumulate for entire drama session
- Limit: Memory pressure on long sessions (hundreds of scenes with dozens of bubbles each)
- Scaling path: Implement pagination or windowing in `SceneBubbleList`, only keep recent N bubbles in memory

**WebSocket reconnection:**
- Current capacity: Max 5 retries with exponential backoff
- Limit: Permanent failure after 5 retries, user must manually retry
- Scaling path: Add infinite retry with increasing delays, or background service for reconnection

## Dependencies at Risk

**Google ADK (Agent Development Kit):**
- Risk: Relatively new framework, API may change
- Impact: Backend `event_mapper.py` and tool definitions would need updating
- Migration plan: Pin ADK version, add integration tests for event mapping

## Missing Critical Features

**No test infrastructure:**
- Problem: Zero test files, no test dependencies, no CI
- Blocks: Confidence in refactoring, regression prevention, code quality

**No offline support:**
- Problem: App requires constant server connection; no local caching of drama state beyond manual saves
- Blocks: Usage in poor network conditions

## Test Coverage Gaps

**Entire codebase is untested:**
- What's not tested: All functionality
- Files: All `.kt` files
- Risk: Any change could introduce regressions without detection
- Priority: High

**Highest-priority testing targets:**
1. `DetectActorInteractionUseCase` — Pure logic, easy to test, high value
2. `DramaDetailViewModel.handleWsEvent()` — Core business logic, complex branching
3. `DramaRepositoryImpl.getSceneBubbles()` — DTO mapping correctness
4. `WebSocketManager` — Connection lifecycle and reconnection

---

*Concerns audit: 2026-04-25*
