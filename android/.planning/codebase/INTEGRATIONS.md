# External Integrations

**Analysis Date:** 2026-04-24

## APIs & External Services

**Drama Backend (Director-Actor-Drama Server):**
- REST API for drama CRUD, commands, and status queries
  - SDK/Client: Retrofit (`DramaApiService`)
  - Base URL: Dynamic — from `ServerConfig.toApiBaseUrl()` → `http://{ip}:{port}/api/v1/` or `{baseUrl}/api/v1/`
  - Endpoints: 16 REST endpoints defined in `DramaApiService.kt`
    - `POST drama/start` — Create new drama (blocking, minutes-long)
    - `POST drama/next` — Advance to next scene
    - `POST drama/action` — User action in drama
    - `POST drama/speak` — Actor speaks
    - `POST drama/steer` — Steer drama direction
    - `POST drama/auto` — Auto-advance scenes
    - `POST drama/storm` — Trigger STORM workflow
    - `POST drama/chat` — Send chat message (with optional @mention)
    - `POST drama/end` — End current drama
    - `GET drama/status` — Get current drama status (polling)
    - `GET drama/cast` — Get actor cast info
    - `GET drama/cast/status` — Get actor A2A status
    - `GET drama/list` — List all dramas
    - `DELETE drama/{folder}` — Delete a drama
    - `POST drama/save` — Save current drama
    - `POST drama/load` — Load a saved drama
    - `POST drama/export` — Export drama
    - `GET drama/scenes` — List scene summaries
    - `GET drama/scenes/{sceneNumber}` — Get scene detail
  - Auth: Bearer token in `Authorization` header (injected by `AuthInterceptor`)

- WebSocket for real-time events
  - SDK/Client: OkHttp `WebSocket` via `WebSocketManager`
  - URL: `ws://{ip}:{port}/api/v1/ws` or `wss://{baseUrl}/api/v1/ws`
  - Auth: Token passed as query parameter `?token={token}`
  - Event types received:
    - `storm_discover`, `storm_research`, `storm_outline`, `storm_cast` — STORM progress
    - `scene_start`, `scene_end` — Scene transitions
    - `dialogue`, `narration`, `end_narration` — Content events
    - `actor_chime_in`, `actor_created`, `cast_update` — Actor events
    - `tension_update` — Tension score change
    - `typing` — AI typing indicator
    - `tool_result`, `tool_results` — Tool execution results
    - `director_log` — Structured backend progress log
    - `save_confirm`, `load_confirm` — Save/load confirmations
    - `error` — Error events
    - `ping` (heartbeat) — Client responds with `{"type":"pong"}`
    - `replay` — Replays missed events after reconnect
  - Reconnect: Exponential backoff (1s → 30s cap), ConnectivityManager NetworkCallback
  - Degradation: After 5 consecutive WS failures, falls back to REST-only polling

**Auth Service:**
- `GET auth/verify` — Check server auth mode (bypass or require_token)
  - SDK/Client: Temporary Retrofit instance (not Hilt-provided, built in `AuthRepositoryImpl`)
  - Auth: No token (verification happens before token is known)

## Data Storage

**Databases:**
- None (no Room/SQL)

**File Storage:**
- Local filesystem only (DataStore + EncryptedSharedPreferences)

**Caching:**
- None (no HTTP cache configured)

## Authentication & Identity

**Auth Provider:**
- Custom (backend-defined)
  - Implementation: Two modes determined by `GET /auth/verify`:
    1. **Bypass** — No token required, direct access
    2. **RequireToken** — User must enter token, stored encrypted on device
  - Token injection: `AuthInterceptor` adds `Authorization: Bearer {token}` to all Retrofit requests
  - Token storage: `SecureStorage` uses `EncryptedSharedPreferences` with AES256_GCM
  - WebSocket auth: Token passed as `?token=` query parameter in WS URL

## Monitoring & Observability

**Error Tracking:**
- None (no Crashlytics, Sentry, etc.)

**Logs:**
- Android `Log` with named TAGs (`"WebSocketManager"`, `"DramaDetailViewModel"`, `"NetworkException"`)
- OkHttp `HttpLoggingInterceptor` at BODY level with `Authorization` header redacted

## CI/CD & Deployment

**Hosting:**
- N/A (client app, user-installed APK)

**CI Pipeline:**
- None detected (no GitHub Actions, Fastlane, etc.)
- Build script: `build_apk.sh` at project root

## Environment Configuration

**Required env vars:**
- None (all config is user-entered at runtime via ConnectionGuideDialog)

**Secrets location:**
- Auth token: `EncryptedSharedPreferences` file `drama_secure_prefs`
- Server config: DataStore file `drama_settings`
- No `.env` files or build-time secrets

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- WebSocket heartbeat: Client sends `{"type":"pong"}` in response to server `{"type":"ping"}`
- `WebSocketManager.onReconnected` callback — triggers `DramaDetailViewModel.onWsReconnected()` for state sync
- `WebSocketManager.onPermanentFailure` callback — triggers UI degradation to REST-only mode

---

*Integration audit: 2026-04-24*
