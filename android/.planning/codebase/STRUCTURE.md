# Codebase Structure

**Analysis Date:** 2026-04-24

## Directory Layout

```
android/
├── app/                              # Main application module
│   ├── build.gradle.kts              # App-level Gradle config (deps, SDK versions)
│   ├── proguard-rules.pro            # ProGuard rules (currently minimal)
│   ├── _fix_drama.py                 # Utility script (not part of build)
│   └── src/main/
│       ├── AndroidManifest.xml       # App manifest (MainActivity, internet permission)
│       ├── java/com/drama/app/
│       │   ├── DramaApplication.kt   # @HiltAndroidApp entry
│       │   ├── MainActivity.kt       # Single Activity, Compose host
│       │   ├── data/                 # Data layer
│       │   │   ├── local/            # Local storage
│       │   │   ├── remote/           # Network layer
│       │   │   └── repository/       # Repository implementations
│       │   ├── di/                   # Hilt DI modules
│       │   ├── domain/               # Domain layer
│       │   │   ├── model/            # Business models
│       │   │   ├── repository/       # Repository interfaces
│       │   │   └── usecase/          # Use case classes
│       │   └── ui/                   # Presentation layer
│       │       ├── components/       # Shared UI components
│       │       ├── navigation/       # NavHost and route definitions
│       │       ├── screens/          # Screen composables + ViewModels
│       │       └── theme/            # Material3 theme
│       └── res/                      # Android resources
├── gradle/
│   ├── libs.versions.toml            # Version catalog
│   └── wrapper/                      # Gradle wrapper
├── build.gradle.kts                  # Root Gradle config
├── settings.gradle.kts               # Module declaration
├── build_apk.sh                      # Build script
└── .planning/codebase/               # Codebase analysis docs
```

## Directory Purposes

**`data/local/`:**
- Purpose: On-device persistent storage
- Contains: `SecureStorage.kt` (encrypted token), `ServerPreferences.kt` (DataStore server config)
- Key files: `SecureStorage.kt`, `ServerPreferences.kt`

**`data/remote/api/`:**
- Purpose: Retrofit API service interfaces
- Contains: `DramaApiService.kt` (all drama endpoints), `AuthApiService.kt` (token verification)
- Key files: `DramaApiService.kt`, `AuthApiService.kt`

**`data/remote/dto/`:**
- Purpose: Data Transfer Objects for API serialization
- Contains: All request/response DTOs (11 files)
- Key files: `WsEventDto.kt`, `CommandResponseDto.kt`, `DramaStatusResponseDto.kt`, `RequestDtos.kt`, `ChatRequestDto.kt`

**`data/remote/interceptor/`:**
- Purpose: OkHttp interceptors for cross-cutting network concerns
- Contains: `AuthInterceptor.kt` (token injection), `NetworkExceptionInterceptor.kt` (error conversion)
- Key files: `AuthInterceptor.kt`, `NetworkExceptionInterceptor.kt`

**`data/remote/ws/`:**
- Purpose: WebSocket connection management
- Contains: `WebSocketManager.kt` (connect, disconnect, reconnect, event flow)
- Key files: `WebSocketManager.kt`

**`data/repository/`:**
- Purpose: Repository pattern implementations
- Contains: `DramaRepositoryImpl.kt`, `AuthRepositoryImpl.kt`, `ServerRepositoryImpl.kt`
- Key files: `DramaRepositoryImpl.kt` (largest file, ~278 lines, maps DTOs ↔ domain models)

**`domain/model/`:**
- Purpose: Core business models (pure Kotlin, no Android/framework dependencies)
- Contains: 7 model files
- Key files: `SceneBubble.kt`, `CommandType.kt`, `ServerConfig.kt`, `ConnectionStatus.kt`

**`domain/repository/`:**
- Purpose: Repository interface contracts
- Contains: `DramaRepository.kt`, `AuthRepository.kt`, `ServerRepository.kt`
- Key files: `DramaRepository.kt` (16 methods)

**`domain/usecase/`:**
- Purpose: Business logic use cases
- Contains: `DetectActorInteractionUseCase.kt`
- Key files: `DetectActorInteractionUseCase.kt`

