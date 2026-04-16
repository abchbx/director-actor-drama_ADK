---
phase: 14-websocket-layer
plan: 01
subsystem: api, websocket
tags: [websocket, event-bridge, fastapi, connection-manager, event-mapper]

# Dependency graph
requires:
  - phase: 13-api-foundation
    provides: run_command_and_collect, FastAPI app with lifespan, CORS, flush_state_sync hook
provides:
  - event_callback parameter in run_command_and_collect (D-01)
  - WsEvent/ReplayMessage/HeartbeatMessage Pydantic models
  - ConnectionManager with connect/disconnect/broadcast/create_broadcast_callback
  - event_mapper.py with TOOL_EVENT_MAP and map_runner_event
  - WebSocket endpoint at /api/v1/ws
  - ConnectionManager initialization in app.py lifespan
affects: [14-02, 14-03, 15-auth]

# Tech tracking
tech-stack:
  added: []
  patterns: [event-callback-injection, connection-manager, event-mapper-pattern, replay-buffer]

key-files:
  created:
    - app/api/event_mapper.py
    - app/api/ws_manager.py
    - app/api/routers/websocket.py
    - tests/unit/test_event_mapper.py
    - tests/unit/test_ws_manager.py
    - tests/unit/test_runner_utils.py
  modified:
    - app/api/runner_utils.py
    - app/api/models.py
    - app/api/app.py

key-decisions:
  - "EventBridge is a callback function, not a separate class/service (D-02)"
  - "event_callback exception does not block Runner execution"
  - "ConnectionManager uses set[WebSocket] with MAX_CONNECTIONS=10 (T-14-01)"
  - "broadcast uses asyncio.wait_for with 5s timeout, removes slow clients (T-14-04)"
  - "map_runner_event returns list[dict] for flexible one-to-many mapping (D-07)"

patterns-established:
  - "EventCallback injection: optional Callable[[Event], Awaitable[None]] | None parameter"
  - "ConnectionManager pattern: set[WebSocket] pool + deque replay buffer + broadcast with timeout"
  - "Event mapper pattern: TOOL_EVENT_MAP dict + map_runner_event function for ADK→business mapping"

requirements-completed: [WS-01, WS-03]

# Metrics
duration: 15min
completed: 2026-04-15
---

# Phase 14 Plan 01: WebSocket Foundation Summary

**EventBridge callback hook, WebSocket endpoint at /api/v1/ws, event_mapper with 14-tool TOOL_EVENT_MAP, and ConnectionManager with replay buffer and broadcast timeout**

## Performance

- **Duration:** 15 min
- **Started:** 2026-04-15T12:58:01Z
- **Completed:** 2026-04-15T13:13:16Z
- **Tasks:** 2
- **Files modified:** 9 (3 modified, 6 created)

## Accomplishments

- Added event_callback parameter to run_command_and_collect (D-01) — REST path unchanged when None
- Created WsEvent, ReplayMessage, HeartbeatMessage Pydantic models for WS message format
- Created ConnectionManager with connect/disconnect/broadcast/create_broadcast_callback
- Created WebSocket endpoint at /api/v1/ws that accepts connections and sends replay on connect
- Created event_mapper.py with TOOL_EVENT_MAP (14 tools) and map_runner_event function
- Initialized ConnectionManager in app.py lifespan, registered WS router at /api/v1
- Added MAX_CONNECTIONS=10 limit (T-14-01 mitigation)
- Added 5s broadcast timeout with slow client removal (T-14-04 mitigation)
- 48 new tests (21 event_mapper + 19 ws_manager + 4 runner_utils + 4 ws_endpoint)

## Files Created/Modified

- `app/api/runner_utils.py` — Added event_callback parameter with try/except passthrough
- `app/api/models.py` — Added WsEvent, ReplayMessage, HeartbeatMessage models
- `app/api/event_mapper.py` — TOOL_EVENT_MAP + map_runner_event + _extract_call_data + _extract_response_data + _extract_tension
- `app/api/ws_manager.py` — ConnectionManager class with MAX_CONNECTIONS, replay buffer, broadcast timeout
- `app/api/routers/websocket.py` — WebSocket endpoint with connect/receive/disconnect lifecycle
- `app/api/app.py` — Lifespan init of ConnectionManager + WS router registration + shutdown cleanup
- `tests/unit/test_event_mapper.py` — 21 tests for TOOL_EVENT_MAP and map_runner_event
- `tests/unit/test_ws_manager.py` — 23 tests for ConnectionManager, WsEvent models, and WS endpoint
- `tests/unit/test_runner_utils.py` — 4 tests for event_callback parameter

## Decisions Made

- EventBridge callback exception silently caught — must not block Runner execution
- ConnectionManager uses discard() not remove() for safe disconnect of missing connections
- WebSocket endpoint does not hold Runner Lock (D-11) — pure receiver only
- create_broadcast_callback lazy-imports event_mapper to avoid circular imports
- TestClient WS tests manually set up connection_manager since lifespan doesn't run

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- TestClient doesn't trigger lifespan, so WS endpoint tests must manually initialize ConnectionManager on app.state. This is a known TestClient limitation, not a code issue.

## Next Phase Readiness

- WebSocket foundation complete, ready for Plan 14-02 (wire event_callback into command endpoints)
- ConnectionManager.create_broadcast_callback ready for commands.py integration
- event_mapper fully functional with 14-tool mapping and conditional event detection

---
*Phase: 14-websocket-layer*
*Completed: 2026-04-15*
