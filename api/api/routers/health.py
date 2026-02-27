"""Health check endpoint (public — no auth required)."""

import logging
import time

import asyncpg
from fastapi import APIRouter, Request

router = APIRouter(tags=["System"])
request_logger = logging.getLogger("jobbot.requests")


@router.get("/api/health")
async def health(request: Request):
    """Check API and database health, return pool stats and uptime."""
    pool = request.app.state.pool
    started_at = getattr(request.app.state, "started_at", None)
    uptime = round(time.monotonic() - started_at) if started_at else None

    pool_stats = {
        "size": pool.get_size(),
        "free": pool.get_idle_size(),
        "used": pool.get_size() - pool.get_idle_size(),
        "min": pool.get_min_size(),
        "max": pool.get_max_size(),
    }

    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {
            "status": "ok",
            "db": True,
            "version": request.app.version,
            "uptime_seconds": uptime,
            "pool": pool_stats,
        }
    except (asyncpg.PostgresError, OSError, TimeoutError) as e:
        request_logger.warning("Health check DB probe failed: %s", e)
        return {
            "status": "degraded",
            "db": False,
            "version": request.app.version,
            "uptime_seconds": uptime,
            "pool": pool_stats,
        }
