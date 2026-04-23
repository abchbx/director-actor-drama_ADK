# External Integrations

**Analysis Date:** 2026-04-22

## APIs & External Services

**Backend REST API (FastAPI):**
- Base URL: `http://{serverIp}:{serverPort}/api/v1/` (user-configured)
- SDK/Client: Retrofit (`DramaApiService`)
- Auth: Token via `AuthInterceptor` (reads from `ServerPreferences` DataStore)

**WebSocket Server:**
- URL: `ws://{serverIp}:{serverPort}/api/v1/ws?token={token}` (or `wss://` if baseUrl is HTTPS)
- SDK/Client: OkHttp WebSocket via `WebSocketManager`
- Auth: Token as query parameter
- Events: `storm_discover`, `storm_research`, `storm_outline`, `storm_cast`, `scene_start`, `dialogue`, `narration`, `end_narration`, `scene_end`, `tension_update`, `typing`, `error`, `director_log`, `actor_chime_in`, `save_confirm`, `load_confirm`, `replay`

## Data Storage

**Databases:**
- None on client side — all data comes from backend API

**File Storage:**
- Local filesystem only for DataStore preferences file (server config, auth token)

**Caching:**
- None — every screen fetches fresh data from backend

## Authentication & Identity

**Auth Provider:**
- Custom token-based (backend-generated)
  - Implementation: `AuthInterceptor` adds token to all Retrofit requests; token passed as query param in WS URL
  - Token stored in: `ServerPreferences` (DataStore)
  - Auth verification: `AuthApiService` (separate Retrofit instance for pre-connection verification)
  - Files: `android/app/src/main/java/com/drama/app/data/remote/interceptor/AuthInterceptor.kt`, `android/app/src/main/java/com/drama/app/data/local/ServerPreferences.kt`

## Monitoring & Observability

**Error Tracking:**
- None — errors shown as Snackbar or inline UI messages only

**Logs:**
- OkHttp `HttpLoggingInterceptor` at `Level.BODY` (verbose, development only)
- No structured logging or crash reporting

## CI/CD & Deployment

**Hosting:**
- Android APK (side-loaded, not on Play Store based on build scripts)

**CI Pipeline:**
- None detected — `build_apk.sh` for manual builds

## Environment Configuration

**Required env vars:**
- None at build time — all configuration is runtime (server IP/port/token entered by user)

**Secrets location:**
- DataStore preferences file (device-local, not in source code)
- `.env` files are in the Python backend, not the Android app

## Webhooks & Callbacks

**Incoming:**
- WebSocket events from backend (see Events list above)

**Outgoing:**
- REST API calls to backend (see DramaApiService for full list)

## API Endpoint Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/drama/start` | POST | Create new drama with theme |
| `/drama/status` | GET | Get current drama status |
| `/drama/next` | POST | Advance to next scene |
| `/drama/action` | POST | User action (free text) |
| `/drama/speak` | POST | Make actor speak |
| `/drama/chat` | POST | Send chat message with optional @mention |
| `/drama/end` | POST | End the drama |
| `/drama/cast` | GET | Get actor cast details |
| `/drama/cast/status` | GET | Get A2A actor status |
| `/drama/list` | GET | List all dramas |
| `/drama/save` | POST | Save current drama |
| `/drama/load` | POST | Load a drama by save_name |
| `/drama/export` | POST | Export drama |
| `/drama/scenes` | GET | Get scene list |
| `/drama/scenes/{n}` | GET | Get scene detail |
| `/drama/{folder}` | DELETE | Delete a drama |
| `/ws` | WebSocket | Real-time events stream |

---

*Integration audit: 2026-04-22*
