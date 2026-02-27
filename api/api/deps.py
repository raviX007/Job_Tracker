"""Shared FastAPI dependencies."""

import logging
import os
import secrets

from fastapi import Header, HTTPException, Request

from core.auth import decode_token

logger = logging.getLogger("jobbot.api")

API_SECRET_KEY = os.getenv("API_SECRET_KEY", "")

if not API_SECRET_KEY:
    logger.warning(
        "API_SECRET_KEY is not set — all requests will bypass authentication. "
        "This is unsafe for production. Set API_SECRET_KEY in your .env file."
    )


async def verify_auth(
    request: Request,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    authorization: str | None = Header(None),
):
    """Accept either X-API-Key (service-to-service) or Bearer JWT (UI).

    Priority:
    1. If X-API-Key is present and valid -> allow (pipeline/service)
    2. If Authorization: Bearer <token> is present and valid -> allow (UI)
    3. If API_SECRET_KEY is not configured -> allow all (local dev)
    4. Otherwise -> 401
    """
    # 1. API key check (service-to-service)
    if x_api_key:
        if not API_SECRET_KEY or secrets.compare_digest(x_api_key, API_SECRET_KEY):
            # API key is valid — but also decode JWT if present so
            # request.state.user_id is available for profile endpoints.
            if authorization and authorization.startswith("Bearer "):
                try:
                    payload = decode_token(authorization[7:])
                    request.state.user_id = payload["sub"]
                    request.state.username = payload["username"]
                except Exception:
                    pass  # API key auth still valid, JWT is optional here
            return
        raise HTTPException(status_code=401, detail="Invalid API key")

    # 2. JWT Bearer check (UI)
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        try:
            payload = decode_token(token)
            request.state.user_id = payload["sub"]
            request.state.username = payload["username"]
            return
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

    # 3. No key configured — local dev bypass
    if not API_SECRET_KEY:
        return

    # 4. No credentials provided
    raise HTTPException(status_code=401, detail="Authentication required")


ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "rajx02")


async def require_editor(request: Request):
    """Block non-admin users from mutating endpoints. Returns 403 for viewers."""
    username = getattr(request.state, "username", None)
    if not username or username != ADMIN_USERNAME:
        raise HTTPException(
            status_code=403,
            detail="View-only access — editing is restricted",
        )


# Backward compatibility alias
verify_api_key = verify_auth
