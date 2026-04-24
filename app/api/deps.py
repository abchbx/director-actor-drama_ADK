"""FastAPI dependency injection for the Drama API.

Provides shared dependencies that access app.state for runner,
session service, lock, tool context, and auth verification.
"""

import asyncio
import logging

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

logger = logging.getLogger(__name__)

# Session constants — defined locally to avoid circular import with app.py
APP_NAME = "app"
USER_ID = "drama_user"
SESSION_ID = "drama_session"


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
    if session is None:
        await session_service.create_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
        )

    # CRITICAL: InMemorySessionService.get_session() returns a deepcopy.
    # Writing to session.state only modifies the copy and is lost for subsequent
    # requests. We must reference the internal session object directly so that
    # state_manager functions (e.g., init_drama_state -> _set_state) persist.
    internal_session = (
        session_service.sessions
        .get(APP_NAME, {})
        .get(USER_ID, {})
        .get(SESSION_ID)
    )
    if internal_session is None:
        raise RuntimeError("Internal session not found after creation")

    return ToolContextAdapter(state=internal_session.state)


# HTTPBearer scheme for Swagger UI auto-detection (AUTH-04)
_bearer_scheme = HTTPBearer(auto_error=False)


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> bool:
    """Validate Bearer token against app.state.api_token (AUTH-04, D-01~D-06).

    - D-05: No API_TOKEN → auth disabled (dev mode), all requests pass
    - D-06: Dev mode logs WARNING at startup + debug per-request
    - D-12: Static token, no expiry/refresh
    - D-16: Auth events logged to Python logger
    - AUTH-04: FastAPI HTTPBearer dependency injection

    Returns True on success. Raises HTTPException(401) on invalid token.
    """
    # D-05: Dev mode bypass — no API_TOKEN configured
    auth_enabled = getattr(request.app.state, "auth_enabled", False)
    if not auth_enabled:
        logger.debug("Auth bypass: no API_TOKEN configured (dev mode)")
        return True

    # Auth enabled: credentials must be present
    if credentials is None:
        logger.warning("Auth failed: missing Authorization header")
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Validate token against app.state.api_token (D-03)
    api_token = getattr(request.app.state, "api_token", None)
    if credentials.credentials != api_token:
        logger.warning("Auth failed: invalid token")
        raise HTTPException(status_code=401, detail="Invalid token")

    logger.debug("Auth succeeded: valid token")
    return True
