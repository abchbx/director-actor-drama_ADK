"""Unit and integration tests for Bearer Token authentication.

Covers:
- require_auth dependency: valid token, invalid token, missing header, dev mode bypass
- Lifespan: API_TOKEN → app.state.api_token, auth_enabled flag, WARNING log
- GET /api/v1/auth/verify endpoint: valid/bypass/invalid scenarios
- Endpoint protection: all 14 REST endpoints require auth when enabled
- Full auth integration flow (REST + WebSocket)
- Token format compatibility
- Auth logging verification
"""

import asyncio
import os
import secrets
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


# ---------------------------------------------------------------------------
# Test 4: Endpoint protection — all 14 REST endpoints
# ---------------------------------------------------------------------------


# All 14 REST endpoints to test for auth protection
# 8 command endpoints + 6 query endpoints + auth/verify = 15 total
# We test the 14 drama endpoints (auth/verify is tested above)
COMMAND_ENDPOINTS = [
    ("POST", "/api/v1/drama/start", {"theme": "test"}),
    ("POST", "/api/v1/drama/next", None),
    ("POST", "/api/v1/drama/action", {"description": "test"}),
    ("POST", "/api/v1/drama/speak", {"actor_name": "A", "situation": "test"}),
    ("POST", "/api/v1/drama/steer", {"direction": "test"}),
    ("POST", "/api/v1/drama/auto", {"num_scenes": 1}),
    ("POST", "/api/v1/drama/end", None),
    ("POST", "/api/v1/drama/storm", {"focus": "test"}),
]

QUERY_ENDPOINTS = [
    ("GET", "/api/v1/drama/status", None),
    ("GET", "/api/v1/drama/cast", None),
    ("POST", "/api/v1/drama/save", {"save_name": "test"}),
    ("POST", "/api/v1/drama/load", {"save_name": "test"}),
    ("GET", "/api/v1/drama/list", None),
    ("POST", "/api/v1/drama/export", {"format": "markdown"}),
]

ALL_ENDPOINTS = COMMAND_ENDPOINTS + QUERY_ENDPOINTS


def _make_auth_client(auth_enabled: bool, token: str | None = None):
    """Create an API client with configurable auth state and mocked deps.

    Args:
        auth_enabled: If True, API_TOKEN is required. If False, dev mode.
        token: The API_TOKEN value. If None and auth_enabled, defaults to "test-token-12345".
    """
    from app.api.deps import get_runner, get_runner_lock, get_tool_context as _get_tc

    app = create_app()
    if auth_enabled:
        app.state.auth_enabled = True
        app.state.api_token = token or "test-token-12345"
    else:
        app.state.auth_enabled = False
        app.state.api_token = None

    # Mock all deps so endpoints can execute without real Runner/Session
    mock_runner = MagicMock()
    mock_lock = asyncio.Lock()
    mock_tc = _make_mock_tool_context()

    app.dependency_overrides[get_runner] = lambda: mock_runner
    app.dependency_overrides[get_runner_lock] = lambda: mock_lock
    app.dependency_overrides[_get_tc] = lambda: mock_tc

    return app


