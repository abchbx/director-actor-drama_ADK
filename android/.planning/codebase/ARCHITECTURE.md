# Architecture

**Analysis Date:** 2026-04-27

## Pattern Overview

**Overall:** Clean Architecture with MVVM (Hilt DI + Jetpack Compose)

**Key Characteristics:**
- Layered architecture: domain → data → ui, with clear separation
- Dependency inversion via repository interfaces in domain layer
- Unidirectional data flow: ViewModel → StateFlow → Composable
- Network layer uses interceptor chain pattern for cross-cutting concerns
- WebSocket uses reference-counted Activity-scoped lifecycle management

## Layers

**Domain Layer:**
- Purpose: Business models, repository interfaces, use cases
- Location: `app/src/main/java/com/drama/app/domain/`
- Contains: Models (ServerConfig, ConnectionStatus, AuthMode, Drama, SceneBubble, ActorInfo, CommandType), Repository interfaces (DramaRepository, AuthRepository, ServerRepository), Use cases (DetectActorInteractionUseCase)
- Depends on: Nothing (pure Kotlin)
- Used by: Data layer (implementations), UI layer (ViewModels)

**Data Layer:**
- Purpose: Data access, API communication, local persistence
- Location: `app/src/main/java/com/drama/app/data/`
- Contains: Repository implementations, API services, DTOs, interceptors, WebSocket manager, local storage (ServerPreferences, SecureStorage, DramaSaveRepository)
- Depends on: Domain layer (interfaces), OkHttp, Retrofit, DataStore, Security-Crypto
- Used by: UI layer (via repository interfaces)

**DI Layer:**
- Purpose: Dependency injection configuration
- Location: `app/src/main/java/com/drama/app/di/`
- Contains: Hilt modules (NetworkModule, DataStoreModule, DramaModule, WebSocketModule)
- Depends on: All other layers (wiring)
- Used by: Hilt runtime

**UI Layer:**
- Purpose: Screen rendering, user interaction, view state management
- Location: `app/src/main/java/com/drama/app/ui/`
- Contains: Screens (connection, drama create, drama detail), Components, Navigation, Theme
- Depends on: Domain layer (via ViewModels), Compose framework
- Used by: Android framework

## Data Flow

**REST API Call Flow:**

1. ViewModel calls repository method
2. Repository calls Retrofit `DramaApiService` method
3. OkHttp interceptor chain executes:
   a. `BaseUrlInterceptor` — replaces request URL scheme/host/port from `ServerPreferences`
   b. `AuthInterceptor` — injects `Authorization: Bearer {token}` header from `SecureStorage`
   c. `NetworkExceptionInterceptor` — catches network exceptions, converts to HTTP error responses
   d. (Debug only) `HttpLoggingInterceptor` — logs request/response body
4. Retrofit deserializes JSON response to DTOs
5. Repository maps DTOs to domain models
6. ViewModel updates StateFlow
7. Composable recomposes

**WebSocket Connection Flow:**

1. `ConnectionOrchestrator.connect()` acquires reference on `WebSocketManager`
2. Reads server config from `ServerPreferences`
3. `WebSocketManager.connect()` builds WS URL (`ws://` or `wss://`) with token query param
4. OkHttp creates WebSocket with `WebSocketListener` callbacks
5. Server heartbeat: ping/pong messages (server sends `{"type":"ping"}`, client replies `{"type":"pong"}`)
6. Events parsed from JSON → `WsEventDto` → emitted to `SharedFlow`
7. `ConnectionOrchestrator` forwards events to ViewModel via `ConnectionEvent` sealed class
8. Reconnection: exponential backoff (2s initial, 30s max, 10 retries max)
9. Permanent failure → degrade to REST polling

**Server Configuration Flow:**

1. User enters IP:port or cloud URL on Connection screen
2. `ConnectionViewModel.connect()` calls `AuthRepository.verifyServer()`
3. `AuthRepositoryImpl` creates temporary Retrofit instance (no interceptors) for verification
4. `GET /api/v1/auth/verify` returns auth mode (Bypass or RequireToken)
5. If Bypass: save config and connect
6. If RequireToken: show token input, then save config
7. `ServerPreferences.saveServerConfig()` persists to DataStore + updates memory cache
8. Subsequent API calls use `BaseUrlInterceptor` to route to configured server

