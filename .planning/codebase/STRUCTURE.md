# Codebase Structure

**Analysis Date:** 2026-04-22

## Directory Layout

```
android/app/src/main/java/com/drama/app/
├── DramaApplication.kt              # Hilt Application class
├── MainActivity.kt                   # Single Activity, enableEdgeToEdge, NavHost setup
├── data/
│   ├── local/
│   │   └── ServerPreferences.kt      # DataStore for server config persistence
│   ├── remote/
│   │   ├── api/
│   │   │   ├── AuthApiService.kt     # Retrofit auth verification
│   │   │   └── DramaApiService.kt    # Retrofit drama CRUD + chat API
│   │   ├── dto/
│   │   │   ├── AuthVerifyResponseDto.kt
│   │   │   ├── CastResponseDto.kt
│   │   │   ├── CastStatusResponseDto.kt
│   │   │   ├── ChatRequestDto.kt
│   │   │   ├── CommandResponseDto.kt
│   │   │   ├── DeleteDramaResponseDto.kt
│   │   │   ├── DramaItemDto.kt
│   │   │   ├── DramaListResponseDto.kt
│   │   │   ├── DramaStatusResponseDto.kt
│   │   │   ├── ExportResponseDto.kt
│   │   │   ├── RequestDtos.kt        # StartDrama, Action, Speak, Save, Load, etc.
│   │   │   ├── SaveLoadResponseDto.kt
│   │   │   ├── SceneDto.kt
│   │   │   └── WsEventDto.kt
│   │   ├── interceptor/
│   │   │   └── AuthInterceptor.kt    # OkHttp interceptor for token auth
│   │   └── ws/
│   │       └── WebSocketManager.kt   # Global WS singleton with reconnect
│   └── repository/
│       ├── AuthRepositoryImpl.kt
│       ├── DramaRepositoryImpl.kt    # Implements DramaRepository via DramaApiService
│       └── ServerRepositoryImpl.kt
├── di/
│   ├── DataStoreModule.kt            # DataStore preferences DI
│   ├── DramaModule.kt                # Binds DramaRepository
│   └── NetworkModule.kt              # OkHttpClient, Retrofit, Json, WebSocketManager
├── domain/
│   ├── model/
│   │   ├── ActorInfo.kt
│   │   ├── AuthMode.kt
│   │   ├── CommandType.kt
│   │   ├── ConnectionStatus.kt
│   │   ├── Drama.kt                  # Drama data class (folder, theme, status, etc.)
│   │   ├── SceneBubble.kt            # Sealed class: Narration, Dialogue, UserMessage, ActorInteraction, SceneDivider
│   │   └── ServerConfig.kt
│   └── repository/
│       ├── AuthRepository.kt
│       ├── DramaRepository.kt        # Interface: startDrama, listDramas, loadDrama, sendChatMessage, etc.
│       └── ServerRepository.kt
└── ui/
    ├── components/
    │   └── AppBottomNavigationBar.kt  # Bottom nav: 戏剧/创建/设置
    ├── navigation/
    │   ├── DramaNavHost.kt           # NavHost with type-safe routes
    │   └── Route.kt                  # @Serializable route definitions
    ├── screens/
    │   ├── connection/
    │   │   ├── ConnectionGuideDialog.kt  # First-run server setup dialog
    │   │   └── ConnectionViewModel.kt    # Server connection logic
    │   ├── dramacreate/
    │   │   ├── DramaCreateScreen.kt      # Theme input + creation progress UI
    │   │   └── DramaCreateViewModel.kt   # Create drama, poll status, WS events, navigate on complete
    │   ├── dramadetail/
    │   │   ├── DramaDetailScreen.kt      # Chat UI with TopAppBar + SceneBubbleList + ChatInputBar
    │   │   ├── DramaDetailViewModel.kt   # Load drama, WS events, chat, scene history, actor panel
    │   │   └── components/
    │   │       ├── ActorCard.kt
    │   │       ├── ActorDrawerContent.kt
    │   │       ├── ActorInteractionBubble.kt
    │   │       ├── ChatInputBar.kt        # iMessage-style input with @mention, commands, IME padding
    │   │       ├── CommandInputBar.kt
    │   │       ├── DialogueBubble.kt
    │   │       ├── NarrationBubble.kt
    │   │       ├── SceneBubbleList.kt
    │   │       ├── SceneHistorySheet.kt
    │   │       ├── TensionIndicator.kt
    │   │       ├── TypingIndicator.kt
    │   │       └── UserMessageBubble.kt
    │   ├── dramalist/
    │   │   ├── DramaListScreen.kt        # Drama list with search, filter, batch select
    │   │   ├── DramaListScreen_append.kt # 1-byte placeholder
    │   │   └── DramaListViewModel.kt     # List, delete, load dramas
    │   └── settings/
    │       ├── SettingsScreen.kt
    │       └── SettingsViewModel.kt
    └── theme/
        ├── Color.kt
        ├── Theme.kt                   # Material3 theme + WindowCompat edge-to-edge
        └── Type.kt
```

## Directory Purposes

**`ui/screens/dramacreate/`:**
- Purpose: Drama creation flow — user enters theme, watches STORM progress, auto-navigates to detail
- Contains: Screen composable + ViewModel
- Key files: `DramaCreateViewModel.kt` (19KB — orchestration of create/poll/WS/navigate)

**`ui/screens/dramadetail/`:**
- Purpose: Main drama interaction screen — chat, scenes, actors, commands
- Contains: Screen composable + ViewModel + component composables
- Key files: `DramaDetailViewModel.kt` (39KB — largest file, handles all detail logic), `ChatInputBar.kt` (14KB)

