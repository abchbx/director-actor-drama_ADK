"""Authentication endpoint for token verification.

D-08: GET /api/v1/auth/verify returns token validity.
"""

import logging

from fastapi import APIRouter, Depends, Request

from app.api.deps import require_auth
from app.api.models import AuthVerifyResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


@router.get("/auth/verify", response_model=AuthVerifyResponse)
async def verify_token(
    request: Request,
    _auth: bool = Depends(require_auth),
):
    """Verify the current token is valid (D-08).

    When auth is enabled: requires valid Bearer token, returns mode="token".
    When auth is disabled (dev mode): automatically passes, returns mode="bypass".
    """
    auth_enabled = getattr(request.app.state, "auth_enabled", False)
    mode = "token" if auth_enabled else "bypass"
    logger.debug(f"Auth verify: mode={mode}")
    return AuthVerifyResponse(valid=True, mode=mode)
