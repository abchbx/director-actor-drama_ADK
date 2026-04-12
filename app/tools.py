"""Tools for the Director agent (A2A version) with STORM framework support.

The director creates actors as A2A services and communicates with them
via RemoteA2aAgent, ensuring true multi-agent isolation.

STORM (Synthesis of Topic Outlines through Retrieval and
Multi-perspective Question Asking) tools support multi-phase
drama creation: Discovery → Research → Outline → Directing.
"""

import os
from datetime import datetime

from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.tools import ToolContext

from .state_manager import (
    add_narration,
    add_conversation,
    add_dialogue,
    add_system_message,
    advance_scene,
    export_script,
    export_conversations,
    get_actor_info,
    get_all_actors,
    get_current_state,
    get_drama_folder,
    init_drama_state,
    list_dramas,
    list_saves,
    load_progress,
    register_actor,
    save_progress,
    set_drama_status,
    storm_add_perspective,
    storm_add_research_result,
    storm_get_perspectives,
    storm_get_research_results,
    storm_set_outline,
    storm_get_outline,
    update_actor_emotion,
    update_actor_memory,
    update_script,
    _get_state,
    _set_state,
)
from .actor_service import (
    create_actor_service,
    get_actor_remote_config,
    stop_actor_service,
    stop_all_actor_services,
    list_running_actors,
)
from .context_builder import build_actor_context, build_director_context, _extract_scene_transition
from .memory_manager import (
    add_working_memory,
    detect_importance,
    mark_critical_memory,
)
from .semantic_retriever import retrieve_relevant_scenes, backfill_tags


def start_drama(theme: str, tool_context: ToolContext) -> dict:
    """Start a new drama with the given theme. Use this when user provides /start command.

    Creates a dedicated folder for the drama and initializes conversation logging.

    Args:
        theme: The theme or premise for the drama.

    Returns:
        dict with initialization status.
    """
    result = init_drama_state(theme, tool_context)
    if result["status"] == "success":
        set_drama_status("setup", tool_context)
        
        # Get the drama folder path
        folder_info = get_drama_folder(tool_context)
        folder_path = folder_info.get("folder", "dramas/<主题>")
        
        # Add system message about folder creation
        add_system_message(
            f"戏剧「{theme}」已创建，数据保存路径: {folder_path}",
            tool_context
        )
        
        return {
            "status": "success",
            "message": (
                f"戏剧「{theme}」已启动！\n"
                f"📁 数据保存路径: {folder_path}\n\n"
                "请开始头脑风暴，构思剧情方向。你可以：\n"
                "1. 思考故事的核心冲突和主题\n"
                "2. 规划主要角色\n"
                "3. 设计故事的起承转合\n"
                "完成后，使用 create_actor 工具创建角色，然后用 advance_scene 开始第一场。"
            ),
            "drama_folder": folder_path,
        }
    return result


def create_actor(
    actor_name: str,
    role: str,
    personality: str,
    background: str,
    knowledge_scope: str,
    tool_context: ToolContext,
) -> dict:
    """Create a new actor/character as an A2A service. The director uses this to add characters.

    Each actor runs as an independent A2A agent with its own session and memory,
    ensuring true cognitive boundary isolation.

    Args:
        actor_name: The name of the character.
        role: The character's role (e.g., protagonist, antagonist, mentor).
        personality: Personality traits and speaking style (e.g., "沉稳冷静，说话简短有力").
        background: The character's backstory.
        knowledge_scope: What this character knows (defines cognitive boundary).

    Returns:
        dict with creation status and A2A connection info.
    """
    # Get other actors info FIRST (before creating the new actor)
    # This is needed so the new actor knows about existing actors for direct A2A communication
    actors_info = get_all_actors(tool_context)
    other_actors_list = []
    other_names = []
    if actors_info["status"] == "success":
        for name, info in actors_info["actors"].items():
            other_actors_list.append({
                "name": name,
                "role": info.get("role", ""),
                "personality": info.get("personality", ""),
                "background": info.get("background", ""),
            })
            other_names.append(f"{name}({info['role']})")
    
    other_info = "、".join(other_names) if other_names else "无"
    
    # Now create the actor service with other actors info
    service_result = create_actor_service(
        actor_name, role, personality, background, knowledge_scope, other_actors_list
    )
    if service_result["status"] != "success":
        return service_result
    
    # Register in state (after service is created)
    result = register_actor(actor_name, role, personality, background, knowledge_scope, tool_context, port=service_result.get("port"))
    if result["status"] != "success":
        return result

    return {
        "status": "success",
        "message": (
            f"角色「{actor_name}」A2A 服务已启动！\n"
            f"身份: {role}\n"
            f"性格: {personality}\n"
            f"认知范围: {knowledge_scope}\n"
            f"A2A端口: {service_result.get('port', 'N/A')}\n"
            f"其他角色: {other_info}\n\n"
            "该角色作为独立 A2A Agent 运行，拥有自己的会话和记忆，"
            "认知边界通过物理隔离保证。"
            + (f"\n该角色可以直接联系其他演员进行 A2A 对话。" if other_names else "")
        ),
        "actor_name": actor_name,
        "role": role,
        "port": service_result.get("port"),
        "card_file": service_result.get("card_file"),
    }


