"""Job management endpoints (obsolete toggle, link check)."""

import httpx as httpx_client
from fastapi import APIRouter, Depends, HTTPException, Request

from api.deps import require_editor

router = APIRouter(tags=["Jobs"])


@router.put("/api/jobs/{job_id}/obsolete", dependencies=[Depends(require_editor)])
async def mark_job_obsolete(request: Request, job_id: int):
    """Toggle a job's obsolete status."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT is_obsolete FROM jobs WHERE id = $1", job_id)
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        new_status = not row["is_obsolete"]
        if new_status:
            await conn.execute(
                "UPDATE jobs SET is_obsolete = true, obsolete_at = NOW() WHERE id = $1", job_id,
            )
        else:
            await conn.execute(
                "UPDATE jobs SET is_obsolete = false, obsolete_at = NULL WHERE id = $1", job_id,
            )
    return {"job_id": job_id, "is_obsolete": new_status}


@router.get("/api/jobs/{job_id}/check-link")
async def check_job_link(request: Request, job_id: int):
    """Check if a job URL is still live."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT job_url FROM jobs WHERE id = $1", job_id)
    if not row or not row["job_url"]:
        raise HTTPException(status_code=404, detail="Job or URL not found")

    try:
        async with httpx_client.AsyncClient(follow_redirects=True, timeout=10) as client:
            resp = await client.head(row["job_url"])
        return {"job_id": job_id, "alive": resp.status_code < 400, "status_code": resp.status_code}
    except (httpx_client.HTTPError, OSError, TimeoutError) as e:
        return {"job_id": job_id, "alive": False, "error": str(e)}
