---
phase: 06-tension-scoring-conflict-engine
plan: 01
subsystem: engine
tags: [heuristic, tension-scoring, conflict-injection, dedup, urgency-escalation]

# Dependency graph
requires:
  - phase: 01-memory-foundation
    provides: "critical_memories with reason=未决事件, arc_summary.structured.unresolved"
  - phase: 02-context-builder
    provides: "_EMOTION_CN mapping, _build_conflict_section forward-compat"
provides:
  - "calculate_tension: 4-signal weighted tension scoring (0-100)"
  - "select_conflict_type: 8-scene dedup conflict type selection"
  - "generate_conflict_suggestion: structured suggestion with urgency escalation"
  - "update_conflict_engine_state: state management for conflict_engine sub-dict"
  - "CONFLICT_TEMPLATES: 7 conflict type definitions"
  - "_EMOTION_WEIGHTS: emotion-to-tension-weight mapping"
affects: [07-arc-tracking, 08-dynamic-storm, tools-py, agent-py, context-builder-py, state-manager-py]

# Tech tracking
tech-stack:
  added: []
  patterns: [pure-heuristic-scoring, director-suggestion-mode, dedup-window, urgency-escalation]

key-files:
  created:
    - app/conflict_engine.py
    - tests/unit/test_conflict_engine.py
  modified: []

key-decisions:
  - "使用前20字+角色名作为对话重复度匹配键，降低短句误判"
  - "情感方差归一化除以4.0（理论最大方差），两演员极端情况(angry+neutral)可达1.0"
  - "未决冲突密度归一化除以5.0，5个以上未决事件饱和"
  - "冲突建议中 involved_actors 选择情绪权重最高的2个角色"
  - "limit_reached 时附带最旧冲突信息（Pitfall 6 缓解）"

patterns-established:
  - "纯计算模块模式：所有函数接收 state:dict，不依赖 ToolContext"
  - "信号归一化：所有信号返回 0-1 float，加权后乘 100 得到 0-100 张力评分"
  - "导演建议模式：冲突注入返回结构化建议，非强制执行"
  - "渐进升级模式：1场→normal，2场→high，3+场→critical"

requirements-completed: [CONFLICT-01, CONFLICT-03, CONFLICT-04]

# Metrics
duration: 33min
completed: 2026-04-12
---

# Phase 6 Plan 01: 张力评分与冲突注入核心模块 Summary

**纯启发式4信号加权张力评分(0-100) + 7种冲突模板 + 8场去重 + 渐进升级注入建议**

## Performance

- **Duration:** 33 min
- **Started:** 2026-04-12T11:49:35Z
- **Completed:** 2026-04-12T12:22:18Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- 完成4个启发式信号函数（情感方差/未决密度/对话重复/注入间隔），全部归一化到0-1
- 实现calculate_tension核心函数，4信号加权计算张力评分(0-100)，is_boring阈值30
- 定义7种冲突模板CONFLICT_TEMPLATES，每种含name/description/prompt_hint/suggested_emotions
- 实现select_conflict_type 8场去重逻辑，同类型8场内不重复
- 实现generate_conflict_suggestion，支持3级urgency渐进升级和活跃冲突上限4条
- 实现update_conflict_engine_state，管理张力历史(20条上限)、连续低张力计数、冲突注入追踪
- 完整TDD流程：先写40个失败测试，再实现功能代码全部通过
- T-06-01安全缓解：validate conflict_type在CONFLICT_TEMPLATES中

## Task Commits

Each task was committed atomically:

1. **Task 1: conflict_engine.py 核心计算函数 + CONFLICT_TEMPLATES + 单元测试** - `03307ca` (test) + `aba210e` (feat)

_Note: TDD tasks have multiple commits (test → feat)_

## Files Created/Modified
- `app/conflict_engine.py` - 冲突引擎核心模块：4信号函数 + calculate_tension + select_conflict_type + generate_conflict_suggestion + update_conflict_engine_state + CONFLICT_TEMPLATES + _EMOTION_WEIGHTS
- `tests/unit/test_conflict_engine.py` - 40个单元测试覆盖所有函数

## Decisions Made
- 使用前20字+角色名作为对话重复度匹配键，降低"我明白了"等短句误判（测试验证有效）
- 情感方差归一化除以4.0：两演员极端情况(angry=5, neutral=1)方差=4.0，归一化后=1.0
- 未决冲突密度归一化除以5.0：5个以上未决事件饱和在1.0
- 冲突建议中 involved_actors 选择情绪权重最高的2个角色（按_EMOTION_WEIGHTS排序）
- limit_reached 时附带最旧冲突信息："建议优先解决：{description}（已持续 {N} 场）"

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] 修正test_normal_tension测试数据**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** 测试使用angry(5)+fearful(5)两演员，权重相同导致emotion_variance=0，加上空working_memory导致dialogue_repetition=0，总分18<30
- **Fix:** 将道衍情绪改为neutral(1)使方差>0，添加working_memory条目使dialogue_repetition>0
- **Files modified:** tests/unit/test_conflict_engine.py
- **Verification:** calculate_tension返回68，在30-70范围内
- **Committed in:** aba210e (Task 1 feat commit)

**2. [Rule 2 - Missing Critical] 添加conflict_type验证（T-06-01缓解）**
- **Found during:** Task 1 (implementation)
- **Issue:** threat_model要求validate conflict_type，计划action中未明确提及验证逻辑
- **Fix:** 在generate_conflict_suggestion中添加conflict_type验证，不在CONFLICT_TEMPLATES.keys()中返回error
- **Files modified:** app/conflict_engine.py
- **Verification:** 无效类型返回status=error
- **Committed in:** aba210e (Task 1 feat commit)

---

**Total deviations:** 2 auto-fixed (1 bug fix, 1 missing critical security validation)
**Impact on plan:** Both auto-fixes necessary for correctness and security. No scope creep.

## Issues Encountered
- None beyond the deviation fixes above

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- conflict_engine.py核心模块完成，可被tools.py薄代理封装
- Plan 02可集成evaluate_tension和inject_conflict到tools.py、agent.py、context_builder.py、state_manager.py
- 所有信号函数和冲突逻辑已测试验证，集成时只需关注ToolContext封装和state路径映射

## Self-Check: PASSED

- [x] app/conflict_engine.py exists
- [x] tests/unit/test_conflict_engine.py exists
- [x] 06-01-SUMMARY.md exists
- [x] Commit 03307ca (test RED) exists
- [x] Commit aba210e (feat GREEN) exists
- [x] All 40 unit tests pass
- [x] Module imports cleanly with all exports

---
*Phase: 06-tension-scoring-conflict-engine*
*Completed: 2026-04-12*