async def actor_speak(
    actor_name: str,
    situation: str,
    tool_context: ToolContext,
) -> dict:
    """Make an actor speak by sending a message to their A2A service and getting their response.

    The actor is an independent A2A agent. This tool sends the situation to the
    actor's A2A service and returns the actor's actual dialogue response.

    Args:
        actor_name: The name of the actor who should speak.
        situation: The current situation or dialogue prompt for the actor to respond to.

    Returns:
        dict with actor info and the actor's actual dialogue response.
        The 'dialogue' field contains the raw response from the A2A agent.
        The 'formatted_dialogue' field contains a ready-to-display version.
    """
    actor_info = get_actor_info(actor_name, tool_context)
    if actor_info["status"] != "success":
        return actor_info

    actor_data = actor_info["actor"]

    # Get A2A connection config (pass saved_port for robustness)
    saved_port = actor_data.get("port")
    config = get_actor_remote_config(actor_name, saved_port=saved_port)
    if not config:
        return {
            "status": "error",
            "message": f"Actor '{actor_name}' A2A service not found. Was it created with create_actor?",
        }
    # 1. Build memory context using new 3-tier system (replaces flat memory_str)
    memory_context = build_actor_context(actor_name, tool_context)

    # 2. Add current situation to working memory with importance detection
    is_critical, critical_reason = detect_importance(situation)
    importance = "critical" if is_critical else "normal"
    add_working_memory(
        actor_name=actor_name,
        entry=f"面对情境: {situation}",
        importance=importance,
        critical_reason=critical_reason,
        tool_context=tool_context,
    )

    # 3. Build enhanced prompt with layered context
    role_label = actor_data.get("role", "")
    personality = actor_data.get("personality", "")
    emotion_label = actor_data.get("emotions", "neutral")
    emotion_cn = {
        "neutral": "平静", "angry": "愤怒", "sad": "悲伤", "happy": "喜悦",
        "fearful": "恐惧", "confused": "困惑", "determined": "决绝",
        "anxious": "焦虑", "hopeful": "充满希望",
    }.get(emotion_label, emotion_label)

    prompt = (
        f"【角色锚点】你是{actor_name}，{role_label}。{personality}\n\n"
        f"【当前情绪】{emotion_cn}\n\n"
        f"【当前情境】{situation}\n\n"
        f"{memory_context}\n\n"
        f"请以「{actor_name}」的身份回应上述情境。"
        f"保持角色一致性，不要跳出角色。"
        f"如有内心独白，用（内心：...）格式。"
    )

    # Call the actor A2A service directly via async — no event loop hack needed
    card_file = config["card_file"]
    port = config.get("port", "N/A")
    try:
        actor_dialogue = await _call_a2a_sdk(card_file, prompt, actor_name, port)
    except Exception as e:
        err_type = type(e).__name__
        msg = str(e).lower()
        if "connect" in err_type or "refused" in msg or "connection" in msg:
            actor_dialogue = f"[{actor_name}连接失败(端口:{port})。请用create_actor重启服务。]"
        elif "timeout" in err_type or "timeout" in msg or "timed out" in msg:
            actor_dialogue = f"[{actor_name}响应超时。LLM推理可能较慢，稍后重试。]"
        else:
            actor_dialogue = f"[{actor_name}调用失败({err_type}): {e}]"

    # Record actor's own dialogue in working memory (Pitfall 5: actor must remember what they said)
    if not (actor_dialogue.startswith("[") and ("失败" in actor_dialogue or "超时" in actor_dialogue)):
        add_working_memory(
            actor_name=actor_name,
            entry=f"我说：{actor_dialogue[:200]}",  # Truncate to avoid excessive length
            importance="normal",
            critical_reason=None,
            tool_context=tool_context,
        )

    # Auto-log the dialogue to conversation record
    if not (actor_dialogue.startswith("[") and ("失败" in actor_dialogue or "超时" in actor_dialogue)):
        add_dialogue(actor_name=actor_name, dialogue=actor_dialogue, tool_context=tool_context)

    # Build a formatted version that the director can directly use
    formatted_lines = []
    formatted_lines.append(f"🎭 {actor_name}（{role_label} · {emotion_cn}）：")

    # Check if dialogue starts with [error] - format differently
    if actor_dialogue.startswith("[") and ("失败" in actor_dialogue or "超时" in actor_dialogue):
        formatted_lines.append(f"  ⚠️ {actor_dialogue}")
    else:
        # Split by newlines and indent each line as dialogue
        for line in actor_dialogue.split("\n"):
            if line.strip():
                formatted_lines.append(f"  {line}")
            else:
                formatted_lines.append("")

    formatted_dialogue = "\n".join(formatted_lines)

    return {
        "status": "success",
        "actor_name": actor_name,
        "role": role_label,
        "personality": actor_data.get("personality", ""),
        "emotions": emotion_label,
        "emotions_cn": emotion_cn,
        "memories": memory_context,  # Updated: 3-tier context instead of flat memory_str
        "situation": situation,
        "dialogue": actor_dialogue,
        "formatted_dialogue": formatted_dialogue,
        "message": formatted_dialogue,
        "a2a_card_file": config["card_file"],
        "a2a_card_url": config["card_url"],
        "a2a_rpc_url": config["rpc_url"],
        "port": config["port"],
    }


async def _call_a2a_sdk(card_file: str, prompt: str, actor_name: str, port: str) -> str:
    """Core async A2A call via a2a SDK (ClientFactory + Message types).
    
    Handles both streaming (async generator) and non-streaming responses.
    In a2a-sdk 0.3.x, send_message returns an AsyncIterator[ClientEvent | Message],
    where ClientEvent is tuple[Task, UpdateEvent].
    """
    import json
    import uuid
    import httpx
    from a2a.client import ClientFactory, ClientConfig
    from a2a.types import AgentCard, Message, Part, Role, Task

    def _extract_text_from_part(part) -> tuple[str | None, bool]:
        """Extract text from a Part object, handling different part types.
        
        Returns (text, is_thought) tuple.
        TextPart uses root.text structure, so we need to check both
        direct text attribute and root.text for compatibility.
        """
        text = None
        is_thought = False
        
        # Try direct text attribute first (for DataPart, etc.)
        t = getattr(part, "text", None)
        if t:
            text = t
            # Check metadata on direct part
            metadata = getattr(part, "metadata", None)
            if metadata and metadata.get("adk_thought"):
                is_thought = True
        
        # For TextPart and other structured parts, check root
        root = getattr(part, "root", None)
        if root is not None:
            # Check if root has text attribute
            t = getattr(root, "text", None)
            if t:
                text = t
            # Check metadata on root (for TextPart)
            metadata = getattr(root, "metadata", None)
            if metadata and metadata.get("adk_thought"):
                is_thought = True
        
        return text, is_thought

    with open(card_file, "r", encoding="utf-8") as f:
        card_data = json.load(f)
    agent_card = AgentCard(**card_data)

    httpx_client = httpx.AsyncClient(timeout=httpx.Timeout(timeout=120))
    client_config = ClientConfig(httpx_client=httpx_client, streaming=False, polling=False)
    factory = ClientFactory(config=client_config)
    client = factory.create(card=agent_card)

    # messageId is required in a2a-sdk 0.3.x
    a2a_msg = Message(messageId=str(uuid.uuid4()), parts=[Part(text=prompt)], role="user")
    
    texts: list[str] = []
    
    # send_message returns AsyncIterator[ClientEvent | Message]
    async for event in client.send_message(a2a_msg):
        if isinstance(event, Message):
            # Direct Message response
            for part in getattr(event, "parts", []):
                t, is_thought = _extract_text_from_part(part)
                if t and not is_thought:
                    texts.append(t)
        elif isinstance(event, tuple):
            # ClientEvent: tuple[Task, UpdateEvent]
            for item in event:
                if isinstance(item, Task):
                    # Task may have artifacts with the response
                    if hasattr(item, "artifacts") and item.artifacts:
                        for artifact in item.artifacts:
                            for part in getattr(artifact, "parts", []):
                                t, is_thought = _extract_text_from_part(part)
                                if t and not is_thought:
                                    texts.append(t)
                    # Also check status.message
                    if hasattr(item, "status") and item.status:
                        status = item.status
                        if hasattr(status, "message") and status.message:
                            for part in getattr(status.message, "parts", []):
                                t, is_thought = _extract_text_from_part(part)
                                if t and not is_thought:
                                    texts.append(t)
    
    await httpx_client.aclose()

    if texts:
        return "\n".join(texts).strip()
    else:
        return f"[{actor_name}已响应但无文本内容]"



