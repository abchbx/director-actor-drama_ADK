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
    "start_drama": ["scene_start", "status", "command_echo"],       # ★ command_echo 回显用户指令
    "next_scene": ["scene_start", "command_echo"],
    "director_narrate": ["narration"],
    "actor_speak": ["dialogue"],                        # ★ 对话事件 — 只映射 dialogue，chime_in 由独立工具触发
    "actor_speak_batch": ["dialogue"],                  # ★ 批量对话 — 映射到 dialogue，results 列表中每个演员一条
    "actor_chime_in": ["actor_chime_in"],               # ★ 自发插话事件 — 独立映射，携带所有插话结果
    "user_action": ["command_echo"],  # ★ 用户行动仅回显命令，气泡由客户端本地创建
    "write_scene": ["scene_end"],
    "update_emotion": ["actor_status"],
    "create_actor": ["actor_created", "cast_update"],  # D-06: cast_update
    "storm_discover_perspectives": ["storm_discover"],
    "storm_research_perspective": ["storm_research"],
    "storm_synthesize_outline": ["storm_outline"],
    "save_drama": ["save_confirm", "command_echo"],
    "load_drama": ["load_confirm", "command_echo"],
    "export_drama": ["progress", "command_echo"],
    "end_drama": ["end_narration", "command_echo"],
    "steer_drama": ["command_echo"],                    # ★ steer 也回显
    "auto_advance": ["command_echo"],                   # ★ auto 也回显
    # ★ 语义检索 & Dynamic STORM — 前端需要详细进度透出
    "retrieve_relevant_scenes_tool": ["command_echo"],  # ★ 语义检索 — typing + director_log 驱动进度
    "backfill_tags_tool": ["command_echo"],             # ★ 标签回填 — 同上
    "dynamic_storm": ["storm_discover"],               # ★ 动态STORM — 映射到 storm_discover 推送进度
}

# DEBUG: Tools whose function_call/function_response should emit rich 'director_log' events.
# These are the long-running tools where Android users need visibility into backend progress.
DIRECTOR_LOG_TOOLS = {
    "start_drama", "storm_discover_perspectives", "storm_research_perspective",
    "storm_synthesize_outline", "create_actor", "next_scene", "write_scene",
    "actor_speak", "actor_speak_batch", "actor_chime_in", "user_action", "director_narrate",
    # ★ 语义检索 & Dynamic STORM — 长耗时工具，Android 需要详细进度透出
    "retrieve_relevant_scenes_tool", "backfill_tags_tool", "dynamic_storm",
}


def _extract_call_data(event_type: str, function_call) -> dict:
    """Extract relevant data from function_call for the given event type."""
    args = dict(function_call.args) if function_call.args else {}
    if event_type == "scene_start":
        return {"tool": function_call.name, "sender_type": "director", "sender_name": "旁白"}
    elif event_type == "status":
        return {"tool": function_call.name, "sender_type": "director", "sender_name": "旁白"}
    elif event_type == "narration":
        content = args.get("content", args.get("text", args.get("narration", "")))
        return {"tool": function_call.name, "text": content, "sender_type": "director", "sender_name": "旁白"}
    elif event_type == "dialogue":
        return {
            "actor_name": args.get("actor_name", ""),
            "tool": function_call.name,
            "situation": args.get("situation", ""),
            "sender_type": "actor",
            "sender_name": args.get("actor_name", ""),
        }
    elif event_type == "actor_created":
        return {"actor_name": args.get("actor_name", ""), "tool": function_call.name, "sender_type": "director", "sender_name": "旁白"}
    elif event_type == "cast_update":
        return {"tool": function_call.name, "sender_type": "director", "sender_name": "旁白"}
    elif event_type == "actor_chime_in":
        # ★ chime_in call 阶段：返回触发上下文（typing 指示用）
        return {
            "tool": function_call.name,
            "trigger_context": args.get("trigger_context", ""),
            "speaking_actor": args.get("speaking_actor", ""),
            "sender_type": "director",
            "sender_name": "旁白",
        }
    elif event_type == "command_echo":
        return {
            "tool": function_call.name,
            "command": _format_command_echo(function_call.name, args),
            "args": {k: str(v)[:100] for k, v in args.items()},
            "sender_type": "user",
            "sender_name": "用户",
        }
    elif event_type == "user_action_echo":
        # ★ 用户行动事件 — 以用户身份在聊天中展示
        desc = args.get("description", args.get("action", ""))
        return {
            "text": desc,
            "sender_type": "user",
            "sender_name": "用户",
        }
    else:
        return {"tool": function_call.name}


