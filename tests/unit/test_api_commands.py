"""Unit tests for command-style REST endpoints.

Tests the 8 command endpoints that route through the ADK Runner:
- POST /api/v1/drama/start, /next, /action, /speak, /steer, /auto, /end, /storm
- 404 when no active drama (except /start)
- 504 on timeout
- Auto-save on /start when drama already exists
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api import create_app
from app.api.deps import ToolContextAdapter


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


@pytest.fixture
def mock_runner():
    """Create a mock ADK Runner."""
    return MagicMock()


@pytest.fixture
def mock_lock():
    """Create a mock asyncio.Lock that actually context-manages."""
    lock = asyncio.Lock()
    return lock


@pytest.fixture
def mock_session_service():
    """Create a mock InMemorySessionService."""
    return MagicMock()


@pytest_asyncio.fixture
async def api_client_with_deps(mock_runner, mock_lock, mock_session_service):
    """Create an API client with all deps mocked at the app.state level."""
    app = create_app()

    # Override lifespan to inject our mocks into app.state
    # We patch the dependency functions instead of the lifespan
    mock_tc = _make_mock_tool_context()

    with (
        patch("app.api.deps.get_runner", return_value=mock_runner),
        patch("app.api.deps.get_session_service", return_value=mock_session_service),
        patch("app.api.deps.get_runner_lock", return_value=mock_lock),
        patch("app.api.deps.get_tool_context", return_value=mock_tc),
        patch(
            "app.api.runner_utils.run_command_and_collect",
            new=AsyncMock(return_value=MOCK_RESULT),
        ),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client, mock_tc


# ---------------------------------------------------------------------------
# Tests — Happy path for all 8 endpoints
# ---------------------------------------------------------------------------


class TestStartDrama:
    """POST /api/v1/drama/start"""

    @pytest.mark.asyncio
    async def test_start_drama_endpoint(self, api_client_with_deps):
        """POST /api/v1/drama/start with theme returns CommandResponse."""
        client, _ = api_client_with_deps
        with patch(
            "app.api.runner_utils.run_command_and_collect",
            new=AsyncMock(return_value=MOCK_RESULT),
        ):
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
        with patch(
            "app.api.runner_utils.run_command_and_collect",
            new=AsyncMock(return_value=MOCK_RESULT),
        ):
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
        with patch(
            "app.api.runner_utils.run_command_and_collect",
            new=AsyncMock(return_value=MOCK_RESULT),
        ):
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
        with patch(
            "app.api.runner_utils.run_command_and_collect",
            new=AsyncMock(return_value=MOCK_RESULT),
        ):
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
        with patch(
            "app.api.runner_utils.run_command_and_collect",
            new=AsyncMock(return_value=MOCK_RESULT),
        ):
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
        with patch(
            "app.api.runner_utils.run_command_and_collect",
            new=AsyncMock(return_value=MOCK_RESULT),
        ):
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
        with patch(
            "app.api.runner_utils.run_command_and_collect",
            new=AsyncMock(return_value=MOCK_RESULT),
        ):
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
        with patch(
            "app.api.runner_utils.run_command_and_collect",
            new=AsyncMock(return_value=MOCK_RESULT),
        ):
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
    async def test_no_active_drama_returns_404(self, mock_runner, mock_lock, mock_session_service):
        """POST /api/v1/drama/next without active drama returns 404."""
        app = create_app()
        empty_tc = _make_empty_tool_context()

        with (
            patch("app.api.deps.get_runner", return_value=mock_runner),
            patch("app.api.deps.get_session_service", return_value=mock_session_service),
            patch("app.api.deps.get_runner_lock", return_value=mock_lock),
            patch("app.api.deps.get_tool_context", return_value=empty_tc),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/drama/next")
        assert response.status_code == 404
        assert "No active drama session" in response.json()["detail"]


class TestTimeout:
    """Timeout scenario returns 504."""

    @pytest.mark.asyncio
    async def test_timeout_returns_504(self, mock_runner, mock_lock, mock_session_service):
        """POST /api/v1/drama/next when Runner times out returns 504."""
        from fastapi import HTTPException

        app = create_app()
        mock_tc = _make_mock_tool_context()

        async def timeout_side_effect(*args, **kwargs):
            raise HTTPException(status_code=504, detail="Command execution timed out")

        with (
            patch("app.api.deps.get_runner", return_value=mock_runner),
            patch("app.api.deps.get_session_service", return_value=mock_session_service),
            patch("app.api.deps.get_runner_lock", return_value=mock_lock),
            patch("app.api.deps.get_tool_context", return_value=mock_tc),
            patch(
                "app.api.runner_utils.run_command_and_collect",
                new=AsyncMock(side_effect=timeout_side_effect),
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/drama/next")
        assert response.status_code == 504


# ---------------------------------------------------------------------------
# Tests — Auto-save on /start
# ---------------------------------------------------------------------------


class TestStartAutoSave:
    """POST /api/v1/drama/start auto-saves existing drama before starting new one."""

    @pytest.mark.asyncio
    async def test_start_auto_saves_existing(self, mock_runner, mock_lock, mock_session_service):
        """save_progress + flush_state_sync called when drama already exists before /start."""
        app = create_app()
        mock_tc = _make_mock_tool_context(theme="existing drama")

        with (
            patch("app.api.deps.get_runner", return_value=mock_runner),
            patch("app.api.deps.get_session_service", return_value=mock_session_service),
            patch("app.api.deps.get_runner_lock", return_value=mock_lock),
            patch("app.api.deps.get_tool_context", return_value=mock_tc),
            patch(
                "app.api.runner_utils.run_command_and_collect",
                new=AsyncMock(return_value=MOCK_RESULT),
            ),
            patch("app.api.routers.commands.save_progress") as mock_save,
            patch("app.api.routers.commands.flush_state_sync") as mock_flush,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/drama/start", json={"theme": "新戏剧"}
                )
        assert response.status_code == 200
        mock_save.assert_called_once()
        mock_flush.assert_called_once()
