"""FastAPI app factory with lifespan, CORS, and API versioning.

Creates a FastAPI application that wraps the root_agent from app.agent,
providing REST API access without modifying any of the 12 core modules.
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from app.actor_service import stop_all_actor_services
from app.agent import root_agent
from app.api.lock import acquire_lock, release_lock
from app.api.routers import commands, queries
from app.state_manager import flush_state_sync

# Constants matching CLI session configuration
APP_NAME = "app"
USER_ID = "drama_user"
SESSION_ID = "drama_session"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage Runner lifecycle: create on startup, cleanup on shutdown."""
    # Startup: acquire lock file (D-07/STATE-03)
    acquire_lock()

    # Create session service, session, and runner
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    # Store on app.state for dependency injection
    app.state.runner = runner
    app.state.session_service = session_service
    app.state.runner_lock = asyncio.Lock()

    # STATE-02: flush-on-push hook for Phase 14 WebSocket
    app.state.flush_before_push = True
    app.state.flush_state_sync = flush_state_sync

    yield

    # Shutdown: flush state, release lock, and stop actor services
    flush_state_sync()  # Ensure final state is written
    release_lock()  # D-07
    stop_all_actor_services()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI instance with CORS middleware and mounted routers.
    """
    app = FastAPI(
        title="Director-Actor Drama API",
        version="2.0.0",
        lifespan=lifespan,
    )

    # CORS middleware (API-05): dev mode uses wildcard, production restricts
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount routers with API versioning prefix (API-04)
    app.include_router(commands.router, prefix="/api/v1")
    app.include_router(queries.router, prefix="/api/v1")

    return app
