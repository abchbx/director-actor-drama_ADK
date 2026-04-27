# External Integrations

**Analysis Date:** 2026-04-27

## APIs & External Services

**Director-Actor-Drama Backend (FastAPI):**
- REST API - All drama operations (start, next, action, speak, steer, auto, storm, chat, end, status, cast, scenes, save/load/export)
  - SDK/Client: Retrofit (`DramaApiService`, `AuthApiService`)
  - Base URL: Dynamic — stored in `ServerPreferences` DataStore, can be IP:port or cloud URL
  - Auth: Bearer token in `Authorization` header (injected by `AuthInterceptor`)
  - API path prefix: `/api/v1/`
  - Example: `http://192.168.1.100:8000/api/v1/drama/start`

- WebSocket - Real-time drama events (scene updates, actor dialogue, heartbeat)
  - SDK/Client: OkHttp `WebSocket` via `WebSocketManager`
  - URL pattern: `ws://{host}:{port}/api/v1/ws?token={token}` or `wss://` for cloud
  - Auth: Token as query parameter on connection
  - Heartbeat: Server-driven ping every 15s, client replies `{"type":"pong"}`

## Data Storage

**Databases:**
- None (no Room/SQLite)

**Preferences:**
- DataStore Preferences (`drama_settings`) - Server IP, port, base URL, last connected timestamp
  - Location: `com.drama.app.data.local.ServerPreferences`
  - File: `app/src/main/java/com/drama/app/data/local/ServerPreferences.kt`

- DataStore Preferences (`drama_saves`) - Drama save/load metadata
  - Location: `com.drama.app.data.local.DramaSaveRepository`
  - Qualified with `@SavesDataStore` annotation

- EncryptedSharedPreferences (`drama_secure_prefs`) - Auth token
  - Location: `com.drama.app.data.local.SecureStorage`
  - File: `app/src/main/java/com/drama/app/data/local/SecureStorage.kt`
  - Encryption: MasterKey AES256_GCM + PrefValueEncryption AES256_GCM + PrefKeyEncryption AES256_SIV

**File Storage:**
- Local filesystem only (no cloud storage)

**Caching:**
- None (no HTTP cache configured on OkHttpClient)

## Authentication & Identity

**Auth Provider:**
- Custom token-based (server-side)
  - Implementation: Bearer token in `Authorization` header via `AuthInterceptor`
  - Token stored encrypted in `SecureStorage` (EncryptedSharedPreferences)
  - Auth modes: `Bypass` (no token needed) or `RequireToken` (token required)
  - Verification: `GET /api/v1/auth/verify` returns auth mode
  - WebSocket auth: Token passed as query parameter `?token={token}`
  - WebSocket auth error: Server closes with code 4001

## Monitoring & Observability

**Error Tracking:**
- None (no Crashlytics, Sentry, etc.)

**Logs:**
- `android.util.Log` with tag-based filtering
  - `NetworkException` tag - Network errors from `NetworkExceptionInterceptor`
  - `WebSocketManager` tag - WebSocket lifecycle events
  - `ConnectionOrchestrator` tag - Connection orchestration events
  - `HttpLoggingInterceptor` - Full HTTP request/response logging (DEBUG builds only)
  - Authorization header redacted in logs via `redactHeader("Authorization")`

## CI/CD & Deployment

**Hosting:**
- Server component: Self-hosted FastAPI (uvicorn), typically on developer machine or Cloud Studio

**CI Pipeline:**
- None detected in Android project

**Build Script:**
- `android/build_apk.sh` - Shell script for building debug APK

## Environment Configuration

**Required env vars (server-side, not Android):**
- `OPENAI_API_KEY` - LLM API key
- `OPENAI_BASE_URL` - LLM endpoint
- `MODEL_NAME` - Model identifier
- `API_TOKEN` - Auth token for server
- Source: `/workspace/director-actor-drama/app/.env.example`

**Secrets location:**
- Server-side: `.env` file (gitignored)
- Android-side: `EncryptedSharedPreferences` (hardware-backed keystore)
- No `.env` files in Android project directory

**Android runtime config (no env vars):**
- Server IP: User-entered, stored in DataStore
- Server Port: Default `8000`, stored in DataStore
- Base URL: Optional cloud URL, stored in DataStore
- Auth Token: Stored encrypted in SecureStorage

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## Network Security Configuration

**Release builds** (`network_security_config.xml`):
- `cleartextTrafficPermitted="false"` by default
- Exception: localhost/127.0.0.1/10.0.2.2 allowed for cleartext (emulator → host)
- Trust anchors: System certificates only
- `android:usesCleartextTraffic="false"` in manifest

**Debug builds** (`network_security_config_debug.xml`):
- `cleartextTrafficPermitted="true"` globally (allows LAN development)
- Trust anchors: System + User certificates
- Supports connecting to LAN development servers (192.168.x.x)

**Manifest placeholder** (`${networkSecurityConfig}`):
- Debug → `@xml/network_security_config_debug`
- Release → `@xml/network_security_config`

## Key Error Code Mapping

| Code | Source | Meaning |
|------|--------|---------|
| 504 | `NetworkExceptionInterceptor` | SocketTimeoutException → "网络连接超时" |
| 503 | `NetworkExceptionInterceptor` | UnknownHostException/ConnectException/SSLException/IOException → various messages |
| 504 | Server `runner_utils.py` | `asyncio.TimeoutError` → "Command execution timed out" |
| 401 | Server | Auth failure |
| 4001 | Server WebSocket | Auth error (WS close code) |

**Critical finding**: The `NetworkExceptionInterceptor` converts `SocketTimeoutException` to HTTP 504. The server-side `runner_utils.py` also raises HTTP 504 on command timeout. Both sources produce "UNKNOWN:504" in `AuthRepositoryImpl`'s error handling pattern `UNKNOWN:${e.code()}`.

---

*Integration audit: 2026-04-27*
