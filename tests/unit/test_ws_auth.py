"""Tests for Phase 15: WebSocket authentication.

Covers AUTH-03, D-09~D-11, D-16.
- WebSocket ?token=xxx validation
- Invalid token → WebSocketException(4001)
- Dev mode bypass
- Auth events logged
"""

import logging
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.ws_manager import ConnectionManager


# ============================================================================
# Helpers
# ============================================================================


def _setup_auth_app(token="test-ws-token-12345"):
    """Create app with auth state set (lifespan doesn't run in TestClient)."""
    app = create_app()
    app.state.api_token = token
    app.state.auth_enabled = bool(token)
    if not hasattr(app.state, "connection_manager"):
        app.state.connection_manager = ConnectionManager()
    return app


def _setup_dev_app():
    """Create app in dev mode (auth disabled)."""
    app = create_app()
    app.state.api_token = None
    app.state.auth_enabled = False
    if not hasattr(app.state, "connection_manager"):
        app.state.connection_manager = ConnectionManager()
    return app


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def auth_app():
    """Create app with API_TOKEN set (auth enabled)."""
    return _setup_auth_app("test-ws-token-12345")


@pytest.fixture
def dev_app():
    """Create app without API_TOKEN (dev mode)."""
    return _setup_dev_app()


# ============================================================================
# Test: WebSocket token auth
# ============================================================================


class TestWsTokenAuth:
    """WS connection tests with auth enabled."""

    def test_valid_token_connects(self, auth_app):
        """WS connection with valid ?token= succeeds."""
        client = TestClient(auth_app)
        with client.websocket_connect("/api/v1/ws?token=test-ws-token-12345") as ws:
            pass  # Successfully connected

    def test_missing_token_rejected(self, auth_app):
        """WS connection without ?token= when auth enabled → 4001."""
        client = TestClient(auth_app)
        with pytest.raises(Exception):
            with client.websocket_connect("/api/v1/ws"):
                pass

    def test_invalid_token_rejected(self, auth_app):
        """WS connection with ?token=wrong → 4001."""
        client = TestClient(auth_app)
        with pytest.raises(Exception):
            with client.websocket_connect("/api/v1/ws?token=wrong-token"):
                pass


class TestWsDevMode:
    """WS connection tests with auth disabled (dev mode)."""

    def test_no_token_dev_mode_connects(self, dev_app):
        """WS connection without ?token= in dev mode → accepted."""
        client = TestClient(dev_app)
        with client.websocket_connect("/api/v1/ws"):
            pass

    def test_with_token_dev_mode_connects(self, dev_app):
        """WS connection with ?token=anything in dev mode → accepted."""
        client = TestClient(dev_app)
        with client.websocket_connect("/api/v1/ws?token=anything"):
            pass


class TestWsAuthBeforeAccept:
    """Verify token check happens before accept (D-10)."""

    def test_invalid_token_does_not_add_to_pool(self, auth_app):
        """After failed auth, active_connections unchanged."""
        initial_count = len(auth_app.state.connection_manager.active_connections)
        client = TestClient(auth_app)
        try:
            with client.websocket_connect("/api/v1/ws?token=wrong"):
                pass
        except Exception:
            pass
        final_count = len(auth_app.state.connection_manager.active_connections)
        assert final_count == initial_count


class TestWsAuthLogging:
    """Tests for WS auth events logged to Python logger."""

    def test_ws_auth_failure_logged(self, auth_app, caplog):
        """Invalid WS token → warning log."""
        client = TestClient(auth_app)
        with caplog.at_level(logging.WARNING, logger="app.api.routers.websocket"):
            try:
                with client.websocket_connect("/api/v1/ws?token=wrong"):
                    pass
            except Exception:
                pass
        assert "WS auth failed" in caplog.text

    def test_ws_validate_function_exists(self):
        """websocket.py exports _validate_ws_token function."""
        from app.api.routers.websocket import _validate_ws_token
        assert callable(_validate_ws_token)
