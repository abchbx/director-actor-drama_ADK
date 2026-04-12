# Testing Patterns

**Analysis Date:** 2026-04-11

## Test Framework

**Runner:**
- pytest >=8.3.4 (configured in `pyproject.toml`)
- pytest-asyncio >=0.23.8 (for async test support)
- Config: `[tool.pytest.ini_options]` in `pyproject.toml`
  - `pythonpath = "."`
  - `asyncio_default_fixture_loop_scope = "function"`

**Assertion Library:**
- Standard `assert` statements (no assertion helper libraries)

**Run Commands:**
```bash
make test                              # Run unit + integration tests
uv run pytest tests/unit               # Unit tests only
uv run pytest tests/integration        # Integration tests only
uv run pytest tests/unit/test_dummy.py # Specific file
```

## Test File Organization

**Location:**
- Separate `tests/` directory at project root (not co-located with source)
- Three subdirectories: `unit/`, `integration/`, `eval/`

**Naming:**
- Test files: `test_{module}.py`
- Test functions: `test_{behavior}` (e.g., `test_dummy`, `test_agent_stream`)

**Structure:**
```
tests/
├── unit/
│   └── test_dummy.py           # Placeholder — no real unit tests yet
├── integration/
│   └── test_agent.py           # ADK runner integration test
└── eval/
    ├── eval_config.json         # LLM-as-judge evaluation config
    └── evalsets/
        ├── basic.evalset.json   # Basic eval test cases
        └── README.md            # Eval documentation
```

## Test Structure

**Suite Organization:**
```python
# tests/unit/test_dummy.py — Placeholder pattern
def test_dummy() -> None:
    """Placeholder - replace with real tests."""
    assert 1 == 1

# tests/integration/test_agent.py — ADK integration test pattern
def test_agent_stream() -> None:
    """Integration test for the agent stream functionality."""
    session_service = InMemorySessionService()
    session = session_service.create_session_sync(user_id="test_user", app_name="test")
    runner = Runner(agent=root_agent, session_service=session_service, app_name="test")

    message = types.Content(
        role="user", parts=[types.Part.from_text(text="Why is the sky blue?")]
    )

    events = list(
        runner.run(
            new_message=message,
            user_id="test_user",
            session_id=session.id,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        )
    )
    assert len(events) > 0, "Expected at least one message"
```

**Patterns:**
- No `conftest.py` — no shared fixtures defined yet
- No setup/teardown logic
- Integration tests import directly from `app.agent`
- Return type annotations on test functions: `-> None`

## Mocking

**Framework:** No mocking framework in use currently

**What to Mock (when adding tests):**
- `ToolContext` — create mock/fake with `state` dict attribute for state manager tests
- A2A service calls — mock `_call_a2a_sdk` and `create_actor_service` to avoid subprocess spawning
- LLM calls — mock `LiteLlm` responses to avoid API costs
- File system operations — consider `tmp_path` fixture for state persistence tests

