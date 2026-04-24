# Codebase Concerns

**Analysis Date:** 2026-04-24

## Tech Debt

**No Test Coverage:**
- Issue: Zero test files exist — no unit, integration, or UI tests
- Files: Entire project
- Impact: Any refactor or feature change risks regression; complex flows like script creation are fragile
- Fix approach: Add unit tests for ViewModels first (highest risk), then repository mapping logic, then use cases

**Retrofit baseUrl Fixed at Build Time:**
- Issue: `NetworkModule.provideRetrofit()` reads server config at Hilt graph creation time via `runBlocking`; server changes require Activity restart
- Files: `app/src/main/java/com/drama/app/di/NetworkModule.kt` (line 74-83)
- Impact: User cannot switch servers without restarting the app; `runBlocking` in DI provider is an anti-pattern
- Fix approach: Use a custom `BaseUrlInterceptor` with OkHttp that reads the current server config dynamically, eliminating the need to rebuild Retrofit

**Monolithic ViewModel Files:**
- Issue: `DramaDetailViewModel.kt` is 877 lines with 20+ responsibilities; `DramaCreateViewModel.kt` is 534 lines
- Files: `app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt`, `app/src/main/java/com/drama/app/ui/screens/dramacreate/DramaCreateViewModel.kt`
- Impact: Hard to navigate, test, and maintain; mixed concerns (WS handling, REST calls, state, navigation)
- Fix approach: Extract WS event handling into a dedicated `WsEventHandler` class; extract polling logic into `PollingManager`; keep ViewModel as thin orchestrator

**DramaListScreen_append.kt Placeholder:**
- Issue: File exists with 1 byte content — appears to be a leftover placeholder
- Files: `app/src/main/java/com/drama/app/ui/screens/dramalist/DramaListScreen_append.kt`
- Impact: Confusion; may cause build issues if it contains invalid Kotlin
- Fix approach: Delete the file or implement its intended content

## Known Bugs

**Race Condition in WebSocket/Navigation:**
- Symptoms: Multiple comments reference race conditions between WS connection creation and ViewModel lifecycle
- Files: `app/src/main/java/com/drama/app/data/remote/ws/WebSocketManager.kt`, `app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt`
- Trigger: Rapid navigation between create and detail screens
- Workaround: `hasCalledConnectWebSocket` flag and `connectGeneration` counter mitigate but don't eliminate the issue
- Note: Extensive fix comments (★ markers) suggest these have been partially addressed

## Security Considerations

**WebSocket Token in URL:**
- Risk: Auth token passed as query parameter in WS URL (`?token=xxx`) may be logged by proxies/servers
- Files: `app/src/main/java/com/drama/app/data/remote/ws/WebSocketManager.kt` (lines 115-119)
- Current mitigation: OkHttp logging redacts `Authorization` header but not URL query params
- Recommendations: Consider using a short-lived WS-specific token or initial auth frame instead of URL parameter

**No Certificate Pinning:**
- Risk: No TLS certificate pinning configured — MITM attacks possible on cloud URL connections
- Files: `app/src/main/java/com/drama/app/di/NetworkModule.kt`
- Current mitigation: None
- Recommendations: Add certificate pinning for known cloud deployment domains

**Retrofit Logging at BODY Level in Release:**
- Risk: Full request/response bodies logged in production builds
- Files: `app/src/main/java/com/drama/app/di/NetworkModule.kt` (lines 50-54)
- Current mitigation: `Authorization` header is redacted
- Recommendations: Set logging level to `NONE` for release builds using `BuildConfig.DEBUG`

## Performance Bottlenecks

**Polling Storm on Top of WebSocket:**
- Problem: During drama creation, both WebSocket events AND REST polling (2-10s intervals) run simultaneously
- Files: `app/src/main/java/com/drama/app/ui/screens/dramacreate/DramaCreateViewModel.kt` (lines 223-282)
- Cause: Polling serves as fallback but runs even when WS is fully active (just at lower 10s frequency)
- Improvement path: Stop polling entirely when WS confirms active event delivery; only restart on WS disconnect