def director_narrate(narration: str, tool_context: ToolContext) -> dict:
    """The director narrates as a voiceover to describe scene transitions, atmosphere, or plot development.

    Args:
        narration: The narration text to add as voiceover.

    Returns:
        dict with status and the full narration text in multiple formats for display.
    """
    result = add_narration(narration, tool_context)
    
    # Auto-include director context for scene awareness
    director_ctx = build_director_context(tool_context)
    
    # Auto-log the narration to conversation record
    add_conversation(
        speaker="导演",
        content=narration,
        conversation_type="narration",
        tool_context=tool_context
    )

    # Build formatted narration with visual markers
    formatted_lines = []
    formatted_lines.append("🎬 【舞台指示 / 旁白】")
    for line in narration.split("\n"):
        if line.strip():
            formatted_lines.append(f"  {line}")
        else:
            formatted_lines.append("")
    formatted_narration = "\n".join(formatted_lines)

    separator = "─" * 30

    return {
        "status": "success",
        "narration": narration,
        "formatted_narration": formatted_narration,
        "director_context": director_ctx,
        "message": f"\n{separator}\n{formatted_narration}\n{separator}",
    }


def write_scene(
    scene_number: int,
    scene_title: str,
    scene_description: str,
    dialogue_content: str,
    tool_context: ToolContext,
) -> dict:
    """Write or update a scene in the script.

    Args:
        scene_number: The scene number (1-based).
        scene_title: Title of the scene.
        scene_description: Stage directions and scene description.
        dialogue_content: The dialogue and narration content for this scene.

    Returns:
        dict with status and the full scene content for display.
        The 'formatted_scene' field contains a complete script-formatted version.
    """
    result = update_script(
        scene_number, scene_title, scene_description, dialogue_content, tool_context
    )
    result["scene_number"] = scene_number
    result["scene_title"] = scene_title
    result["scene_description"] = scene_description
    result["dialogue_content"] = dialogue_content

    # Build a complete formatted version of the scene record
    top_line = "━" * 30
    formatted_scene = (
        f"\n{top_line}\n"
        f"📝 第 {scene_number} 场：「{scene_title}」\n"
        f"{top_line}\n\n"
        f"*{scene_description}*\n\n"
        f"{dialogue_content}\n\n"
        f"{top_line}\n"
        f"✅ 第 {scene_number} 场记录已保存至剧本。\n"
    )

    return {
        **result,
        "formatted_scene": formatted_scene,
        "message": formatted_scene,
    }


def next_scene(tool_context: ToolContext) -> dict:
    """Advance to the next scene with transition info. Use when user provides /next command.

    Returns transition information (D-08/D-09/D-10/D-13) including:
    - is_first_scene: True if this is the first scene (D-13)
    - transition: {last_ending, actor_emotions, unresolved} (D-09)
    - transition_text: Formatted paragraph for director prompt

    Args:
        tool_context: The tool context.

    Returns:
        dict with the new scene info, transition info, and format guidance.
    """
    result = advance_scene(tool_context)
    state = tool_context.state.get("drama", {})
    scene_num = state.get("current_scene", 1)

    # Extract transition info (D-08/D-09/D-10/D-13)
    transition = _extract_scene_transition(state)

    # Build transition paragraph for director prompt
    transition_text = ""
    if transition["is_first_scene"]:
        transition_text = "🎬 这是本剧的第一场戏！请输出开场白，介绍故事背景和主要角色。"
    else:
        parts = []
        if transition["last_ending"]:
            parts.append(f"上一场结局：{transition['last_ending']}")
        if transition["actor_emotions"]:
            emotions_str = "、".join(
                f"{name}（{emo}）" for name, emo in transition["actor_emotions"].items()
            )
            parts.append(f"角色情绪：{emotions_str}")
        if transition["unresolved"]:
            parts.append(f"未决事件：{'；'.join(transition['unresolved'][:3])}")
        transition_text = "【上一场衔接】\n" + "\n".join(parts)

    # Phase 5: Auto-advance counter decrement (A4 mitigation)
    # When remaining_auto_scenes > 0, decrement on each new scene start.
    # This is a code-level safety net — the prompt also instructs LLM to decrement.
    auto_remaining = state.get("remaining_auto_scenes", 0)
    auto_status = ""
    if auto_remaining > 0:
        state["remaining_auto_scenes"] = max(0, auto_remaining - 1)
        auto_remaining = state["remaining_auto_scenes"]
        if auto_remaining == 0:
            auto_status = "\n\n🔄 自动推进已结束，回到手动模式。"
        else:
            auto_status = f"\n\n[自动推进中... 剩余 {auto_remaining} 场，输入任意内容中断]"
        # Persist the counter change
        _set_state(state, tool_context)

    # Phase 5: Clear steer_direction after it's been read for this scene (D-09)
    steer_info = state.get("steer_direction")
    if steer_info:
        state["steer_direction"] = None
        _set_state(state, tool_context)

    # Auto-include director context for scene continuity
    # D-10 compliance: next_scene() returns concise transition_text (must-read),
    # while director_context provides broader global view. The _improv_director
    # prompt must instruct: use transition_text for scene-to-scene continuity,
    # use director_context only when you need global arc/storm overview.
    # This prevents duplicate transition info in the LLM's working context.
    director_ctx = build_director_context(tool_context)

    # Get current actors for context
    actors_data = state.get("actors", {})
    actor_names = list(actors_data.keys())
    actor_list = "、".join(actor_names) if actor_names else "（尚无演员）"

    return {
        "status": "success",
        "current_scene": scene_num,
        "is_first_scene": transition["is_first_scene"],
        "transition": transition,
        "transition_text": transition_text,
        "actors_available": actor_names,
        "director_context": director_ctx,
        "auto_remaining": auto_remaining,
        "steer_direction": steer_info,
        "message": (
            f"▶️ 已推进至第 {scene_num} 场。\n\n"
            f"{transition_text}\n\n"
            f"当前可用演员: {actor_list}\n\n"
            f"请按以下顺序执行：\n"
            f"  ① director_narrate —— 描述本场环境\n"
            f"  ② actor_speak —— 让角色对话\n"
            f"  ③ write_scene —— 记录本场\n\n"
            f"输出完整剧本格式片段后等待用户指令。"
            f"{auto_status}"
        ),
    }


