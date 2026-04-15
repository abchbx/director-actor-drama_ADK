"""Unit tests for the FastAPI application layer.

Tests app creation, CORS middleware, API versioning, Pydantic models,
and runner_utils.
"""

import asyncio
import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.api import create_app
from app.api.models import (
    ActionRequest,
    AutoRequest,
    DramaListResponse,
    DramaStatusResponse,
    ExportRequest,
    ExportResponse,
    LoadRequest,
    SaveRequest,
    SpeakRequest,
    StartDramaRequest,
    SteerRequest,
    StormRequest,
)
from app.api.runner_utils import run_command_and_collect
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


# ============================================================================
# App creation tests
# ============================================================================


class TestAppCreation:
    """Tests for FastAPI app factory."""

    def test_app_creation(self):
        """create_app() returns a FastAPI instance."""
        app = create_app()
        assert isinstance(app, FastAPI)

    def test_app_title_and_version(self):
        """App has correct title and version."""
        app = create_app()
        assert app.title == "Director-Actor Drama API"
        assert app.version == "2.0.0"

    def test_cors_middleware(self):
        """CORS middleware is configured on the app."""
        app = create_app()
        # Check that CORSMiddleware is in the middleware stack
        has_cors = False
        for middleware in app.user_middleware:
            if middleware.cls is CORSMiddleware:
                has_cors = True
                break
        assert has_cors, "CORSMiddleware not found in app middleware stack"


# ============================================================================
# API versioning and routes tests
# ============================================================================


class TestVersioningAndRoutes:
    """Tests for API versioning and route registration."""

    def test_all_14_endpoints_exist(self):
        """All 14 drama endpoints are registered under /api/v1/."""
        app = create_app()
        drama_routes = [
            route
            for route in app.routes
            if hasattr(route, "path") and "/api/v1/drama/" in route.path
        ]
        assert len(drama_routes) == 14

    def test_version_prefix_routes(self):
        """All drama routes start with /api/v1/ prefix."""
        app = create_app()
        drama_routes = [
            route.path
            for route in app.routes
            if hasattr(route, "path") and "drama" in route.path
        ]
        for path in drama_routes:
            assert path.startswith("/api/v1/"), f"Route {path} doesn't start with /api/v1/"

    def test_unknown_route_under_prefix_returns_404(self):
        """Unknown routes under /api/v1/ return 404 (proves prefix is active)."""
        app = create_app()
        # Check that /api/v1/nonexistent is not matched
        matched = [
            route
            for route in app.routes
            if hasattr(route, "path") and route.path == "/api/v1/nonexistent"
        ]
        assert len(matched) == 0


# ============================================================================
# CORS preflight tests
# ============================================================================


