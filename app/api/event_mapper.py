"""Event mapper: ADK Runner events → 18 business event types for WebSocket push.

D-04: Uses function_call.name as primary mapping key.
D-05: Mapping rules for each tool name → event type(s).
D-06: Extra handling for tension_update, typing, cast_update, end_narration, error.
D-07: One function_call may map to multiple business events.
DEBUG: All STORM lifecycle events now also emit 'director_log' with rich detail.
"""

import logging
import time
from google.adk.events import Event

from app.api.models import WsEvent

logger = logging.getLogger(__name__)

# D-05: Primary mapping table — function_call.name → list of business event types
TOOL_EVENT_MAP: dict[str, list[str]] = {
    "start_drama": ["scene_start", "status"],       # D-07: one-to-many
    "next_scene": ["scene_start"],
    "director_narrate": ["narration"],
    "actor_speak": ["dialogue", "actor_chime_in"],   # CHAT-07: chime_in when actor speaks
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

# DEBUG: Tools whose function_call/function_response should emit rich 'director_log' events.
# These are the long-running tools where Android users need visibility into backend progress.
DIRECTOR_LOG_TOOLS = {
    "start_drama", "storm_discover_perspectives", "storm_research_perspective",
    "storm_synthesize_outline", "create_actor", "next_scene", "write_scene",
    "actor_speak", "user_action", "director_narrate",
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
    elif event_type == "actor_chime_in":
        return {"actor_name": args.get("actor_name", ""), "tool": function_call.name}
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
    """Extract tension score from response if present (D-06).

    Returns None only when neither 'tension_score' nor 'tension' key exists.
    A value of 0 is valid and should be emitted as a tension_update.
    """
    if "tension_score" in response:
        return response["tension_score"]
    if "tension" in response:
        return response["tension"]
    return None


def _build_director_log_call(fn_name: str, args: dict) -> str:
    """Build a human-readable director log message for function_call arrival.

    Returns the message string, or empty string if nothing useful to report.
    """
    match fn_name:
        case "start_drama":
            theme = args.get("theme", "")
            return f"🎬 开始创作剧本「{theme}」"
        case "storm_discover_perspectives":
            return "🔍 正在发现叙事视角..."
        case "storm_research_perspective":
            perspective = args.get("perspective_name", args.get("name", ""))
            return f"📚 研究视角: {perspective or '(未知)'}"
        case "storm_synthesize_outline":
            return "✍️ 正在合成故事大纲..."
        case "create_actor":
            name = args.get("actor_name", args.get("name", ""))
            role = args.get("role", "")
            desc = f"({role})" if role else ""
            return f"🎭 创建角色: {name or '(未知)'} {desc}"
        case "next_scene":
            return "🎬 推进到下一场..."
        case "write_scene":
            scene = args.get("scene_number", "?")
            title = args.get("title", "")
            return f"📝 写入第{scene}场: {title}"
        case "actor_speak":
            actor = args.get("actor_name", "")
            situation = args.get("situation", "")[:40]
            return f"💬 {actor} 说话: {situation}"
        case "user_action":
            desc = args.get("description", "")[:60]
            return f"👤 用户行动: {desc}"
        case "director_narrate":
            content = args.get("content", "")[:50]
            return f"🎬 导演旁白: {content}"
        case _:
            return f"⚙️ 执行 {fn_name}"


def _build_director_log_response(fn_name: str, response: dict) -> str:
    """Build a human-readable director log message for function_response.

    Returns the message string, or empty string if nothing useful to report.
    """
    status_val = response.get("status", "ok")
    msg = response.get("message", "")

    match fn_name:
        case "start_drama":
            theme = response.get("theme", "")
            folder = response.get("drama_folder", "")
            return f"✅ 剧本初始化完成「{theme}」→ {folder}"
        case "storm_discover_perspectives":
            count = len(response.get("perspectives", []))
            return f"✅ 发现了 {count} 个叙事视角"
        case "storm_research_perspective":
            perspective = response.get("perspective_name", "")
            return f"✅ 「{perspective}」研究完成"
        case "storm_synthesize_outline":
            acts = response.get("num_acts", response.get("acts_count", "?"))
            status_text = " (状态切换为 acting)" if response.get("new_status") == "acting" else ""
            return f"✅ 大纲合成完成 ({acts} 幕){status_text}"
        case "create_actor":
            name = response.get("actor_name", "")
            port = response.get("a2a_port", "")
            port_info = f" [端口:{port}]" if port else ""
            return f"✅ 角色「{name}」就绪{port_info}"
        case "next_scene":
            scene = response.get("scene_number", "?")
            title = response.get("title", "")
            return f"✅ 第{scene}场开始: {title}"
        case "write_scene":
            scene = response.get("scene_number", "?")
            tension = response.get("tension_score")
            tension_str = f" 张力:{tension}" if tension is not None else ""
            return f"✅ 第{scene}场写入完成{tension_str}"
        case _:
            if status_val == "error":
                return f"❌ {fn_name} 失败: {(msg or '')[:80]}"
            preview = (msg or "")[:80]
            return f"✅ {fn_name} 完成: {preview}" if preview else ""


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
        # Handle function_call → typing + mapped events + director_log
        if part.function_call:
            fn_name = part.function_call.name
            # D-06: function_call arrival = typing indicator
            results.append({"type": "typing", "data": {"tool": fn_name}})

            # DEBUG: Emit rich director_log for STORM/long-running tools
            if fn_name in DIRECTOR_LOG_TOOLS:
                args = dict(part.function_call.args) if part.function_call.args else {}
                log_msg = _build_director_log_call(fn_name, args)
                if log_msg:
                    results.append({
                        "type": "director_log",
                        "data": {
                            "message": log_msg,
                            "tool": fn_name,
                            "phase": "call",
                            "timestamp": time.strftime("%H:%M:%S"),
                        },
                    })

            # D-05: Map function_call.name to business events
            if fn_name in TOOL_EVENT_MAP:
                for event_type in TOOL_EVENT_MAP[fn_name]:
                    results.append({
                        "type": event_type,
                        "data": _extract_call_data(event_type, part.function_call),
                    })

        # Handle function_response → conditional events + response data + director_log
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

            # DEBUG: Emit rich director_log for tool completion
            if fn_name in DIRECTOR_LOG_TOOLS:
                log_msg = _build_director_log_response(fn_name, resp)
                if log_msg:
                    results.append({
                        "type": "director_log",
                        "data": {
                            "message": log_msg,
                            "tool": fn_name,
                            "phase": "done",
                            "status": resp.get("status", "ok"),
                            "timestamp": time.strftime("%H:%M:%S"),
                        },
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