def user_action(action_description: str, tool_context: ToolContext) -> dict:
    """Process a user-injected action or event. Use when user provides /action command.

    Args:
        action_description: Description of the event or action the user wants to inject.

    Returns:
        dict with status and guidance for the director.
    """
    return {
        "status": "success",
        "message": (
            f"用户注入事件: {action_description}\n"
            "请作为导演：\n"
            "1. 考虑这个事件如何影响当前剧情\n"
            "2. 用 director_narrate 描述事件的发生\n"
            "3. 用 actor_speak 让相关角色做出反应\n"
            "4. 更新角色的情绪和记忆"
        ),
        "action": action_description,
    }


def auto_advance(scenes: int, tool_context: ToolContext) -> dict:
    """Enable auto-advance mode for N scenes. The director will advance N scenes autonomously.

    设置自动推进模式，AI 将自主推进指定场数的戏剧。用户可随时输入任何内容中断。

    Args:
        scenes: Number of scenes to auto-advance. Must be >= 1. Default 3, soft cap at 10.

    Returns:
        dict with auto-advance status and guidance.
    """
    # Validate scenes > 0
    if scenes < 1:
        return {
            "status": "error",
            "message": f"❌ 自动推进场数必须 ≥ 1，当前值: {scenes}",
        }

    state = _get_state(tool_context)

    # D-05: Soft cap at 10 — warn once, then allow on repeated request
    confirmed = state.get("_auto_advance_confirmed", False)
    if scenes > 10 and not confirmed:
        state["_auto_advance_confirmed"] = True
        _set_state(state, tool_context)
        current = state.get("remaining_auto_scenes", 0)
        return {
            "status": "info",
            "message": (
                f"⚠️ 请求推进 {scenes} 场超过建议上限(10场)。\n"
                f"大量自动推进可能消耗较多 token。建议使用 /auto 10 以内。\n"
                f"如果确认，请再次发送 /auto {scenes}"
            ),
            "remaining_auto_scenes": current,
        }
    # Clear confirmation flag regardless
    state.pop("_auto_advance_confirmed", None)

    # D-04: Default 3 handled by caller (router/CLI passes 3 if no arg)
    state["remaining_auto_scenes"] = scenes
    _set_state(state, tool_context)

    return {
        "status": "success",
        "message": (
            f"🎬 自动推进模式已启动！将自主推进 {scenes} 场戏。\n"
            f"每场结束后会提示剩余场数。\n"
            f"输入任何内容即可中断，回到手动模式。"
        ),
        "remaining_auto_scenes": scenes,
    }


def steer_drama(direction: str, tool_context: ToolContext) -> dict:
    """Set a directional guidance for the next scene. Lighter than /action which injects specific events.

    设置下一场的方向引导，导演会在此方向上发挥创意。
    与 /action 不同：/steer 给方向（"让朱棣更偏执"），/action 给事件（"朱棣发现密信"）。

    Args:
        direction: The direction or guidance for the next scene.

    Returns:
        dict with confirmation that the steer is set.
    """
    state = _get_state(tool_context)

    # Validate non-empty direction
    if not direction or not direction.strip():
        return {
            "status": "error",
            "message": "❌ 方向不能为空。请提供方向引导，例如 /steer 让朱棣更偏执",
        }

    state["steer_direction"] = direction
    _set_state(state, tool_context)

    return {
        "status": "success",
        "message": (
            f"🧭 方向已设置：{direction}\n"
            f"下一场将在此方向上发挥创意。\n"
            f"效力仅一场，之后自动清除。"
        ),
        "steer_direction": direction,
    }


def end_drama(tool_context: ToolContext) -> dict:
    """End the drama with epilogue narration, auto-save, and script export.

    触发终幕机制：设置 drama_status 为 ended，提示导演生成终幕旁白，
    自动保存存档，并导出完整剧本。结束后可继续番外篇。

    Args:
        tool_context: The tool context.

    Returns:
        dict with end status and epilogue template.
    """
    state = _get_state(tool_context)
    state["status"] = "ended"

    # A5 mitigation: Clear steer_direction on end to prevent residue
    state["steer_direction"] = None

    # Reset auto-advance counter
    state["remaining_auto_scenes"] = 0

    _set_state(state, tool_context)

    return {
        "status": "success",
        "message": (
            "🎭 终幕已触发！\n"
            "请按照终幕协议生成终幕旁白：\n"
            "1. 回顾全剧主线\n"
            "2. 各角色结局\n"
            "3. 主题升华\n"
            "4. 落幕致辞\n\n"
            "生成终幕旁白后，自动调用 save_drama 和 export_drama。\n"
            "结束后用户仍可用 /next 继续番外篇。"
        ),
        "drama_status": "ended",
        "epilogue_template": (
            "🎭 终幕 ——\n"
            "【回顾】全剧主线梳理\n"
            "【角色结局】各角色命运\n"
            "【主题升华】核心主题回响\n"
            "【落幕致辞】最后的旁白"
        ),
    }


def trigger_storm(focus_area: str, tool_context: ToolContext) -> dict:
    """Trigger a lightweight perspective review of the current drama.

    手动触发视角审视——让导演重新审视当前剧情，发现新的角度或未探索方向。
    轻量版（Phase 5），Phase 8 将升级为完整 Dynamic STORM。

    Args:
        focus_area: Optional area to focus the review on (e.g., "角色关系", "权力斗争").

    Returns:
        dict with storm review status.
    """
    state = _get_state(tool_context)

    # D-22: Ensure storm sub-dict exists
    if "storm" not in state:
        state["storm"] = {"last_review": {}}

    _set_state(state, tool_context)

    return {
        "status": "success",
        "message": (
            f"🔍 视角审视已触发！聚焦领域：{focus_area}\n"
            f"请重新审视当前剧情，输出 1-2 个新角度或未探索方向。\n"
            f"格式：以【视角审视】标记输出。"
        ),
        "focus_area": focus_area,
    }


