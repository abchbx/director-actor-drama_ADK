---
phase: 01-memory-foundation
reviewed: 2026-04-11T12:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - app/memory_manager.py
  - app/state_manager.py
  - app/tools.py
  - app/agent.py
  - tests/unit/test_memory_manager.py
  - tests/unit/test_integration.py
  - tests/unit/test_async_compression.py
  - tests/unit/conftest.py
findings:
  critical: 2
  warning: 5
  info: 3
  total: 10
status: issues_found
---

# Phase 1: Code Review Report

**Reviewed:** 2026-04-11T12:00:00Z
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Reviewed 8 source files implementing the 3-tier drama memory architecture (working memory → scene summaries → arc summary) with async LLM compression, critical memory protection, and legacy migration. The core logic is well-structured and the test coverage is reasonable, but there are two critical bugs and several warnings that need attention.

**Critical issues:** An operator precedence bug in `tools.py` causes incorrect error dialogue detection, and a missing bounds check in `mark_critical_memory` allows invalid index operations on empty working memory.

**Key concerns:** The async compression fallback path uses `asyncio.run()` which can conflict with running event loops, and a module-level mutable `_conversation_log` shares state across dramas without isolation.

## Critical Issues

### CR-01: Operator precedence bug in error dialogue detection

**File:** `app/tools.py:275`
**Issue:** The condition `actor_dialogue.startswith("[") and "失败" in actor_dialogue or "超时" in actor_dialogue` has incorrect operator precedence. Python evaluates `and` before `or`, so the expression is parsed as `(actor_dialogue.startswith("[") and "失败" in actor_dialogue) or "超时" in actor_dialogue`. This means ANY dialogue containing "超时" (even legitimate dialogue like "我们讨论了超时工作的问题") will be flagged as an error and formatted with ⚠️. Additionally, this condition at line 275 is inconsistent with the similar checks at lines 257 and 267 which correctly use `startswith("[") and ("失败" in ... or "超时" in ...)`.

**Fix:**
```python
# Line 275: Fix operator precedence with parentheses
if actor_dialogue.startswith("[") and ("失败" in actor_dialogue or "超时" in actor_dialogue):
    formatted_lines.append(f"  ⚠️ {actor_dialogue}")
```

### CR-02: IndexError when `mark_critical_memory` called with `memory_index=-1` on empty list

**File:** `app/memory_manager.py:715-718`
**Issue:** The bounds check on line 715 is `if memory_index < 0 or memory_index >= len(working)`. When `working` is empty, `len(working)-1` evaluates to `-1`. The caller `mark_memory` in `tools.py` (line 878) passes `memory_index=len(working) - 1`, which becomes `-1` for empty working memory. Since the check `memory_index < 0` catches `-1`, it returns an error. However, if `working` has exactly 1 entry, `len(working)-1 = 0`, and `pop(0)` works. The real bug is that `mark_memory` in `tools.py` does check `if not working` on line 864, BUT `mark_critical_memory` itself does NOT guard against `memory_index=-1` from other callers who might pass `-1` directly — and `-1 < 0` IS caught. The actual edge case is: if a race condition or stale state causes `working` to become empty between the `if not working` check in `mark_memory` and the `mark_critical_memory` call, `memory_index=-1` would pass the `< 0` check correctly. However, the error message on line 716 would say `"索引 -1 超出范围（0--1）。"` — showing `0--1` which is confusing. More critically, the `mark_memory` tool function checks `if not working` but doesn't verify `len(working) > 0` before computing `len(working) - 1`, and the error message from `mark_critical_memory` uses `f"索引 {memory_index} 超出范围（0-{len(working)-1}）。"` which produces `0--1` when the list is empty, leaking implementation details.

**Fix:**
```python
# In mark_critical_memory (memory_manager.py line 715-716):
if not working or memory_index < 0 or memory_index >= len(working):
    return {"status": "error", "message": f"索引 {memory_index} 超出范围。工作记忆为空或索引无效。"}
```

## Warnings

### WR-01: `asyncio.run()` in `check_and_compress` can conflict with running event loops

**File:** `app/memory_manager.py:544,573`
**Issue:** The `check_and_compress` function catches `RuntimeError` from `asyncio.get_running_loop()` and falls back to `asyncio.run()`. However, `asyncio.run()` creates a NEW event loop and will fail with `RuntimeError` if called from within an existing event loop's callback (which is the case when `check_and_compress` is called from within an async context that already has a loop but the function itself is synchronous). The inner `except RuntimeError: pass` on lines 552-554 and 577-578 silently swallows this error, leaving pending_entries in the queue indefinitely with no compression happening. In ADK's async runtime, `check_and_compress` is called from `add_working_memory` which is a sync tool function — but ADK may run tool functions inside an event loop, making `asyncio.get_running_loop()` succeed but `loop.create_task()` run in a context where the task may never be awaited.

**Fix:** Consider making `check_and_compress` an async function, or use `asyncio.ensure_future()` with a dedicated background thread/loop for the sync fallback path. At minimum, log a warning when compression is skipped due to event loop conflicts:
```python
except RuntimeError:
    logger.warning(f"Cannot compress memory for {actor_name}: no event loop available. Entries retained in pending.")
    pass
```

### WR-02: Module-level `_conversation_log` shares state across dramas without isolation

