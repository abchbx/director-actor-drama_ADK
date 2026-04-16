---
phase: 12-integration-polish
plan: 01
subsystem: state_manager
tags: [debounce, conversation_log, scene-archival, persistence, backward-compat]
dependency_graph:
  requires: []
  provides: [debounce-saving, conversation-log-in-state, scene-archival]
  affects: [state_manager, context_builder]
tech_stack:
  added: [threading.Timer, atexit, SCENE_ARCHIVE_THRESHOLD]
  patterns: [debounce-write, state-embedded-conversation-log, scene-archival-threshold]
key_files:
  created:
    - tests/unit/test_state_manager.py
  modified:
    - app/state_manager.py
decisions:
  - D-09: 5-second debounce via threading.Timer for _set_state()
  - D-06: conversation_log migrated from global _conversation_log to state["conversation_log"]
  - D-10: Scene archival at 20-scene threshold with on-demand load_archived_scene()
  - D-07: _current_drama_folder migration deferred with TODO comment
metrics:
  duration: 1225s
  completed: 2026-04-14
  tasks: 2
  tests_added: 16
  tests_passed: 491
---

# Phase 12 Plan 01: State Manager Core Refactoring Summary

Debounce state saving (5s timer), conversation_log migration from global to ToolContext.state, and scene archival (20-scene threshold) — three tightly coupled refactors in state_manager.py.

## What Was Done

### Task 1: Debounce state saving + conversation_log migration

**Part A — Debounce (D-09):**
- Added `import threading`, `import atexit` to state_manager.py
- Added module-level debounce variables: `_save_dirty`, `_save_timer`, `_latest_theme`, `_latest_state_ref`, `DEBOUNCE_SECONDS = 5`
- Implemented `_flush_state()`: internal timer callback that writes pending state to disk
- Implemented `flush_state_sync()`: public function that cancels timer and forces immediate write
- Refactored `_set_state()`: no longer calls `_save_state_to_file()` directly; instead sets dirty flag and creates a daemon Timer
- Added `atexit.register(flush_state_sync)` at module bottom for zero data loss on exit
- Updated `save_progress()` to call `flush_state_sync()` before explicit save
- `init_drama_state()` retains direct `_save_state_to_file()` call after `_set_state()` (initialization should persist immediately)

**Part B — conversation_log migration (D-06):**
- Added `state["conversation_log"] = []` to `init_drama_state()`
- Refactored `add_conversation()`: writes to `state.setdefault("conversation_log", []).append(entry)`, triggers `_set_state()` for debounced save
- Refactored `get_conversation_log()`: reads from `state.get("conversation_log", [])`, filters by scene
- Refactored `export_conversations()`: reads from `state.get("conversation_log", [])`
- Refactored `clear_conversation_log()`: sets `state["conversation_log"] = []`, calls `_set_state()`
- Added backward compatibility in `load_progress()`: if `conversation_log` not in state, reads from old `conversations/conversation_log.json`
- Deprecated `_save_conversations()` (now a no-op) and `_get_conversations_dir()` (kept for export and backward compat)
- Removed module-level `_conversation_log: list[dict] = []` global variable
- Removed all `global _conversation_log` declarations
- Added TODO comment on `_current_drama_folder` (D-07 deferred)

### Task 2: Scene archival (20-scene threshold)

- Implemented `SCENE_ARCHIVE_THRESHOLD = 20` constant
- Implemented `archive_old_scenes(state)`: when scenes > 20, archives oldest scenes to `scenes/scene_{num:04d}.json` files, replaces with index metadata (scene_number, title, time_label, archived=True)
- Implemented `load_archived_scene(theme, scene_num)`: reads archived scene from disk, returns None if not found
- Verified `context_builder.py` needs NO changes: `_build_recent_scenes_section()` uses `scenes[-10:]`, `_extract_scene_transition()` uses `scenes[-1]` — both always in the kept (non-archived) region

## Files Modified

| File | Action | Lines |
|------|--------|-------|
| app/state_manager.py | Modified | 1369 (+160/-52) |
| tests/unit/test_state_manager.py | Created | 471 |

## Tests Passing

- 16 new unit tests in `test_state_manager.py`
- 491 total unit tests passing across entire test suite
- Test coverage: debounce (4 tests), conversation_log (6 tests), scene archival (4 tests), init/load (2 tests)

## Deviations from Plan

None — plan executed exactly as written. Context_builder.py confirmed to need no changes (as plan anticipated).

## Key Decisions

1. **Debounce uses daemon Timer** — Timer.daemon = True ensures no blocking on program exit; atexit handler provides explicit flush
2. **init_drama_state retains direct _save_state_to_file** — initialization must persist immediately, not wait 5 seconds
3. **_save_conversations() is no-op, not deleted** — backward compat: any code still calling it won't break
4. **_get_conversations_dir() preserved** — still used by export_conversations() for write path and load_progress() for backward compat
5. **Scene archival not auto-triggered** — archive_old_scenes() is a pure function; integration with next_scene() deferred to Plan 02

## Self-Check: PASSED

- FOUND: app/state_manager.py
- FOUND: tests/unit/test_state_manager.py
- FOUND: .planning/phases/12-integration-polish/12-01-SUMMARY.md
- FOUND: fc6fde5 (test commit)
- FOUND: bc7d7db (feat commit)
