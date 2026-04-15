# Requirements: Director-Actor-Drama v2.0 Android 移动端

**Defined:** 2026-04-14
**Core Value:** 无限畅写，逻辑不断

## v2 Requirements

Requirements for C/S architecture: FastAPI API Server + Android (Kotlin/Jetpack Compose) client.

### API Foundation

- [x] **API-01**: FastAPI application wraps existing DramaRouter without modifying 12 core modules
- [x] **API-02**: 14 REST endpoints map all CLI commands (start, next, action, speak, cast, status, save, load, export, end, list, storm, auto_advance, steer). Note: `/quit` is a program exit command handled by process lifecycle, not a REST endpoint; `/storm` (trigger_storm) maps to `POST /api/v1/drama/storm` instead.
- [x] **API-03**: Pydantic v2 models define request/response schemas for all endpoints
- [x] **API-04**: API versioning via URL prefix `/api/v1/`
- [x] **API-05**: CORS middleware allows Android app origin

### WebSocket Real-time Push

- [ ] **WS-01**: WebSocket endpoint at `/api/v1/ws` receives real-time scene events
- [ ] **WS-02**: 18 event types: scene_start, narration, dialogue, scene_end, tension_update, actor_created, actor_status, storm_discover, storm_research, storm_outline, error, typing, status, cast_update, progress, save_confirm, load_confirm, end_narration
- [ ] **WS-03**: EventBridge observes ADK Runner event stream without modifying tool code
- [ ] **WS-04**: 100-event replay buffer for reconnected clients to catch up
- [ ] **WS-05**: WebSocket connection lifecycle management (connect, heartbeat, disconnect, reconnect)

### Authentication

- [ ] **AUTH-01**: Server generates API token on first connection request
- [ ] **AUTH-02**: All REST endpoints require Bearer token in Authorization header
- [ ] **AUTH-03**: WebSocket accepts token via query parameter on handshake
- [ ] **AUTH-04**: Token validation uses FastAPI HTTPBearer dependency

### State Migration

- [x] **STATE-01**: `_current_drama_folder` global variable migrated to session-scoped context
- [x] **STATE-02**: Debounce flush-on-push: state is force-saved before WebSocket push events
- [x] **STATE-03**: API server supports one active drama session at a time (single-user mode preserved)

### Android App — Core

- [ ] **APP-01**: App connects to backend server via IP:port configuration
- [ ] **APP-02**: Drama creation screen with theme input, triggers STORM discovery
- [ ] **APP-03**: Drama list screen shows all saved dramas with load/resume/delete actions
- [ ] **APP-04**: Main drama screen displays current scene with real-time WebSocket updates
- [ ] **APP-05**: Command input bar supports /next, /action, /speak, /end commands
- [ ] **APP-06**: Scene history scrollable list with timeline navigation

### Android App — Features

- [ ] **APP-07**: Actor panel shows cast list with A2A service status and memory summary
- [ ] **APP-08**: Drama status overview (current scene, tension score, arc progress, time period)
- [ ] **APP-09**: Script export to local file (Markdown format)
- [ ] **APP-10**: Typing indicator displays during LLM generation (10-30s waits)
- [ ] **APP-11**: Rich scene display with character name highlights and emotion tags
- [ ] **APP-12**: Save/load drama with confirmation feedback

### Android App — Infrastructure

- [ ] **APP-13**: MVVM architecture with Repository pattern
- [ ] **APP-14**: Hilt dependency injection
- [ ] **APP-15**: WebSocket auto-reconnect with exponential backoff on network change
- [ ] **APP-16**: Material Design 3 theming with dynamic colors and dark mode

## v2+ Requirements

Deferred to future release.

### Multi-user

- **MULTI-01**: User registration and login
- **MULTI-02**: Concurrent drama sessions per user
- **MULTI-03**: Session isolation with per-user state

### Enhanced Features

- **ENH-01**: Push notifications (FCM) for scene events
- **ENH-02**: Voice input for commands
- **ENH-03**: iOS client (Swift/SwiftUI)
- **ENH-04**: Offline scene browsing with local cache

## Out of Scope

| Feature | Reason |
|---------|--------|
| In-app LLM model selection | Uses server-side default model configuration |
| Offline mode | Backend is the sole compute source (LLM + A2A), offline is meaningless |
| OAuth/registration system | Simple token sufficient for single-user/LAN scenario |
| FCM push notifications | WebSocket provides real-time push, no need for FCM |
| gRPC | REST + WebSocket sufficient, gRPC adds protobuf complexity |
| GraphQL | REST sufficient for command-style API, GraphQL overkill |
| Database | File-based JSON persistence works well, no ORM needed |
| Multi-user collaboration | A2A isolation design doesn't support shared sessions |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| API-01 | 13 | ✅ Done (13-01) |
| API-02 | 13 | Mapped |
| API-03 | 13 | ✅ Done (13-01) |
| API-04 | 13 | ✅ Done (13-01) |
| API-05 | 13 | ✅ Done (13-01) |
| WS-01 | 14 | Mapped |
| WS-02 | 14 | Mapped |
| WS-03 | 14 | Mapped |
| WS-04 | 14 | Mapped |
| WS-05 | 14 | Mapped |
| AUTH-01 | 15 | Mapped |
| AUTH-02 | 15 | Mapped |
| AUTH-03 | 15 | Mapped |
| AUTH-04 | 15 | Mapped |
| STATE-01 | 13 | Mapped |
| STATE-02 | 13 | Mapped |
| STATE-03 | 13 | Mapped |
| APP-01 | 16 | Mapped |
| APP-02 | 17 | Mapped |
| APP-03 | 17 | Mapped |
| APP-04 | 17 | Mapped |
| APP-05 | 17 | Mapped |
| APP-06 | 17 | Mapped |
| APP-07 | 18 | Mapped |
| APP-08 | 18 | Mapped |
| APP-09 | 18 | Mapped |
| APP-10 | 18 | Mapped |
| APP-11 | 18 | Mapped |
| APP-12 | 17 | Mapped |
| APP-13 | 16 | Mapped |
| APP-14 | 16 | Mapped |
| APP-15 | 18 | Mapped |
| APP-16 | 16 | Mapped |

**Coverage:**
- v2 requirements: 32 total
- Mapped to phases: 32 ✅
- Unmapped: 0

---
*Requirements defined: 2026-04-14*
*Last updated: 2026-04-14 after roadmap creation*
