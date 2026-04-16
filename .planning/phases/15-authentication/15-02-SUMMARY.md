---
phase: 15-authentication
plan: 02
subsystem: auth
tags: [fastapi, websocket, token-auth, query-parameter, websocketexception]

# Dependency graph
requires:
  - phase: 15-authentication
    provides: "require_auth HTTPBearer dependency, app.state.api_token / app.state.auth_enabled, auth/verify endpoint"
  - phase: 14-websocket-layer
    provides: "ConnectionManager, WebSocket router, WS lifecycle"
provides:
  - "_validate_ws_token() function for WS handshake token validation"
  - "WebSocket ?token=xxx query parameter auth (AUTH-03)"
  - "WebSocketException(code=4001) rejection before accept (D-10)"
  - "WS dev mode bypass when auth_enabled=False (D-11)"
  - "WS auth event logging (D-16)"
  - "Full auth integration tests (REST + WS)"
affects: [16-android-foundation, 17-android-interaction, 18-android-features]

# Tech tracking
tech-stack:
  added: [fastapi.WebSocketException]
  patterns: [ws-query-parameter-auth, pre-accept-token-validation, ws-dev-mode-bypass]

key-files:
  created:
    - tests/unit/test_ws_auth.py
  modified:
    - app/api/routers/websocket.py
    - tests/unit/test_auth.py

key-decisions:
  - "_validate_ws_token is a plain function, NOT a FastAPI Depends — WebSocket endpoints don't support the same DI for auth"
  - "WebSocketException(code=4001) raised BEFORE accept — FastAPI sends 4001 close frame, ConnectionManager never polluted"
  - "_validate_ws_token is synchronous (not async) — token comparison is CPU-only, no I/O needed"

patterns-established:
  - "WS auth via ?token=xxx query parameter before websocket.accept()"
  - "Pre-accept validation pattern: validate → raise WebSocketException or proceed → accept → connect"
  - "Dev mode bypass: auth_enabled=False skips WS token validation same as REST"

requirements-completed: [AUTH-03]

# Metrics
duration: 8min
completed: 2026-04-16
---

# Phase 15 Plan 02: WebSocket Token Auth Summary

**WS 握手阶段 ?token=xxx 验证 + WebSocketException(4001) 拒绝 + dev 模式绕过 + REST+WS 集成测试**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-16T05:55:37Z
- **Completed:** 2026-04-16T06:03:15Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- WS endpoint validates ?token=xxx before accept (AUTH-03, D-09, D-10)
- Invalid/missing token → WebSocketException(code=4001) before accept — ConnectionManager never polluted (D-10)
- Dev mode → WS bypasses auth when auth_enabled=False (D-11)
- Auth events (success/failure/bypass) logged to Python logger (D-16)
- Full auth integration tests cover REST + WS flow, token format compatibility, endpoint count, and logging
- 710 total unit tests pass with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: WebSocket token validation in handshake** - `63f0338` (test/TDD RED) + `33c2daf` (feat/TDD GREEN)
2. **Task 2: End-to-end auth integration test + verify all auth paths** - `741a320` (feat)

## Files Created/Modified
- `app/api/routers/websocket.py` - Added _validate_ws_token() with token extraction from query params, dev mode bypass, and pre-accept rejection with WebSocketException(4001)
- `tests/unit/test_ws_auth.py` - New file: 8 WS auth tests (valid token, missing/invalid rejection, dev mode, before-accept verification, logging)
- `tests/unit/test_auth.py` - Extended with TestAuthIntegration: 7 new tests (full flow with/without token, token format compatibility, endpoint count, logging verification, dev mode startup warning)

## Decisions Made
- **_validate_ws_token as plain function, NOT Depends**: WebSocket endpoints don't support the same dependency injection as HTTP for auth; function reads directly from websocket.app.state
- **WebSocketException(code=4001) before accept**: FastAPI intercepts this and sends a 4001 close frame; ConnectionManager.connect() is never called for unauthenticated connections
- **Synchronous _validate_ws_token**: Token comparison is CPU-only (string equality), no I/O needed, so async is unnecessary

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. WS auth uses the same API_TOKEN env var as REST auth.

## Next Phase Readiness
- Phase 15 authentication is fully complete (Plan 01 REST auth + Plan 02 WS auth)
- Android app can use ?token=xxx query parameter for WebSocket connections
- All 15 REST endpoints + 1 WS endpoint have auth protection when API_TOKEN is configured
- Dev mode (no API_TOKEN) allows unauthenticated access for local development

---
*Phase: 15-authentication*
*Completed: 2026-04-16*

## Self-Check: PASSED

- All 3 created/modified files verified to exist
- All 3 task commits (63f0338, 33c2daf, 741a320) verified in git log
- 8 WS auth tests pass
- 24 auth tests pass
- 710 total unit tests pass
