---
phase: 11-timeline-tracking
plan: 01
subsystem: timeline
tags: [pure-functions, tdd, state-management, chinese-nlp]
dependency_graph:
  requires: [coherence_checker.py-patterns, state_manager.py-init-patterns]
  provides: [timeline_tracker.py, timeline-state-init, timeline-tests]
  affects: [app/state_manager.py, app/timeline_tracker.py]
tech_stack:
  added: [re-module-regex, chinese-numeral-lookup-table]
  patterns: [pure-functions, state-dict-input, dict-returns-with-status, lookup-table-for-cjk-numerals]
key_files:
  created:
    - app/timeline_tracker.py
    - tests/unit/test_timeline_tracker.py
  modified:
    - app/state_manager.py
decisions:
  - Chinese numeral conversion uses lookup table (一-九十九) for reliability over algorithmic parsing
  - _build_time脉络 uses reverse-lookup from _CHINESE_NUM_LOOKUP for Chinese day display
  - Jump detection only reports minor/significant jumps, not same-day (normal) changes
  - Flashback entries are skipped in jump detection (D-05 intentional time shifts)
  - MAX_TIME_PERIODS merge strategy: find earliest same-day group, merge scene_range
metrics:
  duration: ~42 minutes
  completed: 2026-04-13
  tasks: 2
  files: 3
  tests_added: 35
---

# Phase 11 Plan 01: Timeline Tracker Core Module Summary

Timeline tracker pure functions + state init + TDD tests — Chinese numeral parsing, time advancement with validation, jump detection with severity classification, and state_manager backward compatibility.

## What Was Built

### app/timeline_tracker.py
Core pure-function module for timeline tracking following coherence_checker.py patterns:
- **Constants**: `TIME_PERIODS` (7 period keywords), `TIMELINE_JUMP_THRESHOLDS` (minor=1, significant=3), `MAX_TIME_PERIODS=20`
- **`_chinese_num_to_int(text)`**: Lookup table converting Chinese numerals 一 through 九十九 to integers (99 entries)
- **`_extract_period(text)`**: Extracts TIME_PERIODS keywords from text using reverse iteration
- **`parse_time_description(text)`**: Parses "第三天黄昏" → `{day: 3, period: "黄昏"}` using regex + helpers
- **`advance_time_logic(state, time_description, day, period, flashback)`**: Full time advancement with auto-parsing, validation, MAX_TIME_PERIODS merge, auto jump detection
- **`detect_timeline_jump_logic(state)`**: Compares adjacent time_periods day values; classifies jumps as normal/minor/significant; skips flashback entries
- **`_merge_oldest_time_periods(state)`**: Merges same-day entries when exceeding MAX_TIME_PERIODS
- **`_build_time脉络(state)`**: Builds formatted timeline display with same-day merging and flashback markers

### app/state_manager.py (modified)
- **`init_drama_state()`**: Added `state["timeline"]` initialization after Phase 10 coherence_checks (D-26/D-27)
- **`load_progress()`**: Added `state.setdefault("timeline", {...})` for backward compatibility (D-28)

### tests/unit/test_timeline_tracker.py
35 TDD tests across 8 test classes:
- `TestAdvanceTimeLogic` (7 tests): full params, parse fallback, parse failure, flashback, MAX merge, invalid period, auto jump detection
- `TestParseTimeDescription` (6 tests): day+period, day-only, large numbers, unrecognized, period-only, various day numbers
- `TestChineseNumToInt` (6 tests): single digits, 十, teens, twenties, 九十九, unrecognized
- `TestExtractPeriod` (3 tests): all TIME_PERIODS, no match, full description
- `TestBuildTime脉络` (4 tests): same-day merging, different days, flashback prefix, empty
- `TestDetectTimelineJumpLogic` (7 tests): empty, single, same-day normal, minor jump, significant jump, multiple jumps, flashback skip
- `TestInitDramaStateTimeline` (1 test): timeline field initialization
- `TestLoadProgressTimeline` (1 test): backward compatibility setdefault

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] _build_time脉络 used integer day numbers instead of Chinese numerals**
- **Found during:** Task 1 (test failure)
- **Issue:** Output was "第1天" instead of "第一天" — inconsistent with descriptive time labels
- **Fix:** Added reverse-lookup from `_CHINESE_NUM_LOOKUP` to convert integer day back to Chinese numeral for display
- **Files modified:** app/timeline_tracker.py
- **Commit:** df3daa0

## Threat Mitigations

| Threat ID | Mitigation | Status |
|-----------|------------|--------|
| T-11-01 | parse_time_description validates day 1-99, period must be in TIME_PERIODS | ✅ Implemented |
| T-11-02 | MAX_TIME_PERIODS=20 with _merge_oldest_time_periods prevents unbounded growth | ✅ Implemented |

## Verification Results

```
35/35 tests passed in test_timeline_tracker.py
466/466 tests passed in full unit test suite
Import verification: all exports accessible
State manager timeline init verified
State manager load_progress backward compat verified
```

## Self-Check: PASSED

- app/timeline_tracker.py: FOUND
- tests/unit/test_timeline_tracker.py: FOUND
- 11-01-SUMMARY.md: FOUND
- Commit df3daa0: FOUND
