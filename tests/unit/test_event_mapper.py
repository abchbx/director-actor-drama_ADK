"""Tests for event_mapper: ADK Runner events → business event types."""

import pytest
from unittest.mock import Mock

from google.adk.events import Event
from google.genai import types

from app.api.event_mapper import TOOL_EVENT_MAP, map_runner_event


class TestToolEventMap:
    """Test TOOL_EVENT_MAP contains all expected tool name keys (D-05)."""

    EXPECTED_TOOLS = [
        "start_drama",
        "next_scene",
        "director_narrate",
        "actor_speak",
        "write_scene",
        "update_emotion",
        "create_actor",
        "storm_discover_perspectives",
        "storm_research_perspective",
        "storm_synthesize_outline",
        "save_drama",
        "load_drama",
        "export_drama",
        "end_drama",
    ]

    def test_tool_event_map_contains_all_14_tools(self):
        """TOOL_EVENT_MAP has all 14 tool name keys."""
        for tool_name in self.EXPECTED_TOOLS:
            assert tool_name in TOOL_EVENT_MAP, f"Missing tool: {tool_name}"

    def test_tool_event_map_has_14_entries(self):
        """TOOL_EVENT_MAP has exactly 14 entries."""
        assert len(TOOL_EVENT_MAP) == 14

    def test_start_drama_maps_to_two_events(self):
        """start_drama maps to scene_start + status (D-07: one-to-many)."""
        assert TOOL_EVENT_MAP["start_drama"] == ["scene_start", "status"]

    def test_create_actor_maps_to_two_events(self):
        """create_actor maps to actor_created + cast_update (D-06)."""
        assert TOOL_EVENT_MAP["create_actor"] == ["actor_created", "cast_update"]