**File:** `app/state_manager.py:18`
**Issue:** `_conversation_log: list[dict] = []` is a module-level mutable variable. If the user loads a different drama, the in-memory conversation log from the previous drama persists unless explicitly cleared. The `load_progress` function does not call `clear_conversation_log()`, so conversation entries from drama A could be mixed with entries from drama B if both are accessed in the same process session. The `get_conversation_log` function only loads from disk if `_conversation_log` is empty (line 208), so stale data from the previous drama may be returned.

**Fix:**
```python
# In load_progress() or init_drama_state(), clear the conversation log:
def load_progress(save_name: str, tool_context=None) -> dict:
    global _conversation_log
    _conversation_log = []  # Clear before loading new drama
    # ... rest of the function
```

### WR-03: `save_state_clean` mutates `actor_data` but doesn't propagate changes back to state dict

**File:** `app/memory_manager.py:330-338`
**Issue:** `save_state_clean` iterates over `state.get("actors", {}).items()` and calls `_serialize_pending_for_save(actor_data)` for each actor. The function mutates `actor_data` in place, which DOES modify the dict value since Python dicts are passed by reference. However, the iteration `for actor_name, actor_data in state.get("actors", {}).items()` gets a view of the dict, and the mutation of the nested dict should work. This is actually correct in Python because `actor_data` is a reference to the nested dict. However, this pattern is fragile — if the state dict is ever replaced wholesale (which `_set_state` does by reassigning `tool_context.state["drama"]`), the serialized changes could be lost if `_set_state` is called with a stale reference. This is currently not a live bug because `save_state_clean` is called standalone without a subsequent `_set_state`, but it's a latent risk.

**Fix:** No immediate code change needed, but add a comment documenting the in-place mutation contract:
```python
def save_state_clean(tool_context: ToolContext) -> None:
    """Clean _pending_compression in all actors before state save.
    
    NOTE: Mutates actor_data dicts in-place within the state dict.
    Call this BEFORE _set_state() — the mutations are visible through
    the state dict reference.
    """
```

### WR-04: List comparison in compression fallback may remove duplicate valid entries

**File:** `app/memory_manager.py:548-551`
**Issue:** After `asyncio.run()` compression succeeds, the code filters pending_entries with `if e not in overflow`. Since both `pending_entries` and `overflow` are lists of dicts, `not in` uses value equality (`==`). If two memory entries have identical content (same entry text, importance, and scene), this filter will remove BOTH from pending, even if only one was part of the overflow being compressed. This could cause valid pending entries to be silently dropped.

**Fix:** Use index-based removal or track which entries were compressed by reference:
```python
# Instead of list comprehension with 'not in', remove overflow entries by identity:
overflow_set = set(id(e) for e in overflow)
pending["pending_entries"] = [
    e for e in pending.get("pending_entries", [])
    if id(e) not in overflow_set
]
```
Or more simply, since overflow entries are the ones just compressed:
```python
pending["pending_entries"] = []  # All pending were compressed
```

### WR-05: `detect_importance` keyword matching can produce false positives for short common words

**File:** `app/memory_manager.py:822-830`
**Issue:** The keyword matching uses `if keyword in combined_text` (substring match). Some keywords like "兴奋" (from 情感高峰) and "愤怒" (from 情感低谷) are common words that appear in normal text. For example, an entry "面对情境: 他兴奋地跑来告诉我好消息" would be classified as 情感高峰 (critical) even if it's a minor event. The word "登场" (from 首次登场) would match "舞台登场" in any theatrical context, always triggering critical. This is a design trade-off acknowledged in the code (D-06), but the false positive rate could be reduced.

**Fix:** Consider requiring multiple keyword hits or using word-boundary matching:
```python
# At minimum, document the false-positive risk and suggest manual review:
def detect_importance(entry_text: str, situation: str = "") -> tuple[bool, Optional[str]]:
    """Detect if a memory entry matches any critical event pattern (D-06).
    
    WARNING: Uses substring matching which can produce false positives.
    Critical detections should be confirmed by the director before marking.
    """
```

## Info

### IN-01: Duplicated emotion mapping dictionary

**File:** `app/memory_manager.py:628-632` and `app/tools.py:225-229`
**Issue:** The emotion-to-Chinese mapping dict `{"neutral": "平静", "angry": "愤怒", ...}` is duplicated in both `build_actor_context()` and `actor_speak()`. Any update to emotion labels must be made in both places.

**Fix:** Extract to a shared constant:
```python
# In memory_manager.py or a constants module:
EMOTION_LABELS = {
    "neutral": "平静", "angry": "愤怒", "sad": "悲伤", "happy": "喜悦",
    "fearful": "恐惧", "confused": "困惑", "determined": "决绝",
    "anxious": "焦虑", "hopeful": "充满希望",
}
```

### IN-02: Import statement in middle of test file

**File:** `tests/unit/test_integration.py:217`
**Issue:** `import os` is placed in the middle of the file (between two test classes) rather than at the top with other imports. This violates PEP 8 style conventions.

**Fix:** Move `import os` to the top of the file with the other imports.

### IN-03: `check_and_compress` is a synchronous function that manages async tasks

**File:** `app/memory_manager.py:493`
**Issue:** `check_and_compress` is a sync function that calls `asyncio.get_running_loop()` and `loop.create_task()` to launch async compression. This mixing of sync/async patterns makes the function harder to reason about and test. The function is called from `add_working_memory` (also sync), but the ADK framework may call tool functions in an async context.

**Fix:** Consider making `add_working_memory` and `check_and_compress` async functions to align with the ADK framework's async tool model, or use a dedicated background worker thread for compression tasks.

---

_Reviewed: 2026-04-11T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
