---
phase: 14-websocket-layer
plan: 03
subsystem: api, websocket
tags: [replay-buffer, heartbeat, pong-tracking, connection-lifecycle, reconnect-handshake]

# Dependency graph
requires:
  - phase: 14-01
    provides: ConnectionManager, create_broadcast_callback, event_mapper, run_command_and_collect with event_callback
  - phase: 14-02
    provides: event_callback wired into all 8 REST command endpoints, flush-before-push integration
provides:
  - Heartbeat tracking with _last_pong dict per connection (D-14)
  - Application-level heartbeat: 15s ping, 30s timeout (D-14)
  - Pong recording via record_pong() and expiration check via is_pong_expired()
  - Connection lifecycle: connect → replay → heartbeat → live push → disconnect (WS-05)
  - Reconnect handshake: new connections receive full replay buffer automatically (D-09/D-10)
  - Connection limit: MAX_CONNECTIONS=10 rejects excess with code 1013 (T-14-08)
  - connect() returns bool indicating acceptance/rejection
  - Slow client cleanup during broadcast also cleans _last_pong
affects: [15-auth]

# Tech tracking
tech-stack:
  added: []
  patterns: [application-level-heartbeat, pong-timeout-tracking, replay-on-connect, connection-limit-guard]

key-files:
  created:
    - tests/unit/test_ws_lifecycle.py
  modified:
    - app/api/ws_manager.py
    - app/api/routers/websocket.py
    - tests/unit/test_ws_manager.py

key-decisions:
  - "connect() returns bool — True if accepted, False if rejected (limit exceeded)"
  - "self.MAX_CONNECTIONS as instance attribute alongside module-level constant for backward compat"
  - "heartbeat runs as asyncio.Task alongside receive loop, cancelled on disconnect"
  - "broadcast() also cleans up _last_pong for slow/disconnected clients"
  - "is_pong_expired returns True for unknown websockets (defensive default)"

patterns-established:
  - "Heartbeat task: asyncio.create_task(manager.heartbeat(ws)) on connect, cancel in finally block"
  - "Pong handling: receive_json loop checks msg_type == 'pong' → manager.record_pong()"
  - "Timeout detection: is_pong_expired() checks (monotonic() - last_pong) > HEARTBEAT_TIMEOUT"

requirements-completed: [WS-04, WS-05]

# Metrics
duration: 11min
completed: 2026-04-15
---

# Phase 14 Plan 03: Replay Buffer, Heartbeat & Connection Lifecycle Summary

**Replay buffer sends last 100 events on connect, application-level heartbeat with 15s ping/30s timeout auto-disconnects dead connections, and full WS lifecycle management with reconnect handshake implemented and tested**

## Performance

- **Duration:** 11 min
- **Started:** 2026-04-15T14:14:37Z
- **Completed:** 2026-04-15T14:25:18Z
- **Tasks:** 2
- **Files modified:** 4 (2 production, 2 test)

## Accomplishments

- Added `_last_pong` dict tracking pong timestamps per WebSocket connection
- Added `record_pong()` method to store client pong timestamps (D-14)
- Added `is_pong_expired()` method to detect 30s timeout (D-14)
- Added `heartbeat()` async method with 15s ping interval, 30s timeout, auto-disconnect
- `connect()` now returns `bool` (True=accepted, False=rejected) and initializes pong timestamp
- `disconnect()` now cleans up `_last_pong` entry alongside connection pool removal
- `broadcast()` now also cleans up `_last_pong` for slow/disconnected clients
- Added `self.MAX_CONNECTIONS = 10` instance attribute (T-14-08)
- WS endpoint starts heartbeat task on connect, handles pong messages, cancels on disconnect
- WS endpoint checks connect() return value, returns early if connection rejected
- Created comprehensive lifecycle tests in test_ws_lifecycle.py (11 tests)
- Added 9 heartbeat tracking tests to test_ws_manager.py
- All 678 unit tests pass with no regressions

## Files Created/Modified

- `app/api/ws_manager.py` — Added `import time`, `_last_pong` dict, `HEARTBEAT_INTERVAL=15`, `HEARTBEAT_TIMEOUT=30`, `MAX_CONNECTIONS=10` instance attr, `record_pong()`, `is_pong_expired()`, `heartbeat()`, updated `connect()` (returns bool, init pong), `disconnect()` (cleanup pong), `broadcast()` (cleanup pong for slow clients)
- `app/api/routers/websocket.py` — Complete rewrite: added heartbeat task creation on connect, pong handling in receive loop, connect() return value check, heartbeat task cancellation in finally block
- `tests/unit/test_ws_manager.py` — Added `import asyncio, time`, added `TestHeartbeatTracking` class with 9 tests
- `tests/unit/test_ws_lifecycle.py` — New file with `TestReplayBuffer` (5 tests), `TestConnectionLimit` (3 tests), `TestFullLifecycle` (1 test), `TestSlowClientRemoval` (2 tests)

## Decisions Made

- `connect()` returns `bool` to allow WS endpoint to check acceptance without checking `active_connections` separately
- `self.MAX_CONNECTIONS` as instance attribute allows per-manager configuration while module-level `MAX_CONNECTIONS = 10` remains for backward compatibility
- `is_pong_expired()` returns `True` for unknown websockets (defensive default — treat untracked connections as expired)
- `heartbeat()` handles `CancelledError` gracefully — normal disconnect path, no logging needed
- `broadcast()` cleans up `_last_pong` for slow clients alongside `active_connections` — complete cleanup

## Deviations from Plan

None — plan executed exactly as written.

## Next Phase Readiness

- Replay buffer sends last 100 events on connect (D-08/D-09/WS-04) ✅
- Application-level heartbeat sends ping every 15s (D-14) ✅
- Client without pong for 30s gets disconnected and removed from pool (D-14/D-13) ✅
- Reconnecting client gets full replay buffer automatically (D-10) ✅
- Connection limit (MAX_CONNECTIONS=10) prevents DoS via connection exhaustion (T-14-08) ✅
- Slow clients removed during broadcast with 5s timeout (T-14-04) ✅
- Full lifecycle: connect → replay → heartbeat → broadcast → disconnect (WS-05) ✅
- Ready for Phase 15 (Authentication)

## Self-Check: PASSED

- All 4 key files exist on disk
- Both commits verified in git log (bdf5c47, ebfaf80)
- 48 WS tests pass (test_ws_manager.py + test_ws_lifecycle.py)
- 678 total unit tests pass with no regressions
- Constants verified: MAX_CONNECTIONS=10, HEARTBEAT_INTERVAL=15, HEARTBEAT_TIMEOUT=30, replay maxlen=100
- WS route registered at /ws

---
*Phase: 14-websocket-layer*
*Completed: 2026-04-15*
