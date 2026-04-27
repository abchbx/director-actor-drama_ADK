# Codebase Structure

**Analysis Date:** 2026-04-26

## Directory Layout

```
director-actor-drama/
├── android/                        # Android app (Kotlin + Jetpack Compose)
│   └── app/src/main/java/com/drama/app/
│       ├── data/                   # Data layer: API, WS, DTOs, Repository impls
│       │   ├── remote/
│       │   │   ├── api/            # Retrofit API service interfaces
│       │   │   ├── dto/            # Request/Response DTOs (kotlinx.serialization)
│       │   │   └── ws/             # WebSocketManager
│       │   └── repository/         # Repository implementations
│       ├── di/                     # Hilt DI modules
│       ├── domain/                 # Domain layer: models, repository interfaces
│       │   ├── model/              # Drama, SceneBubble, ActorInfo
│       │   └── repository/         # DramaRepository interface
│       └── ui/                     # Presentation layer
│           ├── screens/
│           │   ├── dramadetail/    # Main drama screen
│           │   │   └── components/ # TypingIndicator, ActorDrawer, etc.
│           │   ├── dramalist/      # Drama list screen
│           │   ├── settings/       # Server settings screen
│           │   └── createdrama/    # Create new drama screen
│           ├── navigation/         # NavHost, routes
│           └── theme/              # Material3 theme
├── app/                            # Python backend (FastAPI)
│   ├── api/                        # API layer
│   │   ├── routers/                # FastAPI routers (commands, queries, ws)
│   │   ├── models.py               # Pydantic request/response models
│   │   ├── event_mapper.py         # ADK events → 18 business event types
│   │   └── deps.py                 # FastAPI dependencies (auth, tool_context)
│   ├── agents/                     # ADK agent definitions
│   ├── state_manager.py            # Drama state management + tools
│   ├── tools.py                    # ADK tool definitions (export_drama, etc.)
│   ├── vector_memory.py            # ChromaDB-based actor memory
│   └── main.py                     # FastAPI app entry point
└── .planning/                      # GSD planning documents
    └── codebase/                   # Codebase analysis documents
```

## Directory Purposes

**`android/app/src/main/java/com/drama/app/data/remote/api/`:**
- Purpose: Retrofit API interface definitions
- Contains: `DramaApiService.kt` — all REST endpoints
- Key files: `DramaApiService.kt`

**`android/app/src/main/java/com/drama/app/data/remote/dto/`:**
- Purpose: Data transfer objects for API communication
- Contains: Request DTOs, Response DTOs, WsEventDto
- Key files: `WsEventDto.kt`, `RequestDtos.kt`, `ExportResponseDto.kt`

**`android/app/src/main/java/com/drama/app/data/remote/ws/`:**
- Purpose: WebSocket connection management
- Contains: WebSocketManager with reconnect, heartbeat, event emission
- Key files: `WebSocketManager.kt`

**`android/app/src/main/java/com/drama/app/data/repository/`:**
- Purpose: Repository pattern implementations
- Contains: DramaRepositoryImpl — maps DTOs to domain models
- Key files: `DramaRepositoryImpl.kt`

**`android/app/src/main/java/com/drama/app/domain/model/`:**
- Purpose: Domain model definitions
- Contains: SceneBubble (sealed class), Drama, ActorInfo
- Key files: `SceneBubble.kt`, `Drama.kt`, `ActorInfo.kt`

**`android/app/src/main/java/com/drama/app/ui/screens/dramadetail/`:**
- Purpose: Main drama interaction screen
- Contains: ViewModel (state + WS event handling), Screen composable, components
- Key files: `DramaDetailViewModel.kt`, `DramaDetailScreen.kt`

**`app/api/`:**
- Purpose: Backend HTTP/WS API layer
- Contains: Routers, models, event mapping
- Key files: `event_mapper.py`, `models.py`, `routers/commands.py`, `routers/queries.py`

**`app/`:**
- Purpose: Backend core logic
- Contains: State management, tool definitions, agent config, vector memory
- Key files: `state_manager.py`, `tools.py`, `vector_memory.py`

## Key File Locations

**Entry Points:**
- `android/app/src/main/java/com/drama/app/MainActivity.kt`: Android app entry
- `app/main.py`: Backend FastAPI server entry

**Configuration:**
- `android/app/build.gradle.kts`: Android build config
- `app/api/deps.py`: Backend dependency injection (auth, tool context)

**Core Logic:**
- `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt`: WS event handling, UI state management
- `app/api/event_mapper.py`: ADK events → business events mapping
- `app/tools.py`: All ADK tool definitions including export_drama
- `app/state_manager.py`: Drama state + export_script + export_conversations

**WS Event Models:**
- `android/app/src/main/java/com/drama/app/data/remote/dto/WsEventDto.kt`: Generic WsEventDto + ReplayMessageDto + HeartbeatMessageDto
- `app/api/models.py`: WsEvent Pydantic model

**API Layer:**
- `android/app/src/main/java/com/drama/app/data/remote/api/DramaApiService.kt`: All REST endpoints including export
- `app/api/routers/queries.py`: Backend query endpoints including /drama/export
- `app/api/routers/commands.py`: Backend command endpoints

**Testing:**
- No test directories found in main source paths

## Naming Conventions

**Files:**
- Kotlin: PascalCase matching class name: `DramaDetailViewModel.kt`, `WsEventDto.kt`
- Python: snake_case: `event_mapper.py`, `state_manager.py`

**Directories:**
- Kotlin packages: lowercase: `dramadetail/`, `remotedto/`
- Python: lowercase with underscores: `api/`, `routers/`

## Where to Add New Code

**New WS Event Handler:**
- Primary code: `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt` — add case to `handleWsEvent()` when block
- No DTO changes needed — `WsEventDto` is generic (type + data map)

**New REST API Endpoint:**
- API interface: `android/app/src/main/java/com/drama/app/data/remote/api/DramaApiService.kt`
- DTOs: `android/app/src/main/java/com/drama/app/data/remote/dto/`
- Repository interface: `android/app/src/main/java/com/drama/app/domain/repository/DramaRepository.kt`
- Repository impl: `android/app/src/main/java/com/drama/app/data/repository/DramaRepositoryImpl.kt`
- Backend router: `app/api/routers/commands.py` or `queries.py`
- Backend model: `app/api/models.py`

**New Overflow Menu Item:**
- Screen: `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailScreen.kt` — add `DropdownMenuItem` in `DropdownMenu` block (~line 282-293)
- ViewModel: Add action method + UI state field if needed

**New Export Feature:**
- Repository interface: Add `exportDrama()` method to `DramaRepository.kt`
- Repository impl: Implement in `DramaRepositoryImpl.kt` calling `dramaApiService.exportDrama()`
- ViewModel: Add export action + loading/success state
- Screen: Add export button to overflow menu
- DTO: `ExportRequestDto` and `ExportResponseDto` already exist

**Utilities:**
- Shared helpers: `android/app/src/main/java/com/drama/app/domain/usecase/`

## Special Directories

**`android/app/build/`:**
- Purpose: Build artifacts
- Generated: Yes
- Committed: No (gitignored)

**`.planning/`:**
- Purpose: GSD planning and analysis documents
- Generated: Yes (by GSD commands)
- Committed: Yes

---

*Structure analysis: 2026-04-26*
