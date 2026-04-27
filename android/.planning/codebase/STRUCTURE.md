# Codebase Structure

**Analysis Date:** 2026-04-27

## Directory Layout

```
android/
├── app/                          # Main application module
│   ├── build.gradle.kts          # App build config, dependencies, build variants
│   ├── proguard-rules.pro        # R8 keep rules (DTO, API, interceptors, Hilt, Compose)
│   ├── _fix_drama.py             # Dev utility script (not part of build)
│   ├── src/
│   │   ├── main/
│   │   │   ├── AndroidManifest.xml                   # App declaration, permissions, network security
│   │   │   ├── java/com/drama/app/
│   │   │   │   ├── DramaApplication.kt               # @HiltAndroidApp entry point
│   │   │   │   ├── MainActivity.kt                   # Single Activity, Compose host
│   │   │   │   ├── data/
│   │   │   │   │   ├── local/
│   │   │   │   │   │   ├── DramaSave.kt              # Save data model
│   │   │   │   │   │   ├── DramaSaveRepository.kt    # Save/load persistence
│   │   │   │   │   │   ├── SecureStorage.kt          # ★ Encrypted token storage
│   │   │   │   │   │   └── ServerPreferences.kt      # ★ Server URL config + memory cache
│   │   │   │   │   ├── remote/
│   │   │   │   │   │   ├── api/
│   │   │   │   │   │   │   ├── AuthApiService.kt     # Auth verification endpoint
│   │   │   │   │   │   │   └── DramaApiService.kt    # ★ All REST API endpoints
│   │   │   │   │   │   ├── dto/                      # 14 DTO files for API serialization
│   │   │   │   │   │   ├── interceptor/
│   │   │   │   │   │   │   ├── AuthInterceptor.kt    # ★ Bearer token injection
│   │   │   │   │   │   │   ├── BaseUrlInterceptor.kt # ★ Dynamic URL routing
│   │   │   │   │   │   │   └── NetworkExceptionInterceptor.kt # ★ Network error → HTTP response
│   │   │   │   │   │   └── ws/
│   │   │   │   │   │       ├── ConnectionState.kt    # ★ WS state sealed class
│   │   │   │   │   │       └── WebSocketManager.kt   # ★ WS lifecycle + reconnection
│   │   │   │   │   └── repository/
│   │   │   │   │       ├── AuthRepositoryImpl.kt     # ★ Server verification + error mapping
│   │   │   │   │       ├── DramaRepositoryImpl.kt    # API calls + DTO→domain mapping
│   │   │   │   │       └── ServerRepositoryImpl.kt   # Server config CRUD
│   │   │   │   ├── di/
│   │   │   │   │   ├── DataStoreModule.kt            # DataStore, ServerPreferences, repositories
│   │   │   │   │   ├── DramaModule.kt                # Binds DramaRepository
│   │   │   │   │   ├── NetworkModule.kt              # ★ OkHttp, Retrofit, API services, WS
│   │   │   │   │   └── SavesDataStore.kt             # @Qualifier annotation
│   │   │   │   ├── domain/
│   │   │   │   │   ├── model/                        # Domain models
│   │   │   │   │   │   ├── ActorInfo.kt
│   │   │   │   │   │   ├── AuthMode.kt
│   │   │   │   │   │   ├── CommandType.kt
│   │   │   │   │   │   ├── ConnectionStatus.kt       # ★ Error type enum
│   │   │   │   │   │   ├── Drama.kt
│   │   │   │   │   │   ├── SceneBubble.kt
│   │   │   │   │   │   └── ServerConfig.kt           # ★ URL builder (toApiBaseUrl, toWsUrl)
│   │   │   │   │   ├── repository/                   # Repository interfaces
│   │   │   │   │   │   ├── AuthRepository.kt
│   │   │   │   │   │   ├── DramaRepository.kt
│   │   │   │   │   │   └── ServerRepository.kt
│   │   │   │   │   └── usecase/
│   │   │   │   │       └── DetectActorInteractionUseCase.kt
│   │   │   │   └── ui/
│   │   │   │       ├── components/                   # Shared UI components
│   │   │   │       ├── navigation/                   # Compose navigation
│   │   │   │       ├── screens/                      # Feature screens
│   │   │   │       │   ├── connection/               # ★ Server connection UI
│   │   │   │       │   ├── dramacreate/              # Drama creation
│   │   │   │       │   └── dramadetail/              # Drama play screen
│   │   │   │       │       └── orchestrator/         # Sub-components
│   │   │   │       │           └── ConnectionOrchestrator.kt # ★ WS orchestration
│   │   │   │       └── theme/                        # Colors, theme, typography
│   │   │   └── res/
│   │   │       ├── xml/
│   │   │       │   ├── network_security_config.xml       # ★ Release: HTTPS-only
│   │   │       │   └── network_security_config_debug.xml # ★ Debug: allows cleartext
│   │   │       ├── values/
│   │   │       │   ├── strings.xml
│   │   │       │   ├── colors.xml
│   │   │       │   └── themes.xml
│   │   │       ├── drawable/                         # Launcher icons (XML)
│   │   │       └── mipmap-anydpi-v26/                # Adaptive icons
│   │   └── test/java/com/drama/app/
│   │       ├── MainDispatcherRule.kt                 # Test coroutine dispatcher rule
│   │       ├── data/remote/interceptor/
│   │       │   └── BaseUrlInterceptorTest.kt         # ★ URL routing tests
│   │       └── ui/screens/dramadetail/orchestrator/
│   │           ├── BubbleMergerTest.kt
│   │           ├── CommandRouterTest.kt
│   │           └── ConnectionOrchestratorTest.kt
├── build.gradle.kts             # Project-level build config
├── settings.gradle.kts          # Module includes
├── gradle.properties            # Gradle properties
├── gradle/
│   └── libs.versions.toml       # ★ Version catalog (all dependency versions)
├── build_apk.sh                 # Debug APK build script
├── gradlew / gradlew.bat        # Gradle wrapper
└── local.properties             # SDK path (gitignored)
```