def save_drama(save_name: str, tool_context: ToolContext) -> dict:
    """Save the current drama progress. Use when user provides /save command.

    This will:
    1. Save all drama state (theme, scenes, actors, narration)
    2. Export conversations to markdown file

    Args:
        save_name: Name for this save file (optional, for creating named snapshots).

    Returns:
        dict with save status.
    """
    result = save_progress(save_name, tool_context)
    
    if result["status"] == "success":
        # Export conversations to markdown
        conv_result = export_conversations(format="markdown", tool_context=tool_context)
        
        folder_path = result.get("drama_folder", "")
        conv_msg = ""
        if conv_result.get("status") == "success":
            conv_msg = f"\n📝 对话记录已导出至: {conv_result.get('filepath', 'conversations/')}"
        elif conv_result.get("status") == "info":
            conv_msg = "\n📝 暂无对话记录"
        
        result["message"] = (
            f"💾 进度已保存！\n"
            f"📁 剧本数据: {folder_path}\n"
            f"{conv_msg}\n\n"
            f"使用 /load {save_name or '剧本名'} 可重新加载此进度。"
        )
    
    return result


def load_drama(save_name: str, tool_context: ToolContext) -> dict:
    """Load a previously saved drama and restart actor A2A services. Use when user provides /load command.

    This will:
    1. Restore all drama state (theme, scenes, actors, narration)
    2. Automatically restart A2A services for all saved actors
    3. Preserve actor memories and emotions from the save

    Args:
        save_name: The name of the save to load.

    Returns:
        dict with load status and actor restart results.
    """
    result = load_progress(save_name, tool_context)
    if result["status"] != "success":
        return result

    # Restart A2A services for all actors in the save
    actors_data = tool_context.state.get("drama", {}).get("actors", {})
    
    # Build the full other_actors list first (needed for cross-actor A2A communication)
    other_actors_list = []
    for name, info in actors_data.items():
        other_actors_list.append({
            "name": name,
            "role": info.get("role", ""),
            "personality": info.get("personality", ""),
            "background": info.get("background", ""),
        })
    
    restart_results = []
    for actor_name, actor_info in actors_data.items():
        # Extract memory entries for this actor to restore historical context
        # Build memory entries from new 3-tier structure (fallback to old format for compatibility)
        actor_working = actor_info.get("working_memory", [])
        if actor_working:
            # New format: extract entries from working_memory
            memory_entries = [e["entry"] for e in actor_working]
            # Prepend critical memories and arc summary for richer context
            critical = actor_info.get("critical_memories", [])
            if critical:
                critical_entries = [f"[关键] {m['entry']} ({m['reason']})" for m in critical]
                memory_entries = critical_entries + memory_entries
            arc = actor_info.get("arc_summary", {})
            if arc.get("narrative"):
                memory_entries = [f"[故事弧线] {arc['narrative']}"] + memory_entries
        else:
            # Fallback to old format for actors not yet migrated
            memory_entries = [m["entry"] for m in actor_info.get("memory", [])]
        
        svc_result = create_actor_service(
            actor_name=actor_name,
            role=actor_info.get("role", ""),
            personality=actor_info.get("personality", ""),
            background=actor_info.get("background", ""),
            knowledge_scope=actor_info.get("knowledge_scope", ""),
            other_actors=other_actors_list,
            memory_entries=memory_entries,
        )
        # Update port in state (in case it changed or wasn't saved before)
        if svc_result.get("status") == "success" and svc_result.get("port"):
            actors_data[actor_name]["port"] = svc_result["port"]
        restart_results.append({
            "actor_name": actor_name,
            "status": svc_result.get("status", "unknown"),
            "port": svc_result.get("port"),
        })
    
    # Persist updated port info back to state
    tool_context.state["drama"]["actors"] = actors_data

    # Build detailed message
    actor_summary = []
    for r in restart_results:
        status_icon = "✅" if r["status"] == "success" else "❌"
        actor_summary.append(f"{status_icon} {r['actor_name']} (端口: {r.get('port', 'N/A')})")

    actor_list = "\n".join(actor_summary) if actor_summary else "无角色"

    # Build scene summary for context
    scenes = tool_context.state.get("drama", {}).get("scenes", [])
    current_scene = result.get("current_scene", 0)
    scene_summary = ""
    if scenes:
        scene_lines = []
        for s in scenes:
            sn = s.get("scene_number", 0)
            st = s.get("title", "未命名")
            scene_lines.append(f"  第{sn}场「{st}」")
        scene_summary = "\n已有场景:\n" + "\n".join(scene_lines)
    else:
        scene_summary = "\n尚无已记录的场景。"

    # Build narration summary
    narration_log = tool_context.state.get("drama", {}).get("narration_log", [])
    narration_summary = ""
    if narration_log:
        narration_summary = f"\n已有旁白: {len(narration_log)} 条"

    # Build next action guidance using new DramaRouter statuses
    drama_status = result.get("drama_status", "")
    if drama_status == "acting" and current_scene > 0:
        next_action = (
            f"\n\n▶️ 请使用 /next 继续第{current_scene + 1}场，"
            f"或使用 /action 注入事件。当前在第{current_scene}场。"
        )
    elif drama_status == "acting":
        next_action = "\n\n▶️ 请使用 /next 开始第一场戏。"
    elif drama_status == "setup":
        next_action = "\n\n▶️ 请使用 /start <主题> 继续设定。"
    else:
        next_action = "\n\n▶️ 请使用 /next 继续剧情。"

    return {
        "status": "success",
        "message": (
            f"🎭 戏剧「{result.get('theme', '')}」已加载！\n"
            f"📁 数据路径: {result.get('drama_folder', 'N/A')}\n"
            f"状态: {drama_status}\n"
            f"当前场景: 第{current_scene}场\n"
            f"已记录场景: {result.get('num_scenes', 0)}场\n"
            f"演员人数: {result.get('num_actors', 0)}人\n"
            f"{scene_summary}"
            f"{narration_summary}"
            f"\n\n🎭 演员 A2A 服务重启状态:\n{actor_list}"
            f"{next_action}"
        ),
        "theme": result.get("theme", ""),
        "current_scene": result.get("current_scene", 0),
        "num_scenes": result.get("num_scenes", 0),
        "num_actors": result.get("num_actors", 0),
        "drama_status": drama_status,
        "actor_restart_results": restart_results,
        "drama_folder": result.get("drama_folder", ""),
    }