class TestEndpointProtection:
    """Verify all 14 REST endpoints are protected by require_auth."""

    @pytest.mark.asyncio
    async def test_all_endpoints_return_401_without_token(self):
        """All 14 REST endpoints return 401 when auth enabled and no token provided."""
        app = _make_auth_client(auth_enabled=True)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            for method, path, body in ALL_ENDPOINTS:
                if method == "GET":
                    resp = await client.get(path)
                else:
                    resp = await client.post(path, json=body)
                assert resp.status_code == 401, (
                    f"{method} {path} should return 401 without token, got {resp.status_code}"
                )

    @pytest.mark.asyncio
    async def test_all_endpoints_return_401_with_wrong_token(self):
        """All 14 REST endpoints return 401 when auth enabled and wrong token provided."""
        app = _make_auth_client(auth_enabled=True)
        transport = ASGITransport(app=app)
        headers = {"Authorization": "Bearer wrong-token"}
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            for method, path, body in ALL_ENDPOINTS:
                if method == "GET":
                    resp = await client.get(path, headers=headers)
                else:
                    resp = await client.post(path, json=body, headers=headers)
                assert resp.status_code == 401, (
                    f"{method} {path} should return 401 with wrong token, got {resp.status_code}"
                )

    @pytest.mark.asyncio
    async def test_all_endpoints_pass_with_valid_token(self):
        """All 14 REST endpoints pass auth when valid token provided.

        Note: some endpoints may return 404 (no active drama) or other business
        errors after auth, but NOT 401.
        """
        from unittest.mock import patch

        app = _make_auth_client(auth_enabled=True)
        transport = ASGITransport(app=app)
        headers = {"Authorization": "Bearer test-token-12345"}
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Patch run_command_and_collect for command endpoints
            with patch(
                "app.api.routers.commands.run_command_and_collect",
                new=AsyncMock(return_value=MOCK_RESULT),
            ):
                for method, path, body in ALL_ENDPOINTS:
                    if method == "GET":
                        resp = await client.get(path, headers=headers)
                    else:
                        resp = await client.post(path, json=body, headers=headers)
                    assert resp.status_code != 401, (
                        f"{method} {path} should not return 401 with valid token, got {resp.status_code}"
                    )

    @pytest.mark.asyncio
    async def test_all_endpoints_accessible_in_dev_mode(self):
        """All 14 REST endpoints accessible without token in dev mode (auth disabled)."""
        from unittest.mock import patch

        app = _make_auth_client(auth_enabled=False)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch(
                "app.api.routers.commands.run_command_and_collect",
                new=AsyncMock(return_value=MOCK_RESULT),
            ):
                for method, path, body in ALL_ENDPOINTS:
                    if method == "GET":
                        resp = await client.get(path)
                    else:
                        resp = await client.post(path, json=body)
                    assert resp.status_code != 401, (
                        f"{method} {path} should not return 401 in dev mode, got {resp.status_code}"
                    )


# ---------------------------------------------------------------------------
# Test 5: Full auth integration flow (REST + WebSocket)
# ---------------------------------------------------------------------------


