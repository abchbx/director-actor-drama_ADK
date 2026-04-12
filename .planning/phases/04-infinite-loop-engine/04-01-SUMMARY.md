---
phase: 04-infinite-loop-engine
plan: 01
subsystem: agent-router
tags: [adk, baseagent, drama-router, system-prompt, infinite-loop]

# Dependency graph
requires:
  - phase: 01-memory-foundation
    provides: 3-tier memory architecture used by agents
  - phase: 02-context-builder
    provides: context builder for director/actor prompts
  - phase: 03-semantic-retrieval
    provides: semantic scene retrieval tools
provides:
  - DramaRouter class with actors-existence routing logic
  - _setup_agent (merged discoverer+researcher+outliner)
  - _improv_director (infinite loop protocol via system prompt)
  - Unit tests for routing logic
affects: [04-02, 04-03, 05-mixed-autonomy-mode, 06-tension-scoring]

# Tech tracking
tech-stack:
  added: []
  patterns: [baseagent-router, system-prompt-driven-loop, actors-existence-routing]

key-files:
  created:
    - tests/unit/test_agent.py
  modified:
    - app/agent.py
    - tests/unit/test_integration.py

key-decisions:
  - "DramaRouter replaces StormRouter with 2 sub-agents instead of 4"
  - "Routing based on actors existence rather than fine-grained drama.status"
  - "_setup_agent merges 3 STORM agents with explicit step markers to prevent skipping"
  - "_improv_director uses system prompt to enforce infinite loop protocol"
  - "Removed storm_ask_perspective_questions and storm_research_perspective from imports (placeholder data tools per CONCERNS.md)"

patterns-established:
  - "BaseAgent routing: override _run_async_impl, use _sub_agents_map for lookup"
  - "System prompt-driven loop: declare tool call sequence + no-ending constraint in instruction"
  - "Explicit step markers: use 步骤 N markers in prompts to prevent LLM from skipping phases"

requirements-completed: [LOOP-01]

# Metrics
duration: 25min
completed: 2026-04-12
---

# Phase 4 Plan 01: DramaRouter Architecture Summary

**StormRouter→DramaRouter 重构：2子Agent路由（setup/improvise），system prompt 驱动无限循环协议**

## Performance

- **Duration:** 25 min
- **Started:** 2026-04-12T06:27:27Z
- **Completed:** 2026-04-12T06:52:46Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 3

## Accomplishments
- Replaced StormRouter (4 sub-agents) with DramaRouter (2 sub-agents: setup_agent + improv_director)
- _setup_agent merges discoverer+researcher+outliner into one-shot /start flow with explicit step markers
- _improv_director declares infinite loop protocol (no-preset-ending, loop protocol, user wait)
- Routing logic simplified from 5-way status-based routing to 2-way actors-existence routing (D-04)
- Fallback to improv_director when agent lookup fails (D-03)
- All 144 unit tests pass including 8 new DramaRouter routing tests

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Create DramaRouter + _setup_agent + _improv_director** - `76c8dc9` (test)
2. **Task 1 GREEN: Implement DramaRouter** - `28faef8` (feat)

_Note: TDD task with RED→GREEN commits. No REFACTOR needed._

## Files Created/Modified
- `app/agent.py` - Complete rewrite: DramaRouter class, _setup_agent, _improv_director, removed StormRouter + 4 STORM agents
- `tests/unit/test_agent.py` - New: 8 unit tests for routing logic and agent configuration
- `tests/unit/test_integration.py` - Updated: changed _storm_director reference to _improv_director

## Decisions Made
- Removed storm_ask_perspective_questions and storm_research_perspective from agent.py imports per Research Open Question 1 recommendation (they produce placeholder data per CONCERNS.md)
- Kept STORM reference in _setup_agent instruction to preserve multi-perspective exploration value (D-02)
- Removed all STORM-specific terminology from _improv_director instruction per plan requirement
- Test strategy: tested routing logic by simulating the decision path rather than mocking Pydantic model attributes (ADK Agent is a Pydantic model that forbids instance attribute mutation)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_integration.py reference from _storm_director to _improv_director**
- **Found during:** Task 1 (GREEN verification)
- **Issue:** Existing test `TestAgentIncludesMarkMemory` imported `_storm_director` which no longer exists after refactoring
- **Fix:** Changed import from `_storm_director` to `_improv_director` and updated assertion to check improv_director's tool list
- **Files modified:** tests/unit/test_integration.py
- **Verification:** `uv run pytest tests/unit/ -x -q` → 144 passed
- **Committed in:** 28faef8 (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minimal — updated existing test to match new architecture. No scope creep.

## Issues Encountered
- ADK Agent is a Pydantic model that validates sub_agents as BaseAgent instances and forbids instance attribute mutation via __setattr__. Required changing test strategy from mocking sub-agent run_async to testing routing logic by simulating the decision path and verifying _sub_agents_map lookups.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- DramaRouter routing complete, ready for Plan 04-02 (next_scene() transition info + build_director_context() enhancement)
- _improv_director prompt ready for Phase 6 evaluate_tension() interface (evaluation hint already in prompt)
- A2A actor services unaffected by Router refactoring

## Self-Check: PASSED

- app/agent.py: FOUND
- tests/unit/test_agent.py: FOUND
- tests/unit/test_integration.py: FOUND
- 04-01-SUMMARY.md: FOUND
- Commit 76c8dc9: FOUND
- Commit 28faef8: FOUND

---
*Phase: 04-infinite-loop-engine*
*Completed: 2026-04-12*
