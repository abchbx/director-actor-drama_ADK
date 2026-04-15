"""Unit tests for query-style API endpoints.

Tests cover all 6 query endpoints: status, cast, save, load, list, export.
Uses FastAPI dependency_overrides for tool_context and patches state_manager functions.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api import create_app
from app.api.deps import ToolContextAdapter, get_tool_context


# ============================================================================
# Helpers
# ============================================================================


def _make_mock_tool_context(theme: str = "测试戏剧"):
    """Create a mock ToolContextAdapter with drama state."""
    tc = MagicMock(spec=ToolContextAdapter)
    tc.state = {
        "drama": {
            "theme": theme,
            "status": "acting",
            "current_scene": 3,
            "scenes": [{"scene_number": 1}, {"scene_number": 2}, {"scene_number": 3}],
            "actors": {
                "朱棣": {"role": "燕王", "personality": "沉稳冷静", "emotions": "neutral"},
                "苏念": {"role": "宫女", "personality": "温柔聪慧", "emotions": "anxious"},
            },
        }
    }
    return tc


def _make_empty_tool_context():
    """Create a mock ToolContextAdapter with NO active drama."""
    tc = MagicMock(spec=ToolContextAdapter)
    tc.state = {"drama": {}}
    return tc


# ============================================================================
# Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def api_client_with_deps():
    """Create an API client with deps overridden and state_manager functions patched."""
    app = create_app()
    mock_tc = _make_mock_tool_context()

    app.dependency_overrides[get_tool_context] = lambda: mock_tc

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, mock_tc

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def api_client_empty_drama():
    """Create an API client with empty drama state (no active drama)."""
    app = create_app()
    empty_tc = _make_empty_tool_context()

    app.dependency_overrides[get_tool_context] = lambda: empty_tc

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


# ============================================================================
# Test: GET /api/v1/drama/status
# ============================================================================


class TestStatusEndpoint:
    """GET /api/v1/drama/status"""

    @pytest.mark.asyncio
    @patch("app.api.routers.queries.get_current_state")
    async def test_status_endpoint(self, mock_get_state, api_client_with_deps):
        """GET /drama/status returns drama status."""
        client, mock_tc = api_client_with_deps
        mock_get_state.return_value = {
            "status": "success",
            "theme": "测试戏剧",
            "drama_status": "acting",
            "current_scene": 3,
            "num_scenes": 3,
            "num_actors": 2,
            "actors": ["朱棣", "苏念"],
            "drama_folder": "/path/to/drama",
        }

        response = await client.get("/api/v1/drama/status")

        assert response.status_code == 200
        data = response.json()
        assert data["theme"] == "测试戏剧"
        assert data["drama_status"] == "acting"
        assert data["current_scene"] == 3
        assert data["num_scenes"] == 3
        assert data["num_actors"] == 2
        mock_get_state.assert_called_once_with(mock_tc)


# ============================================================================
# Test: GET /api/v1/drama/cast
# ============================================================================


class TestCastEndpoint:
    """GET /api/v1/drama/cast"""

    @pytest.mark.asyncio
    @patch("app.api.routers.queries.get_all_actors")
    async def test_cast_endpoint(self, mock_get_actors, api_client_with_deps):
        """GET /drama/cast returns actor list."""
        client, mock_tc = api_client_with_deps
        mock_get_actors.return_value = {
            "status": "success",
            "actors": {
                "朱棣": {"role": "燕王", "personality": "沉稳冷静", "emotions": "neutral"},
                "苏念": {"role": "宫女", "personality": "温柔聪慧", "emotions": "anxious"},
            },
        }

        response = await client.get("/api/v1/drama/cast")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "朱棣" in data["actors"]
        assert "苏念" in data["actors"]
        mock_get_actors.assert_called_once_with(mock_tc)


# ============================================================================
# Test: POST /api/v1/drama/save
# ============================================================================


class TestSaveEndpoint:
    """POST /api/v1/drama/save"""

    @pytest.mark.asyncio
    @patch("app.api.routers.queries.save_progress")
    async def test_save_endpoint(self, mock_save, api_client_with_deps):
        """POST /drama/save saves drama and returns confirmation."""
        client, mock_tc = api_client_with_deps
        mock_save.return_value = {
            "status": "success",
            "message": "Progress auto-saved",
            "theme": "测试戏剧",
            "drama_status": "acting",
            "current_scene": 3,
            "num_actors": 2,
            "num_scenes": 3,
            "actors_list": ["朱棣", "苏念"],
        }

        response = await client.post("/api/v1/drama/save", json={"save_name": "test_save"})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        mock_save.assert_called_once_with("test_save", mock_tc)


# ============================================================================
# Test: POST /api/v1/drama/load
# ============================================================================


class TestLoadEndpoint:
    """POST /api/v1/drama/load"""

    @pytest.mark.asyncio
    @patch("app.api.routers.queries.load_progress")
    async def test_load_endpoint(self, mock_load, api_client_with_deps):
        """POST /drama/load loads a saved drama."""
        client, mock_tc = api_client_with_deps
        mock_load.return_value = {
            "status": "success",
            "message": "Loaded drama: 测试戏剧",
            "theme": "测试戏剧",
            "drama_status": "acting",
            "current_scene": 3,
            "num_actors": 2,
            "num_scenes": 3,
            "actors_list": ["朱棣", "苏念"],
        }

        response = await client.post("/api/v1/drama/load", json={"save_name": "test"})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["theme"] == "测试戏剧"


# ============================================================================
# Test: GET /api/v1/drama/list
# ============================================================================


class TestListEndpoint:
    """GET /api/v1/drama/list"""

    @pytest.mark.asyncio
    @patch("app.api.routers.queries.list_dramas")
    async def test_list_endpoint(self, mock_list, api_client_with_deps):
        """GET /drama/list returns all saved dramas."""
        client, _ = api_client_with_deps
        mock_list.return_value = {
            "status": "success",
            "dramas": [
                {"folder": "test_drama", "theme": "测试戏剧", "status": "acting", "current_scene": 3},
                {"folder": "another_drama", "theme": "另一戏剧", "status": "setup", "current_scene": 0},
            ],
        }

        response = await client.get("/api/v1/drama/list")

        assert response.status_code == 200
        data = response.json()
        assert len(data["dramas"]) == 2
        assert data["dramas"][0]["theme"] == "测试戏剧"


# ============================================================================
# Test: POST /api/v1/drama/export
# ============================================================================


class TestExportEndpoint:
    """POST /api/v1/drama/export"""

    @pytest.mark.asyncio
    @patch("app.api.routers.queries.export_script")
    async def test_export_endpoint(self, mock_export, api_client_with_deps):
        """POST /drama/export exports script as Markdown."""
        client, mock_tc = api_client_with_deps
        mock_export.return_value = {
            "status": "success",
            "message": "Script exported to: /path/to/export.md",
            "export_path": "/path/to/export.md",
        }

        response = await client.post("/api/v1/drama/export", json={"format": "markdown"})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["export_path"] == "/path/to/export.md"
        mock_export.assert_called_once_with(mock_tc)


# ============================================================================
# Test: 404 for no active drama
# ============================================================================


class TestNoActiveDrama:
    """Endpoints without active drama return 404."""

    @pytest.mark.asyncio
    async def test_status_no_active_drama_404(self, api_client_empty_drama):
        """GET /drama/status returns 404 when no active drama."""
        client = api_client_empty_drama
        response = await client.get("/api/v1/drama/status")

        assert response.status_code == 404
        assert "No active drama session" in response.json()["detail"]


# ============================================================================
# Test: Tool business errors → 200 + status: error (D-04)
# ============================================================================


class TestBusinessErrors:
    """Tool business errors return 200 with status: error (D-04)."""

    @pytest.mark.asyncio
    @patch("app.api.routers.queries.save_progress")
    async def test_save_error_returns_200(self, mock_save, api_client_with_deps):
        """POST /drama/save returns 200 with status: error when tool fails (D-04)."""
        client, mock_tc = api_client_with_deps
        mock_save.return_value = {
            "status": "error",
            "message": "No active drama to save.",
            "theme": "",
            "drama_status": "",
            "current_scene": 0,
            "num_actors": 0,
            "num_scenes": 0,
            "actors_list": [],
        }

        response = await client.post("/api/v1/drama/save", json={"save_name": ""})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert data["message"] == "No active drama to save."
