"""Command-style endpoints for the Drama API.

These endpoints modify drama state by sending commands through the ADK Runner.
Each endpoint:
1. Acquires asyncio.Lock for serial Runner access (STATE-03)
2. Checks for active drama session (except /start)
3. Formats message matching CLI command format
4. Calls run_command_and_collect to execute via Runner
5. Returns structured CommandResponse
DEBUG: All endpoints log entry/exit with timing and key parameters.
"""

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

        logger.info("[DIRECTOR-LOG] ⏳ 调用 Runner: /start %s (等待LLM完成全部STORM流程)...", theme)
        result = await run_command_and_collect(
            runner, f"/start {theme}", USER_ID, SESSION_ID,
            event_callback=_get_event_callback(req),
        )
        elapsed = time.monotonic() - t0
        final_resp_preview = (result.get("final_response") or "")[:100]
        tool_count = len(result.get("tool_results", []))
        logger.info(
            "[DIRECTOR-LOG] 🏁 /drama/start 完成! 用时=%.1fs, 工具调用=%d, 响应=%s",
            elapsed, tool_count, final_resp_preview.replace("\n", " "),
        )
        return CommandResponse(**result)


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
    """Inject a user action/event into the drama."""
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
    """
    async with lock:
        _require_active_drama(tool_context)
        if body.mention:
            # @提及 → /speak 角色名 情境
            msg = f"/speak {body.mention} {body.message}"
        else:
            # 群消息 → /action
            msg = f"/action {body.message}"
        result = await run_command_and_collect(
            runner, msg, USER_ID, SESSION_ID,
            event_callback=_get_event_callback(req),
        )
        return CommandResponse(**result)