class TestMapRunnerEvent:
    """Test map_runner_event function with mock ADK events."""

    def test_empty_event_returns_empty_list(self):
        """Event with no content returns empty list."""
        event = Event(author="model")
        assert map_runner_event(event) == []

    def test_event_with_no_parts_returns_empty_list(self):
        """Event with content but no parts returns empty list."""
        event = Event(
            author="model",
            content=types.Content(parts=[], role="model"),
        )
        assert map_runner_event(event) == []

    def test_function_call_emits_typing_event(self):
        """function_call arrival emits typing event (D-06)."""
        event = Event(
            author="model",
            content=types.Content(
                parts=[types.Part.from_function_call(name="next_scene", args={})],
                role="model",
            ),
        )
        results = map_runner_event(event)
        typing_events = [r for r in results if r["type"] == "typing"]
        assert len(typing_events) == 1
        assert typing_events[0]["data"]["tool"] == "next_scene"

    def test_start_drama_emits_typing_and_scene_start_and_status(self):
        """start_drama function_call emits typing + scene_start + status (D-07)."""
        event = Event(
            author="model",
            content=types.Content(
                parts=[types.Part.from_function_call(name="start_drama", args={"theme": "test"})],
                role="model",
            ),
        )
        results = map_runner_event(event)
        event_types = [r["type"] for r in results]
        assert "typing" in event_types
        assert "scene_start" in event_types
        assert "status" in event_types
        assert len(results) == 3  # typing + scene_start + status

    def test_next_scene_function_call_emits_typing_and_scene_start(self):
        """next_scene function_call emits typing + scene_start."""
        event = Event(
            author="model",
            content=types.Content(
                parts=[types.Part.from_function_call(name="next_scene", args={})],
                role="model",
            ),
        )
        results = map_runner_event(event)
        event_types = [r["type"] for r in results]
        assert "typing" in event_types
        assert "scene_start" in event_types
        assert len(results) == 2  # typing + scene_start

    def test_function_response_with_error_emits_error_event(self):
        """function_response with status='error' emits error event (D-06)."""
        event = Event(
            author="model",
            content=types.Content(
                parts=[
                    types.Part.from_function_response(
                        name="next_scene",
                        response={"status": "error", "message": "Something went wrong"},
                    )
                ],
                role="model",
            ),
        )
        results = map_runner_event(event)
        error_events = [r for r in results if r["type"] == "error"]
        assert len(error_events) == 1
        assert error_events[0]["data"]["tool"] == "next_scene"
        assert error_events[0]["data"]["message"] == "Something went wrong"

    def test_function_response_with_tension_emits_tension_update(self):
        """next_scene response with tension_score emits tension_update (D-06)."""
        event = Event(
            author="model",
            content=types.Content(
                parts=[
                    types.Part.from_function_response(
                        name="next_scene",
                        response={"status": "success", "tension_score": 7},
                    )
                ],
                role="model",
            ),
        )
        results = map_runner_event(event)
        tension_events = [r for r in results if r["type"] == "tension_update"]
        assert len(tension_events) == 1
        assert tension_events[0]["data"]["tension_score"] == 7

    def test_function_response_with_tension_key_emits_tension_update(self):
        """Response with 'tension' key (not 'tension_score') also emits tension_update."""
        event = Event(
            author="model",
            content=types.Content(
                parts=[
                    types.Part.from_function_response(
                        name="write_scene",
                        response={"status": "success", "tension": 5},
                    )
                ],
                role="model",
            ),
        )
        results = map_runner_event(event)
        tension_events = [r for r in results if r["type"] == "tension_update"]
        assert len(tension_events) == 1
        assert tension_events[0]["data"]["tension_score"] == 5

    def test_final_response_emits_end_narration(self):
        """Final response with text emits end_narration (D-06)."""
        event = Event(
            author="model",
            turn_complete=True,
            content=types.Content(
                parts=[types.Part.from_text(text="The drama concludes.")],
                role="model",
            ),
        )
        results = map_runner_event(event)
        narration_events = [r for r in results if r["type"] == "end_narration"]
        assert len(narration_events) == 1
        assert narration_events[0]["data"]["text"] == "The drama concludes."

    def test_create_actor_emits_typing_actor_created_cast_update(self):
        """create_actor function_call emits typing + actor_created + cast_update."""
        event = Event(
            author="model",
            content=types.Content(
                parts=[
                    types.Part.from_function_call(
                        name="create_actor",
                        args={"actor_name": "Alice"},
                    )
                ],
                role="model",
            ),
        )
        results = map_runner_event(event)
        event_types = [r["type"] for r in results]
        assert "typing" in event_types
        assert "actor_created" in event_types
        assert "cast_update" in event_types
        # Verify actor_name is extracted for actor_created
        actor_created_events = [r for r in results if r["type"] == "actor_created"]
        assert actor_created_events[0]["data"]["actor_name"] == "Alice"

    def test_non_mapped_function_call_emits_only_typing(self):
        """Unknown function_call emits only typing, no mapped events."""
        event = Event(
            author="model",
            content=types.Content(
                parts=[types.Part.from_function_call(name="unknown_tool", args={})],
                role="model",
            ),
        )
        results = map_runner_event(event)
        assert len(results) == 1
        assert results[0]["type"] == "typing"

    def test_function_response_for_mapped_tool_emits_response_data(self):
        """function_response for a mapped tool emits events with response data."""
        event = Event(
            author="model",
            content=types.Content(
                parts=[
                    types.Part.from_function_response(
                        name="write_scene",
                        response={
                            "status": "success",
                            "scene_number": 3,
                            "scene_title": "The Confrontation",
                        },
                    )
                ],
                role="model",
            ),
        )
        results = map_runner_event(event)
        scene_end_events = [r for r in results if r["type"] == "scene_end"]
        assert len(scene_end_events) == 1
        assert scene_end_events[0]["data"]["scene_number"] == 3
        assert scene_end_events[0]["data"]["scene_title"] == "The Confrontation"

    def test_next_scene_response_with_tension_emits_tension_and_scene_start(self):
        """next_scene response with tension emits both tension_update and scene_start."""
        event = Event(
            author="model",
            content=types.Content(
                parts=[
                    types.Part.from_function_response(
                        name="next_scene",
                        response={"status": "success", "tension_score": 8},
                    )
                ],
                role="model",
            ),
        )
        results = map_runner_event(event)
        event_types = [r["type"] for r in results]
        assert "tension_update" in event_types
        assert "scene_start" in event_types

    def test_update_emotion_response_emits_actor_status(self):
        """update_emotion response emits actor_status with emotion data."""
        event = Event(
            author="model",
            content=types.Content(
                parts=[
                    types.Part.from_function_response(
                        name="update_emotion",
                        response={"status": "success", "actor_name": "Bob", "emotion": "angry"},
                    )
                ],
                role="model",
            ),
        )
        results = map_runner_event(event)
        status_events = [r for r in results if r["type"] == "actor_status"]
        assert len(status_events) == 1
        assert status_events[0]["data"]["actor_name"] == "Bob"
        assert status_events[0]["data"]["emotion"] == "angry"

    def test_save_drama_response_emits_save_confirm(self):
        """save_drama response emits save_confirm with message."""
        event = Event(
            author="model",
            content=types.Content(
                parts=[
                    types.Part.from_function_response(
                        name="save_drama",
                        response={"status": "success", "message": "Saved!"},
                    )
                ],
                role="model",
            ),
        )
        results = map_runner_event(event)
        confirm_events = [r for r in results if r["type"] == "save_confirm"]
        assert len(confirm_events) == 1
        assert confirm_events[0]["data"]["message"] == "Saved!"

    def test_load_drama_response_emits_load_confirm(self):
        """load_drama response emits load_confirm with message and theme."""
        event = Event(
            author="model",
            content=types.Content(
                parts=[
                    types.Part.from_function_response(
                        name="load_drama",
                        response={"status": "success", "message": "Loaded!", "theme": "mystery"},
                    )
                ],
                role="model",
            ),
        )
        results = map_runner_event(event)
        confirm_events = [r for r in results if r["type"] == "load_confirm"]
        assert len(confirm_events) == 1
        assert confirm_events[0]["data"]["message"] == "Loaded!"
        assert confirm_events[0]["data"]["theme"] == "mystery"

    def test_export_drama_response_emits_progress(self):
        """export_drama response emits progress with message and export_path."""
        event = Event(
            author="model",
            content=types.Content(
                parts=[
                    types.Part.from_function_response(
                        name="export_drama",
                        response={"status": "success", "message": "Exported!", "export_path": "/tmp/drama.md"},
                    )
                ],
                role="model",
            ),
        )
        results = map_runner_event(event)
        progress_events = [r for r in results if r["type"] == "progress"]
        assert len(progress_events) == 1
        assert progress_events[0]["data"]["message"] == "Exported!"
        assert progress_events[0]["data"]["export_path"] == "/tmp/drama.md"

    def test_end_drama_response_emits_end_narration(self):
        """end_drama function_response emits end_narration with formatted_narration."""
        event = Event(
            author="model",
            content=types.Content(
                parts=[
                    types.Part.from_function_response(
                        name="end_drama",
                        response={"status": "success", "formatted_narration": "Thus it ends."},
                    )
                ],
                role="model",
            ),
        )
        results = map_runner_event(event)
        narration_events = [r for r in results if r["type"] == "end_narration"]
        assert len(narration_events) == 1
        assert narration_events[0]["data"]["text"] == "Thus it ends."

    def test_multiple_events_from_one_function_call(self):
        """One function_call can produce multiple events (D-07: one-to-many)."""
        event = Event(
            author="model",
            content=types.Content(
                parts=[types.Part.from_function_call(name="start_drama", args={"theme": "test"})],
                role="model",
            ),
        )
        results = map_runner_event(event)
        # start_drama → typing + scene_start + status = 3 events
        assert len(results) == 3

    def test_no_tension_update_when_not_present(self):
        """No tension_update event when tension fields are absent."""
        event = Event(
            author="model",
            content=types.Content(
                parts=[
                    types.Part.from_function_response(
                        name="next_scene",
                        response={"status": "success"},
                    )
                ],
                role="model",
            ),
        )
        results = map_runner_event(event)
        tension_events = [r for r in results if r["type"] == "tension_update"]
        assert len(tension_events) == 0
