---
phase: 04-infinite-loop-engine
reviewed: 2026-04-12T08:30:00Z
depth: quick
files_reviewed: 7
files_reviewed_list:
  - app/agent.py
  - app/context_builder.py
  - app/tools.py
  - app/state_manager.py
  - tests/unit/test_agent.py
  - tests/unit/test_context_builder.py
  - tests/unit/test_integration.py
findings:
  critical: 1
  warning: 3
  info: 4
  total: 8
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-04-12T08:30:00Z
**Depth:** quick
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Reviewed all 7 files changed in Phase 04 (infinite-loop-engine). The phase replaced StormRouter with DramaRouter (2 sub-agents), added scene transition extraction, and implemented legacy status migration. Found 1 critical bug (stale `drama_status` in `load_progress` return), 3 warnings (legacy status values still set at runtime, test masking production bug, redundant import), and 4 info items.

## Critical Issues

### CR-01: `load_progress` returns stale pre-migration `drama_status`

**File:** `app/state_manager.py:487`
**Issue:** `load_progress()` calls `_migrate_legacy_status(state)` on line 476 which mutates `state["status"]` from old values (e.g., `"brainstorming"`, `"storm_researching"`) to new values (`"setup"` or `"acting"`). However, the return dict on line 487 reads `save_data.get("status", "")` — the **original unmigrated** data, not the migrated `state`. Downstream consumers like `load_drama()` (tools.py:727) use `result.get("drama_status", "")` to build next-action guidance. This means after loading an old STORM-era save, the user sees the old status (e.g., `"storm_researching"`) instead of the migrated status, causing the guidance branch in `load_drama()` lines 728-738 to fall through to the generic else clause: `"▶️ 请使用 /next 继续剧情。"` — which is incorrect for a drama that should be in `"setup"` or `"acting"` state.
**Fix:**
```python
# state_manager.py, load_progress(), lines 483-493
return {
    "status": "success",
    "message": f"Loaded drama: {save_data.get('theme', 'Unknown')}",
    "theme": save_data.get("theme", ""),
    "drama_status": state.get("status", ""),   # Use migrated state, not save_data
    "current_scene": state.get("current_scene", 0),  # Also use state for consistency
    "num_actors": len(state.get("actors", {})),
    "num_scenes": len(state.get("scenes", [])),
    "actors_list": list(state.get("actors", {}).keys()),
    "drama_folder": os.path.dirname(state_file),
}
```

## Warnings

### WR-01: Legacy STORM status values still set at runtime

**File:** `app/tools.py:75,969,1029,1145` and `app/state_manager.py:339`
**Issue:** The Phase 04 migration introduced new status values (`"setup"`, `"acting"`) and `_migrate_legacy_status()` to convert old values on load. However, multiple code paths still **set** old status values at runtime:
- `start_drama()` sets `"brainstorming"` (tools.py:75)
- `init_drama_state()` sets `"brainstorming"` (state_manager.py:339)
- `storm_discover_perspectives()` sets `"storm_discovering"` then `"storm_researching"` (tools.py:969,1029)
- `storm_research_perspective()` sets `"storm_outlining"` (tools.py:1145)

While `DramaRouter` routing is based on actors existence (not status), and `_migrate_legacy_status` handles saved states, these runtime-set legacy values still appear in `show_status()`, `build_director_context()`, and the saved JSON — creating inconsistency with the new status model. If any future code adds status-based branching, these legacy values will cause bugs.
**Fix:** Replace all runtime `set_drama_status("brainstorming"/"storm_*")` calls with `"setup"`. The STORM tools are now consolidated into `_setup_agent`, so intermediate statuses are no longer needed:
```python
# tools.py:75
set_drama_status("setup", tool_context)  # was "brainstorming"

# state_manager.py:339
state["status"] = "setup"  # was "brainstorming"

# tools.py:969,1029,1145 — remove or change to "setup"
```

