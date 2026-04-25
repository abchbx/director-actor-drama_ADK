# Codebase Structure

**Analysis Date:** 2026-04-25

## Directory Layout

```
android/
├── app/
│   ├── build.gradle.kts              # App module build config (Compose, Hilt, etc.)
│   ├── proguard-rules.pro
│   └── src/main/
│       ├── AndroidManifest.xml        # Single Activity declaration
│       ├── java/com/drama/app/
│       │   ├── DramaApplication.kt    # Application class (@HiltAndroidApp)
│       │   ├── MainActivity.kt        # Single Activity + NavHost + BottomBar
│       │   ├── data/
│       │   │   ├── local/             # Local persistence (DataStore, SecureStorage)
│       │   │   ├── remote/            # Network layer (API, WebSocket, DTOs)
│       │   │   └── repository/        # Repository implementations
│       │   ├── di/                    # Hilt DI modules
│       │   ├── domain/
│       │   │   ├── model/             # Domain models (SceneBubble, ActorInfo, etc.)
│       │   │   ├── repository/        # Repository interfaces
│       │   │   └── usecase/           # Business use cases
│       │   └── ui/
│       │       ├── components/        # Shared UI components (MarkdownText, BottomBar)
│       │       ├── navigation/        # NavHost + Route definitions
│       │       ├── screens/           # Feature screens (each with ViewModel)
│       │       └── theme/             # Color, Theme, Typography definitions
│       └── res/
│           ├── drawable/              # Launcher icons
│           ├── mipmap-anydpi-v26/     # Adaptive icons
│           └── values/                # colors.xml, strings.xml, themes.xml
├── build.gradle.kts                  # Root build config
├── gradle/
│   └── libs.versions.toml            # Version catalog
└── settings.gradle.kts
```

## Directory Purposes

**`data/local/`:**
- Purpose: Local persistence layer
- Contains: `DramaSave.kt` (save model), `DramaSaveRepository.kt` (DataStore CRUD + bubble JSON encode/decode), `SecureStorage.kt` (encrypted prefs), `ServerPreferences.kt` (server config DataStore)
- Key files: `DramaSaveRepository.kt` (6.65KB), `ServerPreferences.kt` (2.06KB)

**`data/remote/api/`:**
- Purpose: Retrofit API service interfaces
- Contains: `DramaApiService.kt` (REST endpoints), `AuthApiService.kt`
- Key files: `DramaApiService.kt` (1.99KB)

**`data/remote/dto/`:**
- Purpose: Network request/response data transfer objects
- Contains: 12 DTO files for all API shapes
- Key files: `WsEventDto.kt`, `CommandResponseDto.kt`, `DramaStatusResponseDto.kt`, `ChatRequestDto.kt`, `SceneDto.kt`

**`data/remote/ws/`:**
- Purpose: WebSocket connection management
- Contains: `WebSocketManager.kt` (OkHttp WS client with auto-reconnect), `ConnectionState.kt` (sealed class)
- Key files: `WebSocketManager.kt` (15.98KB — largest file in data layer)

**`data/remote/interceptor/`:**
- Purpose: OkHttp network interceptors
- Contains: `AuthInterceptor.kt` (token injection), `NetworkExceptionInterceptor.kt` (error mapping)

**`data/repository/`:**
- Purpose: Repository pattern implementations
- Contains: `DramaRepositoryImpl.kt` (main business logic + DTO→domain mapping), `AuthRepositoryImpl.kt`, `ServerRepositoryImpl.kt`
- Key files: `DramaRepositoryImpl.kt` (10.76KB — contains `getSceneBubbles()`, `sendChatMessageAsBubbles()`, `getMergedCast()`)

**`di/`:**
- Purpose: Hilt dependency injection modules
- Contains: `NetworkModule.kt` (Retrofit + OkHttp + WS client), `DramaModule.kt` (repository bindings), `DataStoreModule.kt` (DataStore instances), `SavesDataStore.kt`

**`domain/model/`:**
- Purpose: Core business models — pure Kotlin, no framework dependencies
- Contains: `SceneBubble.kt` (sealed class hierarchy for all message types), `ActorInfo.kt`, `CommandType.kt`, `ConnectionStatus.kt`, `Drama.kt`, `ServerConfig.kt`, `AuthMode.kt`
- Key files: `SceneBubble.kt` (4.5KB — the central domain model)

**`domain/repository/`:**
- Purpose: Repository interface contracts
- Contains: `DramaRepository.kt`, `AuthRepository.kt`, `ServerRepository.kt`

**`domain/usecase/`:**
- Purpose: Business logic use cases
- Contains: `DetectActorInteractionUseCase.kt` (determines if dialogue should render as ActorInteraction bubble)

**`ui/components/`:**
- Purpose: Shared UI components used across screens
- Contains: `MarkdownText.kt` (custom Markdown renderer), `MarkdownConfig.kt` (config + color classes), `AppBottomNavigationBar.kt`
- Key files: `MarkdownText.kt` (12.78KB), `MarkdownConfig.kt` (7.08KB)

**`ui/navigation/`:**
- Purpose: Compose Navigation graph
- Contains: `DramaNavHost.kt` (NavHost with composable destinations), `Route.kt` (type-safe route definitions)

