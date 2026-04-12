---
phase: 01-memory-foundation
fixed_at: 2026-04-11T12:30:00Z
review_path: .planning/phases/01-memory-foundation/01-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 7
skipped: 0
status: all_fixed
---

# Phase 1: Code Review Fix Report

**Fixed at:** 2026-04-11T12:30:00Z
**Source review:** .planning/phases/01-memory-foundation/01-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 7
- Fixed: 7
- Skipped: 0

## Fixed Issues

### CR-01: Operator precedence bug in error dialogue detection

**Files modified:** `app/tools.py`
**Commit:** not committed (per instructions)
**Applied fix:** Added parentheses around the `or` condition on line 275 to fix operator precedence. Changed `actor_dialogue.startswith("[") and "失败" in actor_dialogue or "超时" in actor_dialogue` to `actor_dialogue.startswith("[") and ("失败" in actor_dialogue or "超时" in actor_dialogue)`, making it consistent with lines 257 and 267.

### CR-02: IndexError when `mark_critical_memory` called with `memory_index=-1` on empty list

**Files modified:** `app/memory_manager.py`
**Commit:** not committed (per instructions)
**Applied fix:** Changed bounds check on line 715 from `if memory_index < 0 or memory_index >= len(working):` to `if not working or memory_index < 0 or memory_index >= len(working):` and updated error message to `f"索引 {memory_index} 超出范围。工作记忆为空或索引无效。"` to avoid confusing `0--1` output when working memory is empty.

### WR-01: `asyncio.run()` in `check_and_compress` can conflict with running event loops

**Files modified:** `app/memory_manager.py`
**Commit:** not committed (per instructions)
**Applied fix:** Added `logger.warning()` calls before `pass` in both `RuntimeError` handlers (lines 552-554 and 577-578). The first logs: "Cannot compress memory for {actor_name}: no event loop available. Entries retained in pending." The second logs: "Cannot compress scene→arc for {actor_name}: no event loop available. Entries retained in pending."

### WR-02: Module-level `_conversation_log` shares state across dramas without isolation

**Files modified:** `app/state_manager.py`
**Commit:** not committed (per instructions)
**Applied fix:** Added `global _conversation_log; _conversation_log = []` at the beginning of `load_progress()`, after loading the save file and before updating state. This clears conversation log from previous drama to avoid cross-drama contamination.

### WR-03: `save_state_clean` mutates `actor_data` but doesn't propagate changes back to state dict

**Files modified:** `app/memory_manager.py`
**Commit:** not committed (per instructions)
**Applied fix:** Added NOTE to docstring of `save_state_clean` documenting the in-place mutation contract: "NOTE: Mutates actor_data dicts in-place within the state dict. Call this BEFORE _set_state() — the mutations are visible through the state dict reference."

### WR-04: List comparison in compression fallback may remove duplicate valid entries

**Files modified:** `app/memory_manager.py`
**Commit:** not committed (per instructions)
**Applied fix:** Replaced value-based `not in overflow` comparison with identity-based removal using `id()`. Changed from `if e not in overflow` to building a set of overflow entry ids (`overflow_ids = set(id(e) for e in overflow)`) and filtering with `if id(e) not in overflow_ids`. This prevents duplicate entries with identical content from being incorrectly removed.

### WR-05: `detect_importance` keyword matching can produce false positives for short common words

**Files modified:** `app/memory_manager.py`
**Commit:** not committed (per instructions)
**Applied fix:** Added WARNING to `detect_importance` docstring: "WARNING: Uses substring matching which can produce false positives. For example, '兴奋' in 情感高峰 patterns matches normal text like '兴奋地跑来'. Critical detections should be confirmed by the director before marking."

---

_Fixed: 2026-04-11T12:30:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
