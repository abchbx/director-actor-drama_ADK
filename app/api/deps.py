"""FastAPI dependency injection for the Drama API.

Provides shared dependencies that access app.state for runner,
session service, lock, and tool context.
"""

import asyncio

from fastapi import Depends, Request
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from app.api.app import APP_NAME, SESSION_ID, USER_ID


class ToolContextAdapter:
    """Lightweight adapter that wraps session.state dict.

    Mimics ToolContext's `.state` attribute that state_manager functions expect,
    allowing query-style endpoints to call state_manager functions directly.
    """

    def __init__(self, state: dict):
        self.state = state


def get_runner(request: Request) -> Runner:
    """Get the ADK Runner from application state."""
    return request.app.state.runner


def get_session_service(request: Request) -> InMemorySessionService:
    """Get the InMemorySessionService from application state."""
    return request.app.state.session_service


def get_runner_lock(request: Request) -> asyncio.Lock:
    """Get the asyncio Lock for Runner access serialization."""
    return request.app.state.runner_lock


async def get_tool_context(
    session_service: InMemorySessionService = Depends(get_session_service),
) -> ToolContextAdapter:
    """Get a ToolContextAdapter wrapping the current session state.

    Fetches the session from the session service and wraps its state dict
    in a ToolContextAdapter, which exposes the `.state` attribute that
    state_manager functions (e.g., get_current_state, save_progress) expect.
    """
    session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    return ToolContextAdapter(state=session.state)