**`ui/screens/dramadetail/`:**
- Purpose: Drama detail chat screen — the primary user-facing feature
- Contains: `DramaDetailScreen.kt` (screen composable), `DramaDetailViewModel.kt` (state management + WS/REST coordination)
- Key files: `DramaDetailViewModel.kt` (51.19KB — largest file, ~1227 lines), `DramaDetailScreen.kt` (25.44KB)

**`ui/screens/dramadetail/components/`:**
- Purpose: Chat UI component composables
- Contains: 11 composable files for bubble types, input bars, indicators
- Key files: `SceneBubbleList.kt` (LazyColumn + animations), `DialogueBubble.kt`, `NarrationBubble.kt`, `ActorInteractionBubble.kt`, `UserMessageBubble.kt`, `ChatInputBar.kt`, `TypingIndicator.kt`

**`ui/theme/`:**
- Purpose: Material3 theme configuration
- Contains: `Color.kt` (drama-themed color palette + ActorPalette + MarkdownColors), `Theme.kt` (light/dark ColorScheme), `Type.kt` (typography)

## Key File Locations

**Entry Points:**
- `app/src/main/java/com/drama/app/MainActivity.kt`: Single Activity host
- `app/src/main/java/com/drama/app/DramaApplication.kt`: Hilt application

**Configuration:**
- `app/build.gradle.kts`: Module dependencies and Compose config
- `gradle/libs.versions.toml`: Version catalog
- `app/src/main/res/values/colors.xml`: XML color resources
- `app/src/main/res/values/themes.xml`: XML theme

**Core Logic:**
- `app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt`: Central state machine for drama chat
- `app/src/main/java/com/drama/app/data/repository/DramaRepositoryImpl.kt`: DTO→domain mapping + REST API calls
- `app/src/main/java/com/drama/app/data/remote/ws/WebSocketManager.kt`: WS lifecycle + auto-reconnect
- `app/src/main/java/com/drama/app/domain/model/SceneBubble.kt`: Message type hierarchy

**Testing:**
- No test files detected in the current codebase

## Naming Conventions

**Files:**
- PascalCase for Kotlin files matching class names: `DramaDetailViewModel.kt`, `SceneBubble.kt`
- Suffix conventions: `*Dto.kt` (DTOs), `*Repository.kt` (repos), `*Screen.kt` (screens), `*ViewModel.kt` (VMs), `*Bubble.kt` (composables), `*Bar.kt` (input bars), `*Indicator.kt` (indicators)
- Package structure mirrors clean architecture layers: `data/`, `domain/`, `ui/`, `di/`

**Directories:**
- Feature-based grouping under `ui/screens/`: `dramadetail/`, `dramalist/`, `dramacreate/`, `settings/`, `connection/`
- Sub-components grouped under feature: `dramadetail/components/`
- Data layer split by source: `data/local/`, `data/remote/`, `data/repository/`
- Remote split by type: `data/remote/api/`, `data/remote/dto/`, `data/remote/ws/`, `data/remote/interceptor/`

## Where to Add New Code

**New Feature:**
- Primary code: `ui/screens/<feature>/` (create new directory)
- ViewModel: `ui/screens/<feature>/<Feature>ViewModel.kt`
- Screen: `ui/screens/<feature>/<Feature>Screen.kt`
- Navigation route: `ui/navigation/Route.kt` (add `@Serializable` object/data class)
- NavHost registration: `ui/navigation/DramaNavHost.kt` (add `composable<Route>` block)

**New Bubble Type:**
- Domain model: `domain/model/SceneBubble.kt` (add new data class subtype)
- Composable: `ui/screens/dramadetail/components/<Type>Bubble.kt`
- SceneBubbleList dispatch: `ui/screens/dramadetail/components/SceneBubbleList.kt` (add `is SceneBubble.<Type>` branch)
- ViewModel handler: `ui/screens/dramadetail/DramaDetailViewModel.kt` (add event type in `handleWsEvent()`)

**New REST API Endpoint:**
- DTO: `data/remote/dto/<Name>Dto.kt`
- API service: `data/remote/api/DramaApiService.kt` (add @GET/@POST method)
- Repository interface: `domain/repository/DramaRepository.kt` (add method)
- Repository impl: `data/repository/DramaRepositoryImpl.kt` (implement method)

**New WS Event Type:**
- ViewModel handler: `ui/screens/dramadetail/DramaDetailViewModel.kt` (add `when` branch in `handleWsEvent()`)
- Backend mapper: `/workspace/director-actor-drama/app/api/event_mapper.py` (add to `TOOL_EVENT_MAP` + `_extract_call_data`/`_extract_response_data`)

**Utilities:**
- Shared helpers: `ui/components/` for shared Compose components
- Domain utilities: `domain/usecase/` for business logic

## Special Directories

**`app/build/`:**
- Purpose: Gradle build output (generated sources, intermediates, APKs)
- Generated: Yes
- Committed: No (should be in .gitignore)

**`app/src/main/res/`:**
- Purpose: Android resources (layouts, drawables, values)
- Generated: No
- Committed: Yes

---

*Structure analysis: 2026-04-25*
