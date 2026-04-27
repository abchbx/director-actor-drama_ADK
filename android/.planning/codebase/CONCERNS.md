# Codebase Concerns

**Analysis Date:** 2026-04-27

## Tech Debt

**NetworkExceptionInterceptor 504 code collision:**
- Issue: `NetworkExceptionInterceptor` uses HTTP 504 (Gateway Timeout) for client-side `SocketTimeoutException`, but the server also returns real HTTP 504 from `runner_utils.py` when command execution exceeds the timeout. Both produce "UNKNOWN:504" in `AuthRepositoryImpl`, making it impossible to distinguish client-side timeout from server-side timeout.
- Files: `app/src/main/java/com/drama/app/data/remote/interceptor/NetworkExceptionInterceptor.kt`, `app/src/main/java/com/drama/app/data/repository/AuthRepositoryImpl.kt`
- Impact: Cannot differentiate "network unreachable / connection timed out" from "server received request but processing timed out". Users see generic "UNKNOWN:504" instead of actionable error messages.
- Fix approach: Use a custom error code (e.g., 599 or a non-HTTP code) for client-side timeouts in `NetworkExceptionInterceptor`, or add a custom header (e.g., `X-Client-Error: true`) to distinguish synthetic responses from real server responses.

**AuthRepositoryImpl temporary Retrofit instance:**
- Issue: `AuthRepositoryImpl.verifyServer()` creates a new `Retrofit` instance per verification call instead of using the Hilt-provided one. The comment explains this is intentional (no interceptors for pre-connection verification), but the approach creates a new `OkHttpClient` each time (via `okHttpClient.newBuilder()`) which allocates new connection pools and threads.
- Files: `app/src/main/java/com/drama/app/data/repository/AuthRepositoryImpl.kt` (line 24-37)
- Impact: Repeated server verification (e.g., user retrying connection) creates orphaned OkHttp resources until GC
- Fix approach: Create a dedicated `@NoAuth` qualified OkHttpClient in NetworkModule that shares the same connection pool but has no auth interceptor, and inject it into AuthRepositoryImpl

**runBlocking in ServerPreferences:**
- Issue: `ServerPreferences.currentApiBaseUrl()` uses `runBlocking` on first access when memory cache is empty. This is called from `BaseUrlInterceptor.intercept()` which runs on OkHttp's dispatcher thread. Blocking OkHttp threads can cause deadlocks in edge cases.
- Files: `app/src/main/java/com/drama/app/data/local/ServerPreferences.kt` (line 53)
- Impact: Potential deadlock if DataStore has pending writes and OkHttp thread is blocked waiting for it
- Fix approach: Pre-populate the cache during Application.onCreate() or eagerly read DataStore at Hilt module provision time

**No HTTP cache configured:**
- Issue: OkHttpClient has no cache configured, meaning every request hits the network even for cacheable GET endpoints (drama list, drama status, cast, scenes).
- Files: `app/src/main/java/com/drama/app/di/NetworkModule.kt`
- Impact: Unnecessary network usage and slower responses for frequently polled endpoints
- Fix approach: Add `Cache` to OkHttpClient with reasonable size (e.g., 5MB) and configure cache control headers on server or interceptor

## Known Bugs

**"UNKNOWN:504" error message shown to users:**
- Symptoms: When a network timeout occurs, the user sees "UNKNOWN:504" as the error message on the connection screen
- Files: `app/src/main/java/com/drama/app/data/repository/AuthRepositoryImpl.kt` (line 49-56), `app/src/main/java/com/drama/app/ui/screens/connection/ConnectionViewModel.kt` (line 87-94)
- Trigger: 1) SocketTimeoutException caught by NetworkExceptionInterceptor → synthetic 504 response → Retrofit throws HttpException(504) → AuthRepositoryImpl catches and produces "UNKNOWN:504". OR 2) Real server 504 from runner_utils.py timeout → same path.
- Workaround: None — user must retry, but the error message doesn't guide them to the actual cause

