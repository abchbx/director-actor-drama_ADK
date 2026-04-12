---
phase: 05-mixed-autonomy-mode
reviewed: 2026-04-12T10:30:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - app/tools.py
  - app/context_builder.py
  - app/state_manager.py
  - app/agent.py
  - cli.py
  - tests/unit/test_tools_phase5.py
  - tests/unit/test_context_builder.py
  - tests/unit/test_integration.py
  - tests/unit/test_agent.py
  - tests/unit/conftest.py
findings:
  critical: 1
  warning: 3
  info: 3
  total: 7
status: issues_found
---

# Phase 5: Code Review Report

**Reviewed:** 2026-04-12T10:30:00Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Reviewed all Phase 5 (mixed-autonomy-mode) source changes across 10 files: 4 tool functions (auto_advance, steer_drama, end_drama, trigger_storm), 3 context builder sections, state migration, prompt restructure, DramaRouter updates, and CLI changes.

The implementation is well-structured with good test coverage (219 tests passing). Key concerns: one hardcoded API key in `.env` committed to the repo, a logic bug where `advance_scene()` overwrites the "ended" status breaking epilogue mode after first `/next`, a redundant `_set_state` call in `next_scene()`, and auto-advance soft cap that can be trivially bypassed by re-sending the same command.

## Critical Issues

### CR-01: Hardcoded API Key in Committed `.env` File

**File:** `app/.env:1`
**Issue:** The file `app/.env` contains a real API key (`sk-9wZ1DkQ75U90NymzORAVxeE0m3QqRvrCVLsmcejyB8UZh5E4`) committed to the repository. While `.gitignore` excludes `.env`, the file already exists in the working tree with a real secret. If this was ever committed to git history, the key is exposed. The `.env.example` correctly uses placeholder values, but the actual `.env` should never have been created with real credentials in the project directory.
**Fix:**
1. Rotate the exposed API key immediately
2. Verify the file is not in git history: `git log --all -- app/.env`
3. If it is in history, use `git filter-branch` or BFG Repo-Cleaner to remove it
4. Replace the key in `app/.env` with a placeholder matching `.env.example`

## Warnings

### WR-01: `advance_scene()` Overwrites "ended" Status, Breaking Epilogue Mode

**File:** `app/state_manager.py:829`
**Issue:** `advance_scene()` unconditionally sets `state["status"] = "acting"`. When a user calls `/end` (which sets status to "ended") and then `/next` to continue in epilogue/番外篇 mode, `next_scene()` calls `advance_scene()` which resets the status to "acting". This causes the `_build_epilogue_section()` (which checks `state.get("status") != "ended"`) to no longer inject the epilogue context. The director prompt explicitly states: "番外篇模式：/end 后如果用户继续 /next 或 /action，以番外篇/后日谈风格叙事" — but this is broken after the first `/next` call because the status is overwritten.
**Fix:**
```python
def advance_scene(tool_context=None) -> dict:
    state = _get_state(tool_context)
    state["current_scene"] = state.get("current_scene", 0) + 1
    # Only set "acting" if not in epilogue mode (preserve "ended" for 番外篇)
    if state.get("status") != "ended":
        state["status"] = "acting"
    state["updated_at"] = datetime.now().isoformat()
    _set_state(state, tool_context)
    return {
        "status": "success",
        "current_scene": state["current_scene"],
        "message": f"Advanced to scene {state['current_scene']}",
    }
```

### WR-02: Redundant Double `_set_state` Call in `next_scene()`

**File:** `app/tools.py:546,552`
**Issue:** When both `auto_remaining > 0` AND `steer_direction` is set, `next_scene()` calls `_set_state()` twice (line 546 for auto-advance decrement, line 552 for steer clear). Each `_set_state` call triggers `_save_state_to_file()` which performs a full JSON serialization and disk write. This is wasteful — the state should be mutated first, then persisted once.
**Fix:**
```python
    # Phase 5: Auto-advance counter decrement (A4 mitigation)
    auto_remaining = state.get("remaining_auto_scenes", 0)
    auto_status = ""
    state_changed = False

    if auto_remaining > 0:
        state["remaining_auto_scenes"] = max(0, auto_remaining - 1)
        auto_remaining = state["remaining_auto_scenes"]
        if auto_remaining == 0:
            auto_status = "\n\n🔄 自动推进已结束，回到手动模式。"
        else:
            auto_status = f"\n\n[自动推进中... 剩余 {auto_remaining} 场，输入任意内容中断]"
        state_changed = True

    # Phase 5: Clear steer_direction after it's been read for this scene (D-09)
    steer_info = state.get("steer_direction")
    if steer_info:
        state["steer_direction"] = None
        state_changed = True

    # Persist all Phase 5 changes in one write
    if state_changed:
        _set_state(state, tool_context)
```

