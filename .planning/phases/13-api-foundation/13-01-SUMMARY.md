---
phase: 13-api-foundation
plan: 01
subsystem: api
tags: [fastapi, cors, pydantic, runner, deps, testing]
dependency_graph:
  requires: []
  provides: [create_app, run_command_and_collect, ToolContextAdapter, pydantic-models]
  affects: []
tech_stack:
  added: [FastAPI 0.135.3, CORSMiddleware, Pydantic v2, httpx/ASGITransport]
  patterns: [app-factory, lifespan-context-manager, dependency-injection, event-stream-collection]
key_files:
  created:
    - app/api/__init__.py
    - app/api/app.py
    - app/api/deps.py
    - app/api/models.py
    - app/api/runner_utils.py
    - app/api/routers/__init__.py
    - app/api/routers/commands.py
    - app/api/routers/queries.py
    - tests/unit/test_api.py
  modified:
    - tests/unit/conftest.py
decisions:
  - CORS allow_origins=["*"] for dev mode; production restricts in Phase 15+
  - ToolContextAdapter wraps session.state dict to mimic ToolContext.state for state_manager compat
  - Endpoint stubs return structured response models (not bare dicts) for type consistency
  - api_client fixture uses pytest_asyncio.fixture for proper async lifecycle
metrics:
  duration: 16m
  completed: 2026-04-15
  tasks: 2
  files_created: 9
  files_modified: 1
  tests_added: 31
  tests_total: 541
---

# Phase 13 Plan 01: FastAPI App Skeleton Summary

FastAPI app factory with lifespan (Runner lifecycle), CORS middleware, /api/v1 versioning, Pydantic v2 models for all 14 endpoints, dependency injection, and Runner event stream extraction utility.

## What Was Done

### Task 1: FastAPI app factory + CORS + versioning + dependency injection
- Created `app/api/app.py` with `create_app()` factory, async lifespan context manager
- Lifespan startup: InMemorySessionService + session + Runner stored on app.state
- Lifespan shutdown: flush_state_sync() + stop_all_actor_services()
- CORS middleware with allow_origins=["*"] (dev mode)
- Both routers mounted with /api/v1 prefix
- Created `app/api/deps.py` with get_runner, get_session_service, get_runner_lock, get_tool_context
- ToolContextAdapter class wraps session.state for state_manager compatibility
- Created `app/api/routers/commands.py` with 8 command endpoint stubs
- Created `app/api/routers/queries.py` with 6 query endpoint stubs
- Created `app/api/models.py` with all Pydantic v2 request/response models

### Task 2: Pydantic v2 models + Runner event stream utility + unit tests
- All Pydantic v2 models defined with field validation (min_length, max_length, ge, le)
- `app/api/runner_utils.py`: run_command_and_collect() extracts final_response + tool_results
- Timeout handling: asyncio.wait_for + HTTPException 504
- Added API test fixtures to conftest.py (api_app, api_client)
- 31 unit tests covering: app creation, CORS, versioning, Pydantic validation, runner_utils

## Verification Results

- `create_app()` returns FastAPI with 18 routes (14 drama + 4 default)
- All 14 endpoints registered under /api/v1/ prefix
- CORS preflight with proper headers returns Access-Control-Allow-Origin
- Pydantic validation: empty strings rejected, defaults work, constraints enforced
- `run_command_and_collect()` is async, returns dict with final_response + tool_results
- Timeout raises HTTPException 504
- All 541 tests pass (510 existing + 31 new)

## Decisions Made

1. **CORS allow_origins=["*"] for dev mode** — Plan explicitly allows Claude's discretion; production restricts in Phase 15+ deployment config (T-13-02 accepted)
2. **ToolContextAdapter wraps session.state** — state_manager functions expect `.state` attribute; adapter provides this without modifying core modules
3. **Endpoint stubs return structured Pydantic models** — Not bare dicts, for type consistency and auto-generated OpenAPI schema
4. **pytest_asyncio.fixture for async fixtures** — Required for proper async lifecycle in api_client fixture

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

| File | Line | Stub | Reason |
|------|------|------|--------|
| app/api/routers/commands.py | 26 | `CommandResponse(message="not implemented")` | POST /drama/start — wired in plan 13-02 |
| app/api/routers/commands.py | 32 | `CommandResponse(message="not implemented")` | POST /drama/next — wired in plan 13-02 |
| app/api/routers/commands.py | 38 | `CommandResponse(message="not implemented")` | POST /drama/action — wired in plan 13-02 |
| app/api/routers/commands.py | 44 | `CommandResponse(message="not implemented")` | POST /drama/speak — wired in plan 13-02 |
| app/api/routers/commands.py | 50 | `CommandResponse(message="not implemented")` | POST /drama/steer — wired in plan 13-02 |
| app/api/routers/commands.py | 56 | `CommandResponse(message="not implemented")` | POST /drama/auto — wired in plan 13-02 |
| app/api/routers/commands.py | 62 | `CommandResponse(message="not implemented")` | POST /drama/end — wired in plan 13-02 |
| app/api/routers/commands.py | 68 | `CommandResponse(message="not implemented")` | POST /drama/storm — wired in plan 13-02 |
| app/api/routers/queries.py | 39 | `SaveLoadResponse(message="not implemented")` | POST /drama/save — wired in plan 13-03 |
| app/api/routers/queries.py | 45 | `SaveLoadResponse(message="not implemented")` | POST /drama/load — wired in plan 13-03 |
| app/api/routers/queries.py | 57 | `ExportResponse(message="not implemented")` | POST /drama/export — wired in plan 13-03 |

These stubs are intentional — the plan explicitly specifies "placeholder endpoint stubs" and subsequent plans (13-02, 13-03) will wire them up.

## Threat Flags

No new threat surface beyond what the plan's threat model covers. T-13-02 (CORS wildcard) is accepted per plan.

## Self-Check: PASSED

- All 9 created files verified present
- Both task commits verified in git log (8ba8afb, abf02a1)
- 31 new tests passing, 541 total tests passing
