"""Command-style endpoint stubs for the Drama API.

These endpoints modify drama state by sending commands through the ADK Runner.
All endpoints are stubs that return {"message": "not implemented"} until
wired up in subsequent plans.
"""

from fastapi import APIRouter

from app.api.models import (
    ActionRequest,
    AutoRequest,
    CommandResponse,
    SpeakRequest,
    StartDramaRequest,
    SteerRequest,
    StormRequest,
)

router = APIRouter(tags=["commands"])


@router.post("/drama/start", response_model=CommandResponse)
async def start_drama(request: StartDramaRequest):
    """Start a new drama with the given theme."""
    return CommandResponse(message="not implemented")


@router.post("/drama/next", response_model=CommandResponse)
async def next_scene():
    """Advance to the next scene."""
    return CommandResponse(message="not implemented")


@router.post("/drama/action", response_model=CommandResponse)
async def user_action(request: ActionRequest):
    """Inject a user action/event into the drama."""
    return CommandResponse(message="not implemented")


@router.post("/drama/speak", response_model=CommandResponse)
async def actor_speak(request: SpeakRequest):
    """Make a specific actor speak in the current situation."""
    return CommandResponse(message="not implemented")


@router.post("/drama/steer", response_model=CommandResponse)
async def steer_drama(request: SteerRequest):
    """Steer the drama in a given direction."""
    return CommandResponse(message="not implemented")


@router.post("/drama/auto", response_model=CommandResponse)
async def auto_advance(request: AutoRequest):
    """Auto-advance the drama for N scenes."""
    return CommandResponse(message="not implemented")


@router.post("/drama/end", response_model=CommandResponse)
async def end_drama():
    """End the drama with a finale narration."""
    return CommandResponse(message="not implemented")


@router.post("/drama/storm", response_model=CommandResponse)
async def trigger_storm(request: StormRequest):
    """Trigger a STORM perspective discovery."""
    return CommandResponse(message="not implemented")
