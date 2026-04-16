# Phase 7 Plan 01 Summary — Arc Tracker Core

**Status:** ✅ Complete
**Date:** 2026-04-13

## Deliverables

### app/arc_tracker.py (NEW)
- 4 pure functions: `create_thread_logic`, `update_thread_logic`, `resolve_thread_logic`, `set_actor_arc_logic`
- Constants: `ARC_TYPES` (4 entries), `ARC_STAGES` (4 entries), `DORMANT_THRESHOLD=8`, `MAX_PROGRESS_NOTES=10`, `MAX_RESOLVED_CONFLICTS=20`
- `_init_arc_tracker_defaults()` returns `{"plot_threads": []}`
- `_DEFAULT_ARC_PROGRESS` template with arc_type/arc_stage/progress/related_threads

### app/conflict_engine.py (EXTENDED)
- Added `resolved_conflicts: []` to `_init_conflict_engine_defaults()`
- Added `resolve_conflict(conflict_id, state)` — moves conflict from active to resolved list, trims to MAX_RESOLVED_CONFLICTS

### app/state_manager.py (EXTENDED)
- `init_drama_state()`: Added `plot_threads: []` and `resolved_conflicts: []` in conflict_engine
- `register_actor()`: Added `arc_progress` default dict to actor_data
- `load_progress()`: Added backward compat setdefault for `plot_threads`, `arc_progress` per actor, `resolved_conflicts` in conflict_engine

### tests/unit/test_arc_tracker.py (NEW)
- 33 tests across 5 test classes covering all pure functions and constants
- Tests: ID generation, actor validation, status transitions, progress_notes FIFO, linked conflict hints, partial updates

## Verification
- `uv run pytest tests/unit/test_arc_tracker.py tests/unit/test_conflict_engine.py -x` — all pass
- `uv run pytest tests/unit/ -x` — 311 passed (no regressions)