**BaseUrlInterceptor doesn't update Retrofit.baseUrl:**
- Issue: When user switches servers, `BaseUrlInterceptor` correctly redirects requests, but the `Retrofit.baseUrl` remains the original value. This works because the interceptor replaces scheme/host/port before each request, but any code that reads `retrofit.baseUrl()` directly would get the wrong value.
- Files: `app/src/main/java/com/drama/app/di/NetworkModule.kt` (line 82-96)
- Impact: Currently benign (all requests go through interceptor), but could cause confusion if new code relies on `retrofit.baseUrl()`
- Fix approach: Document this explicitly or rebuild Retrofit instance when server changes

## Security Considerations

**Debug build trusts user certificates:**
- Risk: Debug `network_security_config_debug.xml` trusts user-installed certificates, enabling MITM attacks on debug builds
- Files: `app/src/main/res/xml/network_security_config_debug.xml` (line 8)
- Current mitigation: Only affects debug builds, not shipped to users
- Recommendations: Acceptable for development, but developers should be aware they're vulnerable to MITM when using debug builds on shared networks

**Release network_security_config allows localhost cleartext:**
- Risk: The release config allows cleartext HTTP to `10.0.2.2`, `localhost`, `127.0.0.1`. On a real device, `localhost` could be exploited by malicious local apps.
- Files: `app/src/main/res/xml/network_security_config.xml` (line 14-18)
- Current mitigation: `10.0.2.2` only resolves on emulators; `localhost`/`127.0.0.1` are local-only
- Recommendations: Consider removing the localhost exception from release builds entirely, or restrict to emulator-only detection

**WebSocket token in query parameter:**
- Risk: Auth token is passed as `?token=` query parameter in WebSocket URL, which may appear in server logs, proxy logs, and browser history (if applicable)
- Files: `app/src/main/java/com/drama/app/domain/model/ServerConfig.kt` (line 27), `app/src/main/java/com/drama/app/data/remote/ws/WebSocketManager.kt` (line 178-186)
- Current mitigation: OkHttp WebSocket connections don't cache URLs like browsers do; server logs should be secured
- Recommendations: This is standard practice for WebSocket auth (no header support in WS handshake), but ensure server logs don't persist the token

**No certificate pinning:**
- Risk: Without certificate pinning, a compromised CA or trusted root could allow MITM even on HTTPS connections
- Files: `app/src/main/java/com/drama/app/di/NetworkModule.kt`
- Current mitigation: Not implemented
- Recommendations: Consider adding certificate pinning for cloud-hosted servers (baseUrl) if they have known certificates; skip for IP:port local development

## Performance Bottlenecks

**300s read timeout for all requests:**
- Problem: OkHttpClient has 300s (5 minute) read timeout configured for all requests. This was set for LLM calls that can take minutes, but it means quick API calls (status, cast, list) will hang for 5 minutes if the server stops responding.
- Files: `app/src/main/java/com/drama/app/di/NetworkModule.kt` (line 76)
- Cause: Single OkHttpClient shared between all API calls and WebSocket, timeout configured for worst-case LLM scenario
- Improvement path: Use per-request timeout overrides via `okhttp3.Request.Builder.tag(Timeout::class)` or create separate API service interfaces with different client configurations

**No request cancellation on ViewModel clear:**
- Problem: When a ViewModel is cleared (screen navigation), in-flight OkHttp requests continue executing until they complete or timeout (up to 300s)
- Files: `app/src/main/java/com/drama/app/di/NetworkModule.kt`, various ViewModels
- Cause: No call cancellation mechanism tied to ViewModel lifecycle
- Improvement path: Use `viewModelScope` launch + `suspendCancellableCoroutine` to cancel OkHttp calls when coroutine is cancelled

## Fragile Areas

**Interceptor order dependency:**
- Files: `app/src/main/java/com/drama/app/di/NetworkModule.kt` (line 61-74)
- Why fragile: The interceptor chain order is critical: BaseUrlInterceptor MUST be first (routes to correct server), AuthInterceptor MUST be second (adds token), NetworkExceptionInterceptor MUST be third (catches errors from real network calls). Reordering would break functionality.
- Safe modification: Add new interceptors at the correct position in the chain, with clear comments explaining the dependency
- Test coverage: Only `BaseUrlInterceptorTest` exists; no tests for `AuthInterceptor` or `NetworkExceptionInterceptor`

