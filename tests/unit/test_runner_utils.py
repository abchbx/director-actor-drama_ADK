"""Tests for runner_utils: event_callback parameter in run_command_and_collect."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.runner_utils import run_command_and_collect


class TestEventCallback:
    """Test event_callback parameter in run_command_and_collect (D-01)."""

    @pytest.mark.asyncio
    async def test_event_callback_none_works_as_before(self):
        """run_command_and_collect with event_callback=None works exactly as before (REST path unchanged)."""
        # Create mock runner that yields events
        mock_event_final = MagicMock()
        mock_event_final.is_final_response.return_value = True
        mock_event_final.content = MagicMock()
        mock_event_final.content.parts = [MagicMock(text="Director response")]

        mock_runner = MagicMock()
        mock_runner.run_async = MagicMock(return_value=self._async_generator([mock_event_final]))

        result = await run_command_and_collect(
            runner=mock_runner,
            message="/start test",
            user_id="test_user",
            session_id="test_session",
            event_callback=None,
        )
        assert result["final_response"] == "Director response"

    @pytest.mark.asyncio
    async def test_event_callback_is_called_for_each_event(self):
        """run_command_and_collect with event_callback calls the callback for each event."""
        mock_event1 = MagicMock()
        mock_event1.is_final_response.return_value = False
        mock_event1.content = MagicMock()
        mock_event1.content.parts = [MagicMock(function_response=MagicMock(response={"status": "success"}))]

        mock_event2 = MagicMock()
        mock_event2.is_final_response.return_value = True
        mock_event2.content = MagicMock()
        mock_event2.content.parts = [MagicMock(text="Final response")]

        mock_runner = MagicMock()
        mock_runner.run_async = MagicMock(return_value=self._async_generator([mock_event1, mock_event2]))

        callback = AsyncMock()
        result = await run_command_and_collect(
            runner=mock_runner,
            message="/start test",
            user_id="test_user",
            session_id="test_session",
            event_callback=callback,
        )

        # Callback should be called once for each event
        assert callback.call_count == 2
        callback.assert_any_call(mock_event1)
        callback.assert_any_call(mock_event2)
        # Result should still be correct
        assert result["final_response"] == "Final response"

    @pytest.mark.asyncio
    async def test_event_callback_exception_does_not_block_runner(self):
        """Callback failure must NOT block Runner execution."""
        mock_event1 = MagicMock()
        mock_event1.is_final_response.return_value = False
        mock_event1.content = MagicMock()
        mock_event1.content.parts = [MagicMock(function_response=MagicMock(response={"status": "ok"}))]

        mock_event2 = MagicMock()
        mock_event2.is_final_response.return_value = True
        mock_event2.content = MagicMock()
        mock_event2.content.parts = [MagicMock(text="Still works")]

        mock_runner = MagicMock()
        mock_runner.run_async = MagicMock(return_value=self._async_generator([mock_event1, mock_event2]))

        # Callback that raises on first call
        callback = AsyncMock(side_effect=[Exception("boom"), None])

        result = await run_command_and_collect(
            runner=mock_runner,
            message="/start test",
            user_id="test_user",
            session_id="test_session",
            event_callback=callback,
        )

        # Runner should still complete despite callback exception
        assert result["final_response"] == "Still works"

    @pytest.mark.asyncio
    async def test_default_event_callback_is_none(self):
        """event_callback defaults to None, so existing calls work unchanged."""
        import inspect
        sig = inspect.signature(run_command_and_collect)
        assert sig.parameters["event_callback"].default is None

    async def _async_generator(self, events):
        """Helper to create an async generator from a list of events."""
        for event in events:
            yield event