def _extract_response_data(event_type: str, response: dict) -> dict:
    """Extract relevant data from function_response for the given event type.

    ★ 核心修复：dialogue 和 narration 事件必须在 response 阶段携带完整文本，
    前端依赖这些数据创建对话/旁白气泡。call 阶段只有元数据（typing 指示），
    response 阶段才有 LLM 生成的完整内容。
    """
    if event_type == "scene_end":
        return {
            "scene_number": response.get("scene_number"),
            "scene_title": response.get("scene_title", ""),
            "sender_type": "director",
            "sender_name": "旁白",
        }
    elif event_type == "actor_status":
        return {
            "actor_name": response.get("actor_name", ""),
            "emotion": response.get("emotion", ""),
            "sender_type": "director",
            "sender_name": "旁白",
        }
    elif event_type == "dialogue":
        actor_name = response.get("actor_name", "")
        return {
            "actor_name": actor_name,
            "text": response.get("text", response.get("dialogue", "")),
            "emotion": response.get("emotion", response.get("emotions", "")),
            "sender_type": "actor",
            "sender_name": actor_name,
        }
    elif event_type == "actor_chime_in":
        # ★ chime_in response 阶段：携带所有插话演员的完整对话
        # response 包含 chime_ins 列表，每项有 actor_name/dialogue/emotion 等
        chime_ins = response.get("chime_ins", [])
        return {
            "chime_ins": chime_ins,
            "chime_count": response.get("chime_count", len(chime_ins)),
            "trigger_context": response.get("trigger_context", ""),
            "speaking_actor": response.get("speaking_actor", ""),
            "sender_type": "director",
            "sender_name": "旁白",
        }
    elif event_type == "narration":
        return {
            "text": response.get("formatted_narration", response.get("text", response.get("narration", ""))),
            "sender_type": "director",
            "sender_name": "旁白",
        }
    elif event_type == "save_confirm":
        return {"message": response.get("message", ""), "sender_type": "director", "sender_name": "旁白"}
    elif event_type == "user_action_echo":
        # ★ 用户行动事件响应 — 以用户身份展示
        action = response.get("action", "")
        return {
            "text": action,
            "sender_type": "user",
            "sender_name": "用户",
        }
    elif event_type == "load_confirm":
        return {"message": response.get("message", ""), "theme": response.get("theme", ""), "sender_type": "director", "sender_name": "旁白"}
    elif event_type == "progress":
        return {"message": response.get("message", ""), "export_path": response.get("export_path", ""), "sender_type": "director", "sender_name": "旁白"}
    elif event_type == "end_narration":
        return {"text": response.get("formatted_narration", response.get("message", "")), "sender_type": "director", "sender_name": "旁白"}
    elif event_type == "storm_outline":
        outline = response.get("outline", {})
        acts = outline.get("acts", [])
        act_summaries = []
        for act in acts:
            act_summaries.append({
                "act_number": act.get("act_number", 0),
                "title": act.get("title", ""),
                "description": act.get("description", ""),
                "key_conflict": act.get("key_conflict", ""),
                "emotional_arc": act.get("emotional_arc", ""),
            })
        return {
            "theme": response.get("theme", outline.get("theme", "")),
            "message": response.get("message", ""),
            "num_acts": len(acts),
            "acts": act_summaries,
            "core_tensions": outline.get("core_tensions", []),
            "new_status": response.get("new_status", "acting"),
            "sender_type": "director",
            "sender_name": "旁白",
        }
    else:
        return {}


