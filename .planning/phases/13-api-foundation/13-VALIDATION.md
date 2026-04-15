---
phase: 13
slug: api-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-15
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/unit/test_api.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_api.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 13-01-01 | 01 | 1 | API-01 | — | N/A | unit | `uv run pytest tests/unit/test_api.py::test_app_creation -xvs` | ❌ W0 | ⬜ pending |
| 13-01-02 | 01 | 1 | API-04 | — | N/A | unit | `uv run pytest tests/unit/test_api.py::test_version_prefix -xvs` | ❌ W0 | ⬜ pending |
| 13-01-03 | 01 | 1 | API-05 | — | N/A | unit | `uv run pytest tests/unit/test_api.py::test_cors_headers -xvs` | ❌ W0 | ⬜ pending |
| 13-01-04 | 01 | 1 | API-03 | — | N/A | unit | `uv run pytest tests/unit/test_api.py::test_pydantic_models -xvs` | ❌ W0 | ⬜ pending |
| 13-02-01 | 02 | 1 | API-02 | — | N/A | unit | `uv run pytest tests/unit/test_api.py::test_command_endpoints -xvs` | ❌ W0 | ⬜ pending |
| 13-02-02 | 02 | 1 | API-02 | — | N/A | unit | `uv run pytest tests/unit/test_api.py::test_runner_event_extraction -xvs` | ❌ W0 | ⬜ pending |
| 13-03-01 | 03 | 2 | API-02 | — | N/A | unit | `uv run pytest tests/unit/test_api.py::test_query_endpoints -xvs` | ❌ W0 | ⬜ pending |
| 13-03-02 | 03 | 2 | STATE-01 | — | N/A | unit | `uv run pytest tests/unit/test_api.py::test_state_migration -xvs` | ❌ W0 | ⬜ pending |
| 13-04-01 | 04 | 2 | STATE-02 | — | N/A | unit | `uv run pytest tests/unit/test_api.py::test_flush_on_push -xvs` | ❌ W0 | ⬜ pending |
| 13-04-02 | 04 | 2 | STATE-03 | T-13-01 | Lock file enforces single session | unit | `uv run pytest tests/unit/test_api.py::test_single_session -xvs` | ❌ W0 | ⬜ pending |
| 13-04-03 | 04 | 2 | API-01 | — | N/A | integration | `uv run pytest tests/integration/test_api_integration.py -xvs` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_api.py` — stubs for API-01~05, STATE-01~03
- [ ] `tests/unit/conftest.py` — shared fixtures (FastAPI TestClient, mock Runner)
- [ ] `tests/integration/test_api_integration.py` — integration test stubs

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| CLI/API mutual exclusion via lock file | STATE-03 | Requires two concurrent processes | Start API server, attempt CLI start, verify CLI refuses |
| CORS headers returned for Android origin | API-05 | Requires running server + real HTTP client | Start server, send preflight request from Android origin |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