### WR-03: `auto_advance()` Soft Cap is Trivially Bypassable

**File:** `app/tools.py:628-638`
**Issue:** The soft cap at 10 scenes returns a warning message asking the user to re-send the same command to confirm. However, re-sending `/auto 15` calls `auto_advance(15)` again, which hits the same `if scenes > 10` check and returns the same warning — it never actually sets the counter. The soft cap is effectively a hard cap because there is no mechanism to bypass the warning. The prompt says "如果确认，请再次发送 /auto {scenes}" but this creates an infinite loop of warnings. Either: (a) the soft cap should track confirmation state and allow bypass on second call, or (b) it should be documented as a hard cap.
**Fix:** Either implement a confirmation mechanism (e.g., a flag in state like `_auto_advance_confirmed = True`) or change the soft cap to actually allow the operation on the second invocation:
```python
def auto_advance(scenes: int, tool_context: ToolContext) -> dict:
    state = _get_state(tool_context)

    # D-05: Soft cap at 10 — allow bypass if user previously requested same count
    if scenes > 10:
        previous_request = state.get("_pending_auto_confirm")
        if previous_request != scenes:
            state["_pending_auto_confirm"] = scenes
            _set_state(state, tool_context)
            return {
                "status": "info",
                "message": (
                    f"⚠️ 请求推进 {scenes} 场超过建议上限(10场)。\n"
                    f"如果确认，请再次发送 /auto {scenes}"
                ),
                "remaining_auto_scenes": state.get("remaining_auto_scenes", 0),
            }
        # Second request with same count — clear confirmation flag and proceed
        state.pop("_pending_auto_confirm", None)

    state["remaining_auto_scenes"] = scenes
    _set_state(state, tool_context)
    # ...
```

## Info

### IN-01: Duplicate Auto-Advance and Steer Info in Director Context

**File:** `app/context_builder.py:506-517` and `app/context_builder.py:647-717`
**Issue:** The `_build_current_status_section()` (priority 10) displays auto-advance status and steer direction, while `_build_auto_advance_section()` (priority 9) and `_build_steer_section()` (priority 8) also display the same information with slightly different wording. This means the director context contains the same information twice — once in the "current status" summary and once in the dedicated section. This wastes tokens without adding value.
**Fix:** Remove the auto-advance and steer lines from `_build_current_status_section()` since the dedicated sections already provide this information with more detail. The current_status section should only show: theme, scene number, and drama status.

### IN-02: `auto_advance()` Does Not Validate `scenes <= 0`

**File:** `app/tools.py:614-652`
**Issue:** `auto_advance()` accepts `scenes <= 0` without validation. Setting `scenes=0` writes `remaining_auto_scenes=0` (no-op but wasteful), and `scenes=-1` writes `-1` to the counter. While `_build_auto_advance_section` checks `remaining <= 0`, the `next_scene()` code only decrements when `auto_remaining > 0`, so a negative value would be harmless but semantically wrong. The function should validate the input.
**Fix:** Add input validation at the start of `auto_advance()`:
```python
if scenes <= 0:
    return {"status": "error", "message": "自动推进场数必须大于0。"}
```

### IN-03: `steer_drama()` Does Not Validate Empty Direction

**File:** `app/tools.py:655-679`
**Issue:** `steer_drama()` accepts an empty string as `direction`. This would set `steer_direction=""` in state, and `_build_steer_section()` checks `if not steer` — but an empty string `""` is falsy, so the section wouldn't render. However, `next_scene()` checks `if steer_info:` before clearing — an empty string would pass this check and trigger an unnecessary `_set_state` call. The inconsistency between "setting" and "displaying" an empty steer could cause subtle bugs.
**Fix:** Add validation at the start of `steer_drama()`:
```python
if not direction or not direction.strip():
    return {"status": "error", "message": "方向引导不能为空。"}
```

---

_Reviewed: 2026-04-12T10:30:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
