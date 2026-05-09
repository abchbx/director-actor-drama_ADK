"""Command-style endpoints for the Drama API.

Phase 27: Director-mode commands are now ENQUEUED instead of BLOCKING.
API endpoints return immediately with status="queued" + command_id.
A background CommandQueue worker executes commands serially, holding
runner_lock only during actual execution.

Flow per endpoint (except /start and /free_chat):
1. Checks for active drama session (except /start)
2. Formats message matching CLI command format
3. Enqueues command via CommandQueue (returns < 50ms)
4. Worker dequeues → acquires lock → runs via Runner → pushes WS events
5. Client receives real-time updates via WebSocket

DEBUG: All lifecycle events are logged via logging module (server console)
     and optionally pushed as 'director_log' WS events for Android visibility.
"""

import asyncio
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import (
    get_command_queue,
    get_runner,
    get_runner_lock,
    get_tool_context,
    require_auth,
)
from app.api.models import (
    ActionRequest,
    AutoRequest,
    ChatRequest,
    CommandResponse,
    CommandStatusResponse,
    FreeChatRequest,
    SpeakRequest,
    StartDramaRequest,
    SteerRequest,
    StormRequest,
)
from app.api.runner_utils import run_command_and_collect
from app.free_chat_service import broadcast_free_chat

router = APIRouter(tags=["commands"])

logger = logging.getLogger(__name__)

# Module-level constants matching app.py session configuration
USER_ID = "drama_user"
SESSION_ID = "drama_session"


def _require_active_drama(tool_context):
    """Raise 404 if no active drama session exists."""
    if not tool_context.state.get("drama", {}).get("theme"):
        raise HTTPException(status_code=404, detail="No active drama session")


def _get_event_callback(request: Request):
    """Get event_callback from ConnectionManager if WS clients are connected.

    D-12: REST and WS coexist — event_callback is None when no WS clients.
    D-02: EventBridge is a callback function created by ConnectionManager.
    """
    manager = getattr(request.app.state, "connection_manager", None)
    if manager and manager.active_connections:
        flush_fn = getattr(request.app.state, "flush_state_sync", None)
        return manager.create_broadcast_callback(flush_fn=flush_fn)
    return None


async def _enqueue_director_command(
    command_queue,
    command_text: str,
    request: Request,
) -> CommandResponse:
    """Enqueue a director-mode command and return queued response immediately.

    Phase 27: API endpoints no longer block on runner_lock.
    The CommandQueue worker executes commands serially in the background.
    """
    event_callback = _get_event_callback(request)
    cmd_id = await command_queue.enqueue(command_text, event_callback)
    return CommandResponse(
        status="queued",
        message=f"命令已入队，正在执行...",
        command_id=cmd_id,
    )


async def _run_storm_setup(
    runner,
    lock,
    theme: str,
    request: Request,
    director_style: str = "default",
):
    """Run STORM setup in background after /start has returned immediately.

    This allows Android clients to poll /drama/status while the LLM
    progressively creates actors. The lock serializes access so other
    commands (like /next) block until setup completes — acceptable during
    the setup phase.

    ★ 修复：只创建一次 event_callback，复用同一个 callback 实例。
    因为 create_broadcast_callback 内部有去重状态（_seen_content_keys），
    如果每次事件都创建新实例，去重机制会失效，导致同一事件被推送多次。
    """
    try:
        async with lock:
            logger.info("[DIRECTOR-LOG] 🔄 后台 STORM 开始: /start %s (style=%s)", theme, director_style)
            # ★ 只创建一次 callback 实例，在整个 STORM 过程中复用
            callback = _get_event_callback(request)

            async def _event_callback(event):
                if callback:
                    try:
                        await callback(event)
                    except Exception:
                        pass

            result = await run_command_and_collect(
                runner, f"/start {theme}", USER_ID, SESSION_ID,
                event_callback=_event_callback,
            )
            logger.info(
                "[DIRECTOR-LOG] ✅ 后台 STORM 完成: %s (tools=%d)",
                theme, len(result.get("tool_results", [])),
            )
    except Exception as e:
        logger.error("[DIRECTOR-LOG] 💥 后台 STORM 失败: %s | %s", theme, e)