def _format_command_echo(fn_name: str, args: dict) -> str:
    """Format a human-readable command echo string for the frontend.

    ★ 新增：将工具调用转换为可读的用户指令格式，
    前端收到 command_echo 事件后可直接显示。
    """
    match fn_name:
        case "start_drama":
            theme = args.get("theme", "")
            return f"/start {theme}"
        case "next_scene":
            return "/next"
        case "user_action":
            desc = args.get("description", "")[:60]
            return f"/action {desc}"
        case "actor_speak":
            actor = args.get("actor_name", "")
            return f"@{actor}"
        case "actor_chime_in":
            ctx = args.get("trigger_context", "")[:40]
            speaker = args.get("speaking_actor", "")
            return f"🔔 插话触发: {ctx}" + (f" (after {speaker})" if speaker else "")
        case "save_drama":
            name = args.get("save_name", "")
            return f"/save {name}".strip()
        case "load_drama":
            name = args.get("save_name", "")
            return f"/load {name}"
        case "export_drama":
            return "/export"
        case "end_drama":
            return "/end"
        case "steer_drama":
            direction = args.get("direction", "")
            return f"/steer {direction}"
        case "auto_advance":
            n = args.get("num_scenes", "?")
            return f"/auto {n}"
        case "show_cast":
            return "/cast"
        case _:
            return f"/{fn_name}"


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
        case "actor_speak_batch":
            actors_list = args.get("actors", [])
            names = "、".join(a.get("actor_name", "?") for a in (actors_list if isinstance(actors_list, list) else []))
            return f"💬⚡ 批量对话: {names}"
        case "actor_chime_in":
            ctx = args.get("trigger_context", "")[:40]
            speaker = args.get("speaking_actor", "")
            return f"🔔 自发插话检测: {ctx}" + (f" (after {speaker})" if speaker else "")
        case "user_action":
            desc = args.get("description", "")[:60]
            return f"👤 用户行动: {desc}"
        case "director_narrate":
            content = args.get("content", "")[:50]
            return f"🎬 导演旁白: {content}"
        # ★ 语义检索 & Dynamic STORM 进度透出
        case "retrieve_relevant_scenes_tool":
            tags = args.get("tags", "")[:60]
            return f"🔍 正在检索人物记忆... (标签: {tags})"
        case "backfill_tags_tool":
            return "🏷️ 正在回填场景标签..."
        case "dynamic_storm":
            focus = args.get("focus_area", "")[:40]
            return f"⚡ 正在推演剧情走向... (聚焦: {focus})" if focus else "⚡ 正在推演剧情走向..."
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
        case "actor_speak":
            # Handled by default case below
            pass
        case "actor_chime_in":
            count = response.get("chime_count", 0)
            chime_ins = response.get("chime_ins", [])
            names = "、".join(c.get("actor_name", "?") for c in chime_ins[:3])
            if count > 0:
                return f"✅ 自发插话: {names} 等{count}人反应"
            else:
                return "✅ 自发插话检测完毕: 无人插话"
        # ★ 语义检索 & Dynamic STORM 响应进度
        case "retrieve_relevant_scenes_tool":
            count = len(response.get("relevant_scenes", []))
            return f"✅ 人物记忆检索完成: 找到 {count} 条相关回忆"
        case "backfill_tags_tool":
            count = response.get("backfilled_count", 0)
            return f"✅ 标签回填完成: {count} 条场景"
        case "dynamic_storm":
            count = len(response.get("new_perspectives", []))
            focus = response.get("focus_area", "")
            focus_str = f"「{focus}」" if focus else ""
            return f"✅ 剧情推演完成{focus_str}: 发现 {count} 个新视角"
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
                # ★ actor_speak_batch 特殊处理：展开 results 列表为多个独立 dialogue 事件
                if fn_name == "actor_speak_batch":
                    batch_results = resp.get("results", [])
                    for actor_result in batch_results:
                        results.append({
                            "type": "dialogue",
                            "data": _extract_response_data("dialogue", actor_result),
                        })
                    # 同时推送 speedup 信息
                    speedup = resp.get("speedup", "")
                    parallel_time = resp.get("parallel_time_sec", 0)
                    if speedup:
                        results.append({
                            "type": "director_log",
                            "data": {
                                "message": f"⚡ 批量对话完成: {len(batch_results)}人并行 {parallel_time}s (提速{speedup})",
                                "tool": fn_name,
                                "phase": "done",
                                "timestamp": time.strftime("%H:%M:%S"),
                            },
                        })
                # ★ actor_chime_in 特殊处理：展开 chime_ins 列表为多个独立 actor_chime_in 事件
                elif fn_name == "actor_chime_in":
                    chime_ins = resp.get("chime_ins", [])
                    for chime in chime_ins:
                        results.append({
                            "type": "actor_chime_in",
                            "data": _extract_response_data("dialogue", chime),
                        })
                    # 推送插话汇总 director_log
                    if chime_ins:
                        names = "、".join(c.get("actor_name", "?") for c in chime_ins[:3])
                        results.append({
                            "type": "director_log",
                            "data": {
                                "message": f"✅ 自发插话: {names} 等{len(chime_ins)}人反应",
                                "tool": fn_name,
                                "phase": "done",
                                "timestamp": time.strftime("%H:%M:%S"),
                            },
                        })
                    else:
                        results.append({
                            "type": "director_log",
                            "data": {
                                "message": "✅ 自发插话检测完毕: 无人插话",
                                "tool": fn_name,
                                "phase": "done",
                                "timestamp": time.strftime("%H:%M:%S"),
                            },
                        })
                else:
                    for event_type in TOOL_EVENT_MAP[fn_name]:
                        results.append({
                            "type": event_type,
                            "data": _extract_response_data(event_type, resp),
                        })

    # D-06: end_narration from final_response text (for /end command)
    if event.is_final_response() and event.content and event.content.parts:
        for part in event.content.parts:
            if part.text:
                text = part.text.strip()
                # ★ 识别 command_complete 合成事件
                if text == "[COMMAND_COMPLETE]":
                    results.append({
                        "type": "command_complete",
                        "data": {},
                    })
                elif text:
                    results.append({
                        "type": "end_narration",
                        "data": {"text": text},
                    })

    # ★ 兜底：无论 is_final_response 结果如何，只要内容包含 [COMMAND_COMPLETE] 就识别
    # 某些 ADK 版本对 synthetic event 的 is_final_response() 判断可能不一致
    if event.content and event.content.parts:
        for part in event.content.parts:
            if part.text and part.text.strip() == "[COMMAND_COMPLETE]":
                # 避免重复添加
                if not any(r.get("type") == "command_complete" for r in results):
                    results.append({
                        "type": "command_complete",
                        "data": {},
                    })

    return results
