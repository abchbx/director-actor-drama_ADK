# External Integrations

**Analysis Date:** 2026-04-25

## APIs & External Services

**Backend REST API:**
- Base URL: Configurable via `ServerPreferences` (IP + port + optional baseUrl)
- SDK/Client: Retrofit (`DramaApiService`)
- Auth: Bearer token via `AuthInterceptor` (from `SecureStorage`)
- Key endpoints:
  - `POST /drama/start` — Start new drama
  - `GET /drama/status` — Get current drama status
  - `POST /drama/chat` — Send chat message
  - `POST /drama/next` — Advance to next scene
  - `POST /drama/action` — User action
  - `POST /drama/speak` — Actor speak
  - `POST /drama/end` — End drama
  - `GET /drama/scenes` — Get scene list
  - `GET /drama/scenes/{n}` — Get scene detail
  - `GET /drama/cast` — Get cast info
  - `GET /drama/cast/status` — Get cast status
  - `POST /drama/save` — Save drama (server-side)
  - `POST /drama/load` — Load drama (server-side)
  - `DELETE /drama/{folder}` — Delete drama

**Backend WebSocket:**
- URL: `ws://{ip}:{port}/ws` (constructed from ServerConfig)
- SDK/Client: OkHttp `WebSocket` via `WebSocketManager`
- Auth: Token passed as query parameter on connect
- Protocol: JSON frames with `type` + `data` fields (`WsEventDto`)
- Event types: narration, dialogue, actor_chime_in, scene_end, scene_start, tension_update, typing, error, storm_discover, storm_research, storm_outline, director_log, command_echo, actor_created, cast_update, user_message, save_confirm, load_confirm
- Auto-reconnect: Exponential backoff with max 5 retries (`ConnectionState.Reconnecting`)
- Heartbeat: Ping/pong frames

**Google ADK (Agent Development Kit) — Backend:**
- Server-side framework for AI agent orchestration
- `event_mapper.py` maps ADK `Event` → business WebSocket events
- Tools mapped: start_drama, next_scene, director_narrate, actor_speak, actor_chime_in, user_action, write_scene, update_emotion, create_actor, storm_*, save/load/end_drama, steer_drama, auto_advance

## Data Storage

**Databases:**
- None (no Room/SQLite)

**Local Storage:**
- DataStore Preferences — Local drama saves (bubble JSON serialization), server preferences
  - Connection: `DataStoreModule` provides instances
  - Client: `DramaSaveRepository`, `ServerPreferences`
- EncryptedSharedPreferences — Auth tokens, server credentials
  - Connection: `SecureStorage`
  - Client: `AuthRepositoryImpl`

**File Storage:**
- Local filesystem only (DataStore files in app sandbox)

**Caching:**
- None (no in-memory cache, no LRU cache)

## Authentication & Identity

**Auth Provider:**
- Custom token-based
  - Implementation: `AuthRepository` → `AuthRepositoryImpl` → `AuthApiService`
  - Token stored in `SecureStorage` (EncryptedSharedPreferences)
  - Token injected via `AuthInterceptor` on all API requests
  - Token passed as query parameter on WebSocket connection

## Monitoring & Observability

**Error Tracking:**
- None (no Crashlytics, Sentry, etc.)

**Logs:**
- Android `Log` (Logcat) with TAG-based filtering
- `DramaDetailViewModel` uses `TAG = "DramaDetailViewModel"`

## CI/CD & Deployment

**Hosting:**
- Android app (client-side only)

**CI Pipeline:**
- None detected (no `.github/workflows`, no `fastlane`, no CI config)

**Build:**
- `build_apk.sh` script exists for APK generation

## Environment Configuration

**Required env vars:**
- None on Android side (all config via UI setup in `ConnectionGuideDialog`)

**Secrets location:**
- `SecureStorage` (EncryptedSharedPreferences) — stores auth token
- `ServerPreferences` (DataStore) — stores server IP, port, baseUrl

## Webhooks & Callbacks

**Incoming:**
- WebSocket events from server (real-time push)

**Outgoing:**
- REST API calls to server
- WebSocket messages to server (chat, commands)

---

*Integration audit: 2026-04-25*
