---
phase: 3
slug: semantic-retrieval
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-11
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

|| Property | Value |
||----------|-------|
|| **Framework** | pytest 9.0.2 |
|| **Config file** | pyproject.toml (pytest section) |
|| **Quick run command** | `uv run pytest tests/unit/test_semantic_retriever.py -x -q` |
|| **Full suite command** | `uv run pytest tests/ -x -q` |
|| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_semantic_retriever.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

|| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
||---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
|| 03-01-01 | 01 | 1 | MEMORY-05 | T-03-01 / T-03-03 | Tag length ≤ 50 chars; prefix whitelist; malformed tags non-fatal | unit | `uv run pytest tests/unit/test_semantic_retriever.py -x -q` | ❌ W0 | ⬜ pending |
|| 03-01-02 | 01 | 1 | MEMORY-05 | — | Tags parsed from LLM output (JSON + regex fallback); tags default [] on failure | unit | `uv run pytest tests/unit/test_memory_manager.py -x -q` | ❌ W0 | ⬜ pending |
|| 03-02-01 | 02 | 2 | MEMORY-05 | T-03-04 | retrieve_relevant_scenes_tool validates tag length ≤ 50 | unit | `uv run pytest tests/unit/test_context_builder.py -x -q` | ✅ exists | ⬜ pending |
|| 03-02-02 | 02 | 2 | MEMORY-05 | T-03-05 | Actor auto-injection respects D-07 (own memories only) | unit | `uv run pytest tests/unit/test_context_builder.py -x -q` | ✅ exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_semantic_retriever.py` — stubs for MEMORY-05 (tag matching, three-layer search, dedup, tag parsing, backfill, latency)
- [ ] `tests/unit/test_memory_manager.py` — extend with tag generation in compression tests

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

|| Behavior | Requirement | Why Manual | Test Instructions |
||----------|-------------|------------|-------------------|
|| Retrieval latency < 100ms at scale | MEMORY-05 | Needs realistic data volume (200+ entries) | Run `test_retrieval_latency` with 200 entries × 10 tags benchmark |

*All other phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