def export_drama(tool_context: ToolContext) -> dict:
    """Export the complete drama script as Markdown. Use when user provides /export command.

    This exports:
    1. The full script (scenes, dialogues, narrations)
    2. Conversation log as markdown

    Args:
        tool_context: The tool context.

    Returns:
        dict with export status and file paths.
    """
    result = export_script(tool_context)
    
    if result["status"] == "success":
        # Also export conversations
        conv_result = export_conversations(format="markdown", tool_context=tool_context)
        
        script_path = result.get("filepath", "")
        conv_path = conv_result.get("filepath", "") if conv_result.get("status") == "success" else None
        
        result["message"] = (
            f"📜 剧本已导出！\n"
            f"📄 剧本文件: {script_path}\n"
            f"💬 对话记录: {conv_path or '暂无对话记录'}"
        )
        result["conversation_filepath"] = conv_path
    
    return result


def show_cast(tool_context: ToolContext) -> dict:
    """Show all current actors and their status. Use when user provides /cast command.

    Args:
        tool_context: The tool context.

    Returns:
        dict with actors info.
    """
    state_actors = get_all_actors(tool_context)
    running = list_running_actors()

    result = {
        "status": "success",
        "actors": state_actors.get("actors", {}),
        "running_services": running.get("actors", {}),
    }
    return result


def list_all_dramas(tool_context: ToolContext) -> dict:
    """List all available dramas. Use when user provides /list command.

    Args:
        tool_context: The tool context.

    Returns:
        dict with list of dramas.
    """
    result = list_dramas()
    
    if result.get("dramas"):
        lines = ["📚 可用的剧本:"]
        for drama in result["dramas"]:
            theme = drama.get("theme", "未知")
            status = drama.get("status", "unknown")
            updated = drama.get("updated_at", "未知")
            scene = drama.get("current_scene", 0)
            lines.append(f"  • {theme} (状态: {status}, 第{scene}场, 更新: {updated[:10]})")
        result["message"] = "\n".join(lines)
    else:
        result["message"] = "暂无已保存的剧本。使用 /start <主题> 开始新剧。"
    
    return result


def show_status(tool_context: ToolContext) -> dict:
    """Show the current drama status. Use when user provides /status command.

    Args:
        tool_context: The tool context.

    Returns:
        dict with current status.
    """
    state = get_current_state(tool_context)
    folder = get_drama_folder(tool_context)
    
    if state.get("theme"):
        state["message"] = (
            f"🎭 当前剧本: {state.get('theme', '')}\n"
            f"📁 数据路径: {folder.get('folder', 'N/A')}\n"
            f"状态: {state.get('drama_status', 'unknown')}\n"
            f"当前场景: 第{state.get('current_scene', 0)}场\n"
            f"已记录场景: {state.get('num_scenes', 0)}场\n"
            f"演员人数: {state.get('num_actors', 0)}人\n"
            f"演员: {', '.join(state.get('actors', [])) or '暂无'}"
        )
    
    return state


def get_director_context(tool_context: ToolContext) -> dict:
    """Get the current director context summary. Use when you need to review the overall story state, all actors' arcs, recent scenes, and active conflicts.

    Returns a formatted context string containing: global story arc, current status, recent scenes, actor emotions, STORM perspectives, and any active conflicts or established facts.

    Args:
        tool_context: The tool context.

    Returns:
        dict with the director context summary.
    """
    context = build_director_context(tool_context)
    return {
        "status": "success",
        "context": context,
        "message": f"📋 导演上下文摘要:\n{context[:500]}..." if len(context) > 500 else f"📋 导演上下文摘要:\n{context}",
    }


def update_emotion(actor_name: str, emotion: str, tool_context: ToolContext) -> dict:
    """Update an actor's emotional state after a scene event.

    Args:
        actor_name: The name of the actor.
        emotion: The new emotional state (e.g., "愤怒", "悲伤", "喜悦", "恐惧").

    Returns:
        dict with status.
    """
    return update_actor_emotion(actor_name, emotion, tool_context)


def mark_memory(
    actor_name: str,
    reason: str,
    tool_context: ToolContext,
) -> dict:
    """Mark the most recent working memory of an actor as critical. Use when user provides /mark command.

    Marks the last entry in the actor's working memory as a critical memory.
    Critical memories are never compressed and always included in the actor's context.

    Args:
        actor_name: The name of the actor whose memory to mark.
        reason: Brief explanation of why this is important (e.g., "这段很重要", "关键转折").

    Returns:
        dict with status.
    """
    state = tool_context.state.get("drama", {})
    actors = state.get("actors", {})

    if actor_name not in actors:
        return {"status": "error", "message": f"演员「{actor_name}」不存在。"}

    working = actors[actor_name].get("working_memory", [])
    if not working:
        return {"status": "error", "message": f"演员「{actor_name}」没有工作记忆可标记。"}

    # Map user's free-text reason to closest CRITICAL_REASONS category
    # Default to "用户标记" per D-06 type 5
    from .memory_manager import CRITICAL_REASONS
    matched_reason = "用户标记"  # Default
    for cr in CRITICAL_REASONS:
        if cr in reason:
            matched_reason = cr
            break

    result = mark_critical_memory(
        actor_name=actor_name,
        memory_index=len(working) - 1,  # Mark the LAST entry
        reason=matched_reason,
        tool_context=tool_context,
    )

    if result["status"] == "success":
        return {
            "status": "success",
            "message": f"✅ 已将「{actor_name}」的最近记忆标记为关键记忆（{matched_reason}）。",
        }
    return result


# ============================================================================
# STORM Framework Tools
# ============================================================================