**ServerPreferences memory cache invalidation:**
- Files: `app/src/main/java/com/drama/app/data/local/ServerPreferences.kt`
- Why fragile: The `@Volatile cachedApiBaseUrl` is only invalidated by `saveServerConfig()` and `clearServerConfig()`. If DataStore is modified externally (e.g., backup restore, multi-process), the cache becomes stale.
- Safe modification: Always update both DataStore and cache atomically; consider adding a cache invalidation mechanism
- Test coverage: No tests for ServerPreferences

**WebSocket generation counter pattern:**
- Files: `app/src/main/java/com/drama/app/data/remote/ws/WebSocketManager.kt` (line 56, 174, 192-346)
- Why fragile: The `connectGeneration` counter is used to ignore stale WebSocket callbacks. If the counter overflows (unlikely but theoretically possible with rapid connect/disconnect), stale callbacks could be processed.
- Safe modification: The Long type makes overflow practically impossible, but the pattern is complex and error-prone
- Test coverage: ConnectionOrchestratorTest exists but tests orchestrator, not WebSocketManager directly

## Scaling Limits

**Single Retrofit instance for all API calls:**
- Current capacity: All REST calls share one Retrofit instance with one OkHttpClient
- Limit: Cannot configure different timeouts for different endpoints (e.g., fast status check vs slow LLM calls)
- Scaling path: Create qualified Retrofit instances (e.g., `@LongTimeout`, `@ShortTimeout`) or use per-request timeout overrides

**WebSocket is Activity-scoped:**
- Current capacity: One WebSocket connection per Activity lifecycle
- Limit: Multiple concurrent drama sessions are not supported
- Scaling path: If multi-session is needed, elevate WebSocketManager to Singleton scope with multi-connection support

## Dependencies at Risk

**Security Crypto alpha version:**
- Risk: `androidx.security:security-crypto:1.1.0-alpha06` is an alpha release with known issues on some devices (Keystore exceptions)
- Impact: Token storage could fail on certain devices/Android versions, causing auth failures
- Migration plan: Monitor for stable release; consider fallback to regular SharedPreferences with obfuscation if EncryptedSharedPreferences fails

**OkHttp 4.12.0:**
- Risk: OkHttp 4.x is in maintenance mode; OkHttp 5.x is the active development line
- Impact: No future features or non-critical bug fixes
- Migration plan: Plan migration to OkHttp 5.x when Retrofit adds support

## Missing Critical Features

**No retry mechanism for REST API calls:**
- Problem: Failed REST calls are not automatically retried. Only WebSocket has reconnection logic.
- Blocks: Resilient operation on flaky mobile networks

**No offline mode or request queueing:**
- Problem: All functionality requires active server connection
- Blocks: Viewing cached drama data when offline

## Test Coverage Gaps

**NetworkExceptionInterceptor:**
- What's not tested: Error conversion logic (SocketTimeoutException→504, UnknownHostException→503, etc.)
- Files: `app/src/main/java/com/drama/app/data/remote/interceptor/NetworkExceptionInterceptor.kt`
- Risk: Changes to error codes or messages could break UI error handling without detection
- Priority: High (directly impacts "UNKNOWN:504" error flow)

**AuthInterceptor:**
- What's not tested: Token injection, no-token passthrough
- Files: `app/src/main/java/com/drama/app/data/remote/interceptor/AuthInterceptor.kt`
- Risk: Token header changes could silently break auth
- Priority: Medium

**ServerPreferences:**
- What's not tested: Memory cache lifecycle, runBlocking fallback, save/clear operations
- Files: `app/src/main/java/com/drama/app/data/local/ServerPreferences.kt`
- Risk: Cache invalidation bugs could route requests to wrong server
- Priority: High

**AuthRepositoryImpl:**
- What's not tested: Error mapping (TIMEOUT, NETWORK_UNREACHABLE, AUTH_FAILED, UNKNOWN:code)
- Files: `app/src/main/java/com/drama/app/data/repository/AuthRepositoryImpl.kt`
- Risk: Error type classification changes could break connection screen error display
- Priority: High (directly impacts "UNKNOWN:504" flow)

**WebSocketManager:**
- What's not tested: Reconnection logic, heartbeat, generation counter, reference counting
- Files: `app/src/main/java/com/drama/app/data/remote/ws/WebSocketManager.kt`
- Risk: Reconnection or lifecycle bugs could cause connection leaks or UI deadlocks
- Priority: Medium

---

*Concerns audit: 2026-04-27*
