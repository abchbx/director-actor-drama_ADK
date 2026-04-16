---
phase: 6
slug: tension-scoring-conflict-engine
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-12
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8.3.4 |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/unit/test_conflict_engine.py -x -q` |
| **Full suite command** | `uv run pytest tests/unit/ -x` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_conflict_engine.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/unit/ -x`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | CONFLICT-01 | T-6-01 | emotion_variance/unresolved_density/dialogue_repetition/scenes_since_inject 返回 0-1 | unit | `uv run pytest tests/unit/test_conflict_engine.py::TestCalcEmotionVariance -x` | ❌ W0 | ⬜ pending |
| 06-01-01 | 01 | 1 | CONFLICT-01 | — | calculate_tension 返回 0-100 tension_score + is_boring + signals | unit | `uv run pytest tests/unit/test_conflict_engine.py::TestEvaluateTension -x` | ❌ W0 | ⬜ pending |
| 06-01-01 | 01 | 1 | CONFLICT-03 | — | CONFLICT_TEMPLATES 包含 7 种类型，每种含 name/description/prompt_hint/suggested_emotions | unit | `uv run pytest tests/unit/test_conflict_engine.py::TestConflictTemplates -x` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | CONFLICT-02 | — | inject_conflict 返回结构化冲突建议 + urgency 渐进升级 | unit | `uv run pytest tests/unit/test_conflict_engine.py::TestInjectConflict -x` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | CONFLICT-04 | — | 同类型 8 场去重 + used_conflict_types 更新 | unit | `uv run pytest tests/unit/test_conflict_engine.py::TestConflictDedup -x` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | CONFLICT-02 | T-6-02 | conflict_type 参数验证（必须在 CONFLICT_TEMPLATES.keys() 中） | unit | `uv run pytest tests/unit/test_conflict_engine.py::TestConflictTypeValidation -x` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | CONFLICT-02 | — | 活跃冲突上限 4 条，超出返回建议而非注入 | unit | `uv run pytest tests/unit/test_conflict_engine.py::TestActiveConflictLimit -x` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 2 | CONFLICT-01 | — | evaluate_tension tool 注册为 _improv_director Tool | unit | `uv run pytest tests/unit/test_tools_phase6.py::TestEvaluateTensionTool -x` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 2 | CONFLICT-02 | — | inject_conflict tool 注册为 _improv_director Tool | unit | `uv run pytest tests/unit/test_tools_phase6.py::TestInjectConflictTool -x` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 2 | — | — | init_drama_state 初始化 conflict_engine 7 字段 | unit | `uv run pytest tests/unit/test_tools_phase6.py -x` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 2 | — | — | load_progress 兼容旧存档（setdefault） | unit | `uv run pytest tests/unit/test_tools_phase6.py -x` | ❌ W0 | ⬜ pending |
| 06-02-02 | 02 | 2 | — | — | build_director_context 包含【张力状态】段落 | unit | `uv run pytest tests/unit/test_context_builder.py -x` | ❌ W0 | ⬜ pending |
| 06-02-02 | 02 | 2 | — | — | 导演 prompt 包含 §8 张力评估段落 | grep | `grep "§8" app/agent.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_conflict_engine.py` — covers CONFLICT-01~04
- [ ] `tests/unit/conftest.py` — add conflict_engine fixtures (mock_tool_context with conflict_engine sub-dict)
- [ ] `tests/unit/test_tools_phase6.py` — test evaluate_tension + inject_conflict tool wrappers
- [ ] `tests/unit/test_context_builder.py` — add tests for _build_tension_section

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 导演 LLM 遵循 §8 主动调用 evaluate_tension() | CONFLICT-01 | 依赖 LLM 行为，无法自动化 | 运行 5+ 场戏，检查 tension_history 是否有记录 |
| 冲突建议自然融入剧情 | CONFLICT-02 | 主观判断，需人工评估 | 运行低张力场景，检查注入的冲突是否合理融入 |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
