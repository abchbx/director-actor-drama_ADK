---
phase: 04-infinite-loop-engine
plan: 02
subsystem: context_builder
tags: [scene-transition, context-assembly, LOOP-03]
dependency_graph:
  requires: []
  provides: [_extract_scene_transition, _build_last_scene_transition_section, last_scene_transition priority 7]
  affects: [build_director_context, _DIRECTOR_SECTION_PRIORITIES]
tech_stack:
  added: []
  patterns: [pure-function-extraction, section-builder-pattern]
key_files:
  created: []
  modified:
    - app/context_builder.py
    - tests/unit/test_context_builder.py
decisions:
  - Priority 7 for last_scene_transition (higher than recent_scenes=4, lower than current_status=10)
  - Non-truncatable section (transition info must always be shown for continuity)
  - _extract_scene_transition as pure function (no LLM calls, per D-08)
  - Max 5 unresolved items to save tokens
  - is_first_scene=True when current_scene==0 OR scenes empty
metrics:
  duration: 5m
  completed: "2026-04-12"
  tasks: 1
  files: 2
---

# Phase 4 Plan 2: Scene Transition Section Summary

## One-liner

Added _extract_scene_transition() and _build_last_scene_transition_section() to context_builder.py, providing 3-element scene transition (last ending + actor emotions + unresolved events) with priority 7 and non-truncatable status.

## What Changed

### app/context_builder.py
- Added `"last_scene_transition": 7` to `_DIRECTOR_SECTION_PRIORITIES`
- Added `_extract_scene_transition(state)` — pure function extracting 3 transition elements from state:
  - ① Last scene ending from `scenes[-1].description` + `content` tail
  - ② Actor emotions mapped via `_EMOTION_CN`
  - ③ Unresolved events from `critical_memories` (reason="未决事件") + `arc_summary.structured.unresolved`
- Added `_build_last_scene_transition_section(state)` — section builder returning `{key, text, priority=7, truncatable=False}`
- Wired `_build_last_scene_transition_section(state)` into `build_director_context()` sections list after `_build_current_status_section(state)`

### tests/unit/test_context_builder.py
- Added `TestExtractSceneTransition` class (6 tests)
- Added `TestBuildLastSceneTransitionSection` class (4 tests)
- Added `TestDirectorContextTransitionIntegration` class (2 tests)
- Updated imports to include `_extract_scene_transition` and `_build_last_scene_transition_section`

## Deviations from Plan

None — plan executed exactly as written.

## Test Results

```
60 passed in 1.25s (tests/unit/test_context_builder.py -x -q)
```

## Verification

```
grep "_extract_scene_transition" app/context_builder.py → 2 matches ✓
grep "_build_last_scene_transition_section" app/context_builder.py → 2 matches ✓
grep "last_scene_transition.*7" app/context_builder.py → 1 match ✓
```

## Self-Check: PASSED

- [x] `app/context_builder.py` exists — FOUND
- [x] `tests/unit/test_context_builder.py` exists — FOUND
- [x] Commit `9ceaa49` exists — FOUND