**`di/`:**
- Purpose: Hilt dependency injection modules
- Contains: `NetworkModule.kt`, `DataStoreModule.kt`, `DramaModule.kt`
- Key files: `NetworkModule.kt` (Retrofit, OkHttp, WebSocketManager providers)

**`ui/screens/dramacreate/`:**
- Purpose: Drama creation screen (STORM workflow)
- Contains: `DramaCreateScreen.kt`, `DramaCreateViewModel.kt`
- Key files: `DramaCreateViewModel.kt` (534 lines — most complex ViewModel)

**`ui/screens/dramadetail/`:**
- Purpose: Drama detail/conversation screen (chat interface)
- Contains: `DramaDetailScreen.kt`, `DramaDetailViewModel.kt`, `components/` subdirectory
- Key files: `DramaDetailViewModel.kt` (877 lines — largest file), `DramaDetailScreen.kt`

**`ui/screens/dramadetail/components/`:**
- Purpose: Composable sub-components for the detail screen
- Contains: 12 composable files
- Key files: `ChatInputBar.kt`, `SceneBubbleList.kt`, `DialogueBubble.kt`, `ActorDrawerContent.kt`

**`ui/screens/dramalist/`:**
- Purpose: Drama list browser screen
- Contains: `DramaListScreen.kt`, `DramaListViewModel.kt`, `DramaListScreen_append.kt` (placeholder)
- Key files: `DramaListScreen.kt` (32KB — most complex screen composable)

**`ui/screens/connection/`:**
- Purpose: Server connection guide dialog
- Contains: `ConnectionGuideDialog.kt`, `ConnectionViewModel.kt`
- Key files: `ConnectionViewModel.kt`

**`ui/screens/settings/`:**
- Purpose: App settings screen
- Contains: `SettingsScreen.kt`, `SettingsViewModel.kt`
- Key files: `SettingsScreen.kt`

**`ui/components/`:**
- Purpose: Shared composable components
- Contains: `AppBottomNavigationBar.kt`, `MarkdownConfig.kt`, `MarkdownText.kt`
- Key files: `MarkdownText.kt` (12.78KB), `AppBottomNavigationBar.kt`

**`ui/navigation/`:**
- Purpose: Navigation graph definition
- Contains: `DramaNavHost.kt`, `Route.kt`
- Key files: `Route.kt` (5 route definitions), `DramaNavHost.kt`

**`ui/theme/`:**
- Purpose: Material3 theme definition
- Contains: `Color.kt`, `Theme.kt`, `Type.kt`
- Key files: `Color.kt`, `Theme.kt`

## Key File Locations

**Entry Points:**
- `app/src/main/java/com/drama/app/DramaApplication.kt`: Hilt application
- `app/src/main/java/com/drama/app/MainActivity.kt`: Single Activity, Compose host, start destination logic
- `app/src/main/AndroidManifest.xml`: Manifest with `INTERNET` permission

**Navigation:**
- `app/src/main/java/com/drama/app/ui/navigation/Route.kt`: Route definitions (ConnectionGuide, DramaList, DramaCreate, Settings, DramaDetail)
- `app/src/main/java/com/drama/app/ui/navigation/DramaNavHost.kt`: NavHost composable

**"开始剧本" Flow:**
- `app/src/main/java/com/drama/app/ui/screens/dramacreate/DramaCreateScreen.kt`: "开始创作" button (line 217), theme input
- `app/src/main/java/com/drama/app/ui/screens/dramacreate/DramaCreateViewModel.kt`: `createDrama()` method, WS+REST+polling orchestration
- `app/src/main/java/com/drama/app/domain/repository/DramaRepository.kt`: `startDrama()` interface method
- `app/src/main/java/com/drama/app/data/repository/DramaRepositoryImpl.kt`: `startDrama()` implementation
- `app/src/main/java/com/drama/app/data/remote/api/DramaApiService.kt`: `POST drama/start` endpoint
- `app/src/main/java/com/drama/app/data/remote/dto/RequestDtos.kt`: `StartDramaRequestDto`

