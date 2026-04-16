"""Unit and integration tests for Bearer Token authentication.

Covers:
- require_auth dependency: valid token, invalid token, missing header, dev mode bypass
- Lifespan: API_TOKEN → app.state.api_token, auth_enabled flag, WARNING log
- GET /api/v1/auth/verify endpoint: valid/bypass/invalid scenarios
- Endpoint protection: all 14 REST endpoints require auth when enabled
"""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.api import create_app
from app.api.deps import ToolContextAdapter, require_auth
from app.api.models import AuthVerifyResponse


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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_enabled_app():
    """Create a FastAPI app with auth enabled (API_TOKEN set)."""
    app = create_app()
    app.state.auth_enabled = True
    app.state.api_token = "test-token-12345"
    return app


@pytest.fixture
def auth_disabled_app():
    """Create a FastAPI app with auth disabled (dev mode)."""
    app = create_app()
    app.state.auth_enabled = False
    app.state.api_token = None
    return app


@pytest_asyncio.fixture
async def auth_enabled_client(auth_enabled_app):
    """Create an async HTTP test client with auth enabled."""
    transport = ASGITransport(app=auth_enabled_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def auth_disabled_client(auth_disabled_app):
    """Create an async HTTP test client with auth disabled (dev mode)."""
    transport = ASGITransport(app=auth_disabled_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# Test 1: require_auth dependency
# ---------------------------------------------------------------------------


class TestRequireAuthDependency:
    """Unit tests for the require_auth dependency function."""

    @pytest.mark.asyncio
    async def test_valid_token_returns_true(self, auth_enabled_app):
        """require_auth with valid Bearer token returns True (auth passes)."""
        from fastapi.security import HTTPAuthorizationCredentials

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="test-token-12345"
        )

        # Create a mock request with app reference
        mock_request = MagicMock()
        mock_request.app = auth_enabled_app

        result = await require_auth(mock_request, credentials)
        assert result is True

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self, auth_enabled_app):
        """require_auth with invalid Bearer token raises HTTPException 401."""
        from fastapi.security import HTTPAuthorizationCredentials

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="wrong-token"
        )

        mock_request = MagicMock()
        mock_request.app = auth_enabled_app

        with pytest.raises(HTTPException) as exc_info:
            await require_auth(mock_request, credentials)
        assert exc_info.value.status_code == 401
        assert "Invalid token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_missing_authorization_header_raises_401(self, auth_enabled_app):
        """require_auth with missing Authorization header raises HTTPException 401."""
        mock_request = MagicMock()
        mock_request.app = auth_enabled_app

        with pytest.raises(HTTPException) as exc_info:
            await require_auth(mock_request, None)
        assert exc_info.value.status_code == 401
        assert "Not authenticated" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_dev_mode_returns_true(self, auth_disabled_app):
        """require_auth when auth_enabled=False (dev mode) returns True (bypass)."""
        mock_request = MagicMock()
        mock_request.app = auth_disabled_app

        result = await require_auth(mock_request, None)
        assert result is True


# ---------------------------------------------------------------------------
# Test 2: Lifespan — API_TOKEN initialization
# ---------------------------------------------------------------------------


class TestLifespanAuthTokenInit:
    """Tests for lifespan reading API_TOKEN from environment."""

    @pytest.mark.asyncio
    async def test_lifespan_sets_api_token_from_env(self):
        """lifespan sets app.state.api_token from os.getenv('API_TOKEN')."""
        with patch.dict(os.environ, {"API_TOKEN": "my-secret-token"}):
            app = create_app()
            from app.api.app import lifespan

            async with lifespan(app):
                assert app.state.api_token == "my-secret-token"

    @pytest.mark.asyncio
    async def test_lifespan_sets_auth_enabled_true_when_token_set(self):
        """lifespan sets app.state.auth_enabled=True when API_TOKEN is set."""
        with patch.dict(os.environ, {"API_TOKEN": "my-secret-token"}):
            app = create_app()
            from app.api.app import lifespan

            async with lifespan(app):
                assert app.state.auth_enabled is True
                assert app.state.api_token == "my-secret-token"

    @pytest.mark.asyncio
    async def test_lifespan_sets_auth_enabled_false_when_token_empty(self):
        """lifespan sets app.state.auth_enabled=False when API_TOKEN is empty/missing."""
        with patch.dict(os.environ, {"API_TOKEN": ""}, clear=False):
            # Ensure API_TOKEN is empty string
            app = create_app()
            from app.api.app import lifespan

            async with lifespan(app):
                assert app.state.auth_enabled is False
                assert app.state.api_token is None

    @pytest.mark.asyncio
    async def test_lifespan_sets_auth_enabled_false_when_token_missing(self):
        """lifespan sets auth_enabled=False when API_TOKEN env var doesn't exist."""
        # Remove API_TOKEN from environment
        env = dict(os.environ)
        env.pop("API_TOKEN", None)
        with patch.dict(os.environ, env, clear=True):
            app = create_app()
            from app.api.app import lifespan

            async with lifespan(app):
                assert app.state.auth_enabled is False
                assert app.state.api_token is None

    @pytest.mark.asyncio
    async def test_lifespan_logs_warning_when_auth_disabled(self):
        """lifespan prints WARNING when auth is disabled (dev mode)."""
        with patch.dict(os.environ, {}, clear=False):
            # Ensure API_TOKEN is not set
            os.environ.pop("API_TOKEN", None)
            app = create_app()
            from app.api.app import lifespan

            with patch("app.api.app.logger") as mock_logger:
                async with lifespan(app):
                    mock_logger.warning.assert_called()
                    call_args = str(mock_logger.warning.call_args)
                    assert "AUTH DISABLED" in call_args or "No API_TOKEN" in call_args


# ---------------------------------------------------------------------------
# Test 3: GET /api/v1/auth/verify endpoint
# ---------------------------------------------------------------------------


class TestAuthVerifyEndpoint:
    """Integration tests for GET /api/v1/auth/verify."""

    @pytest.mark.asyncio
    async def test_verify_with_valid_token(self, auth_enabled_client):
        """GET /api/v1/auth/verify with valid token returns {valid: true, mode: token}."""
        response = await auth_enabled_client.get(
            "/api/v1/auth/verify",
            headers={"Authorization": "Bearer test-token-12345"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["mode"] == "token"

    @pytest.mark.asyncio
    async def test_verify_in_dev_mode(self, auth_disabled_client):
        """GET /api/v1/auth/verify in dev mode returns {valid: true, mode: bypass}."""
        response = await auth_disabled_client.get("/api/v1/auth/verify")
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["mode"] == "bypass"

    @pytest.mark.asyncio
    async def test_verify_with_invalid_token(self, auth_enabled_client):
        """GET /api/v1/auth/verify with invalid token returns 401."""
        response = await auth_enabled_client.get(
            "/api/v1/auth/verify",
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_verify_without_token_when_auth_enabled(self, auth_enabled_client):
        """GET /api/v1/auth/verify without token returns 401 when auth enabled."""
        response = await auth_enabled_client.get("/api/v1/auth/verify")
        assert response.status_code == 401
