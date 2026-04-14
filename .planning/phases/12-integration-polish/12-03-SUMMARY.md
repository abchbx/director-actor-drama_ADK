---
phase: 12-integration-polish
plan: 03
subsystem: cli
tags: [rich, spinner, scene-summary, chinese-errors, ux]

# Dependency graph
requires:
  - phase: 12-01
    provides: debounce + conversation_log migration + scene archival
provides:
  - CLI spinner during LLM wait
  - Scene summary display after write_scene
  - Unified Chinese error messages with fix suggestions
affects: [cli-ux, error-handling]

# Tech tracking
tech-stack:
  added: [rich.spinner, rich.live]
  patterns: [Live start/stop for async runner, fallback text indicator, scene summary extraction]

key-files:
  created: []
  modified:
    - cli.py

key-decisions:
  - "Use rich Live start/stop (not context manager) since Live lacks __aenter__/__aexit__ for async"
  - "Fallback to simple text prompt if rich Live.start() throws exception"
  - "_extract_actors_from_response tries actors_in_scene first, then regex fallback on dialogue content"
  - "finally block ensures spinner always stops (T-12-07 mitigation)"

patterns-established:
  - "Spinner lifecycle: Live.start() on first non-final event, Live.stop() on final_response/error/finally"
  - "Scene summary format: ── 第N场：标题 ── 参演：角色1、角色2"
  - "Chinese error messages with pattern matching (rate_limit/timeout/api_key) and 💡 suggestion for unknown errors"

requirements-completed: [INTEG-04a, INTEG-04b]

# Metrics
duration: 10min
completed: 2026-04-14
---

# Phase 12 Plan 03: CLI UX Optimization Summary

**Rich spinner + scene summary display + unified Chinese error messages for CLI user experience**

## Performance

- **Duration:** 10 min
- **Started:** 2026-04-14T02:48:34Z
- **Completed:** 2026-04-14T02:58:39Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- LLM wait indicator: rich Spinner ("dots") with "🤔 思考中..." text, started on first non-final event, stopped on final response
- Scene summary display: "── 第N场：标题 ── 参演：角色1、角色2" format after write_scene responses (D-15)
- Unified Chinese error messages: rate limit, timeout, API key errors get specific Chinese messages; unknown errors get 💡 suggestion
- Spinner always cleaned up in finally block (T-12-07 mitigation)
- Fallback to simple "⏳ 思考中..." text if rich Live.start() fails

## Task Commits

Each task was committed atomically:

1. **Task 1: CLI spinner + scene summary + Chinese error messages** - `9fec262` (feat)

## Files Created/Modified
- `cli.py` - Added rich imports (Console, Live, Spinner), re import; added `_extract_actors_from_response()` helper; refactored `_send_message()` with spinner lifecycle, scene summary display, and Chinese error messages

## Decisions Made
- Used `Live.start()`/`Live.stop()` methods instead of context manager (`with Live(...)`) because `Live` lacks `__aenter__`/`__aexit__` — verified by inspecting rich 14.3.2 source
- Wrapped `live.start()` and `live.stop()` in try/except for graceful fallback — if rich terminal control fails, simple text prompts are used instead
- `_extract_actors_from_response()` uses two-stage extraction: explicit `actors_in_scene` field first, then regex `🎭\s*(\S+?)（` pattern on dialogue_content/formatted_scene as fallback
- `spinner_active` flag tracks state across the async generator to prevent double-start/double-stop

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

- ✅ `from cli import _send_message, _extract_actors_from_response` — imports OK
- ✅ `grep -c "Spinner\|思考中" cli.py` → 4 matches
- ✅ `grep -c "参演" cli.py` → 1 match
- ✅ `grep "💡" cli.py` → Chinese error suggestion found
- ✅ `import cli` — syntax check OK
- ✅ `_extract_actors_from_response` — all test cases pass (explicit actors, dialogue pattern, empty)
- ✅ Rich Live start/stop lifecycle — works with asyncio, double-stop safe, stop-without-start safe

## Self-Check: PASSED

- cli.py: FOUND
- Commit 9fec262: FOUND
- 12-03-SUMMARY.md: FOUND