**WebSocket & REST Connection:**
- `app/src/main/java/com/drama/app/data/remote/ws/WebSocketManager.kt`: WS connect/disconnect/reconnect, event flow
- `app/src/main/java/com/drama/app/data/remote/api/DramaApiService.kt`: All REST endpoints
- `app/src/main/java/com/drama/app/data/remote/api/AuthApiService.kt`: Auth verification endpoint
- `app/src/main/java/com/drama/app/di/NetworkModule.kt`: OkHttp, Retrofit, WebSocketManager providers
- `app/src/main/java/com/drama/app/data/remote/interceptor/AuthInterceptor.kt`: Token injection
- `app/src/main/java/com/drama/app/data/remote/interceptor/NetworkExceptionInterceptor.kt`: Error conversion
- `app/src/main/java/com/drama/app/domain/model/ServerConfig.kt`: `toApiBaseUrl()`, `toWsUrl()` methods

**Conversation/Chat Screen:**
- `app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailScreen.kt`: Chat UI layout, TopAppBar, bubble list, ChatInputBar
- `app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt`: WS event handling, chat/command send, state management
- `app/src/main/java/com/drama/app/ui/screens/dramadetail/components/ChatInputBar.kt`: Message input with @mention chips
- `app/src/main/java/com/drama/app/ui/screens/dramadetail/components/CommandInputBar.kt`: Slash command input
- `app/src/main/java/com/drama/app/ui/screens/dramadetail/components/SceneBubbleList.kt`: Bubble list rendering
- `app/src/main/java/com/drama/app/ui/screens/dramadetail/components/DialogueBubble.kt`: Actor dialogue bubble
- `app/src/main/java/com/drama/app/ui/screens/dramadetail/components/NarrationBubble.kt`: Narration bubble
- `app/src/main/java/com/drama/app/ui/screens/dramadetail/components/UserMessageBubble.kt`: User message bubble
- `app/src/main/java/com/drama/app/ui/screens/dramadetail/components/ActorInteractionBubble.kt`: A2A interaction bubble
- `app/src/main/java/com/drama/app/ui/screens/dramadetail/components/ActorDrawerContent.kt`: Actor panel drawer
- `app/src/main/java/com/drama/app/ui/screens/dramadetail/components/SceneHistorySheet.kt`: Scene history bottom sheet

**ViewModels:**
- `app/src/main/java/com/drama/app/ui/screens/dramacreate/DramaCreateViewModel.kt`: Script creation orchestration
- `app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt`: Chat/conversation state & commands
- `app/src/main/java/com/drama/app/ui/screens/dramalist/DramaListViewModel.kt`: Drama list browsing
- `app/src/main/java/com/drama/app/ui/screens/connection/ConnectionViewModel.kt`: Server connection & auth
- `app/src/main/java/com/drama/app/ui/screens/settings/SettingsViewModel.kt`: Settings state

**API Service Definitions:**
- `app/src/main/java/com/drama/app/data/remote/api/DramaApiService.kt`: 16 endpoints (start, next, action, speak, steer, auto, storm, chat, end, status, cast, cast/status, list, save, load, export, scenes, scenes/{n})
- `app/src/main/java/com/drama/app/data/remote/api/AuthApiService.kt`: 1 endpoint (auth/verify)

**Domain Models:**
- `app/src/main/java/com/drama/app/domain/model/SceneBubble.kt`: Sealed class hierarchy (Narration, Dialogue, UserMessage, ActorInteraction, SceneDivider)
- `app/src/main/java/com/drama/app/domain/model/CommandType.kt`: Command enum (NEXT, ACTION, SPEAK, END, FREE_TEXT)
- `app/src/main/java/com/drama/app/domain/model/ServerConfig.kt`: Server connection config with URL builders
- `app/src/main/java/com/drama/app/domain/model/ConnectionStatus.kt`: Connection state sealed class
- `app/src/main/java/com/drama/app/domain/model/AuthMode.kt`: Auth mode sealed class
- `app/src/main/java/com/drama/app/domain/model/ActorInfo.kt`: Actor data model
- `app/src/main/java/com/drama/app/domain/model/Drama.kt`: Drama list item model

