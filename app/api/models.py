"""Pydantic v2 request/response models for the Drama API.

Defines all 14 endpoint request/response schemas with field validation,
plus WebSocket event models for real-time scene push.
"""

from datetime import datetime

from pydantic import BaseModel, Field


# ============================================================================
# Request models
# ============================================================================


class StartDramaRequest(BaseModel):
    """Request to start a new drama."""

    theme: str = Field(..., min_length=1, max_length=200, description="Drama theme/premise")


class ActionRequest(BaseModel):
    """Request to inject a user action into the drama."""

    description: str = Field(..., min_length=1, description="Action description to inject")


class SpeakRequest(BaseModel):
    """Request to make a specific actor speak."""

    actor_name: str = Field(..., min_length=1, description="Name of the actor to speak")
    situation: str = Field(..., min_length=1, description="Situation context for the actor")


class SteerRequest(BaseModel):
    """Request to steer the drama in a direction."""

    direction: str = Field(..., min_length=1, description="Direction guidance for next scene")


class AutoRequest(BaseModel):
    """Request to auto-advance the drama."""

    num_scenes: int = Field(default=3, ge=1, le=10, description="Number of scenes to auto-advance")


class StormRequest(BaseModel):
    """Request to trigger a STORM perspective discovery."""

    focus: str | None = Field(default=None, description="Optional focus area for STORM discovery")


class ChatRequest(BaseModel):
    """Request to send a chat message in group chat mode.

    If mention is provided, routes to /speak for that actor.
    Otherwise, routes to /action (broadcast to all actors).
    """

    message: str = Field(..., min_length=1, description="Chat message text")
    mention: str | None = Field(default=None, description="Optional @mention actor name")


class SaveRequest(BaseModel):
    """Request to save drama progress."""

    save_name: str = Field(default="", description="Optional name for save snapshot")


class LoadRequest(BaseModel):
    """Request to load a previously saved drama."""

    save_name: str = Field(..., min_length=1, description="Name of save to load (theme or snapshot)")


class ExportRequest(BaseModel):
    """Request to export the drama script."""

    format: str = Field(default="markdown", description="Export format (markdown)")


# ============================================================================
# Response models
# ============================================================================


class CommandResponse(BaseModel):
    """Response for command-style endpoints (D-02/D-03)."""

    final_response: str = Field(default="", description="Director's final text response")
    tool_results: list[dict] = Field(default_factory=list, description="Structured results from tool calls")
    status: str = Field(default="success")
    message: str = Field(default="", description="Status message")


class DramaStatusResponse(BaseModel):
    """Response for drama status query."""

    theme: str = ""
    drama_status: str = ""
    current_scene: int = 0
    num_scenes: int = 0
    num_actors: int = 0
    actors: list[str] = Field(default_factory=list)
    drama_folder: str = ""
    arc_progress: list[dict] = Field(default_factory=list, description="Per-actor arc progress")
    time_period: str = Field(default="", description="Current time period description")
    has_outline: bool = Field(default=False, description="Whether STORM outline has been synthesized")


class CastResponse(BaseModel):
    """Response for cast query."""

    status: str = "success"
    actors: dict = Field(default_factory=dict)


class CastStatusResponse(BaseModel):
    """Response for cast A2A process status."""

    status: str = "success"
    actors: dict = Field(default_factory=dict, description="Per-actor A2A status: {name: {pid, running, port}}")


class SaveLoadResponse(BaseModel):
    """Response for save/load operations."""

    status: str = "success"
    message: str = ""
    theme: str = ""
    drama_status: str = ""
    current_scene: int = 0
    num_actors: int = 0
    num_scenes: int = 0
    actors_list: list[str] = Field(default_factory=list)


class DramaListResponse(BaseModel):
    """Response for drama list query."""

    dramas: list[dict] = Field(default_factory=list)


class SceneSummaryItem(BaseModel):
    """Summary item for a single scene in the scenes list."""

    scene_number: int
    title: str = ""
    description: str = ""


class ScenesResponse(BaseModel):
    """Response for the scene list query."""

    scenes: list[SceneSummaryItem] = Field(default_factory=list)
    total: int = 0


class SceneDetailResponse(BaseModel):
    """Response for a single scene detail query."""

    scene_number: int = 0
    title: str = ""
    narration: str = ""
    dialogue: list[dict] = Field(default_factory=list)
    raw: dict = Field(default_factory=dict)


class DeleteDramaResponse(BaseModel):
    """Response for drama delete operation."""

    status: str = "success"
    message: str = ""


class ExportResponse(BaseModel):
    """Response for drama export."""

    status: str = "success"
    message: str = ""
    export_path: str = ""


class ErrorResponse(BaseModel):
    """Error response."""

    detail: str


class AuthVerifyResponse(BaseModel):
    """Response for auth token verification (D-08)."""

    valid: bool = Field(default=True, description="Whether the token is valid")
    mode: str = Field(default="token", description="Auth mode: 'token' or 'bypass'")


# ============================================================================
# WebSocket event models (Phase 14)
# ============================================================================


class MessageSender(BaseModel):
    """消息发送者标识 — 三方消息体系（导演/演员/用户）.

    sender_type:
      - "director": 导演/旁白
      - "actor": 演员（附带 actor_name）
      - "user": 用户/主角
    """

    sender_type: str = Field(
        ..., description="发送者类型: director, actor, user"
    )
    sender_name: str = Field(
        default="", description="发送者名称（导演=旁白, 演员=角色名, 用户=主角）"
    )


class WsEvent(BaseModel):
    """WebSocket event message for real-time scene push (WS-02)."""

    type: str = Field(..., description="Event type (one of 18 business types)")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    data: dict = Field(default_factory=dict, description="Event payload")


class ReplayMessage(BaseModel):
    """Replay buffer message sent on WS connection (D-09)."""

    type: str = "replay"
    events: list[dict] = Field(default_factory=list)


class HeartbeatMessage(BaseModel):
    """Application-level heartbeat (D-14)."""

    type: str = "ping"