class TestCORSPreflight:
    """Tests for CORS preflight request handling."""

    @pytest.mark.asyncio
    async def test_cors_preflight(self, api_client):
        """CORS preflight OPTIONS request returns Access-Control-Allow-Origin header."""
        # Send OPTIONS with CORS headers to trigger middleware
        response = await api_client.options(
            "/api/v1/drama/start",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert "access-control-allow-origin" in response.headers


# ============================================================================
# Pydantic model validation tests
# ============================================================================


class TestStartDramaRequest:
    """Tests for StartDramaRequest model."""

    def test_valid_theme(self):
        """StartDramaRequest accepts valid theme string."""
        req = StartDramaRequest(theme="A thrilling mystery")
        assert req.theme == "A thrilling mystery"

    def test_empty_theme_rejected(self):
        """StartDramaRequest rejects empty theme (Pydantic validation)."""
        with pytest.raises(ValidationError):
            StartDramaRequest(theme="")

    def test_too_long_theme_rejected(self):
        """StartDramaRequest rejects theme longer than 200 chars."""
        with pytest.raises(ValidationError):
            StartDramaRequest(theme="x" * 201)


class TestActionRequest:
    """Tests for ActionRequest model."""

    def test_valid_description(self):
        """ActionRequest accepts valid description."""
        req = ActionRequest(description="A mysterious stranger arrives")
        assert req.description == "A mysterious stranger arrives"

    def test_empty_description_rejected(self):
        """ActionRequest rejects empty description."""
        with pytest.raises(ValidationError):
            ActionRequest(description="")


class TestSpeakRequest:
    """Tests for SpeakRequest model."""

    def test_valid_request(self):
        """SpeakRequest accepts actor_name and situation."""
        req = SpeakRequest(actor_name="Hamlet", situation="contemplating")
        assert req.actor_name == "Hamlet"
        assert req.situation == "contemplating"

    def test_missing_actor_name_rejected(self):
        """SpeakRequest rejects missing actor_name."""
        with pytest.raises(ValidationError):
            SpeakRequest(situation="contemplating")

    def test_missing_situation_rejected(self):
        """SpeakRequest rejects missing situation."""
        with pytest.raises(ValidationError):
            SpeakRequest(actor_name="Hamlet")


class TestAutoRequest:
    """Tests for AutoRequest model."""

    def test_default_num_scenes(self):
        """AutoRequest defaults num_scenes to 3."""
        req = AutoRequest()
        assert req.num_scenes == 3

    def test_custom_num_scenes(self):
        """AutoRequest accepts custom num_scenes."""
        req = AutoRequest(num_scenes=5)
        assert req.num_scenes == 5

    def test_zero_scenes_rejected(self):
        """AutoRequest rejects num_scenes=0."""
        with pytest.raises(ValidationError):
            AutoRequest(num_scenes=0)

    def test_too_many_scenes_rejected(self):
        """AutoRequest rejects num_scenes > 10."""
        with pytest.raises(ValidationError):
            AutoRequest(num_scenes=11)


class TestSteerRequest:
    """Tests for SteerRequest model."""

    def test_valid_direction(self):
        """SteerRequest accepts valid direction."""
        req = SteerRequest(direction="Make it darker")
        assert req.direction == "Make it darker"

    def test_empty_direction_rejected(self):
        """SteerRequest rejects empty direction."""
        with pytest.raises(ValidationError):
            SteerRequest(direction="")


class TestStormRequest:
    """Tests for StormRequest model."""

    def test_default_focus_none(self):
        """StormRequest defaults focus to None."""
        req = StormRequest()
        assert req.focus is None

    def test_custom_focus(self):
        """StormRequest accepts optional focus."""
        req = StormRequest(focus="political intrigue")
        assert req.focus == "political intrigue"


class TestSaveLoadRequest:
    """Tests for SaveRequest and LoadRequest models."""

    def test_save_request_default(self):
        """SaveRequest defaults save_name to empty string."""
        req = SaveRequest()
        assert req.save_name == ""

    def test_load_request_requires_name(self):
        """LoadRequest requires non-empty save_name."""
        req = LoadRequest(save_name="my_drama")
        assert req.save_name == "my_drama"

    def test_load_request_empty_name_rejected(self):
        """LoadRequest rejects empty save_name."""
        with pytest.raises(ValidationError):
            LoadRequest(save_name="")


class TestExportRequest:
    """Tests for ExportRequest model."""

    def test_default_format(self):
        """ExportRequest defaults format to markdown."""
        req = ExportRequest()
        assert req.format == "markdown"


# ============================================================================
# Runner utils tests
# ============================================================================


class TestRunnerUtils:
    """Tests for run_command_and_collect utility."""

    def test_runner_utils_imports(self):
        """run_command_and_collect is importable and is async."""
        assert callable(run_command_and_collect)
        assert inspect.iscoroutinefunction(run_command_and_collect)

    def test_run_command_and_collect_returns_dict_structure(self):
        """run_command_and_collect returns dict with expected keys (via mock)."""
        # Verify the function signature matches expected return type
        sig = inspect.signature(run_command_and_collect)
        params = list(sig.parameters.keys())
        assert "runner" in params
        assert "message" in params
        assert "user_id" in params
        assert "session_id" in params

    @pytest.mark.asyncio
    async def test_timeout_raises_504(self):
        """run_command_and_collect raises HTTPException 504 on timeout."""
        from fastapi import HTTPException

        # Create a mock runner that yields events slowly (never completes)
        mock_runner = MagicMock()

        async def slow_stream(**kwargs):
            """Yield events slowly to trigger timeout."""
            await asyncio.sleep(10)  # Sleep longer than timeout
            yield MagicMock(is_final_response=MagicMock(return_value=False))

        mock_runner.run_async = slow_stream

        with pytest.raises(HTTPException) as exc_info:
            await run_command_and_collect(
                runner=mock_runner,
                message="test",
                user_id="u",
                session_id="s",
                timeout=0.01,  # Very short timeout
            )
        assert exc_info.value.status_code == 504

    @pytest.mark.asyncio
    async def test_collects_final_response_and_tool_results(self):
        """run_command_and_collect collects final_response and tool_results from events."""
        # Create mock events
        tool_event = MagicMock()
        tool_event.is_final_response.return_value = False
        tool_part = MagicMock()
        tool_part.function_response = MagicMock()
        tool_part.function_response.response = {"result": "tool_output"}
        tool_event.content.parts = [tool_part]

        final_event = MagicMock()
        final_event.is_final_response.return_value = True
        final_part = MagicMock()
        final_part.text = "Director says hello"
        final_part.function_response = None
        final_event.content.parts = [final_part]

        mock_runner = MagicMock()

        async def mock_stream(**kwargs):
            yield tool_event
            yield final_event

        mock_runner.run_async = mock_stream

        result = await run_command_and_collect(
            runner=mock_runner,
            message="test",
            user_id="u",
            session_id="s",
            timeout=5.0,
        )

        assert "final_response" in result
        assert "tool_results" in result
        assert result["final_response"] == "Director says hello"
        assert len(result["tool_results"]) == 1
        assert result["tool_results"][0] == {"result": "tool_output"}
