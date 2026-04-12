---
phase: 01-memory-foundation
plan: 02
subsystem: memory-integration
tags: [integration, state-manager, tools, memory, migration]
dependency_graph:
  requires: [01-01]
  provides: [memory-integration, mark-memory-tool, auto-migration]
  affects: [app/state_manager.py, app/tools.py, app/agent.py]
tech_stack:
  added: [memory_manager integration, 3-tier context in prompts]
  patterns: [delegation pattern, auto-migration on load, importance detection]
key_files:
  created:
    - tests/unit/test_integration.py
  modified:
    - app/state_manager.py
    - app/tools.py
    - app/agent.py
decisions:
  - D-12: New actors get 4 new memory fields at registration
  - D-13: Old memory field preserved as read-only for backward compatibility
  - D-11: Auto-migration on load_progress triggers when working_memory missing
  - D-06: mark_memory maps free-text reason to CRITICAL_REASONS, defaults to 用户标记
  - Pitfall 5: Actor records own dialogue in working memory after A2A response
metrics:
  duration: 5min
  completed: "2026-04-11"
  tasks: 2
  files_modified: 3
  files_created: 1
  tests_added: 10
---

# Phase 01 Plan 02: Integration — state_manager.py & tools.py Summary

3-tier memory architecture integrated into existing system: state_manager registration/migration, tools.py actor_speak with layered context, /mark command via mark_memory tool.

## Changes Made

### Task 1: state_manager.py (4 changes)

1. **register_actor()** — Added 4 new memory fields (`working_memory`, `scene_summaries`, `arc_summary`, `critical_memories`) to actor_data dict, preserving old `memory` field (D-13)
2. **update_actor_memory()** — Replaced direct memory append with delegation to `add_working_memory()`, including auto importance detection via `detect_importance()`
3. **load_progress()** — Added auto-migration loop that calls `migrate_legacy_memory()` for actors without `working_memory` field
4. **get_all_actors()** — Added `working_memory_count`, `scene_summaries_count`, `critical_memories_count`, `has_arc_summary` to summary output

### Task 2: tools.py + agent.py (4 changes)

1. **actor_speak()** — Replaced flat `memory_str` construction with `build_actor_context()`, added role/personality/emotion anchor to prompt, added importance detection for situation, recorded dialogue in working memory after A2A response
2. **load_drama()** — Replaced flat memory extraction with new 3-tier structure extraction (working_memory + critical_memories + arc_summary), with fallback to old format
3. **mark_memory** — New tool function that marks last working memory entry as critical, maps user free-text reason to closest CRITICAL_REASONS category (default: "用户标记")
4. **agent.py** — Added `mark_memory` import and tool to `_storm_director` tools list

## Test Coverage

- 10 integration tests in `tests/unit/test_integration.py`
- All 33 tests pass (10 integration + 23 memory_manager unit)
- Full suite: 35 passed

## Commits

| Commit | Message |
|--------|---------|
| 65f1ec9 | feat(01-02): update state_manager.py — new fields, delegation, migration, stats |
| 35422ae | feat(01-02): update tools.py and agent.py — new memory integration + mark_memory tool |

## Deviations from Plan

None - plan executed exactly as written.

## Verification

- ✅ `python -m pytest tests/unit/test_integration.py tests/unit/test_memory_manager.py -x -q` — all green (33 passed)
- ✅ `python -c "from app.tools import mark_memory; print('OK')"` — mark_memory importable
- ✅ `python -c "from app.agent import _storm_director; ... assert 'mark_memory' in tools"` — tool registered
- ✅ `python -m pytest tests/ -x -q` — full suite green (35 passed)

## Self-Check: PASSED

All created files verified present. All commits verified in git log.
