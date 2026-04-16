# Phase 8: Dynamic STORM — Research

**Date:** 2026-04-13
**Phase:** 08-dynamic-storm

## Research Question

What do I need to know to PLAN Phase 8 (Dynamic STORM) well?

## 1. Current Codebase State

### Existing trigger_storm() (tools.py L764-792)
- Simple prompt-only implementation: sets focus_area, returns message asking director to review
- No LLM call for perspective generation
- No dedup, no fact constraint, no merge into storm data
- Returns `{"status": "success", "message": "...", "focus_area": focus_area}`
- Phase 5 placeholder; must be upgraded to full Dynamic STORM

### Existing evaluate_tension() (tools.py L795-835)
- Calls `conflict_engine.calculate_tension(state)` — pure heuristic
- Updates state via `update_conflict_engine_state()`
- Returns: `tension_score`, `is_boring`, `suggested_action`, `signals`
- `suggested_action` currently only: "inject_conflict" | "cool_down" | "maintain"
- Phase 8 needs to add "dynamic_storm" to suggested_action

### Existing _build_dynamic_storm_section() (context_builder.py L746-767)
- Empty shell with forward-compatible D-04 stub
- Reads `state["dynamic_storm"]["trigger_history"]` if exists
- Returns empty text when no trigger_history
- Priority: 3 (can be truncated but try to keep)

### Existing storm data structure (state)
- `state["storm"]` — initialized as `{"last_review": {}}` in init_drama_state()
- Setup phase fills `storm["perspectives"]` with list of `{name, description, questions}`
- Setup phase fills `storm["outline"]`
- Phase 8 must merge new perspectives into `storm["perspectives"]`

### Existing state_manager patterns
- `init_drama_state()` — initializes all fields with defaults
- `load_progress()` — backward compat via `state.setdefault()` for missing fields
- `advance_scene()` (L866-883) — increments current_scene, sets status
- No `scenes_since_last_storm` counter exists yet

### Existing conflict_engine.py patterns
- Pure functions: `calculate_tension(state: dict) -> dict`
- State management: `update_conflict_engine_state(state, tension_result, conflict_suggestion) -> dict`
- Constants: `DEDUP_WINDOW = 8`, `MAX_TENSION_HISTORY = 20`
- Template-driven: `CONFLICT_TEMPLATES` dict with 7 types

### Existing arc_tracker.py patterns
- Pure functions: `detect_dormant_threads(state)`, `update_thread_state(...)`
- Constants: `DORMANT_THRESHOLD = 8`, `MAX_RESOLVED_CONFLICTS = 20`
- Module-level utility functions

### Director prompt structure (agent.py)
- `_improv_director` has sections §1-§9
- §5 currently covers "视角审视（/storm）" — references trigger_storm
- §8 covers "张力评估与冲突注入"
- §9 covers "弧线追踪与线索管理"
- Phase 8 needs: §5 update + new §10 "Dynamic STORM"

### Director tools list (agent.py L117+)
- Currently includes `trigger_storm` in tools
- Must be replaced with `dynamic_storm` (or keep both for alias)

## 2. Architecture Patterns to Follow

### Module pattern: app/dynamic_storm.py (NEW)
Following conflict_engine.py pattern:
- Constants at top: `STORM_INTERVAL = 8`, `MAX_TRIGGER_HISTORY = 10`, etc.
- Pure functions for core logic (no ToolContext dependency)
- State management function: `update_dynamic_storm_state(state, ...) -> dict`
- Key functions: `discover_perspectives(...)`, `check_overlap(...)`, `suggest_conflict_types(...)`

### Tool function pattern (tools.py)
- Signature: `def dynamic_storm(focus_area: str, tool_context: ToolContext) -> dict`
- Alias: `trigger_storm` preserved as backward-compat wrapper
- Return format: `{"status": "success", "message": "...", "new_perspectives": [...], ...}`

### State initialization pattern
- `init_drama_state()`: add `state["dynamic_storm"] = {...defaults...}`
- `load_progress()`: add `state.setdefault("dynamic_storm", {...defaults...})`
- `advance_scene()`: increment `dynamic_storm.scenes_since_last_storm`

### Context builder pattern
- `_build_dynamic_storm_section(state) -> dict`: return `{"key": "dynamic_storm", "text": "...", "priority": 3, "truncatable": True}`