## Directory Purposes

**`data/local/`:**
- Purpose: Local data persistence layer
- Contains: DataStore repositories, secure storage, preference models
- Key files: `ServerPreferences.kt` (server URL config), `SecureStorage.kt` (token encryption)

**`data/remote/`:**
- Purpose: Network communication layer
- Contains: API service interfaces, DTOs, OkHttp interceptors, WebSocket manager
- Key files: `NetworkModule.kt` (DI wiring), interceptors, `WebSocketManager.kt`

**`data/remote/interceptor/`:**
- Purpose: Cross-cutting HTTP concerns
- Contains: 3 interceptors in chain order: BaseUrl → Auth → NetworkException
- Key files: All 3 interceptors are critical for network behavior

**`data/remote/api/`:**
- Purpose: Retrofit API interface definitions
- Contains: `DramaApiService` (all drama endpoints), `AuthApiService` (verification)

**`data/remote/dto/`:**
- Purpose: Data transfer objects for API serialization
- Contains: 14 DTO files with `@Serializable` annotations
- Key files: `WsEventDto.kt` (WebSocket events), `CommandResponseDto.kt` (command results)

**`data/remote/ws/`:**
- Purpose: WebSocket connection management
- Contains: `WebSocketManager` (lifecycle, reconnection, heartbeat), `ConnectionState` (sealed class)

**`di/`:**
- Purpose: Hilt dependency injection modules
- Contains: Network, DataStore, Drama modules + qualifier annotations
- Key files: `NetworkModule.kt` (OkHttp + Retrofit + WS configuration)

**`domain/model/`:**
- Purpose: Business domain models
- Contains: Data classes and sealed classes representing core concepts
- Key files: `ServerConfig.kt` (URL builders), `ConnectionStatus.kt` (error types)

**`domain/repository/`:**
- Purpose: Repository interfaces (dependency inversion)
- Contains: 3 repository interfaces implemented by data layer

## Key File Locations

**Entry Points:**
- `app/src/main/java/com/drama/app/DramaApplication.kt`: Hilt application
- `app/src/main/java/com/drama/app/MainActivity.kt`: Compose host activity

