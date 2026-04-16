---
phase: 11-timeline-tracking
plan: 02
subsystem: timeline-integration
tags: [tools, context-builder, agent-prompt, coherence-checker, integration]
dependency_graph:
  requires: [timeline_tracker.py, coherence_checker.py, context_builder.py, agent.py, tools.py]
  provides: [advance_time-tool, detect_timeline_jump-tool, add_fact-time_context, write_scene-time_label, _build_timeline_section, actor-current_time, §12-时间线管理, temporal-consistency-prompt]
  affects: [app/tools.py, app/context_builder.py, app/agent.py, app/coherence_checker.py, tests/unit/test_timeline_integration.py]
tech_stack:
  added: []
  patterns: [thin-proxy-tool, section-builder-dict, keyword-only-toolcontext, prompt-§number-format]
key_files:
  created:
    - tests/unit/test_timeline_integration.py
  modified:
    - app/tools.py
    - app/context_builder.py
    - app/agent.py
    - app/coherence_checker.py
decisions:
  - advance_time uses *, for tool_context keyword-only arg (consistent with add_fact pattern)
  - time_context added to fact dict post-creation in Tool layer (logic function unchanged, same pattern as repair_contradiction)
  - _build_timeline_section returns empty text when timeline is None (defensive)
  - Actor 【当前时间】 only shown when current_time is non-empty (no "第一天" default noise for new dramas)
metrics:
  duration: ~15 minutes
  completed: 2026-04-13
  tasks: 2
  files: 5
  tests_added: 9
---

# Phase 11 Plan 02: Timeline Integration Layer Summary

Timeline integration into director/actor context, Tool functions, agent prompt §12, and coherence_checker temporal validation — connecting Plan 01 pure functions to the full director-actor workflow.

## What Was Built

### app/tools.py (modified)
- **`advance_time(time_description, day, period, flashback, *, tool_context)`** (D-31/D-07): Thin proxy to `advance_time_logic` — sets timeline default, calls logic, persists state, returns formatted dict with ⏰ message
- **`detect_timeline_jump(tool_context)`** (D-32): Thin proxy to `detect_timeline_jump_logic` — persists `last_jump_check` in timeline state on success
- **`add_fact()` extended** (D-33/D-18): Added optional `time_context: str | None = None` parameter; when provided, post-creates `time_context` field on the newly added fact dict
- **`write_scene()` extended** (D-08): After `update_script()`, reads `timeline.current_time` and sets `time_label` on the matching scene dict
- **Import added**: `from .timeline_tracker import advance_time_logic, detect_timeline_jump_logic`

### app/context_builder.py (modified)
- **`_build_timeline_section(state)`** (D-20/D-23): Full section builder returning dict with key/text/priority/truncatable — shows current time, days elapsed, scene coverage, jump alerts, and time lineage
- **`_DIRECTOR_SECTION_PRIORITIES["timeline"] = 5`** (D-21): Same priority as facts, tension, arc_tracking
- **`_ACTOR_SECTION_PRIORITIES["current_time"] = 6`** (D-22): Same priority as anchor — time info constrains behavior
- **【当前时间】paragraph in `_assemble_actor_sections`** (D-22): One-line display `【当前时间】{current_time}`, only shown when non-empty
- **Import added**: `from .timeline_tracker import _build_time脉络, TIME_PERIODS`
- **`build_director_context` sections list**: Added `_build_timeline_section(state)` after `_build_facts_section(state)`

### app/agent.py (modified)
- **§12 时间线管理** added to `_INSTRUCTION_STRATEGY` (D-24/D-25): 4 rules — advance_time on scene changes, respond to jump alerts, add_fact with time_context, cross-validate timeline with facts
- **Tool imports**: Added `advance_time` and `detect_timeline_jump`
- **`_improv_director` tools list**: Registered `advance_time` and `detect_timeline_jump` (Phase 11)

### app/coherence_checker.py (modified)
- **`validate_consistency_prompt()` enhanced** (D-17): Added temporal consistency instruction — "检查事件时序：事实中标记了 time_context 的，其因果顺序应与时间线一致。如果事实 A 发生在事实 B 之后但 time_context 更早，这是时序矛盾。"

### tests/unit/test_timeline_integration.py (created)
9 integration tests across 2 test classes:
- `TestTimelineIntegration` (5 tests): advance_time state updates, auto jump detection, temporal prompt check, time lineage display, fact time_context storage
- `TestTimelineContextBuilder` (4 tests): timeline section shows current time, jump alerts, director priority=5, actor priority=6

## Deviations from Plan

None — plan executed exactly as written.

## Threat Mitigations

| Threat ID | Mitigation | Status |
|-----------|------------|--------|
| T-11-03 | advance_time time_description parse failures handled gracefully — updates current_time string but warns | ✅ Inherited from Plan 01 |
| T-11-04 | add_fact time_context is optional field, no validation against timeline — LLM trusted for creative decisions | ✅ Implemented |
| T-11-05 | Actor sees only current_time, no sensitive timeline details exposed | ✅ Implemented |

## Verification Results

```
9/9 tests passed in test_timeline_integration.py
44/44 tests passed in test_timeline_tracker.py + test_timeline_integration.py
475/475 tests passed in full unit test suite
§12 exists in agent.py: ✅
advance_time registered in _improv_director: ✅
_build_timeline_section in context_builder.py: ✅
时序 in coherence_checker.py: ✅
Import verification: all exports accessible ✅
```

## Self-Check: PASSED

- app/tools.py: FOUND (advance_time, detect_timeline_jump, time_context, time_label)
- app/context_builder.py: FOUND (_build_timeline_section, priorities, actor time paragraph)
- app/agent.py: FOUND (§12, imports, tools registration)
- app/coherence_checker.py: FOUND (时序矛盾)
- tests/unit/test_timeline_integration.py: FOUND
- Commit 23ba4d4: FOUND
- Commit f60c685: FOUND
