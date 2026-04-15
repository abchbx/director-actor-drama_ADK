"""Command-style endpoints for the Drama API.

These endpoints modify drama state by sending commands through the ADK Runner.
Each endpoint:
1. Acquires asyncio.Lock for serial Runner access (STATE-03)
2. Checks for active drama session (except /start)
3. Formats message matching CLI command format
4. Calls run_command_and_collect to execute via Runner
5. Returns structured CommandResponse
"""

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_runner, get_runner_lock, get_tool_context
from app.api.models import (
    ActionRequest,
    AutoRequest,
    CommandResponse,
    SpeakRequest,
    StartDramaRequest,
    SteerRequest,
    StormRequest,
)
from app.api.runner_utils import run_command_and_collect

router = APIRouter(tags=["commands"])

# Module-level constants matching app.py session configuration
USER_ID = "drama_user"
SESSION_ID = "drama_session"


def _require_active_drama(tool_context):
    """Raise 404 if no active drama session exists."""
    if not tool_context.state.get("drama", {}).get("theme"):
        raise HTTPException(status_code=404, detail="No active drama session")


@router.post("/drama/start", response_model=CommandResponse)
async def start_drama(
    request: StartDramaRequest,
    runner=Depends(get_runner),
    lock=Depends(get_runner_lock),
    tool_context=Depends(get_tool_context),
):
    """Start a new drama with the given theme.

    D-06: Auto-saves existing drama before starting a new one.
    """
    async with lock:
        # D-06: auto-save existing drama before starting new one
        drama_state = tool_context.state.get("drama", {})
        if drama_state.get("theme"):
            from app.state_manager import save_progress, flush_state_sync

            save_progress(save_name="", tool_context=tool_context)
            flush_state_sync()

        result = await run_command_and_collect(
            runner, f"/start {request.theme}", USER_ID, SESSION_ID
        )
        return CommandResponse(**result)


@router.post("/drama/next", response_model=CommandResponse)
async def next_scene(
    runner=Depends(get_runner),
    lock=Depends(get_runner_lock),
    tool_context=Depends(get_tool_context),
):
    """Advance to the next scene."""
    async with lock:
        _require_active_drama(tool_context)
        result = await run_command_and_collect(
            runner, "/next", USER_ID, SESSION_ID
        )
        return CommandResponse(**result)


@router.post("/drama/action", response_model=CommandResponse)
async def user_action(
    request: ActionRequest,
    runner=Depends(get_runner),
    lock=Depends(get_runner_lock),
    tool_context=Depends(get_tool_context),
):
    """Inject a user action/event into the drama."""
    async with lock:
        _require_active_drama(tool_context)
        result = await run_command_and_collect(
            runner, f"/action {request.description}", USER_ID, SESSION_ID
        )
        return CommandResponse(**result)


@router.post("/drama/speak", response_model=CommandResponse)
async def actor_speak(
    request: SpeakRequest,
    runner=Depends(get_runner),
    lock=Depends(get_runner_lock),
    tool_context=Depends(get_tool_context),
):
    """Make a specific actor speak in the current situation."""
    async with lock:
        _require_active_drama(tool_context)
        result = await run_command_and_collect(
            runner,
            f"/speak {request.actor_name} {request.situation}",
            USER_ID,
            SESSION_ID,
        )
        return CommandResponse(**result)


@router.post("/drama/steer", response_model=CommandResponse)
async def steer_drama(
    request: SteerRequest,
    runner=Depends(get_runner),
    lock=Depends(get_runner_lock),
    tool_context=Depends(get_tool_context),
):
    """Steer the drama in a given direction."""
    async with lock:
        _require_active_drama(tool_context)
        result = await run_command_and_collect(
            runner, f"/steer {request.direction}", USER_ID, SESSION_ID
        )
        return CommandResponse(**result)


@router.post("/drama/auto", response_model=CommandResponse)
async def auto_advance(
    request: AutoRequest,
    runner=Depends(get_runner),
    lock=Depends(get_runner_lock),
    tool_context=Depends(get_tool_context),
):
    """Auto-advance the drama for N scenes (default 3, max 10)."""
    async with lock:
        _require_active_drama(tool_context)
        result = await run_command_and_collect(
            runner, f"/auto {request.num_scenes}", USER_ID, SESSION_ID
        )
        return CommandResponse(**result)


@router.post("/drama/end", response_model=CommandResponse)
async def end_drama(
    runner=Depends(get_runner),
    lock=Depends(get_runner_lock),
    tool_context=Depends(get_tool_context),
):
    """End the drama with a finale narration."""
    async with lock:
        _require_active_drama(tool_context)
        result = await run_command_and_collect(
            runner, "/end", USER_ID, SESSION_ID
        )
        return CommandResponse(**result)


@router.post("/drama/storm", response_model=CommandResponse)
async def trigger_storm(
    request: StormRequest,
    runner=Depends(get_runner),
    lock=Depends(get_runner_lock),
    tool_context=Depends(get_tool_context),
):
    """Trigger a STORM perspective discovery."""
    async with lock:
        _require_active_drama(tool_context)
        msg = f"/storm {request.focus}" if request.focus else "/storm"
        result = await run_command_and_collect(runner, msg, USER_ID, SESSION_ID)
        return CommandResponse(**result)
