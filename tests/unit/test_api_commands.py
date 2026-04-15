"""Unit tests for command-style REST endpoints.

Tests the 8 command endpoints that route through the ADK Runner:
- POST /api/v1/drama/start, /next, /action, /speak, /steer, /auto, /end, /storm
- 404 when no active drama (except /start)
- 504 on timeout
- Auto-save on /start when drama already exists
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api import create_app
from app.api.deps import ToolContextAdapter, get_tool_context


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MOCK_RESULT = {
    "final_response": "Director response",
    "tool_results": [{"result": "ok"}],
    "status": "success",
}


def _make_mock_tool_context(theme: str = "existing drama"):
    """Create a mock ToolContextAdapter with drama state."""
    tc = MagicMock(spec=ToolContextAdapter)
    tc.state = {"drama": {"theme": theme, "current_scene": 1}}
    return tc


def _make_empty_tool_context():
    """Create a mock ToolContextAdapter with NO active drama."""
    tc = MagicMock(spec=ToolContextAdapter)
    tc.state = {"drama": {}}
    return tc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def api_client_with_deps():
    """Create an API client with all deps overridden via FastAPI dependency_overrides."""
    app = create_app()
    mock_runner = MagicMock()
    mock_lock = asyncio.Lock()
    mock_tc = _make_mock_tool_context()
    mock_collect = AsyncMock(return_value=MOCK_RESULT)

    # Override FastAPI dependencies
    from app.api.deps import get_runner, get_runner_lock, get_tool_context as _get_tc

    app.dependency_overrides[get_runner] = lambda: mock_runner
    app.dependency_overrides[get_runner_lock] = lambda: mock_lock
    app.dependency_overrides[_get_tc] = lambda: mock_tc

    # Patch run_command_and_collect where it's imported in commands.py
    with patch(
        "app.api.routers.commands.run_command_and_collect",
        new=AsyncMock(return_value=MOCK_RESULT),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client, mock_tc

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def api_client_empty_drama():
    """Create an API client with empty drama state (no active drama)."""
    app = create_app()
    mock_runner = MagicMock()
    mock_lock = asyncio.Lock()
    empty_tc = _make_empty_tool_context()

    from app.api.deps import get_runner, get_runner_lock, get_tool_context as _get_tc

    app.dependency_overrides[get_runner] = lambda: mock_runner
    app.dependency_overrides[get_runner_lock] = lambda: mock_lock
    app.dependency_overrides[_get_tc] = lambda: empty_tc

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


# We need `patch` from unittest.mock at module level for the fixture above
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Tests — Happy path for all 8 endpoints
# ---------------------------------------------------------------------------


class TestStartDrama:
    """POST /api/v1/drama/start"""

    @pytest.mark.asyncio
    async def test_start_drama_endpoint(self, api_client_with_deps):
        """POST /api/v1/drama/start with theme returns CommandResponse."""
        client, _ = api_client_with_deps
        response = await client.post(
            "/api/v1/drama/start", json={"theme": "测试"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "final_response" in data
        assert "tool_results" in data
        assert "status" in data


class TestNextScene:
    """POST /api/v1/drama/next"""

    @pytest.mark.asyncio
    async def test_next_scene_endpoint(self, api_client_with_deps):
        """POST /api/v1/drama/next returns CommandResponse with status."""
        client, _ = api_client_with_deps
        response = await client.post("/api/v1/drama/next")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"


class TestAction:
    """POST /api/v1/drama/action"""

    @pytest.mark.asyncio
    async def test_action_endpoint(self, api_client_with_deps):
        """POST /api/v1/drama/action with description returns CommandResponse."""
        client, _ = api_client_with_deps
        response = await client.post(
            "/api/v1/drama/action", json={"description": "test action"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["final_response"] == "Director response"


class TestSpeak:
    """POST /api/v1/drama/speak"""

    @pytest.mark.asyncio
    async def test_speak_endpoint(self, api_client_with_deps):
        """POST /api/v1/drama/speak with actor_name and situation returns CommandResponse."""
        client, _ = api_client_with_deps
        response = await client.post(
            "/api/v1/drama/speak",
            json={"actor_name": "朱棣", "situation": "沉思"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"


class TestSteer:
    """POST /api/v1/drama/steer"""

    @pytest.mark.asyncio
    async def test_steer_endpoint(self, api_client_with_deps):
        """POST /api/v1/drama/steer with direction returns CommandResponse."""
        client, _ = api_client_with_deps
        response = await client.post(
            "/api/v1/drama/steer", json={"direction": "冲突升级"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"


class TestAuto:
    """POST /api/v1/drama/auto"""

    @pytest.mark.asyncio
    async def test_auto_endpoint_default(self, api_client_with_deps):
        """POST /api/v1/drama/auto with {} defaults to 3 scenes, returns CommandResponse."""
        client, _ = api_client_with_deps
        response = await client.post("/api/v1/drama/auto", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"


class TestEnd:
    """POST /api/v1/drama/end"""

    @pytest.mark.asyncio
    async def test_end_endpoint(self, api_client_with_deps):
        """POST /api/v1/drama/end returns CommandResponse."""
        client, _ = api_client_with_deps
        response = await client.post("/api/v1/drama/end")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"


class TestStorm:
    """POST /api/v1/drama/storm"""

    @pytest.mark.asyncio
    async def test_storm_endpoint_no_focus(self, api_client_with_deps):
        """POST /api/v1/drama/storm with {} returns CommandResponse."""
        client, _ = api_client_with_deps
        response = await client.post("/api/v1/drama/storm", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"


# ---------------------------------------------------------------------------
# Tests — Error cases
# ---------------------------------------------------------------------------


class TestNoActiveDrama:
    """Endpoints without active drama return 404 (except /start)."""

    @pytest.mark.asyncio
    async def test_no_active_drama_returns_404(self, api_client_empty_drama):
        """POST /api/v1/drama/next without active drama returns 404."""
        client = api_client_empty_drama
        response = await client.post("/api/v1/drama/next")
        assert response.status_code == 404
        assert "No active drama session" in response.json()["detail"]


class TestTimeout:
    """Timeout scenario returns 504."""

    @pytest.mark.asyncio
    async def test_timeout_returns_504(self):
        """POST /api/v1/drama/next when Runner times out returns 504."""
        from fastapi import HTTPException

        app = create_app()
        mock_runner = MagicMock()
        mock_lock = asyncio.Lock()
        mock_tc = _make_mock_tool_context()

        from app.api.deps import get_runner, get_runner_lock, get_tool_context as _get_tc

        app.dependency_overrides[get_runner] = lambda: mock_runner
        app.dependency_overrides[get_runner_lock] = lambda: mock_lock
        app.dependency_overrides[_get_tc] = lambda: mock_tc

        async def timeout_side_effect(*args, **kwargs):
            raise HTTPException(status_code=504, detail="Command execution timed out")

        with patch(
            "app.api.routers.commands.run_command_and_collect",
            new=AsyncMock(side_effect=timeout_side_effect),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/drama/next")
        assert response.status_code == 504
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests — Auto-save on /start
# ---------------------------------------------------------------------------


class TestStartAutoSave:
    """POST /api/v1/drama/start auto-saves existing drama before starting new one."""

    @pytest.mark.asyncio
    async def test_start_auto_saves_existing(self):
        """save_progress + flush_state_sync called when drama already exists before /start."""
        app = create_app()
        mock_runner = MagicMock()
        mock_lock = asyncio.Lock()
        mock_tc = _make_mock_tool_context(theme="existing drama")

        from app.api.deps import get_runner, get_runner_lock, get_tool_context as _get_tc

        app.dependency_overrides[get_runner] = lambda: mock_runner
        app.dependency_overrides[get_runner_lock] = lambda: mock_lock
        app.dependency_overrides[_get_tc] = lambda: mock_tc

        with (
            patch(
                "app.api.routers.commands.run_command_and_collect",
                new=AsyncMock(return_value=MOCK_RESULT),
            ),
            patch("app.state_manager.save_progress") as mock_save,
            patch("app.state_manager.flush_state_sync") as mock_flush,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/drama/start", json={"theme": "新戏剧"}
                )
        assert response.status_code == 200
        mock_save.assert_called_once()
        mock_flush.assert_called_once()
        app.dependency_overrides.clear()