def storm_discover_perspectives(theme: str, tool_context: ToolContext) -> dict:
    """Discover multiple perspectives for exploring a drama theme (STORM Phase 1).

    Generates a list of diverse viewpoints from which to examine the theme,
    ensuring comprehensive exploration before deep research.

    Args:
        theme: The drama theme to explore from multiple perspectives.

    Returns:
        dict with discovered perspectives and guiding questions.
    """
    # Setup phase: status remains "setup" (D-14: no intermediate STORM statuses)
    set_drama_status("setup", tool_context)

    perspectives = [
        {
            "name": "主角视角",
            "description": f"从主角的内心世界出发：{theme}对主角意味着什么？主角最深的渴望和恐惧是什么？",
            "questions": [
                f"在「{theme}」中，主角最核心的矛盾是什么？",
                f"主角在{theme}的情境下，最大的内心冲突是什么？",
                f"主角会如何面对{theme}带来的挑战？",
            ],
        },
        {
            "name": "反派/对立面视角",
            "description": f"从对立面的立场出发：为什么{theme}的另一面也有其合理性？对立力量的内在逻辑是什么？",
            "questions": [
                f"站在{theme}的对立面，什么动机是合理且令人同情的？",
                f"如果反派也有自己的正义，那会是什么样的正义？",
                f"对立力量如何从{theme}中获得力量？",
            ],
        },
        {
            "name": "旁观者/社会视角",
            "description": f"从旁观者和社会的角度：{theme}在更广阔的社会背景下意味着什么？对他人产生了什么影响？",
            "questions": [
                f"{theme}对旁观者或社会有什么深远影响？",
                f"社会如何看待和评判{theme}中的事件？",
                f"有哪些不为人知的角落受到了{theme}的波及？",
            ],
        },
        {
            "name": "伦理/哲学视角",
            "description": f"从伦理和哲学的高度：{theme}触及了什么根本性的道德问题？存在怎样的价值冲突？",
            "questions": [
                f"{theme}触及了什么根本性的伦理困境？",
                f'在{theme}的情境下，什么是"对"什么是"错"的边界？',
                f"如果从不同哲学流派的角度审视{theme}，会有什么不同的结论？",
            ],
        },
        {
            "name": "时间/命运视角",
            "description": f"从时间和命运的维度：{theme}的过去如何塑造了现在？未来可能如何演变？如果时间倒流会怎样？",
            "questions": [
                f"{theme}的根源可以追溯到什么过去的事件？",
                f"如果给{theme}一个转折点，最戏剧性的变化会是什么？",
                f"十年后再回望{theme}，什么才是真正重要的？",
            ],
        },
    ]

    # Store perspectives in state
    for p in perspectives:
        storm_add_perspective(
            perspective_name=p["name"],
            description=p["description"],
            questions=p["questions"],
            tool_context=tool_context,
        )

    # Setup phase: status remains "setup" (D-14: no intermediate STORM statuses)
    set_drama_status("setup", tool_context)

    perspective_summary = "\n".join(
        f"  **{p['name']}**: {p['description']}" for p in perspectives
    )

    return {
        "status": "success",
        "message": (
            f"STORM 发现阶段完成！已为「{theme}」生成 {len(perspectives)} 个探索视角：\n\n"
            f"{perspective_summary}\n\n"
            "接下来进入研究阶段——请使用 /next 继续，"
            "系统将深入挖掘每个视角的戏剧潜力。"
        ),
        "perspectives": perspectives,
        "theme": theme,
        "phase": "discovery",
        "next_phase": "research",
    }


def storm_ask_perspective_questions(
    perspective: str,
    theme: str,
    tool_context: ToolContext,
) -> dict:
    """Generate deep questions for a specific perspective (STORM Phase 2).

    Creates detailed, probing questions that explore the dramatic potential
    of a given perspective on the theme.

    Args:
        perspective: The perspective name to generate questions for.
        theme: The drama theme being explored.

    Returns:
        dict with generated questions for the perspective.
    """
    stored_perspectives = storm_get_perspectives(tool_context)

    # Find the matching perspective
    perspective_data = None
    for p in stored_perspectives.get("perspectives", []):
        if p["name"] == perspective:
            perspective_data = p
            break

    if not perspective_data:
        # Generate default questions if perspective not found in state
        questions = [
            f"从{perspective}来看，「{theme}」最核心的戏剧张力是什么？",
            f"在{perspective}的视角下，{theme}中最大的不确定性是什么？",
            f"{perspective}如何改变我们对{theme}的理解？",
            f"如果完全从{perspective}出发重新解读{theme}，会发现什么被忽视的层面？",
            f"{perspective}与其他视角的{theme}解读之间有什么冲突和互补？",
        ]
    else:
        questions = perspective_data.get("questions", [])

    return {
        "status": "success",
        "perspective": perspective,
        "theme": theme,
        "questions": questions,
        "message": f"已为「{perspective}」视角生成 {len(questions)} 个深入问题。",
    }


def storm_research_perspective(
    perspective: str,
    questions: str,
    tool_context: ToolContext,
) -> dict:
    """Research a perspective deeply based on the questions (STORM Phase 2).

    Gathers dramatic material from the perspective by exploring the questions,
    producing character archetypes, conflict patterns, and emotional arcs.

    Args:
        perspective: The perspective to research.
        questions: The questions to explore (comma-separated or natural text).

    Returns:
        dict with research findings for this perspective.
    """
    question_list = [q.strip() for q in questions.split("；") if q.strip()]
    if not question_list:
        question_list = [q.strip() for q in questions.split(";") if q.strip()]
    if not question_list:
        question_list = [questions]

    # Simulate research findings based on perspective type
    findings = {
        "角色原型": f"从{perspective}的视角中浮现的角色原型",
        "冲突模式": f"{perspective}视角下揭示的核心冲突模式",
        "情感曲线": f"{perspective}维度中的情感走向和转折点",
        "意象符号": f"{perspective}带来的独特意象和象征",
        "跨视角联系": f"{perspective}与其他视角的共鸣或矛盾",
    }

    # Store research result
    storm_add_research_result(
        perspective_name=perspective,
        questions=question_list,
        findings=findings,
        tool_context=tool_context,
    )

    # Check if all perspectives have been researched
    all_perspectives = storm_get_perspectives(tool_context)
    all_results = storm_get_research_results(tool_context)
    total = len(all_perspectives.get("perspectives", []))
    researched = len(all_results.get("results", []))

    if researched >= total and total > 0:
        # All perspectives researched, transition to outlining
        set_drama_status("setup", tool_context)
        next_msg = (
            f"\n\n所有 {total} 个视角已完成研究！系统将进入大纲合成阶段。"
            "请使用 /next 继续。"
        )
    else:
        next_msg = f"\n\n已完成 {researched}/{total} 个视角的研究。"

    return {
        "status": "success",
        "perspective": perspective,
        "questions_explored": question_list,
        "findings": findings,
        "message": (
            f"「{perspective}」视角研究完成！\n"
            f"探索了 {len(question_list)} 个问题。\n"
            f"发现：角色原型、冲突模式、情感曲线、意象符号、跨视角联系。"
            f"{next_msg}"
        ),
        "phase": "research",
        "progress": f"{researched}/{total}",
    }