### WR-02: `next_scene()` tests mock `advance_scene` without state mutation, masking production bug

**File:** `tests/unit/test_agent.py:275,292,303,317,334,345`
**Issue:** All 6 tests in `TestNextSceneTransition` mock `advance_scene` to return `{"status": "success"}` without mutating state. In production, `advance_scene` increments `current_scene` via `_set_state`, so `tool_context.state["drama"]` reflects the incremented value when `_extract_scene_transition` runs. In tests, the state is never incremented, so `_extract_scene_transition` sees `current_scene=0` and `scenes=[]`, matching the test assertions. This means the tests pass for the wrong reason — they verify behavior against an un-mutated state that never occurs in production.
**Fix:** Either: (a) make the mock also mutate `tool_context.state["drama"]["current_scene"]` to simulate production behavior, or (b) extract the transition logic into a testable pure function that receives `scene_num_before_advance` as a parameter. Option (b) is cleaner:
```python
# In next_scene(), save the scene number BEFORE advancing:
scene_num_before = state.get("current_scene", 0)
result = advance_scene(tool_context)
state = tool_context.state.get("drama", {})
transition = _extract_scene_transition(state, scene_before_advance=scene_num_before)
```

### WR-03: `next_scene()` has redundant local import of `_extract_scene_transition`

**File:** `app/tools.py:507`
**Issue:** `_extract_scene_transition` is already imported at module level on line 53 (`from .context_builder import build_actor_context, build_director_context, _extract_scene_transition`), but `next_scene()` re-imports it locally on line 507 (`from .context_builder import _extract_scene_transition`). The local import is unnecessary and creates confusion about which import is authoritative.
**Fix:** Remove the local import on line 507:
```python
# Delete this line:
#   from .context_builder import _extract_scene_transition
# The module-level import on line 53 already provides it.
```

## Info

### IN-01: Utility command routing uses substring matching

**File:** `app/agent.py:321`
**Issue:** `force_improvise = any(cmd in user_message for cmd in utility_commands)` uses substring matching. A user message like "我想要cast角色" or "让我们save一下" would match `/cast` or `/save` and force routing to `improv_director`. While this is unlikely to cause issues in practice (commands typically start with `/`), it could misroute conversational messages containing these substrings.
**Fix:** Consider using startswith matching: `any(user_message.strip().startswith(cmd) for cmd in utility_commands)` or word-boundary matching.

### IN-02: `_EMOTION_CN` dict duplicated across files

**File:** `app/tools.py:226-230` vs `app/context_builder.py:70-74`
**Issue:** The emotion-to-Chinese mapping dictionary is defined twice: once in `context_builder.py` as `_EMOTION_CN` and again inline in `tools.py`'s `actor_speak()` function. If a new emotion is added to one but not the other, they'll drift out of sync.
**Fix:** Import `_EMOTION_CN` from `context_builder.py` in `tools.py` instead of defining the inline dict.

### IN-03: `_truncate_sections` mutates input list in-place

**File:** `app/context_builder.py:155`
**Issue:** `_truncate_sections()` calls `section["items"].pop(0)` and modifies `section["text"]` on the input `sections` list. This mutates the caller's data, which could cause issues if the same sections are reused. Currently this is fine since sections are built fresh each call, but it's a maintainability trap.
**Fix:** Document the mutation behavior in the docstring or make a shallow copy at entry.

### IN-04: `_conversation_log` is a module-level global — not safe for concurrent requests

**File:** `app/state_manager.py:18`
**Issue:** `_conversation_log` is a module-level mutable list. If two drama sessions run concurrently, they'll share and contaminate each other's conversation logs. This is pre-existing (not introduced in Phase 04), but worth noting since Phase 04 added `load_drama` which clears this log on load.
**Fix:** For future consideration: scope conversation logs to drama state instead of module global.

---

_Reviewed: 2026-04-12T08:30:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: quick_
