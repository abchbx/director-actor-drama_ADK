"""Command-style endpoints for the Drama API.

These endpoints modify drama state by sending commands through the ADK Runner.
Each endpoint:
1. Acquires asyncio.Lock for serial Runner access (STATE-03)
2. Checks for active drama session (except /start)
3. Formats message matching CLI command format
4. Calls run_command_and_collect to execute via Runner
5. Returns structured CommandResponse
DEBUG: All lifecycle events are logged via logging module (server console)
     and optionally pushed as 'director_log' WS events for Android visibility.
"""

import asyncio
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import get_runner, get_runner_lock, get_tool_context, require_auth
from app.api.models import (
    ActionRequest,
    AutoRequest,
    ChatRequest,
    CommandResponse,
    SpeakRequest,
    StartDramaRequest,
    SteerRequest,
    StormRequest,
)
from app.api.runner_utils import run_command_and_collect

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


async def _run_storm_setup(
    runner,
    lock,
    theme: str,
    event_callback,
):
    """Run STORM setup in background after /start has returned immediately.

    This allows Android clients to poll /drama/status while the LLM
    progressively creates actors. The lock serializes access so other
    commands (like /next) block until setup completes — acceptable during
    the setup phase.
    """
    try:
        async with lock:
            logger.info("[DIRECTOR-LOG] 🔄 后台 STORM 开始: /start %s", theme)
            result = await run_command_and_collect(
                runner, f"/start {theme}", USER_ID, SESSION_ID,
                timeout=600.0,
                event_callback=event_callback,
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
    logger.info("[DIRECTOR-LOG] 🎬 === /drama/start 入口 === theme='%s'", theme)

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
        init_result = init_drama_state(theme, tool_context)
        flush_state_sync()
        logger.info(
            "[DIRECTOR-LOG] ✅ 新剧本已初始化: %s", init_result.get("drama_folder", "")
        )

    # Spawn STORM background task — Android will poll /drama/status for progress
    event_callback = _get_event_callback(req)
    asyncio.create_task(_run_storm_setup(runner, lock, theme, event_callback))

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
    runner=Depends(get_runner),
    lock=Depends(get_runner_lock),
    tool_context=Depends(get_tool_context),
):
    """Advance to the next scene."""
    async with lock:
        _require_active_drama(tool_context)
        result = await run_command_and_collect(
            runner, "/next", USER_ID, SESSION_ID,
            event_callback=_get_event_callback(req),
            timeout=300.0,
        )
        return CommandResponse(**result)


@router.post("/drama/action", response_model=CommandResponse)
async def user_action(
    body: ActionRequest,
    req: Request,
    _auth: bool = Depends(require_auth),
    runner=Depends(get_runner),
    lock=Depends(get_runner_lock),
    tool_context=Depends(get_tool_context),
):
    """Inject a user action/event into the drama.

    The user acts as the protagonist (主角).
    ★ 用户气泡由 Android ViewModel 在发送时本地创建，后端不需要推送 user_message 事件。
    """
    async with lock:
        _require_active_drama(tool_context)
        result = await run_command_and_collect(
            runner, f"/action {body.description}", USER_ID, SESSION_ID,
            event_callback=_get_event_callback(req),
        )
        return CommandResponse(**result)


@router.post("/drama/speak", response_model=CommandResponse)
async def actor_speak(
    body: SpeakRequest,
    req: Request,
    _auth: bool = Depends(require_auth),
    runner=Depends(get_runner),
    lock=Depends(get_runner_lock),
    tool_context=Depends(get_tool_context),
):
    """Make a specific actor speak in the current situation."""
    async with lock:
        _require_active_drama(tool_context)
        result = await run_command_and_collect(
            runner,
            f"/speak {body.actor_name} {body.situation}",
            USER_ID,
            SESSION_ID,
            event_callback=_get_event_callback(req),
        )
        return CommandResponse(**result)


@router.post("/drama/steer", response_model=CommandResponse)
async def steer_drama(
    body: SteerRequest,
    req: Request,
    _auth: bool = Depends(require_auth),
    runner=Depends(get_runner),
    lock=Depends(get_runner_lock),
    tool_context=Depends(get_tool_context),
):
    """Steer the drama in a given direction."""
    async with lock:
        _require_active_drama(tool_context)
        result = await run_command_and_collect(
            runner, f"/steer {body.direction}", USER_ID, SESSION_ID,
            event_callback=_get_event_callback(req),
        )
        return CommandResponse(**result)


@router.post("/drama/auto", response_model=CommandResponse)
async def auto_advance(
    body: AutoRequest,
    req: Request,
    _auth: bool = Depends(require_auth),
    runner=Depends(get_runner),
    lock=Depends(get_runner_lock),
    tool_context=Depends(get_tool_context),
):
    """Auto-advance the drama for N scenes (default 3, max 10)."""
    async with lock:
        _require_active_drama(tool_context)
        result = await run_command_and_collect(
            runner, f"/auto {body.num_scenes}", USER_ID, SESSION_ID,
            event_callback=_get_event_callback(req),
        )
        return CommandResponse(**result)


@router.post("/drama/end", response_model=CommandResponse)
async def end_drama(
    req: Request,
    _auth: bool = Depends(require_auth),
    runner=Depends(get_runner),
    lock=Depends(get_runner_lock),
    tool_context=Depends(get_tool_context),
):
    """End the drama with a finale narration."""
    async with lock:
        _require_active_drama(tool_context)
        result = await run_command_and_collect(
            runner, "/end", USER_ID, SESSION_ID,
            event_callback=_get_event_callback(req),
        )
        return CommandResponse(**result)


@router.post("/drama/storm", response_model=CommandResponse)
async def trigger_storm(
    body: StormRequest,
    req: Request,
    _auth: bool = Depends(require_auth),
    runner=Depends(get_runner),
    lock=Depends(get_runner_lock),
    tool_context=Depends(get_tool_context),
):
    """Trigger a STORM perspective discovery."""
    async with lock:
        _require_active_drama(tool_context)
        msg = f"/storm {body.focus}" if body.focus else "/storm"
        result = await run_command_and_collect(
            runner, msg, USER_ID, SESSION_ID,
            event_callback=_get_event_callback(req),
            timeout=300.0,
        )
        return CommandResponse(**result)


@router.post("/drama/chat", response_model=CommandResponse)
async def chat_message(
    body: ChatRequest,
    req: Request,
    _auth: bool = Depends(require_auth),
    runner=Depends(get_runner),
    lock=Depends(get_runner_lock),
    tool_context=Depends(get_tool_context),
):
    """Send a chat message in group chat mode.

    If mention is provided, routes to /speak for that actor.
    Otherwise, routes to /action (broadcast to all actors).
    The user is treated as the protagonist (主角) of the drama.
    ★ 用户气泡由 Android ViewModel 在发送时本地创建，后端不需要推送 user_message 事件。
    """
    async with lock:
        _require_active_drama(tool_context)
        # ★ D-22-03: 注入发送者标识 — 非"导演"时在消息前标注 [sender_name]
        sender_prefix = f"[{body.sender_name}]" if body.sender_name != "导演" else ""
        if body.mention:
            # @提及 → /speak 角色名 情境（含发送者标识）
            msg = f"/speak {body.mention} {sender_prefix}{body.message}".strip()
        else:
            # 群消息 → /action（含发送者标识）
            msg = f"/action {sender_prefix}{body.message}".strip()
        result = await run_command_and_collect(
            runner, msg, USER_ID, SESSION_ID,
            event_callback=_get_event_callback(req),
            timeout=300.0,
        )
        return CommandResponse(**result)
