"""Query-style endpoint stubs for the Drama API.

These endpoints read drama state directly without going through the ADK Runner.
All endpoints are stubs that return {"message": "not implemented"} until
wired up in subsequent plans.
"""

from fastapi import APIRouter

from app.api.models import (
    CastResponse,
    DramaListResponse,
    DramaStatusResponse,
    ExportRequest,
    ExportResponse,
    LoadRequest,
    SaveLoadResponse,
    SaveRequest,
)

router = APIRouter(tags=["queries"])


@router.get("/drama/status", response_model=DramaStatusResponse)
async def get_status():
    """Get the current drama status."""
    return DramaStatusResponse()


@router.get("/drama/cast", response_model=CastResponse)
async def get_cast():
    """Get the list of actors in the current drama."""
    return CastResponse()


@router.post("/drama/save", response_model=SaveLoadResponse)
async def save_drama(request: SaveRequest):
    """Save the current drama progress."""
    return SaveLoadResponse(message="not implemented")


@router.post("/drama/load", response_model=SaveLoadResponse)
async def load_drama(request: LoadRequest):
    """Load a previously saved drama."""
    return SaveLoadResponse(message="not implemented")


@router.get("/drama/list", response_model=DramaListResponse)
async def list_dramas():
    """List all saved dramas."""
    return DramaListResponse()


@router.post("/drama/export", response_model=ExportResponse)
async def export_drama(request: ExportRequest):
    """Export the drama script."""
    return ExportResponse(message="not implemented")
