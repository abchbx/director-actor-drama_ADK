# Phase 7 Plan 02 Summary — Arc Tracking Integration

**Status:** ✅ Complete
**Date:** 2026-04-13

## Deliverables

### app/tools.py (EXTENDED)
- 5 new Tool functions: `create_thread`, `update_thread`, `resolve_thread`, `set_actor_arc`, `resolve_conflict_tool`
- All follow thin proxy pattern: get state → call pure function → set state → return
- `create_thread`: accepts comma-separated `involved_actors` string
- `resolve_conflict_tool`: named to avoid clash with `conflict_engine.resolve_conflict`
- Enhanced `inject_conflict`: D-02 thread_id wiring on conflict injection, D-14 suggested_threads when limit_reached
- Added imports from `arc_tracker` and `resolve_conflict` from `conflict_engine`

### app/context_builder.py (EXTENDED)
- `_build_arc_tracking_section(state)`: Shows active/dormant/resolved threads, ⚠️ dormant warnings with gap count
- Added `"arc_tracking": 5` to `_DIRECTOR_SECTION_PRIORITIES`
- Added `"actor_threads": 5` to `_ACTOR_SECTION_PRIORITIES`
- `_assemble_actor_sections()`: New actor thread/arc section — only active threads for the actor + arc_progress info
- `build_director_context()`: Added `_build_arc_tracking_section(state)` call

### app/agent.py (EXTENDED)
- Imported 5 new tools: `create_thread`, `update_thread`, `resolve_thread`, `set_actor_arc`, `resolve_conflict_tool`
- Registered all 5 in `_improv_director` tools list
- Added §9 弧线追踪与线索管理 prompt paragraph after §8

### tests/unit/test_tools_phase7.py (NEW)
- 18 tests across 5 test classes: TestCreateThreadTool, TestUpdateThreadTool, TestResolveThreadTool, TestSetActorArcTool, TestResolveConflictTool

### tests/unit/conftest.py (EXTENDED)
- Added `plot_threads: []` and `resolved_conflicts: []` to mock state
- Added `arc_progress` default to 朱棣 actor
- Added 苏念 actor for multi-actor tests

### tests/unit/test_context_builder.py (EXTENDED)
- TestBuildArcTrackingSection: 6 tests (no threads, active, dormant warning, resolved, priority)
- TestActorThreadSection: 5 tests (active threads, no threads, arc_progress, only active not dormant, priorities)

## Verification
- `uv run pytest tests/unit/test_tools_phase7.py tests/unit/test_context_builder.py tests/unit/test_arc_tracker.py -x` — all pass
- `uv run pytest tests/unit/ -x` — 340 passed (no regressions)
- `grep "create_thread" app/agent.py` — confirmed in import and tools list
- `grep "§9" app/agent.py` — confirmed
- `grep "_build_arc_tracking_section" app/context_builder.py` — confirmed
- `grep "suggested_threads" app/tools.py` — confirmed
- `grep "thread_id" app/tools.py` — confirmed D-02 wiring