**State Management:**
- ViewModel-owned `MutableStateFlow` → `StateFlow` exposed to Composables
- `ServerPreferences` maintains `@Volatile` memory cache for synchronous reads by interceptors
- `WebSocketManager.connectionState` is a `StateFlow<ConnectionState>` sealed class

## Key Abstractions

**Repository Pattern:**
- Purpose: Decouple domain logic from data sources
- Examples: `DramaRepository`/`DramaRepositoryImpl`, `AuthRepository`/`AuthRepositoryImpl`, `ServerRepository`/`ServerRepositoryImpl`
- Pattern: Interface in domain layer, implementation in data layer, bound via Hilt

**Interceptor Chain:**
- Purpose: Cross-cutting HTTP concerns (URL routing, auth, error handling)
- Examples: `BaseUrlInterceptor`, `AuthInterceptor`, `NetworkExceptionInterceptor`
- Pattern: OkHttp Interceptor, order matters (BaseUrl → Auth → NetworkException → Logging)

**WebSocket Manager:**
- Purpose: Manage WebSocket lifecycle with reconnection, reference counting, and network awareness
- Examples: `WebSocketManager`
- Pattern: Activity-scoped singleton with reference counting (acquire/release), exponential backoff reconnection, ConnectivityManager NetworkCallback for network restoration

**Connection Orchestrator:**
- Purpose: Coordinate WebSocket connection for DramaDetail screen
- Examples: `ConnectionOrchestrator`
- Pattern: Injectable sub-component with SharedFlow event bus, bridges WS events to ViewModel

## Entry Points

**Application:**
- Location: `app/src/main/java/com/drama/app/DramaApplication.kt`
- Triggers: Android framework on app launch
- Responsibilities: Hilt initialization (`@HiltAndroidApp`)

**MainActivity:**
- Location: `app/src/main/java/com/drama/app/MainActivity.kt`
- Triggers: Launcher intent
- Responsibilities: Single-activity host for Compose navigation

**Connection Screen (User Entry):**
- Location: `app/src/main/java/com/drama/app/ui/screens/connection/`
- Triggers: First launch or disconnect
- Responsibilities: Server URL input, auth verification, token input, connection establishment

## Error Handling

**Strategy:** Multi-layer with conversion at boundaries

**Patterns:**
- `NetworkExceptionInterceptor` converts network exceptions (SocketTimeoutException → 504, UnknownHostException → 503, ConnectException → 503, SSLException → 503, IOException → 503) to synthetic HTTP responses with JSON error bodies
- `AuthRepositoryImpl.verifyServer()` catches exceptions and wraps in `Result.failure(Exception("ERROR_TYPE"))` where ERROR_TYPE is TIMEOUT/NETWORK_UNREACHABLE/AUTH_FAILED/UNKNOWN:code
- `DramaRepositoryImpl` uses `runCatching {}` for all API calls, converting Retrofit exceptions to `Result<T>`
- WebSocket failures are classified (connection refused, auth error, generic) and surfaced via `ConnectionState.Failed` sealed class
- `ConnectionStatus.Error` with `ErrorType` enum for UI-level error display

**The "UNKNOWN:504" error path:**
1. `NetworkExceptionInterceptor` catches `SocketTimeoutException` → builds response with code 504
2. Retrofit receives 504 response → throws `retrofit2.HttpException` with code 504
3. `AuthRepositoryImpl` catches `HttpException` → `Result.failure(Exception("UNKNOWN:504"))`
4. OR: Server-side `runner_utils.py` raises real HTTP 504 on command timeout
5. Either way, the client receives 504 and the error bubbles up as "UNKNOWN:504"

## Cross-Cutting Concerns

**Logging:** `android.util.Log` with tag constants per class; HttpLoggingInterceptor (BODY level) in debug builds only
**Validation:** Server URL validation via `toHttpUrlOrNull()` in BaseUrlInterceptor; auth verification before connection
**Authentication:** Bearer token via AuthInterceptor for REST, query param for WebSocket; encrypted storage via SecureStorage
**Network Security:** Dual network_security_config (strict for release, permissive for debug); `usesCleartextTraffic=false` in manifest
**Timeout Configuration:** connect=15s, read=300s (LLM calls), write=30s, pingInterval=60s (TCP keepalive)
**ProGuard:** Keep rules for DTO serialization, Retrofit interfaces, OkHttp interceptors, Hilt/Dagger, Compose

---

*Architecture analysis: 2026-04-27*