@router.post("/drama/start", response_model=CommandResponse)
async def start_drama(
    body: StartDramaRequest,
    req: Request,
    _auth: bool = Depends(require_auth),
    runner=Depends(get_runner),
    lock=Depends(get_runner_lock),
    tool_context=Depends(get_tool_context),
):
    """Start a new drama with the given theme.

    D-06: Auto-saves existing drama before starting a new one.

    CRITICAL: Returns immediately after initializing state. STORM setup
    runs in a background task so Android polling clients don't hit 504.
    """
    t0 = time.monotonic()
    theme = body.theme.strip()
    director_style = body.director_style.strip() if body.director_style else "default"
    logger.info("[DIRECTOR-LOG] 🎬 === /drama/start 入口 === theme='%s' style='%s'", theme, director_style)

    async with lock:
        # D-06: auto-save existing drama before starting new one
        drama_state = tool_context.state.get("drama", {})
        if drama_state.get("theme"):
            old_theme = drama_state["theme"]
            logger.info("[DIRECTOR-LOG] 💾 保存旧剧本: '%s' → 开始新创作", old_theme)
            from app.state_manager import save_progress, flush_state_sync

            save_progress(save_name="", tool_context=tool_context)
            flush_state_sync()
            logger.info("[DIRECTOR-LOG] ✅ 旧剧本已保存")

        # ★ 关键修复：立即初始化新剧本状态，不等待 LLM
        from app.state_manager import init_drama_state, flush_state_sync
        init_result = init_drama_state(theme, tool_context, director_style=director_style)
        flush_state_sync()
        logger.info(
            "[DIRECTOR-LOG] ✅ 新剧本已初始化: %s", init_result.get("drama_folder", "")
        )

    # Spawn STORM background task — Android will poll /drama/status for progress
    # ★ 修复：传入 req 对象，让后台任务动态获取 event_callback
    asyncio.create_task(_run_storm_setup(runner, lock, theme, req, director_style))

    elapsed = time.monotonic() - t0
    logger.info(
        "[DIRECTOR-LOG] 🏁 /drama/start 已返回! 用时=%.2fs, 后台 STORM 运行中...", elapsed
    )
    return CommandResponse(
        status="success",
        message=f"剧本「{theme}」已初始化，导演正在后台构思世界观...",
        final_response=f"已开始创作「{theme}」，请稍候...",
        tool_results=[{"status": "success", "message": init_result.get("message", "")}],
    )


@router.post("/drama/next", response_model=CommandResponse)
async def next_scene(
    req: Request,
    _auth: bool = Depends(require_auth),
    command_queue=Depends(get_command_queue),
    tool_context=Depends(get_tool_context),
):
    """Advance to the next scene."""
    _require_active_drama(tool_context)
    return await _enqueue_director_command(command_queue, "/next", req)


@router.post("/drama/action", response_model=CommandResponse)
async def user_action(
    body: ActionRequest,
    req: Request,
    _auth: bool = Depends(require_auth),
    command_queue=Depends(get_command_queue),
    tool_context=Depends(get_tool_context),
):
    """Inject a user action/event into the drama.

    The user acts as the protagonist (主角).
    ★ 用户气泡由 Android ViewModel 在发送时本地创建，后端不需要推送 user_message 事件。
    """
    _require_active_drama(tool_context)
    return await _enqueue_director_command(
        command_queue, f"/action {body.description}", req
    )


@router.post("/drama/speak", response_model=CommandResponse)
async def actor_speak(
    body: SpeakRequest,
    req: Request,
    _auth: bool = Depends(require_auth),
    command_queue=Depends(get_command_queue),
    tool_context=Depends(get_tool_context),
):
    """Make a specific actor speak in the current situation."""
    _require_active_drama(tool_context)
    return await _enqueue_director_command(
        command_queue,
        f"/speak {body.actor_name} {body.situation}",
        req,
    )


@router.post("/drama/steer", response_model=CommandResponse)
async def steer_drama(
    body: SteerRequest,
    req: Request,
    _auth: bool = Depends(require_auth),
    command_queue=Depends(get_command_queue),
    tool_context=Depends(get_tool_context),
):
    """Steer the drama in a given direction."""
    _require_active_drama(tool_context)
    return await _enqueue_director_command(
        command_queue, f"/steer {body.direction}", req
    )


@router.post("/drama/auto", response_model=CommandResponse)
async def auto_advance(
    body: AutoRequest,
    req: Request,
    _auth: bool = Depends(require_auth),
    command_queue=Depends(get_command_queue),
    tool_context=Depends(get_tool_context),
):
    """Auto-advance the drama for N scenes (default 3, max 10)."""
    _require_active_drama(tool_context)
    return await _enqueue_director_command(
        command_queue, f"/auto {body.num_scenes}", req
    )


@router.post("/drama/end", response_model=CommandResponse)
async def end_drama(
    req: Request,
    _auth: bool = Depends(require_auth),
    command_queue=Depends(get_command_queue),
    tool_context=Depends(get_tool_context),
):
    """End the drama with a finale narration."""
    _require_active_drama(tool_context)
    return await _enqueue_director_command(command_queue, "/end", req)


@router.post("/drama/storm", response_model=CommandResponse)
async def trigger_storm(
    body: StormRequest,
    req: Request,
    _auth: bool = Depends(require_auth),
    command_queue=Depends(get_command_queue),
    tool_context=Depends(get_tool_context),
):
    """Trigger a STORM perspective discovery."""
    _require_active_drama(tool_context)
    msg = f"/storm {body.focus}" if body.focus else "/storm"
    return await _enqueue_director_command(command_queue, msg, req)


