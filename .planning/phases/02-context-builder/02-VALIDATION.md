---
phase: 02
slug: context-builder
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-11
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml [tool.pytest.ini_options] |
| **Quick run command** | `uv run pytest tests/unit/test_context_builder.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_context_builder.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | MEMORY-04 | — | N/A | unit | `uv run pytest tests/unit/test_context_builder.py::test_estimate_tokens -xvs` | ✅ W0 | ⬜ pending |
| 02-01-01 | 01 | 1 | MEMORY-04 | — | N/A | unit | `uv run pytest tests/unit/test_context_builder.py::test_truncate_sections -xvs` | ✅ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | MEMORY-04 | — | N/A | unit | `uv run pytest tests/unit/test_context_builder.py::test_build_actor_context_from_memory -xvs` | ✅ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | MEMORY-04 | — | N/A | unit | `uv run pytest tests/unit/test_context_builder.py::test_build_director_context -xvs` | ✅ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | MEMORY-04 | — | N/A | unit | `uv run pytest tests/unit/test_context_builder.py::test_build_director_context_budget -xvs` | ✅ W0 | ⬜ pending |
| 02-02-01 | 02 | 2 | MEMORY-04 | — | N/A | unit | `uv run pytest tests/unit/test_context_builder.py::test_migration_backward_compat -xvs` | ✅ W0 | ⬜ pending |
| 02-02-02 | 02 | 2 | MEMORY-04 | — | N/A | integration | `uv run pytest tests/ -x -q` | ✅ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_context_builder.py` — stubs for MEMORY-04 (estimate_tokens, truncate_sections, build_director_context, build_actor_context_from_memory)
- [ ] Existing `tests/unit/conftest.py` — shared fixtures (already exists from Phase 1)
- [ ] Existing `uv run pytest` infrastructure covers all needs

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 导演上下文格式可读性 | MEMORY-04 | 需人工审查中文标签排版 | 运行 `build_director_context()` 检查输出格式 |
| 逐层裁剪日志输出 | MEMORY-04 | 需人工审查裁剪消息合理性 | 触发超预算场景，检查日志中的裁剪记录 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
