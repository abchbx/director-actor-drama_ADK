---
phase: 14-websocket-layer
plan: 02
subsystem: api, websocket
tags: [event-callback, flush-before-push, event-mapper, command-endpoints, rest-ws-coexistence]

# Dependency graph
requires:
  - phase: 14-01
    provides: ConnectionManager, create_broadcast_callback, event_mapper, run_command_and_collect with event_callback
provides:
  - event_callback wired into all 8 REST command endpoints (WS-02)
  - _get_event_callback helper centralizing callback creation (D-02/D-12)
  - flush-before-push integration in create_broadcast_callback (D-16)
  - All 18 event types verified as producible through map_runner_event (WS-03)
  - Fixed _extract_tension to handle tension_score=0 correctly
affects: [14-03, 15-auth]

# Tech tracking
tech-stack:
  added: []
  patterns: [flush-before-push, event-callback-injection, conditional-event-detection]

key-files:
  created: []
  modified:
    - app/api/routers/commands.py
    - app/api/event_mapper.py
    - tests/unit/test_ws_manager.py
    - tests/unit/test_event_mapper.py

key-decisions:
  - "Pydantic request params renamed from 'request' to 'body' to avoid collision with FastAPI Request"
  - "_extract_tension uses explicit key check instead of 'or' pattern to handle tension_score=0"
  - "event_callback is None when no WS clients connected — zero overhead on REST-only usage (D-12)"
  - "flush_fn exception silently caught — flush failure must not block event broadcast (T-14-06)"

patterns-established:
  - "Flush-before-push: create_broadcast_callback(flush_fn) calls flush before each broadcast"
  - "REST-WS coexistence: _get_event_callback returns None when no active WS connections"
  - "Request dependency: FastAPI auto-injects Request without Depends() for accessing app.state"

requirements-completed: [WS-02, WS-03]

# Metrics
duration: 12min
completed: 2026-04-15
---

# Phase 14 Plan 02: Event Callback Wiring & 18-Event Pipeline Summary

**All 8 command endpoints wired with event_callback via _get_event_callback helper, flush-before-push integrated, and 18-event-type emission pipeline verified with comprehensive tests**

## Performance

- **Duration:** 12 min
- **Started:** 2026-04-15T13:27:38Z
- **Completed:** 2026-04-15T13:39:16Z
- **Tasks:** 2
- **Files modified:** 4 (2 production, 2 test)

## Accomplishments

- Wired event_callback into all 8 REST command endpoints via `_get_event_callback(req)` helper
- Added `Request` parameter to all 8 endpoints for accessing `connection_manager` from `app.state`
- Renamed Pydantic request params from `request` to `body` to avoid FastAPI `Request` collision
- `event_callback` is `None` when no WS clients connected — zero REST-only overhead (D-12)
- Verified `create_broadcast_callback` correctly passes `flush_fn` from `app.state.flush_state_sync` (D-16)
- Verified `flush_fn` exception is caught silently — flush failure doesn't block broadcast (T-14-06)
- Confirmed all 18 event types are producible through `map_runner_event`
- Fixed `_extract_tension` to handle `tension_score=0` correctly (was falsy-skipped by `or` pattern)
- Added 33 new tests: 8 for event_callback wiring, 25 for event mapper coverage

## Files Created/Modified

- `app/api/routers/commands.py` — Added `Request` import, `_get_event_callback` helper, wired all 8 endpoints with `event_callback=_get_event_callback(req)`, renamed Pydantic params from `request` to `body`
- `app/api/event_mapper.py` — Fixed `_extract_tension` to use explicit key check instead of `or` pattern
- `tests/unit/test_ws_manager.py` — Added 8 tests: flush-before-push, flush exception survival, _get_event_callback helper (4 scenarios)
- `tests/unit/test_event_mapper.py` — Added 25 tests: all-18-types verification, director_narrate, actor_speak, storm mappings, conditional events, start_drama multi-event, edge cases

## Decisions Made

- Pydantic request body params renamed to `body` (not `cmd`) to match common FastAPI convention and avoid ambiguity
- `_extract_tension` now uses explicit key existence check (`if "tension_score" in response`) instead of `or` pattern to correctly handle `tension_score=0`
- `_get_event_callback` checks both `connection_manager` existence and `active_connections` non-empty — two-layer guard ensures REST-only path has zero overhead

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed _extract_tension falsy-zero bug**
- **Found during:** Task 2 — reviewing conditional event detection
- **Issue:** `_extract_tension` used `response.get("tension_score") or response.get("tension")` which would skip `tension_score=0` because `0` is falsy
- **Fix:** Changed to explicit key existence check: `if "tension_score" in response: return response["tension_score"]`
- **Files modified:** app/api/event_mapper.py
- **Commit:** 80cd814

## Next Phase Readiness

- All 8 command endpoints pass event_callback — WS clients will receive real-time events
- 18-event-type emission pipeline complete and tested
- flush-before-push integration verified (D-16)
- Ready for Plan 14-03 (heartbeat/ping-pong lifecycle management)

## Self-Check: PASSED

- All 5 key files exist on disk
- All 3 commits verified in git log
- 88 targeted tests pass (event_mapper + ws_manager + api_commands)
- 658 total unit tests pass with no regressions
- 18 unique event types verified via programmatic check

---
*Phase: 14-websocket-layer*
*Completed: 2026-04-15*