**Configuration:**
- `app/build.gradle.kts`: App build config (compileSdk 35, minSdk 26, compose, hilt, serialization)
- `gradle/libs.versions.toml`: Version catalog (all dependency versions)
- `build.gradle.kts`: Root build config
- `settings.gradle.kts`: Module declaration

**Testing:**
- Not yet present (no test source directories found)

## Naming Conventions

**Files:**
- Screen composables: `{Feature}Screen.kt` (e.g., `DramaCreateScreen.kt`)
- ViewModels: `{Feature}ViewModel.kt` (e.g., `DramaCreateViewModel.kt`)
- DTOs: `{Entity}{Request|Response}Dto.kt` or `{Entity}Dto.kt`
- Repository interfaces: `{Entity}Repository.kt`
- Repository implementations: `{Entity}RepositoryImpl.kt`
- API services: `{Entity}ApiService.kt`
- UI components: `{ComponentName}.kt` (PascalCase)
- DI modules: `{Concern}Module.kt`

**Directories:**
- Screen packages: `ui/screens/{feature}/` (lowercase)
- Sub-components: `ui/screens/{feature}/components/`
- Feature packages use lowercase single word: `dramacreate`, `dramadetail`, `dramalist`

## Where to Add New Code

**New Screen:**
- Screen composable: `app/src/main/java/com/drama/app/ui/screens/{feature}/{Feature}Screen.kt`
- ViewModel: `app/src/main/java/com/drama/app/ui/screens/{feature}/{Feature}ViewModel.kt`
- Route: Add `@Serializable` object to `app/src/main/java/com/drama/app/ui/navigation/Route.kt`
- NavHost entry: Add `composable<Route>` to `app/src/main/java/com/drama/app/ui/navigation/DramaNavHost.kt`
- Bottom nav (if tab): Add `BottomNavItem` to `app/src/main/java/com/drama/app/ui/components/AppBottomNavigationBar.kt`

**New API Endpoint:**
- Method in `app/src/main/java/com/drama/app/data/remote/api/DramaApiService.kt`
- Request DTO in `app/src/main/java/com/drama/app/data/remote/dto/RequestDtos.kt` (or separate file)
- Response DTO in `app/src/main/java/com/drama/app/data/remote/dto/{Entity}ResponseDto.kt`
- Repository interface method in `app/src/main/java/com/drama/app/domain/repository/DramaRepository.kt`
- Repository implementation in `app/src/main/java/com/drama/app/data/repository/DramaRepositoryImpl.kt`

**New WS Event Type:**
- Handle in `DramaCreateViewModel.handleStormEvent()` and/or `DramaDetailViewModel.handleWsEvent()`
- Both in their respective `ui/screens/{feature}/` directories

**New Domain Model:**
- `app/src/main/java/com/drama/app/domain/model/{ModelName}.kt`

**New Bubble Type:**
- Add subtype to `app/src/main/java/com/drama/app/domain/model/SceneBubble.kt`
- Add rendering in `app/src/main/java/com/drama/app/ui/screens/dramadetail/components/SceneBubbleList.kt`
- Create dedicated component: `app/src/main/java/com/drama/app/ui/screens/dramadetail/components/{BubbleType}Bubble.kt`

**New Use Case:**
- `app/src/main/java/com/drama/app/domain/usecase/{UseCaseName}.kt`

**New DI Binding:**
- Interface binding: Add to `app/src/main/java/com/drama/app/di/DramaModule.kt`
- Infrastructure providers: Add to `app/src/main/java/com/drama/app/di/NetworkModule.kt` or `DataStoreModule.kt`

**Utilities:**
- Shared helpers: Not yet established; consider `app/src/main/java/com/drama/app/util/`

## Special Directories

**`.planning/codebase/`:**
- Purpose: Codebase analysis documents (this file and siblings)
- Generated: Yes (by GSD mapping tools)
- Committed: Yes

**`app/build/`:**
- Purpose: Gradle build outputs
- Generated: Yes
- Committed: No (gitignored)

**`app/src/main/res/`:**
- Purpose: Android resources (drawables, strings, themes)
- Contains: Launcher icons, color definitions, string resources, theme XML
- Generated: No
- Committed: Yes