**`ui/screens/dramalist/`:**
- Purpose: Drama list with CRUD — browse, search, filter, delete, load existing dramas
- Contains: Screen composable + ViewModel
- Key files: `DramaListScreen.kt` (33KB — complex list UI with selection mode)

**`data/remote/`:**
- Purpose: Network layer — Retrofit API service, DTOs, WebSocket, auth interceptor
- Contains: All API-facing code
- Key files: `WebSocketManager.kt` (global singleton), `DramaApiService.kt` (all REST endpoints)

## Key File Locations

**Entry Points:**
- `android/app/src/main/java/com/drama/app/MainActivity.kt`: Single Activity, sets up NavHost + Scaffold
- `android/app/src/main/java/com/drama/app/DramaApplication.kt`: Hilt application

**Navigation:**
- `android/app/src/main/java/com/drama/app/ui/navigation/Route.kt`: Route definitions (ConnectionGuide, DramaList, DramaCreate, Settings, DramaDetail(dramaId))
- `android/app/src/main/java/com/drama/app/ui/navigation/DramaNavHost.kt`: NavHost composable with all route → screen mappings

**Drama Creation:**
- `android/app/src/main/java/com/drama/app/ui/screens/dramacreate/DramaCreateViewModel.kt`: createDrama(), polling, WS events, navigateToDetail()
- `android/app/src/main/java/com/drama/app/ui/screens/dramacreate/DramaCreateScreen.kt`: Theme input form + progress UI

**Drama Detail / Chat:**
- `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt`: init→load→WS→polling, sendChatMessage(), handleWsEvent()
- `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailScreen.kt`: ModalNavigationDrawer + TopAppBar + SceneBubbleList + ChatInputBar
- `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/components/ChatInputBar.kt`: Input bar with @mention, /next /end commands, IME padding

**API / Repository:**
- `android/app/src/main/java/com/drama/app/domain/repository/DramaRepository.kt`: Interface
- `android/app/src/main/java/com/drama/app/data/repository/DramaRepositoryImpl.kt`: Implementation via DramaApiService
- `android/app/src/main/java/com/drama/app/data/remote/api/DramaApiService.kt`: Retrofit interface

**Configuration:**
- `android/app/src/main/AndroidManifest.xml`: No windowSoftInputMode set (defaults apply)
- `android/app/src/main/res/values/themes.xml`: Theme.DramaApp parent=android:Theme.Material.Light.NoActionBar
- `android/app/build.gradle.kts`: Build config, dependencies

**DI:**
- `android/app/src/main/java/com/drama/app/di/NetworkModule.kt`: OkHttpClient, Retrofit, Json, WebSocketManager
- `android/app/src/main/java/com/drama/app/di/DramaModule.kt`: Binds DramaRepository
- `android/app/src/main/java/com/drama/app/di/DataStoreModule.kt`: DataStore preferences

## Naming Conventions

**Files:**
- PascalCase matching class name: `DramaCreateViewModel.kt`, `ChatInputBar.kt`
- Screen files follow pattern: `{Feature}Screen.kt`, `{Feature}ViewModel.kt`
- Component files in subdirectory: `dramadetail/components/{ComponentName}.kt`

**Directories:**
- Feature-based: `dramacreate/`, `dramadetail/`, `dramalist/`, `settings/`, `connection/`
- Layer-based: `data/`, `domain/`, `ui/`, `di/`

## Where to Add New Code

**New Feature Screen:**
- Create directory: `android/app/src/main/java/com/drama/app/ui/screens/{feature}/`
- Add: `{Feature}Screen.kt`, `{Feature}ViewModel.kt`
- Add route in: `android/app/src/main/java/com/drama/app/ui/navigation/Route.kt`
- Add composable in: `android/app/src/main/java/com/drama/app/ui/navigation/DramaNavHost.kt`

**New API Endpoint:**
- Add method to: `android/app/src/main/java/com/drama/app/data/remote/api/DramaApiService.kt`
- Add DTO in: `android/app/src/main/java/com/drama/app/data/remote/dto/`
- Add method to interface: `android/app/src/main/java/com/drama/app/domain/repository/DramaRepository.kt`
- Add implementation: `android/app/src/main/java/com/drama/app/data/repository/DramaRepositoryImpl.kt`

**New Chat Bubble Type:**
- Add subclass to: `android/app/src/main/java/com/drama/app/domain/model/SceneBubble.kt`
- Add rendering in: `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/components/SceneBubbleList.kt`
- Handle WS event in: `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt`

**New Detail Component:**
- Add file in: `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/components/`

**Utilities:**
- Shared helpers should go in: `android/app/src/main/java/com/drama/app/` (top-level) or a new `util/` package

## Special Directories

**`android/app/src/main/res/`:**
- Purpose: Android resources (layouts, strings, icons, themes)
- Generated: No
- Committed: Yes

**`android/app/build/`:**
- Purpose: Build outputs (APK, intermediate files, KSP caches)
- Generated: Yes
- Committed: No (.gitignore)

**`android/app/src/main/java/com/drama/app/ui/screens/dramadetail/components/`:**
- Purpose: Reusable composables specific to drama detail screen (11 files)
- Contains: Bubble renderers, input bars, indicators, sheets

**`.planning/`:**
- Purpose: GSD planning documents
- Generated: By GSD commands
- Committed: Yes

---

*Structure analysis: 2026-04-22*