## 3. Key Technical Challenges

### LLM Integration for Perspective Discovery
- Current project uses LiteLlm for LLM calls
- Need to call LLM within `dynamic_storm()` to generate new perspectives
- Must construct a structured prompt with: existing perspectives, tension state, active conflicts, dormant threads, actor arcs
- LLM response must be parsed into structured `{name, description, questions}` format
- Risk: LLM may return non-structured text — need robust parsing (JSON mode or regex extraction)

### Keyword Overlap Dedup (D-13, D-14)
- No NLP libraries allowed
- Simple character window sliding (2-4 char) + virtual word removal
- Virtual words list: `["视角", "角度", "观点", "看法", "维度", "层面"]`
- Overlap threshold: >60% → flag with `overlap_warning`
- Must not block generation — only warn

### suggested_conflict_types Mapping (D-21)
- Match new perspective description keywords to CONFLICT_TEMPLATES prompt_hint keywords
- Example: "隐藏的动机" → `secret_revealed`; "两难选择" → `dilemma`
- Keyword mapping table needed (can be hardcoded dict)

### Fact Constraint via Prompt (D-17, D-18, D-19)
- No code-level fact checking (Phase 10's job)
- Prompt injection: include recent 3 scene summaries, active actors, current outline
- Explicit instructions: "新视角必须与已发生事件一致，是扩展而非推翻"

### Merge into storm["perspectives"]
- New perspectives get `source: "dynamic_storm"` and `discovered_scene: current_scene`
- Must append to existing `storm["perspectives"]` list
- Handle case where `storm["perspectives"]` doesn't exist (very old saves)

## 4. Dependency Analysis

### Phase 6 (Tension & Conflict) — DEPENDENCY
- `calculate_tension()` must be extended to return "dynamic_storm" in suggested_action
- `generate_conflict_suggestion()` used for conflict type mapping
- `CONFLICT_TEMPLATES` dict needed for suggested_conflict_types

### Phase 4 (Infinite Loop Engine) — DEPENDENCY
- `DramaRouter` / `_improv_director` carries the loop
- `next_scene()` → `advance_scene()` increments scene counter
- Director tools registration in `_improv_director`

### Phase 7 (Arc Tracking) — READ ONLY
- `plot_threads` (dormant threads) feed into Dynamic STORM prompt
- `arc_progress` data feeds into perspective discovery
- No modification needed to arc_tracker

## 5. Integration Points Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `app/dynamic_storm.py` | NEW | Core module: perspective discovery, overlap check, conflict type suggestion, state management |
| `app/tools.py` | MODIFY | Upgrade `trigger_storm()` → `dynamic_storm()`, extend `evaluate_tension()` |
| `app/agent.py` | MODIFY | Replace trigger_storm with dynamic_storm in tools list, update §5, add §10 |
| `app/context_builder.py` | MODIFY | Implement `_build_dynamic_storm_section()` fully |
| `app/state_manager.py` | MODIFY | Add `dynamic_storm` init, load compat, advance_scene counter |
| `tests/unit/test_dynamic_storm.py` | NEW | TDD unit tests for dynamic_storm.py pure functions |

## 6. Validation Architecture

### Critical validation dimensions:
1. **Functional correctness**: `dynamic_storm()` returns proper structure with new_perspectives, suggested_conflict_types, overlap_warnings
2. **Dedup effectiveness**: Overlap detection catches >60% keyword overlap, doesn't block generation
3. **State persistence**: `dynamic_storm` sub-object properly initialized, saved, loaded
4. **Counter accuracy**: `scenes_since_last_storm` increments on advance_scene, resets on dynamic_storm call
5. **LLM prompt quality**: Prompt contains all required context (existing perspectives, tension, conflicts, dormant threads, arcs)
6. **Backward compatibility**: `trigger_storm` alias works, old saves load without error
7. **Director prompt integration**: §5 updated, §10 present, dynamic_storm tool registered
8. **evaluate_tension extension**: suggested_action includes "dynamic_storm" when appropriate

### Test strategy:
- Pure function tests: `discover_perspectives_prompt()`, `check_keyword_overlap()`, `suggest_conflict_types()`
- State management tests: `update_dynamic_storm_state()`, init defaults, load compat
- Integration tests: `dynamic_storm()` tool function end-to-end, `evaluate_tension()` extended return

---

## RESEARCH COMPLETE
