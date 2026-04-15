---
phase: 13-api-foundation
plan: 02
subsystem: api
tags: [fastapi, adk-runner, rest, async, pydantic]

# Dependency graph
requires:
  - phase: 13-01
    provides: "FastAPI app factory, deps, models, router stubs, runner_utils"
provides:
  - "8 command-style REST endpoints routing through ADK Runner"
  - "Auto-save before /start when drama exists (D-06)"
  - "404 for non-start endpoints when no active drama (D-04)"
  - "504 timeout handling for all command endpoints"
  - "Serial Runner access via asyncio.Lock (STATE-03)"
affects: [13-03, 13-04, 14-websocket-layer]

# Tech tracking
tech-stack:
  added: []
  patterns: ["command-endpoint: lock → check-drama → format-message → run-and-collect → response"]

key-files:
  created:
    - tests/unit/test_api_commands.py
  modified:
    - app/api/routers/commands.py
    - app/api/deps.py

key-decisions:
  - "Broke circular import by moving APP_NAME/USER_ID/SESSION_ID constants to deps.py instead of importing from app.py"
  - "commands.py defines USER_ID/SESSION_ID locally for message passing to runner_utils"
  - "save_progress/flush_state_sync imported lazily inside start_drama to match plan spec"

patterns-established:
  - "Command endpoint pattern: async with lock → _require_active_drama → run_command_and_collect → CommandResponse"
  - "FastAPI dependency_overrides for test injection instead of patching dependency functions"

requirements-completed: [API-01, API-02]

# Metrics
duration: 27min
completed: 2026-04-15
---

# Phase 13 Plan 02: Command Endpoints Summary

**8 command-style REST endpoints routing through ADK Runner with Lock serialization, auto-save on /start, 404 on missing drama, and 504 timeout handling**

## Performance

- **Duration:** 27 min
- **Started:** 2026-04-15T10:40:32Z
- **Completed:** 2026-04-15T11:07:50Z
- **Tasks:** 1
- **Files modified:** 3

## Accomplishments
- All 8 command endpoints implemented: start, next, action, speak, steer, auto, end, storm
- Each endpoint acquires asyncio.Lock before calling Runner (STATE-03: serial access)
- /start auto-saves existing drama before starting new one (D-06)
- Non-start endpoints return 404 when no active drama session (D-04)
- All endpoints return CommandResponse with final_response + tool_results (D-03)
- 120s timeout via run_command_and_collect with 504 HTTPException on timeout
- 11 unit tests covering all endpoints, 404, 504, and auto-save scenarios

## Task Commits

Each task was committed atomically (TDD: RED → GREEN):

1. **Task 1 RED: Failing tests** - `fbc05df` (test)
2. **Task 1 GREEN: Implement endpoints** - `8a7a0fa` (feat)

## Files Created/Modified
- `app/api/routers/commands.py` - 8 command endpoints with Runner integration, Lock serialization, auto-save logic
- `app/api/deps.py` - Moved APP_NAME/USER_ID/SESSION_ID constants locally to break circular import
- `tests/unit/test_api_commands.py` - 11 unit tests (312 lines) for all endpoints, error cases, auto-save

## Decisions Made
- **Broke circular import in deps.py**: Instead of importing APP_NAME/USER_ID/SESSION_ID from app.py (causing circular import when commands.py imports deps), defined constants locally in deps.py. app.py keeps its own definitions independently. This follows the same pattern as runner_utils having independent constants.
- **commands.py defines USER_ID/SESSION_ID locally**: For passing to run_command_and_collect, avoiding any cross-module dependency on app.py constants.
- **Lazy import of save_progress/flush_state_sync**: Used inside start_drama() as specified in the plan, keeping the import close to usage and avoiding top-level import issues.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed circular import between deps.py and app.py**
- **Found during:** Task 1 (endpoint implementation)
- **Issue:** commands.py imports from deps.py, deps.py imports APP_NAME/USER_ID/SESSION_ID from app.py, app.py imports commands router → circular ImportError
- **Fix:** Moved APP_NAME/USER_ID/SESSION_ID constants to deps.py locally, removing the import from app.py. Both app.py and deps.py define these constants independently.
- **Files modified:** app/api/deps.py
- **Verification:** All 42 tests pass (11 new + 31 existing)
- **Committed in:** 8a7a0fa (Task 1 GREEN commit)

**2. [Rule 1 - Bug] Fixed test mock path for run_command_and_collect**
- **Found during:** Task 1 (test writing)
- **Issue:** Patching `app.api.runner_utils.run_command_and_collect` didn't work because commands.py imports it at module level — the reference is already bound
- **Fix:** Changed mock path to `app.api.routers.commands.run_command_and_collect` to patch where it's actually used
- **Files modified:** tests/unit/test_api_commands.py
- **Verification:** All 11 tests pass
- **Committed in:** 8a7a0fa (Task 1 GREEN commit)

**3. [Rule 3 - Blocking] Used FastAPI dependency_overrides instead of patching deps**
- **Found during:** Task 1 (test writing)
- **Issue:** Patching dependency functions (get_runner, etc.) doesn't work with FastAPI's dependency injection system since it resolves deps at route level
- **Fix:** Used `app.dependency_overrides[get_runner] = lambda: mock_runner` which is the FastAPI-native way to override dependencies for testing
- **Files modified:** tests/unit/test_api_commands.py
- **Verification:** All 11 tests pass
- **Committed in:** 8a7a0fa (Task 1 GREEN commit)

---

**Total deviations:** 3 auto-fixed (1 blocking, 1 bug, 1 blocking)
**Impact on plan:** All auto-fixes necessary for tests to work and imports to resolve. No scope creep.

## Issues Encountered
None beyond the deviations documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 8 command endpoints operational, ready for Plan 03 (query endpoints) and Plan 04 (integration testing)
- Pattern established: command endpoint → Lock → drama check → Runner → CommandResponse
- Test infrastructure established: FastAPI dependency_overrides + mock run_command_and_collect pattern

## Self-Check: PASSED

- All 4 key files verified present
- Both commit hashes verified (fbc05df, 8a7a0fa)
- All 42 tests pass (11 new + 31 existing)

---
*Phase: 13-api-foundation*
*Completed: 2026-04-15*