**No Pagination on Drama List:**
- Problem: `GET drama/list` fetches all dramas at once with no pagination
- Files: `app/src/main/java/com/drama/app/data/remote/api/DramaApiService.kt` (line 46)
- Cause: Backend API doesn't support pagination parameters
- Improvement path: Add pagination support to backend API and client

## Fragile Areas

**WebSocketManager Singleton Lifecycle:**
- Files: `app/src/main/java/com/drama/app/data/remote/ws/WebSocketManager.kt`
- Why fragile: Global singleton shared between `DramaCreateViewModel` and `DramaDetailViewModel`; disconnection by one affects the other; `onReconnected`/`onPermanentFailure` callbacks are mutable vars
- Safe modification: Always call `disconnect()` before `connect()` in ViewModel; set callbacks before `connect()`; clear callbacks in `onCleared()`
- Test coverage: None

**Drama Creation Navigation Timing:**
- Files: `app/src/main/java/com/drama/app/ui/screens/dramacreate/DramaCreateViewModel.kt`
- Why fragile: Navigation triggered by multiple conditions (WS `scene_start` event, polling `isComplete`, timeout); `navigated` flag prevents double-navigation but race conditions possible
- Safe modification: Only add new navigation conditions through `navigateToDetail()` which has the `navigated` guard
- Test coverage: None

## Scaling Limits

**WebSocket Single Connection:**
- Current capacity: One active WebSocket connection at a time
- Limit: Cannot monitor multiple dramas simultaneously
- Scaling path: Consider connection multiplexing or per-drama WS channels if multi-drama monitoring needed

**In-Memory Bubble List:**
- Current capacity: All `SceneBubble` objects held in `MutableStateFlow` with no disk cache
- Limit: Long dramas with many scenes will consume increasing memory; no lazy loading of historical scenes
- Scaling path: Implement paging for scene bubbles; only keep recent N scenes in memory; load historical scenes on demand

## Dependencies at Risk

**`security-crypto` 1.1.0-alpha06:**
- Risk: Alpha version, may have breaking changes or bugs
- Impact: Token encryption could fail on certain devices or Android versions
- Migration plan: Monitor for stable release; test on diverse devices

**Compose BOM 2025.12.01:**
- Risk: Very recent BOM version; may have undiscovered issues
- Impact: UI rendering bugs
- Migration plan: Pin specific compose library versions if issues arise

## Missing Critical Features

**No Offline Support:**
- Problem: No local caching of drama data; app is completely non-functional without server connection
- Blocks: Offline viewing of previously loaded dramas

**No Error Recovery for Creation Flow:**
- Problem: If creation fails midway, no way to resume; user must start over
- Blocks: Reliable drama creation on unstable networks

**No Push Notifications:**
- Problem: No FCM/push notification support; user must keep app open to receive WS events
- Blocks: Background drama monitoring

## Test Coverage Gaps

**All ViewModels Untested:**
- What's not tested: All 5 ViewModels — creation flow, chat flow, connection flow, list operations, settings
- Files: All files in `app/src/main/java/com/drama/app/ui/screens/*/`
- Risk: Business logic regressions (polling conditions, navigation timing, error handling)
- Priority: High — `DramaCreateViewModel` and `DramaDetailViewModel` are most critical

**Repository Mapping Logic Untested:**
- What's not tested: DTO → domain model transformations, bubble extraction from CommandResponse
- Files: `app/src/main/java/com/drama/app/data/repository/DramaRepositoryImpl.kt`
- Risk: Silent data corruption if backend changes response format
- Priority: Medium

**WebSocket Event Handling Untested:**
- What's not tested: All 15+ WS event type handlers in `DramaDetailViewModel`
- Files: `app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt` (lines 346-561)
- Risk: UI breaks when new event types are added or existing ones change format
- Priority: High

**DetectActorInteractionUseCase Untested:**
- What's not tested: Keyword matching, interaction type classification, target inference
- Files: `app/src/main/java/com/drama/app/domain/usecase/DetectActorInteractionUseCase.kt`
- Risk: False positives/negatives in actor interaction detection
- Priority: Medium

---

*Concerns audit: 2026-04-24*