class TestAuthIntegration:
    """Integration tests verifying the full auth flow across REST + WebSocket."""

    @pytest.mark.asyncio
    async def test_full_auth_flow_with_token(self):
        """Full flow: auth enabled → verify + drama endpoints with/without token."""
        from app.api.deps import get_runner, get_runner_lock, get_tool_context as _get_tc

        app = create_app()
        app.state.auth_enabled = True
        app.state.api_token = "test-integration-token"

        # Mock deps so endpoints can execute without real Runner/Session
        mock_runner = MagicMock()
        mock_lock = asyncio.Lock()
        mock_tc = _make_mock_tool_context()
        app.dependency_overrides[get_runner] = lambda: mock_runner
        app.dependency_overrides[get_runner_lock] = lambda: mock_lock
        app.dependency_overrides[_get_tc] = lambda: mock_tc

        transport = ASGITransport(app=app)
        headers = {"Authorization": "Bearer test-integration-token"}

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Auth verify with valid token → 200, {valid: true, mode: "token"}
            resp = await client.get("/api/v1/auth/verify", headers=headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["valid"] is True
            assert data["mode"] == "token"

            # 2. Drama status with valid token → 200 or 404 (no drama), NOT 401
            with patch(
                "app.api.routers.commands.run_command_and_collect",
                new=AsyncMock(return_value=MOCK_RESULT),
            ):
                resp = await client.get("/api/v1/drama/status", headers=headers)
                assert resp.status_code != 401

            # 3. Drama status without token → 401
            resp = await client.get("/api/v1/drama/status")
            assert resp.status_code == 401

            # 4. Drama status with wrong token → 401
            resp = await client.get(
                "/api/v1/drama/status",
                headers={"Authorization": "Bearer wrong-token"},
            )
            assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_full_auth_flow_dev_mode(self):
        """Full flow: auth disabled → verify + drama endpoints without token."""
        from app.api.deps import get_runner, get_runner_lock, get_tool_context as _get_tc

        app = create_app()
        app.state.auth_enabled = False
        app.state.api_token = None

        mock_runner = MagicMock()
        mock_lock = asyncio.Lock()
        mock_tc = _make_mock_tool_context()
        app.dependency_overrides[get_runner] = lambda: mock_runner
        app.dependency_overrides[get_runner_lock] = lambda: mock_lock
        app.dependency_overrides[_get_tc] = lambda: mock_tc

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Auth verify without token → 200, {valid: true, mode: "bypass"}
            resp = await client.get("/api/v1/auth/verify")
            assert resp.status_code == 200
            data = resp.json()
            assert data["valid"] is True
            assert data["mode"] == "bypass"

            # 2. Drama status without token → NOT 401
            resp = await client.get("/api/v1/drama/status")
            assert resp.status_code != 401

    @pytest.mark.asyncio
    async def test_token_format_compatibility(self):
        """secrets.token_urlsafe(32) works as Bearer token and WS ?token=."""
        from fastapi.testclient import TestClient

        generated_token = secrets.token_urlsafe(32)

        # Set as API_TOKEN on app.state
        app = create_app()
        app.state.api_token = generated_token
        app.state.auth_enabled = True
        from app.api.ws_manager import ConnectionManager

        if not hasattr(app.state, "connection_manager"):
            app.state.connection_manager = ConnectionManager()

        # 1. Bearer token works on REST endpoints
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/auth/verify",
                headers={"Authorization": f"Bearer {generated_token}"},
            )
            assert resp.status_code == 200
            assert resp.json()["valid"] is True

        # 2. WS ?token= works with same token value
        client = TestClient(app)
        with client.websocket_connect(f"/api/v1/ws?token={generated_token}") as ws:
            pass  # Successfully connected

    def test_15_endpoints_total_count(self):
        """Total endpoint count: 14 drama REST + 1 auth/verify = 15 under /api/v1/."""
        app = create_app()
        routes = [
            route
            for route in app.routes
            if hasattr(route, "path")
            and route.path.startswith("/api/v1/")
            and not route.path.startswith("/api/v1/ws")  # WS is not a REST endpoint
        ]
        # 8 command + 6 query + 1 auth/verify = 15
        assert len(routes) == 15, f"Expected 15 REST endpoints, found {len(routes)}"

    @pytest.mark.asyncio
    async def test_auth_success_logged(self):
        """With auth enabled and valid token, logger.debug called with 'Auth succeeded'."""
        from app.api.deps import get_runner, get_runner_lock, get_tool_context as _get_tc
        from app.api.deps import require_auth as deps_require_auth

        app = create_app()
        app.state.auth_enabled = True
        app.state.api_token = "test-integration-token"

        transport = ASGITransport(app=app)
        headers = {"Authorization": "Bearer test-integration-token"}

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("app.api.deps.logger") as mock_logger:
                resp = await client.get("/api/v1/auth/verify", headers=headers)
                assert resp.status_code == 200
                # Verify debug log was called with success message
                debug_calls = [
                    str(call) for call in mock_logger.debug.call_args_list
                ]
                assert any("Auth succeeded" in call for call in debug_calls), (
                    f"Expected 'Auth succeeded' in debug logs, got: {debug_calls}"
                )

    @pytest.mark.asyncio
    async def test_auth_failure_logged(self):
        """With auth enabled and invalid token, logger.warning called with 'Auth failed'."""
        app = create_app()
        app.state.auth_enabled = True
        app.state.api_token = "test-integration-token"

        transport = ASGITransport(app=app)
        headers = {"Authorization": "Bearer wrong-token"}

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("app.api.deps.logger") as mock_logger:
                resp = await client.get("/api/v1/auth/verify", headers=headers)
                assert resp.status_code == 401
                # Verify warning log was called with failure message
                warning_calls = [
                    str(call) for call in mock_logger.warning.call_args_list
                ]
                assert any("Auth failed" in call for call in warning_calls), (
                    f"Expected 'Auth failed' in warning logs, got: {warning_calls}"
                )

    @pytest.mark.asyncio
    async def test_dev_mode_startup_warning(self):
        """When API_TOKEN is empty, logger.warning called with 'AUTH DISABLED'."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("API_TOKEN", None)
            app = create_app()
            from app.api.app import lifespan

            with patch("app.api.app.logger") as mock_logger:
                async with lifespan(app):
                    warning_calls = [
                        str(call) for call in mock_logger.warning.call_args_list
                    ]
                    assert any("AUTH DISABLED" in call for call in warning_calls), (
                        f"Expected 'AUTH DISABLED' in warning logs, got: {warning_calls}"
                    )
