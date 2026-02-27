"""FastAPI backend — async API layer for the Job Application Agent.

Run: uvicorn api.server:app --reload --port 8000
Docs: http://localhost:8000/docs
"""

import asyncio
import logging
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Ensure project root on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import sentry_sdk

SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=os.getenv("SENTRY_ENVIRONMENT", "development"),
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0")),
        send_default_pii=False,
    )

from core.database import init_db_pool, verify_tables
from api.deps import verify_api_key
from api.routers import (
    health,
    auth,
    profiles,
    overview,
    applications,
    emails,
    analytics,
    tracker,
    jobs,
    pipeline,
    startup_profiles,
)


PIPELINE_TIMEOUT_MINUTES = int(os.getenv("PIPELINE_TIMEOUT_MINUTES", "30"))


async def _reap_stale_runs(pool) -> None:
    """Every 60s, mark pipeline runs stuck in queued/running for >15 min as failed."""
    while True:
        await asyncio.sleep(60)
        try:
            async with pool.acquire() as conn:
                result = await conn.execute(
                    """UPDATE pipeline_runs
                       SET status = 'failed',
                           error = $1,
                           finished_at = NOW()
                       WHERE status IN ('queued', 'running')
                         AND created_at < NOW() - make_interval(mins => $2)""",
                    f"Timed out after {PIPELINE_TIMEOUT_MINUTES} minutes",
                    PIPELINE_TIMEOUT_MINUTES,
                )
                if result and result != "UPDATE 0":
                    logging.getLogger("jobbot.pipeline").warning(
                        "Reaped stale pipeline run (>%d min)", PIPELINE_TIMEOUT_MINUTES,
                    )
        except Exception:
            pass  # Pool might be closing during shutdown


# ─── Lifespan ────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create asyncpg pool on startup, close on shutdown."""
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set in .env")
    pool = await init_db_pool(db_url)
    app.state.pool = pool
    app.state.started_at = time.monotonic()
    await verify_tables(pool)
    # Mark any orphaned pipeline runs (from prior crash/restart) as failed
    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE pipeline_runs
               SET status = 'failed', error = 'Server restarted during run', finished_at = NOW()
               WHERE status IN ('queued', 'running')"""
        )
    # Start background task to timeout stale pipeline runs (15 min)
    reaper = asyncio.create_task(_reap_stale_runs(pool))
    yield
    reaper.cancel()
    await pool.close()


# ─── App Setup ───────────────────────────────────────

app = FastAPI(
    title="Job Application Agent API",
    version="1.0.0",
    description="Async REST API for the job scraping, analysis, and tracking pipeline.",
    lifespan=lifespan,
)

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8501").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key", "Accept", "Authorization"],
    expose_headers=["X-Total-Count", "X-Request-ID"],
)

request_logger = logging.getLogger("jobbot.requests")


# ─── Request Logging Middleware ──────────────────────

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with method, path, status, and duration."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000)
        request_logger.info(
            "%s %s → %s (%dms) [%s]",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        response.headers["X-Request-ID"] = request_id
        return response


app.add_middleware(RequestLoggingMiddleware)


# ─── Security Headers Middleware ───────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["X-DNS-Prefetch-Control"] = "off"
        if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


app.add_middleware(SecurityHeadersMiddleware)


# ─── Global Exception Handlers ──────────────────────

from fastapi import HTTPException  # noqa: E402


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "request_id": request_id},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    request_logger.error(
        "Unhandled exception [%s]: %s %s — %s",
        request_id, request.method, request.url.path, str(exc),
        exc_info=True,
    )
    sentry_sdk.capture_exception(exc)  # no-op if SDK not initialized
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id},
    )


# ─── Rate Limiting ──────────────────────────────────

from slowapi import Limiter, _rate_limit_exceeded_handler  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402
from slowapi.util import get_remote_address  # noqa: E402

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ─── Include Routers ────────────────────────────────

# Public routers (no auth)
app.include_router(health.router)
app.include_router(auth.router)

# All other routers require API key or JWT
_auth = [Depends(verify_api_key)]
app.include_router(profiles.router, dependencies=_auth)
app.include_router(overview.router, dependencies=_auth)
app.include_router(applications.router, dependencies=_auth)
app.include_router(emails.router, dependencies=_auth)
app.include_router(analytics.router, dependencies=_auth)
app.include_router(tracker.router, dependencies=_auth)
app.include_router(jobs.router, dependencies=_auth)
app.include_router(pipeline.router, dependencies=_auth)
app.include_router(startup_profiles.router, dependencies=_auth)
