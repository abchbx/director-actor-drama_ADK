---
phase: 12-integration-polish
plan: 02
subsystem: tools
tags: [bug-fix, shared-client, crash-recovery, error-markers, actor-speak]
dependency_graph:
  requires: [12-01]
  provides: [shared-async-client, crash-recovery, error-markers, scene-archival-integration]
  affects: [app/tools.py, app/actor_service.py, tests/unit/test_tools_phase12.py]
tech_stack:
  added: [httpx.Limits, httpx.AsyncClient singleton]
  patterns: [lazy singleton, passive crash detection, auto-restart with retry]
key_files:
  created:
    - tests/unit/test_tools_phase12.py
  modified:
    - app/tools.py
decisions:
  - "Error detection uses explicit [ERROR:xxx] prefix markers instead of fragile Chinese string matching"
  - "Shared AsyncClient uses lazy singleton with is_closed check for auto-rebuild"
  - "Crash recovery uses passive detection (connection error triggers restart) not polling"
  - "MAX_CRASH_COUNT=3 limits infinite restart loops (T-12-04 mitigation)"
  - "restart_log entries contain ISO timestamp and reason enum"
  - "archive_old_scenes called via lazy import in next_scene()"
metrics:
  duration: ~5min
  completed: "2026-04-14"
---

# Phase 12 Plan 02: Tools Fix & Enhancement Summary

**One-liner:** Shared AsyncClient pool, [ERROR:xxx] error markers replacing fragile Chinese string matching, actor crash recovery with passive detection and auto-restart capped at 3 attempts.

## Changes Made

### Task 1: actor_speak bug fix + shared AsyncClient + scene archival integration

**Part A: Error detection improvement (D-05/D-08)**
- Replaced fragile `"失败" in actor_dialogue` / `"超时" in actor_dialogue` string matching with explicit `[ERROR:xxx]` prefix markers
- All 3 error detection points in actor_speak now use `actor_dialogue.startswith("[ERROR:")` 
- Error categories: `[ERROR:connection]`, `[ERROR:timeout]`, `[ERROR:{exception_type}]`, `[ERROR:empty]`
- Empty response from `_call_a2a_sdk` now returns `[ERROR:empty]` instead of unmarked `[{name}已响应但无文本内容]`

**Part B: Shared AsyncClient (D-11/D-12)**
- Added `_shared_httpx_client` module-level variable
- `get_shared_client()`: lazy singleton with `is_closed` check for auto-rebuild
- `close_shared_client()`: async close + set None, safe to call when already None
- `_call_a2a_sdk()` now uses `get_shared_client()` instead of per-call `httpx.AsyncClient()`
- Removed `await httpx_client.aclose()` from `_call_a2a_sdk` (lifecycle managed by start/end drama)
- `start_drama()` calls `get_shared_client()` to initialize
- `end_drama()` calls `close_shared_client()` to clean up
- Connection pool limits: `max_connections=20, max_keepalive_connections=10`

**Part C: Scene archival integration**
- `next_scene()` now calls `archive_old_scenes(state)` before final `_set_state`
- Uses lazy import (`from .state_manager import archive_old_scenes`) to match codebase pattern

### Task 2: Actor crash recovery (passive detection + auto-restart)

**Core function: `_restart_actor()` (D-16/D-17/D-18/D-19)**
- Reads `crash_count` from state, increments by 1
- If `crash_count >= MAX_CRASH_COUNT (3)`: returns error without attempting restart
- Otherwise: calls `stop_actor_service()` → extracts memory → calls `create_actor_service()` with original config + memory
- Updates `crash_count` and appends to `restart_log` in state

**actor_speak integration:**
- Connection errors (`ConnectionError`, "refused", "connection") trigger `_restart_actor()`
- If restart succeeds: retry `_call_a2a_sdk()` once
- If retry fails: `[ERROR:connection] {name}重启后仍无法连接`
- If restart fails: `[ERROR:connection] {name}重启失败: {message}`
- On successful dialogue: `crash_count` resets to 0

## Tests Added

`tests/unit/test_tools_phase12.py` — 19 tests, 465 lines:

| Class | Tests | Coverage |
|-------|-------|----------|
| TestErrorDetection | 6 | [ERROR:xxx] marker detection |
| TestSharedAsyncClient | 6 | Singleton, rebuild after close, close, idempotent, _call_a2a_sdk integration |
| TestNextSceneArchival | 1 | next_scene calls archive_old_scenes |
| TestRestartActor | 4 | stop+create, crash_count increment, restart_log, max crash limit |
| TestActorSpeakCrashRecovery | 2 | connection error triggers restart, crash_count reset on success |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None. No new security surface beyond what's in the threat model.

## Self-Check: PASSED

All created files verified present. All commit hashes verified in git log.
