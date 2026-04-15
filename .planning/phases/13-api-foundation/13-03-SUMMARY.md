---
phase: 13-api-foundation
plan: 03
subsystem: api
tags: [fastapi, state-manager, query-endpoints, global-removal, pydantic]

# Dependency graph
requires:
  - phase: 13-01
    provides: create_app, ToolContextAdapter, Pydantic models, deps
provides:
  - 6 query-style REST endpoints (status, cast, save, load, list, export)
  - _current_drama_folder global variable fully removed
  - _get_current_theme raises ValueError without tool_context
affects: [14-websocket-layer, 15-authentication]

# Tech tracking
tech-stack:
  added: []
  patterns: [query-endpoint-direct-state-access, dependency-override-testing, require-active-drama-guard]

key-files:
  created:
    - tests/unit/test_api_queries.py
  modified:
    - app/state_manager.py
    - app/api/routers/queries.py
    - tests/unit/test_state_manager.py

key-decisions:
  - "_current_drama_folder global removed entirely — ValueError replaces silent fallback"
  - "_require_active_drama helper centralizes 404 guard for query endpoints"
  - "Query endpoints call state_manager directly (D-05) without Runner"

patterns-established:
  - "Query endpoint pattern: Depends(get_tool_context) → _require_active_drama → state_manager call → Pydantic response"
  - "Dependency override pattern: app.dependency_overrides[get_tool_context] for test isolation"

requirements-completed: [API-02, STATE-01]

# Metrics
duration: 10min
completed: 2026-04-15
---

# Phase 13 Plan 03: Query Endpoints + State Migration Summary

**6 query-style endpoints calling state_manager directly, _current_drama_folder global variable fully removed with ValueError enforcement**

## Performance

- **Duration:** 10 min
- **Started:** 2026-04-15T11:13:15Z
- **Completed:** 2026-04-15T11:23:36Z
- **Tasks:** 1
- **Files modified:** 4

## Accomplishments
- Removed _current_drama_folder global variable from state_manager.py (STATE-01)
- _get_current_theme(None) now raises ValueError instead of silently returning empty string (D-10)
- init_drama_state and load_progress no longer set global variable
- Removed unused typing imports (Any, Optional) from state_manager.py
- Implemented all 6 query-style endpoints: GET /drama/status, GET /drama/cast, POST /drama/save, POST /drama/load, GET /drama/list, POST /drama/export
- Query endpoints call state_manager functions directly without Runner (D-05)
- No active drama → 404 for status/cast/save/export endpoints (D-04)
- Tool business errors → 200 + status: error (D-04)

## Task Commits

Each task was committed atomically:

1. **Task 1: Migrate _current_drama_folder + implement query-style endpoints** - `cf117e0` (feat)

## Files Created/Modified
- `app/state_manager.py` - Removed _current_drama_folder global, _get_current_theme raises ValueError, removed global declarations from init_drama_state and load_progress, removed unused typing imports
- `app/api/routers/queries.py` - Replaced stubs with real implementations calling state_manager directly
- `tests/unit/test_api_queries.py` - 8 unit tests for query endpoints (status, cast, save, load, list, export, 404 guard, error handling)
- `tests/unit/test_state_manager.py` - 5 new tests for state migration (no global, ValueError, tool_context, no global assignment)

## Decisions Made
1. **_current_drama_folder global removed entirely** — ValueError with descriptive message replaces silent empty string fallback, making missing tool_context a loud failure instead of a subtle bug
2. **_require_active_drama helper centralizes 404 guard** — DRY pattern for status/cast/save/export endpoints that require an active drama; /load and /list are exempted (load creates a drama, list doesn't need one)
3. **Query endpoints call state_manager directly (D-05)** — No Runner involvement for fast, predictable responses without LLM

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered
- Initial test implementation used `@patch("app.api.routers.queries.get_tool_context")` which doesn't work because FastAPI resolves dependencies before route handler execution. Fixed by using `app.dependency_overrides[get_tool_context]` pattern (same as 13-02 command tests).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Query endpoints complete, ready for WebSocket event push integration (Phase 14)
- State migration complete — no global variables remain, safe for API + CLI coexistence
- 13-04 (session management) can proceed with all endpoints wired

---
*Phase: 13-api-foundation*
*Completed: 2026-04-15*

## Self-Check: PASSED

- All 4 modified/created files verified present
- Task commit cf117e0 verified in git log
- 565 total tests passing (541 existing + 13 new + 11 from 13-02)