**Network Configuration:**
- `app/src/main/java/com/drama/app/di/NetworkModule.kt`: OkHttpClient, Retrofit, timeout config
- `app/src/main/java/com/drama/app/data/remote/interceptor/BaseUrlInterceptor.kt`: Dynamic URL routing
- `app/src/main/java/com/drama/app/data/remote/interceptor/AuthInterceptor.kt`: Token injection
- `app/src/main/java/com/drama/app/data/remote/interceptor/NetworkExceptionInterceptor.kt`: Error conversion (504/503)
- `app/src/main/res/xml/network_security_config.xml`: Release security (HTTPS-only)
- `app/src/main/res/xml/network_security_config_debug.xml`: Debug security (allows cleartext)

**Server URL Configuration:**
- `app/src/main/java/com/drama/app/data/local/ServerPreferences.kt`: URL storage + memory cache
- `app/src/main/java/com/drama/app/domain/model/ServerConfig.kt`: URL builder logic
- `app/src/main/java/com/drama/app/data/local/SecureStorage.kt`: Token encryption
- Default fallback URL: `http://127.0.0.1:8000/api/v1/` (in ServerPreferences.currentApiBaseUrl())

**WebSocket:**
- `app/src/main/java/com/drama/app/data/remote/ws/WebSocketManager.kt`: Full WS lifecycle
- `app/src/main/java/com/drama/app/data/remote/ws/ConnectionState.kt`: Connection state sealed class
- `app/src/main/java/com/drama/app/ui/screens/dramadetail/orchestrator/ConnectionOrchestrator.kt`: WS orchestration

**Error Handling:**
- `app/src/main/java/com/drama/app/data/remote/interceptor/NetworkExceptionInterceptor.kt`: Network → HTTP error
- `app/src/main/java/com/drama/app/data/repository/AuthRepositoryImpl.kt`: UNKNOWN:code pattern
- `app/src/main/java/com/drama/app/domain/model/ConnectionStatus.kt`: ErrorType enum

**Configuration:**
- `app/build.gradle.kts`: Build variants, network security config placeholders
- `gradle/libs.versions.toml`: All dependency versions
- `app/proguard-rules.pro`: R8 keep rules
- `app/src/main/AndroidManifest.xml`: Permissions, cleartext traffic, network security reference

**Testing:**
- `app/src/test/java/com/drama/app/data/remote/interceptor/BaseUrlInterceptorTest.kt`: Interceptor tests
- `app/src/test/java/com/drama/app/ui/screens/dramadetail/orchestrator/`: Orchestrator tests

## Naming Conventions

**Files:**
- Kotlin files: PascalCase matching class name (`NetworkModule.kt`, `BaseUrlInterceptor.kt`)
- DTOs: Suffix `Dto` (`CommandResponseDto.kt`, `WsEventDto.kt`)
- Repository impls: Suffix `Impl` (`AuthRepositoryImpl.kt`)
- XML resources: snake_case (`network_security_config.xml`)

**Directories:**
- Feature-based: `screens/{feature}/`
- Layer-based: `data/`, `domain/`, `di/`, `ui/`

## Where to Add New Code

**New API Endpoint:**
- Add method to `DramaApiService.kt` (or new API service interface)
- Add request/response DTOs in `data/remote/dto/`
- Add ProGuard keep rules in `proguard-rules.pro` if new DTO/serializable classes

**New Interceptor:**
- Create class in `data/remote/interceptor/` implementing `okhttp3.Interceptor`
- Add to chain in `NetworkModule.provideOkHttpClient()` (order matters!)
- Add ProGuard keep rule for the new interceptor class

**New Repository:**
- Interface in `domain/repository/`
- Implementation in `data/repository/`
- Bind in `di/DataStoreModule.kt` or create new Hilt module

**New Network-Related Model:**
- Domain model in `domain/model/`
- DTO in `data/remote/dto/` with `@Serializable`
- Mapping logic in repository implementation

**New Test:**
- Co-located in `src/test/` mirroring `src/main/` package structure
- Use `MainDispatcherRule` for coroutine testing
- Use MockWebServer for HTTP testing

## Special Directories

**`build/`:**
- Purpose: Build artifacts (generated sources, intermediates, outputs)
- Generated: Yes (by Gradle/AGP)
- Committed: No (gitignored)

**`.kotlin/`:**
- Purpose: Kotlin compiler caches
- Generated: Yes
- Committed: No

---

*Structure analysis: 2026-04-27*