**What NOT to Mock:**
- State manager dict operations (they're pure data manipulation)
- Data serialization/deserialization (test these directly)

## Fixtures and Factories

**Test Data:**
No fixtures or factories defined. When adding:

```python
# Recommended pattern for ToolContext mock
class FakeToolContext:
    def __init__(self, state=None):
        self.state = state or {}

# Recommended pattern for drama state factory
def make_drama_state(theme="测试戏剧", status="acting", **overrides):
    return {
        "theme": theme,
        "status": status,
        "current_scene": 0,
        "scenes": [],
        "actors": {},
        "narration_log": [],
        "storm": {},
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
        **overrides,
    }
```

**Location:**
- Shared fixtures should go in `tests/conftest.py` (does not exist yet)
- Test-specific helpers in the test file itself

## Coverage

**Requirements:** None enforced — no coverage configuration in `pyproject.toml`

**View Coverage:**
```bash
uv run pytest --cov=app tests/          # If pytest-cov is installed
uv run pytest --cov=app --cov-report=html tests/  # HTML report
```

**Note:** `pytest-cov` is NOT listed in dependencies. Must add to dev dependencies first.

## Test Types

**Unit Tests:**
- Location: `tests/unit/`
- Current state: **Placeholder only** — `test_dummy.py` with `assert 1 == 1`
- Should test: `app/state_manager.py` functions, `app/tools.py` tool logic, `app/actor_service.py` port calculation/name sanitization
- These modules are highly testable — they are pure functions operating on dicts

**Integration Tests:**
- Location: `tests/integration/`
- Current state: **1 test** — `test_agent_stream` in `test_agent.py`
- Tests ADK runner + agent composition end-to-end
- Requires LLM API access (not suitable for CI without API key)
- Pattern: create `InMemorySessionService`, build `Runner`, send message, assert on events

**E2E Tests:**
- Not used

**Eval Tests (LLM-as-Judge):**
- Location: `tests/eval/`
- Framework: `google-adk[eval]` — ADK's built-in evaluation framework
- Config: `tests/eval/eval_config.json`
  - Uses `rubric_based_final_response_quality_v1` criteria
  - Judge model: `gemini-3-flash-preview`
  - Threshold: 0.8
  - Rubrics: `relevance` and `helpfulness`
- Eval sets: `tests/eval/evalsets/basic.evalset.json`
  - Currently has 2 generic cases (greeting, weather query)
  - **Not domain-specific** — should be replaced with drama-specific cases

**Run eval:**
```bash
make eval                                                      # Default evalset
make eval EVALSET=tests/eval/evalsets/custom.evalset.json      # Specific evalset
make eval-all                                                  # All evalsets
```

## Common Patterns

**Async Testing:**
```python
# pytest-asyncio is configured with asyncio_default_fixture_loop_scope = "function"
# For async tool functions (like actor_speak), use:
async def test_actor_speak():
    result = await actor_speak(actor_name="测试", situation="test", tool_context=fake_ctx)
    assert result["status"] == "success"
```

**Error Testing:**
```python
# Pattern: test error return dicts
def test_missing_actor():
    result = get_actor_info("nonexistent", tool_context=fake_ctx)
    assert result["status"] == "error"
    assert "not found" in result["message"]
```

**State Manager Testing (recommended pattern):**
```python
def test_init_drama_state():
    fake_ctx = FakeToolContext()
    result = init_drama_state("测试戏剧", fake_ctx)
    assert result["status"] == "success"
    assert fake_ctx.state["drama"]["theme"] == "测试戏剧"
    assert fake_ctx.state["drama"]["status"] == "brainstorming"
```

---

## Test Coverage Gaps

**Critical untested areas:**

| Module | What's Not Tested | Priority |
|--------|-------------------|----------|
| `app/state_manager.py` | All state CRUD operations, save/load, conversation logging | High |
| `app/tools.py` | All 17+ tool functions, return dict structures | High |
| `app/actor_service.py` | Port calculation, name sanitization, service lifecycle | High |
| `app/agent.py` | StormRouter routing logic, sub-agent composition | Medium |
| `app/app_utils/typing.py` | Feedback model validation | Low |
| `app/app_utils/telemetry.py` | Telemetry setup configuration | Low |
| `tests/eval/evalsets/` | No drama-domain-specific eval cases | Medium |

**Recommended test additions:**
1. `tests/unit/test_state_manager.py` — test all `_get_state`/`_set_state`/`register_actor`/`advance_scene`/STORM functions
2. `tests/unit/test_tools.py` — test tool return dict formats, error handling, Chinese message content
3. `tests/unit/test_actor_service.py` — test `_get_actor_port` determinism, `_sanitize_name`, `generate_actor_agent_code` output
4. `tests/integration/test_storm_flow.py` — test full STORM discovery→research→outline→acting flow
5. Update `tests/eval/evalsets/basic.evalset.json` with drama-specific cases (e.g., `/start 靖难之役`, `/next`, `/action 一支暗箭射来`)

---

*Testing analysis: 2026-04-11*
