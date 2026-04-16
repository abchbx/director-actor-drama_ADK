"""Query-style endpoints for the Drama API.

These endpoints read drama state directly without going through the ADK Runner.
They call state_manager functions directly (D-05) for fast, predictable responses.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_tool_context, require_auth
from app.api.models import (
    CastResponse,
    CastStatusResponse,
    DeleteDramaResponse,
    DramaListResponse,
    DramaStatusResponse,
    ExportRequest,
    ExportResponse,
    LoadRequest,
    SaveLoadResponse,
    SaveRequest,
    SceneDetailResponse,
    ScenesResponse,
)
from app.state_manager import (
    delete_drama as delete_drama_fn,
    export_script,
    get_all_actors,
    get_current_state,
    list_dramas,
    load_progress,
    save_progress,
)

router = APIRouter(tags=["queries"])


def _require_active_drama(tool_context):
    """Raise 404 if no active drama session exists."""
    if not tool_context.state.get("drama", {}).get("theme"):
        raise HTTPException(status_code=404, detail="No active drama session")


@router.get("/drama/scenes", response_model=ScenesResponse)
async def get_drama_scenes(
    _auth: bool = Depends(require_auth),
    tool_context=Depends(get_tool_context),
):
    """Get the list of scene summaries for the current drama."""
    _require_active_drama(tool_context)
    from app.state_manager import get_scene_summaries
    result = get_scene_summaries(tool_context)
    return ScenesResponse(**result)


@router.get("/drama/scenes/{scene_number}", response_model=SceneDetailResponse)
async def get_drama_scene_detail(
    scene_number: int,
    _auth: bool = Depends(require_auth),
    tool_context=Depends(get_tool_context),
):
    """Get the full detail of a specific scene."""
    _require_active_drama(tool_context)
    # T-17-08: Validate scene_number range
    if scene_number < 1 or scene_number > 999:
        raise HTTPException(status_code=400, detail="scene_number must be between 1 and 999")
    theme = tool_context.state.get("drama", {}).get("theme", "")
    from app.state_manager import get_scene_detail
    result = get_scene_detail(theme, scene_number)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return SceneDetailResponse(
        scene_number=scene_number,
        title=result.get("title", ""),
        narration=result.get("narration", "") or result.get("content", ""),
        dialogue=result.get("dialogue", []),
        raw=result,
    )


@router.get("/drama/status", response_model=DramaStatusResponse)
async def get_status(
    _auth: bool = Depends(require_auth),
    tool_context=Depends(get_tool_context),
):
    """Get the current drama status."""
    _require_active_drama(tool_context)
    result = get_current_state(tool_context)
    return DramaStatusResponse(**result)


@router.get("/drama/cast", response_model=CastResponse)
async def get_cast(
    _auth: bool = Depends(require_auth),
    tool_context=Depends(get_tool_context),
):
    """Get the list of actors in the current drama."""
    _require_active_drama(tool_context)
    result = get_all_actors(tool_context)
    return CastResponse(**result)


@router.get("/drama/cast/status", response_model=CastStatusResponse)
async def get_cast_status(
    _auth: bool = Depends(require_auth),
    tool_context=Depends(get_tool_context),
):
    """Get A2A process status for each actor."""
    _require_active_drama(tool_context)
    from app.actor_service import list_running_actors
    result = list_running_actors()
    return CastStatusResponse(**result)


@router.post("/drama/save", response_model=SaveLoadResponse)
async def save_drama(
    request: SaveRequest,
    _auth: bool = Depends(require_auth),
    tool_context=Depends(get_tool_context),
):
    """Save the current drama progress."""
    _require_active_drama(tool_context)
    result = save_progress(request.save_name, tool_context)
    # D-04: tool business errors → 200 + status: error
    return SaveLoadResponse(**result)


@router.post("/drama/load", response_model=SaveLoadResponse)
async def load_drama(
    request: LoadRequest,
    _auth: bool = Depends(require_auth),
    tool_context=Depends(get_tool_context),
):
    """Load a previously saved drama."""
    result = load_progress(request.save_name, tool_context)
    return SaveLoadResponse(**result)


@router.get("/drama/list", response_model=DramaListResponse)
async def list_all_dramas(_auth: bool = Depends(require_auth)):
    """List all saved dramas."""
    result = list_dramas()
    return DramaListResponse(**result)


@router.delete("/drama/{folder}", response_model=DeleteDramaResponse)
async def delete_drama(
    folder: str,
    _auth: bool = Depends(require_auth),
):
    """Delete a drama by folder name."""
    # T-17-01: Validate folder name to prevent path traversal
    import re
    if not re.match(r"^[a-zA-Z0-9_\-]+$", folder):
        raise HTTPException(
            status_code=400,
            detail="Invalid folder name: only alphanumeric, underscore, and hyphen allowed",
        )
    result = delete_drama_fn(folder)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return DeleteDramaResponse(**result)


@router.post("/drama/export", response_model=ExportResponse)
async def export_drama(
    request: ExportRequest,
    _auth: bool = Depends(require_auth),
    tool_context=Depends(get_tool_context),
):
    """Export the drama script."""
    _require_active_drama(tool_context)
    result = export_script(tool_context)
    return ExportResponse(**result)
