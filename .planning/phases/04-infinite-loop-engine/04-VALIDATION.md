---
phase: 04
slug: infinite-loop-engine
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-12
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8.3.4 |
| **Config file** | pyproject.toml [tool.pytest.ini_options] |
| **Quick run command** | `uv run pytest tests/unit/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -x` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | LOOP-01 | T-04-01 | DramaRouter routes to _setup_agent when no actors | unit | `uv run pytest tests/unit/test_agent.py::test_drama_router_setup -x` | ❌ W0 | ⬜ pending |
| 04-01-01 | 01 | 1 | LOOP-01 | T-04-01 | DramaRouter routes to _improv_director when actors exist | unit | `uv run pytest tests/unit/test_agent.py::test_drama_router_improvise -x` | ❌ W0 | ⬜ pending |
| 04-01-01 | 01 | 1 | LOOP-01 | T-04-03 | DramaRouter fallback to _improv_director | unit | `uv run pytest tests/unit/test_agent.py::test_drama_router_fallback -x` | ❌ W0 | ⬜ pending |
| 04-01-01 | 01 | 1 | LOOP-01 | — | _improv_director prompt declares infinite loop | unit | `uv run pytest tests/unit/test_agent.py::test_improv_director_no_ending -x` | ❌ W0 | ⬜ pending |
| 04-01-01 | 01 | 1 | LOOP-01 | — | Utility commands route to _improv_director | unit | `uv run pytest tests/unit/test_agent.py::test_drama_router_utility_commands -x` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 1 | LOOP-03 | — | build_director_context() includes transition section | unit | `uv run pytest tests/unit/test_context_builder.py::test_director_context_transition -x` | ❌ W0 | ⬜ pending |
| 04-03-01 | 03 | 2 | LOOP-03 | — | next_scene() returns is_first_scene flag | unit | `uv run pytest tests/unit/test_tools.py::test_next_scene_first_scene -x` | ❌ W0 | ⬜ pending |
| 04-03-01 | 03 | 2 | LOOP-03 | — | next_scene() returns transition info (non-first scene) | unit | `uv run pytest tests/unit/test_tools.py::test_next_scene_transition -x` | ❌ W0 | ⬜ pending |
| 04-03-02 | 03 | 2 | D-14 | — | load_progress() migrates old STORM status values | unit | `uv run pytest tests/unit/test_state_manager.py::test_migrate_legacy_status -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_agent.py` — stubs for LOOP-01 (DramaRouter routing, _improv_director prompt)
- [ ] `tests/unit/test_tools.py` — stubs for LOOP-03 (next_scene transition info)
- [ ] `tests/unit/test_context_builder.py` — additional test for transition section
- [ ] `tests/unit/test_state_manager.py` — stubs for D-14 (status migration)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full end-to-end: /start → setup → /next × 3 → /save → /load → /next | LOOP-01 | Requires live LLM + A2A actor services | Start drama, verify setup works, advance 3 scenes, save, load, continue |
| _improv_director does not self-terminate after N scenes | LOOP-01 | Requires long-running session with live LLM | Run 10+ scenes, verify director never outputs "剧终" or similar ending marker |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter
