# Testing Patterns

**Analysis Date:** 2026-04-25

## Test Framework

**Runner:**
- pytest (Python)
- Config: `pyproject.toml` (test section)

**Assertion Library:**
- Standard pytest assertions

**Run Commands:**
```bash
pytest                          # Run all tests
pytest tests/test_state_manager.py  # Run specific test file
```

## Test File Organization

**Location:**
- Separate `tests/` directory at project root

**Naming:**
- `test_<module_name>.py`

**Structure:**
```
tests/
├── test_state_manager.py
├── test_agent.py
├── ... (other test files)
```

## Test Structure

**Suite Organization:**
```python
# Standard pytest class-based organization
class TestStateManager:
    def test_init_drama_state(self):
        """Test drama state initialization."""
        # Arrange
        theme = "测试剧本"
        # Act
        result = init_drama_state(theme, tool_context)
        # Assert
        assert result["status"] == "success"
```

**Patterns:**
- Setup: Tool context fixtures, mock session state
- Teardown: Not commonly used (stateless tests preferred)
- Assertion: Standard `assert` statements

## Mocking

**Framework:** `unittest.mock` (standard library)

**Patterns:**
```python
# Mocking A2A calls in tests
from unittest.mock import patch, AsyncMock

@patch("app.tools._call_a2a_sdk", new_callable=AsyncMock)
async def test_actor_speak_success(self, mock_a2a):
    mock_a2a.return_value = "这是角色的对话"
    result = await actor_speak("角色A", "情境描述", tool_context)
    assert result["status"] == "success"
    assert result["dialogue"] == "这是角色的对话"
```

**What to Mock:**
- A2A SDK calls (actor service responses)
- LLM calls (expensive, non-deterministic)
- File system operations (for state persistence tests)

**What NOT to Mock:**
- State management logic (test real behavior)
- Event mapping logic (pure functions)
- Data transformation functions

## Fixtures and Factories

**Test Data:**
```python
# Common fixture: mock tool context with drama state
def make_tool_context(drama_state=None):
    """Create a mock ToolContext with optional drama state."""
    ctx = MagicMock()
    ctx.state = {"drama": drama_state or {}}
    return ctx
```

**Location:**
- Inline in test files (no shared conftest.py detected)

## Coverage

**Requirements:** None enforced

**View Coverage:**
```bash
pytest --cov=app tests/
```

## Test Types

**Unit Tests:**
- Scope: Individual tool functions, state management, event mapping
- Approach: Mock external dependencies, test pure logic

**Integration Tests:**
- Scope: Full command flow through Runner (less common)
- Approach: Mock LLM responses, test tool call chains

**E2E Tests:**
- Not used in Python backend
- Not detected in Android client

## Android Testing

**Status:** No Android test files detected in the codebase
- No `androidTest/` directory found
- No local unit test directory found
- This is a significant gap for a production app

## Common Patterns

**Async Testing:**
```python
# Tool functions are async when calling A2A
async def test_actor_speak_calls_a2a():
    result = await actor_speak("角色A", "情境", tool_context)
    assert result["status"] in ("success", "error")
```

**Error Testing:**
```python
# Testing error responses (never exceptions)
def test_actor_speak_unknown_actor():
    result = await actor_speak("不存在的角色", "情境", tool_context)
    assert result["status"] == "error"
    assert "not found" in result["message"].lower()
```

---

*Testing analysis: 2026-04-25*
