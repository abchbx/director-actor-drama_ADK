"""Event mapper: ADK Runner events → 18 business event types for WebSocket push.

D-04: Uses function_call.name as primary mapping key.
D-05: Mapping rules for each tool name → event type(s).
D-06: Extra handling for tension_update, typing, cast_update, end_narration, error.
D-07: One function_call may map to multiple business events.
"""

from google.adk.events import Event

from app.api.models import WsEvent

# D-05: Primary mapping table — function_call.name → list of business event types
TOOL_EVENT_MAP: dict[str, list[str]] = {
    "start_drama": ["scene_start", "status"],       # D-07: one-to-many
    "next_scene": ["scene_start"],
    "director_narrate": ["narration"],
    "actor_speak": ["dialogue"],
    "write_scene": ["scene_end"],
    "update_emotion": ["actor_status"],
    "create_actor": ["actor_created", "cast_update"],  # D-06: cast_update
    "storm_discover_perspectives": ["storm_discover"],
    "storm_research_perspective": ["storm_research"],
    "storm_synthesize_outline": ["storm_outline"],
    "save_drama": ["save_confirm"],
    "load_drama": ["load_confirm"],
    "export_drama": ["progress"],
    "end_drama": ["end_narration"],
}


def _extract_call_data(event_type: str, function_call) -> dict:
    """Extract relevant data from function_call for the given event type."""
    args = dict(function_call.args) if function_call.args else {}
    if event_type == "scene_start":
        return {"tool": function_call.name}
    elif event_type == "status":
        return {"tool": function_call.name}
    elif event_type == "narration":
        return {"tool": function_call.name}
    elif event_type == "dialogue":
        return {"actor_name": args.get("actor_name", ""), "tool": function_call.name}
    elif event_type == "actor_created":
        return {"actor_name": args.get("actor_name", ""), "tool": function_call.name}
    elif event_type == "cast_update":
        return {"tool": function_call.name}
    else:
        return {"tool": function_call.name}


def _extract_response_data(event_type: str, response: dict) -> dict:
    """Extract relevant data from function_response for the given event type."""
    if event_type == "scene_end":
        return {
            "scene_number": response.get("scene_number"),
            "scene_title": response.get("scene_title", ""),
        }
    elif event_type == "actor_status":
        return {
            "actor_name": response.get("actor_name", ""),
            "emotion": response.get("emotion", ""),
        }
    elif event_type == "save_confirm":
        return {"message": response.get("message", "")}
    elif event_type == "load_confirm":
        return {"message": response.get("message", ""), "theme": response.get("theme", "")}
    elif event_type == "progress":
        return {"message": response.get("message", ""), "export_path": response.get("export_path", "")}
    elif event_type == "end_narration":
        return {"text": response.get("formatted_narration", response.get("message", ""))}
    else:
        return {}


def _extract_tension(response: dict) -> int | None:
    """Extract tension score from response if present (D-06)."""
    return response.get("tension_score") or response.get("tension")


def map_runner_event(event: Event) -> list[dict]:
    """Map an ADK Runner Event to 0~N business events.

    D-07: One function_call can map to multiple business events.
    D-06: Additional conditional events detected from response data.

    Args:
        event: An ADK Event from runner.run_async().

    Returns:
        List of dicts, each suitable for WsEvent or direct JSON broadcast.
    """
    results: list[dict] = []

    if not event.content or not event.content.parts:
        return results

    for part in event.content.parts:
        # Handle function_call → typing + mapped events
        if part.function_call:
            fn_name = part.function_call.name
            # D-06: function_call arrival = typing indicator
            results.append({"type": "typing", "data": {"tool": fn_name}})
            # D-05: Map function_call.name to business events
            if fn_name in TOOL_EVENT_MAP:
                for event_type in TOOL_EVENT_MAP[fn_name]:
                    results.append({
                        "type": event_type,
                        "data": _extract_call_data(event_type, part.function_call),
                    })

        # Handle function_response → conditional events + response data
        if part.function_response:
            resp = part.function_response.response or {}
            fn_name = part.function_response.name

            # D-06: error detection from status field
            if resp.get("status") == "error":
                results.append({
                    "type": "error",
                    "data": {"tool": fn_name, "message": resp.get("message", "")},
                })

            # D-06: tension_update detection
            if fn_name in ("next_scene", "write_scene"):
                tension = _extract_tension(resp)
                if tension is not None:
                    results.append({
                        "type": "tension_update",
                        "data": {"tension_score": tension},
                    })

            # Emit response data for mapped event types
            if fn_name in TOOL_EVENT_MAP:
                for event_type in TOOL_EVENT_MAP[fn_name]:
                    results.append({
                        "type": event_type,
                        "data": _extract_response_data(event_type, resp),
                    })

    # D-06: end_narration from final_response text (for /end command)
    if event.is_final_response() and event.content and event.content.parts:
        for part in event.content.parts:
            if part.text and part.text.strip():
                results.append({
                    "type": "end_narration",
                    "data": {"text": part.text.strip()},
                })

    return results