@router.post("/drama/chat", response_model=CommandResponse)
async def chat_message(
    body: ChatRequest,
    req: Request,
    _auth: bool = Depends(require_auth),
    command_queue=Depends(get_command_queue),
    tool_context=Depends(get_tool_context),
):
    """Send a chat message in group chat mode.

    If mention is provided, routes to /speak for that actor.
    Otherwise, routes to /action (broadcast to all actors).
    The user is treated as the protagonist (主角) of the drama.
    ★ 用户气泡由 Android ViewModel 在发送时本地创建，后端不需要推送 user_message 事件.

    Phase 27: Normal chat messages are queued; /cast is executed directly
    because it is a fast state mutation (no LLM involved).
    """
    _require_active_drama(tool_context)
    # ★ D-22-03: 注入发送者标识 — 非"导演"时在消息前标注 [sender_name]
    sender_prefix = f"[{body.sender_name}]" if body.sender_name != "导演" else ""

    # Phase 24: /cast command — direct set_scene_cast invocation (fast, no queue)
    message_stripped = body.message.strip()
    if message_stripped.startswith("/cast "):
        cast_str = message_stripped[6:].strip()
        cast_list = [name.strip() for name in cast_str.split(",") if name.strip()]
        from app.tools import set_scene_cast
        result = set_scene_cast(cast=cast_list, tool_context=tool_context)
        # Push cast_change WS event if clients are connected
        event_callback = _get_event_callback(req)
        if event_callback and result.get("status") == "success":
            import asyncio
            asyncio.create_task(event_callback({
                "type": "cast_change",
                "data": {
                    "scene_cast": result.get("scene_cast", []),
                    "standby": result.get("standby", []),
                    "message": result.get("message", ""),
                    "sender_type": "director",
                    "sender_name": "旁白",
                },
            }))
        return CommandResponse(
            status=result.get("status", "error"),
            message=result.get("message", ""),
            final_response=result.get("message", ""),
            tool_results=[],
        )

    if body.mention:
        # @提及 → /speak 角色名 情境（含发送者标识）
        msg = f"/speak {body.mention} {sender_prefix}{body.message}".strip()
    else:
        # 群消息 → /action（含发送者标识）
        msg = f"/action {sender_prefix}{body.message}".strip()
    return await _enqueue_director_command(command_queue, msg, req)


@router.post("/drama/free_chat", response_model=CommandResponse)
async def free_chat(
    body: FreeChatRequest,
    req: Request,
    _auth: bool = Depends(require_auth),
    tool_context=Depends(get_tool_context),
):
    """Send a free-chat message directly to actors via A2A (bypassing Director).

    Phase 25: Free chat mode — no ADK Runner involved.
    Messages go straight to actors' independent A2A services.
    """
    _require_active_drama(tool_context)

    drama_state = tool_context.state.get("drama", {})
    # Use scene_cast if available, otherwise fall back to all actors
    scene_cast = drama_state.get("scene_cast")
    if scene_cast:
        target_actors = scene_cast
    else:
        target_actors = list(drama_state.get("actors", {}).keys())

    if not target_actors:
        raise HTTPException(status_code=400, detail="没有活跃演员可供聊天")

    results = await broadcast_free_chat(
        message=body.message,
        target_actors=target_actors,
        sender_name=body.sender_name,
        mention=body.mention,
    )

    # Push dialogue WS events so Android clients receive replies in real-time
    event_callback = _get_event_callback(req)
    if event_callback:
        import asyncio
        for r in results:
            if r.get("status") == "success" and r.get("text"):
                asyncio.create_task(event_callback({
                    "type": "dialogue",
                    "data": {
                        "actor_name": r["actor_name"],
                        "text": r["text"],
                        "emotion": "",
                        "sender_name": r["actor_name"],
                        "sender_type": "actor",
                    },
                }))

    tool_results = [{"actor_name": r["actor_name"], "text": r["text"], "status": r["status"]} for r in results]
    final_response = "\n\n".join(
        f"{r['actor_name']}: {r['text']}" for r in results if r.get("text")
    )

    return CommandResponse(
        status="success",
        message=f"收到 {len(results)} 位演员的回应",
        final_response=final_response or "暂无回应",
        tool_results=tool_results,
    )


@router.get("/drama/command/{command_id}", response_model=CommandStatusResponse)
async def get_command_status(
    command_id: str,
    _auth: bool = Depends(require_auth),
    command_queue=Depends(get_command_queue),
):
    """Poll the status of a previously queued director command (Phase 27).

    Clients without WebSocket can poll this endpoint to retrieve
    the final result after the worker has finished execution.
    """
    cmd = command_queue.get_command(command_id)
    if cmd is None:
        raise HTTPException(status_code=404, detail=f"命令 {command_id} 不存在或已过期")

    elapsed = time.monotonic() - cmd.created_at
    resp = CommandStatusResponse(
        command_id=cmd.id,
        status=cmd.status,
        command_text=cmd.command_text,
        queue_depth=command_queue.queue_depth,
        elapsed_seconds=round(elapsed, 2),
    )

    if cmd.status == "completed" and cmd.result:
        resp.result = cmd.result
    elif cmd.status == "failed":
        resp.error = cmd.error or "未知错误"

    return resp
