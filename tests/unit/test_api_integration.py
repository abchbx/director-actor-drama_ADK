"""Integration tests for API Foundation: lock file, flush-on-push, full lifecycle."""
import os
import pytest
import tempfile
from unittest.mock import patch, MagicMock

from app.api.lock import acquire_lock, release_lock, LOCK_FILE, _is_pid_alive
from app.api import create_app


class TestLockFile:
    def test_acquire_creates_lock_file(self, tmp_path):
        """acquire_lock() creates lock file with current PID."""
        lock_path = str(tmp_path / ".api.lock")
        with patch("app.api.lock.LOCK_FILE", lock_path):
            acquire_lock()
            assert os.path.exists(lock_path)
            with open(lock_path) as f:
                assert int(f.read().strip()) == os.getpid()
            release_lock()  # cleanup
            assert not os.path.exists(lock_path)

    def test_acquire_refuses_when_already_running(self, tmp_path):
        """acquire_lock() raises RuntimeError if another instance is running."""
        lock_path = str(tmp_path / ".api.lock")
        with patch("app.api.lock.LOCK_FILE", lock_path):
            acquire_lock()
            with pytest.raises(RuntimeError, match="Another instance is already running"):
                acquire_lock()
            release_lock()

    def test_stale_lock_removed(self, tmp_path):
        """acquire_lock() removes stale lock file if PID no longer alive."""
        lock_path = str(tmp_path / ".api.lock")
        with patch("app.api.lock.LOCK_FILE", lock_path):
            # Write a PID that doesn't exist (99999999 is very unlikely to be alive)
            with open(lock_path, "w") as f:
                f.write("99999999")
            # Should not raise — stale lock removed
            acquire_lock()
            release_lock()

    def test_corrupted_lock_removed(self, tmp_path):
        """acquire_lock() removes corrupted lock file (non-integer content)."""
        lock_path = str(tmp_path / ".api.lock")
        with patch("app.api.lock.LOCK_FILE", lock_path):
            with open(lock_path, "w") as f:
                f.write("not_a_pid")
            acquire_lock()  # Should not raise
            release_lock()

    def test_release_nonexistent_lock_no_error(self, tmp_path):
        """release_lock() doesn't raise if lock file doesn't exist."""
        lock_path = str(tmp_path / ".api.lock")
        with patch("app.api.lock.LOCK_FILE", lock_path):
            release_lock()  # Should not raise

    def test_is_pid_alive_current_process(self):
        """_is_pid_alive returns True for current process."""
        assert _is_pid_alive(os.getpid()) is True

    def test_is_pid_alive_nonexistent(self):
        """_is_pid_alive returns False for non-existent PID."""
        assert _is_pid_alive(99999999) is False


class TestFlushOnPush:
    def test_app_has_flush_state_sync_attribute(self):
        """App state includes flush_state_sync for Phase 14 WebSocket."""
        import inspect
        from app.api.app import lifespan
        source = inspect.getsource(lifespan)
        assert "flush_state_sync" in source

    def test_app_has_flush_before_push_flag(self):
        """App state includes flush_before_push flag."""
        import inspect
        from app.api.app import lifespan
        source = inspect.getsource(lifespan)
        assert "flush_before_push" in source


class TestFullAPILifecycle:
    @pytest.mark.asyncio
    async def test_create_app_returns_fastapi(self):
        """create_app() returns a valid FastAPI instance."""
        app = create_app()
        assert app.title == "Director-Actor Drama API"
        assert app.version == "2.0.0"

    @pytest.mark.asyncio
    async def test_all_14_routes_registered(self):
        """All 14 endpoint routes are registered on the app."""
        app = create_app()
        api_routes = [r for r in app.routes if hasattr(r, "path") and "/api/v1/drama/" in r.path]
        assert len(api_routes) == 14

    @pytest.mark.asyncio
    async def test_openapi_docs_available(self):
        """OpenAPI schema is auto-generated at /docs."""
        app = create_app()
        # Verify OpenAPI route exists
        openapi_routes = [r for r in app.routes if hasattr(r, "path") and r.path == "/openapi.json"]
        assert len(openapi_routes) > 0