def storm_synthesize_outline(theme: str, tool_context: ToolContext) -> dict:
    """Synthesize multi-perspective research into a drama outline (STORM Phase 3).

    Merges findings from all perspectives into a coherent dramatic structure
    with acts, scenes, character arcs, and thematic depth.

    Args:
        theme: The drama theme to synthesize an outline for.

    Returns:
        dict with the synthesized drama outline.
    """
    all_results = storm_get_research_results(tool_context)
    research_results = all_results.get("results", [])

    if not research_results:
        return {
            "status": "error",
            "message": "没有找到研究结果。请先完成 STORM 研究阶段。",
        }

    # Build outline from research results
    perspective_names = [r["perspective"] for r in research_results]
    perspective_findings = {}
    for r in research_results:
        perspective_findings[r["perspective"]] = r.get("findings", {})

    outline = {
        "theme": theme,
        "synthesis_strategy": "多视角辩证融合",
        "acts": [
            {
                "act_number": 1,
                "title": "起——多视角的碰撞",
                "description": (
                    f"从{', '.join(perspective_names[:3])}等视角展开{theme}的初始面貌，"
                    "呈现各视角的碰撞和火花。"
                ),
                "key_conflict": f"{perspective_names[0] if perspective_names else '主角'}与{perspective_names[1] if len(perspective_names) > 1 else '对立面'}的首次交锋",
                "emotional_arc": "好奇 → 紧张 → 震撼",
            },
            {
                "act_number": 2,
                "title": "承——深层的挖掘",
                "description": (
                    f"深入{theme}的深层结构，"
                    "揭示隐藏在多视角背后的共同线索和根本矛盾。"
                ),
                "key_conflict": "表面冲突升级为价值观的对抗",
                "emotional_arc": "紧张 → 压抑 → 爆发",
            },
            {
                "act_number": 3,
                "title": "转——视角的颠覆",
                "description": (
                    f"颠覆初始认知——从意想不到的角度重新解读{theme}，"
                    "所有视角的发现在此汇聚为转折。"
                ),
                "key_conflict": "认知框架的崩塌与重建",
                "emotional_arc": "震惊 → 迷惘 → 觉醒",
            },
            {
                "act_number": 4,
                "title": "合——多视角的统一",
                "description": (
                    f"将所有视角的发现融合为对{theme}的深层理解，"
                    "在统一中保留张力，在和解中留下余韵。"
                ),
                "key_conflict": "对立面的和解或永恒的悬置",
                "emotional_arc": "释然 → 深沉 → 余韵",
            },
        ],
        "core_tensions": [
            f"{p}与其他视角的张力" for p in perspective_names
        ],
        "thematic_layers": {
            "表层": f"{theme}的直接呈现",
            "中层": "人物之间的价值冲突",
            "深层": "关于存在、选择与命运的思考",
        },
        "perspective_integration": {
            p: f"通过角色命运和场景设计体现{p}的洞察"
            for p in perspective_names
        },
    }

    # Store outline in state
    storm_set_outline(outline, tool_context)

    # Transition to acting status
    set_drama_status("acting", tool_context)

    acts_summary = "\n".join(
        f"  第{a['act_number']}幕「{a['title']}」: {a['description'][:60]}..."
        for a in outline["acts"]
    )

    return {
        "status": "success",
        "outline": outline,
        "message": (
            f"STORM 大纲合成完成！「{theme}」的戏剧结构如下：\n\n"
            f"{acts_summary}\n\n"
            f"核心张力: {', '.join(outline['core_tensions'][:3])}\n"
            f"主题层次: {' → '.join(outline['thematic_layers'].keys())}\n\n"
            "现在进入导演阶段——你可以使用 create_actor 创建角色，"
            "然后用 /next 推进第一场戏。"
        ),
        "phase": "outline",
        "next_phase": "directing",
    }


# ============================================================================
# Semantic Retrieval Tools (Phase 3 — MEMORY-05)
# ============================================================================


def retrieve_relevant_scenes_tool(
    tags: str,
    tool_context: ToolContext,
) -> dict:
    """Retrieve relevant scene memories by tags. Use when you need to recall specific past events.

    按标签检索相关历史记忆，导演全局搜索所有演员的记忆。

    Args:
        tags: Comma-separated tags, e.g. "角色:朱棣,情感:愤怒,冲突:权力争夺"

    Returns:
        dict with top-K relevant memories, sorted by relevance score.
    """
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    if not tag_list:
        return {"status": "error", "message": "请提供至少一个标签用于检索。"}

    # Validate tag length (T-03-01)
    for t in tag_list:
        if len(t) > 50:
            return {"status": "error", "message": f"标签过长（{len(t)}字符），限制50字符以内。"}

    state = tool_context.state.get("drama", {})
    current_scene = state.get("current_scene", 0)

    results = retrieve_relevant_scenes(
        tags=tag_list,
        current_scene=current_scene,
        tool_context=tool_context,
        actor_name=None,  # 导演全局搜索 (D-07)
        top_k=5,  # 导演侧 top-5 (D-08)
    )

    # Format results for readability
    formatted = []
    for r in results:
        matched = ", ".join(r.get("matched_tags", []))
        formatted.append(
            f"- 第{r['scenes_covered']}场[{r['source']}]: {r['text'][:150]} (匹配: {matched}, 相关度: {r['score']:.1f})"
        )

    return {
        "status": "success",
        "message": f"找到 {len(results)} 条相关记忆。\n" + "\n".join(formatted),
        "results": results,
    }


async def backfill_tags_tool(tool_context: ToolContext) -> dict:
    """Backfill tags for existing scene summaries that lack tags. Call once when loading an old drama.

    对已有的 scene_summaries 批量生成标签（调用 LLM）。
    执行后标记 tags_backfilled=True，避免重复执行。

    Args:
        tool_context: Tool context for state access.

    Returns:
        dict with backfill status and count of tagged summaries.
    """
    result = await backfill_tags(tool_context)
    return result
