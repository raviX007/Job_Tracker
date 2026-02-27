"""Tracker spreadsheet-view endpoint."""

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from api.helpers import _rows

router = APIRouter(tags=["Tracker"])


@router.get("/api/tracker")
async def tracker_data(
    request: Request,
    profile_id: int = Query(..., gt=0),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Get actionable jobs with application status for the tracker spreadsheet."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        total = await conn.fetchval("""
            SELECT COUNT(*)
            FROM job_analyses ja
            JOIN jobs j ON j.id = ja.job_id
            WHERE ja.profile_id = $1
            AND ja.apply_decision IN ('YES', 'MAYBE', 'MANUAL')
        """, profile_id)

        rows = await conn.fetch("""
            SELECT j.id as job_id, j.title, j.company, j.location, j.source,
                   j.is_remote, j.job_url, j.is_obsolete,
                   ja.match_score, ja.apply_decision, ja.route_action,
                   ja.skills_matched, ja.skills_missing, ja.embedding_score,
                   a.id as app_id,
                   a.method as app_method,
                   a.platform as app_platform,
                   a.applied_at,
                   a.response_type,
                   a.notes as app_notes
            FROM job_analyses ja
            JOIN jobs j ON j.id = ja.job_id
            LEFT JOIN applications a ON a.job_id = j.id AND a.profile_id = ja.profile_id
            WHERE ja.profile_id = $1
            AND ja.apply_decision IN ('YES', 'MAYBE', 'MANUAL')
            ORDER BY ja.match_score DESC
            LIMIT $2 OFFSET $3
        """, profile_id, limit, offset)

    return JSONResponse(
        content=_rows(rows),
        headers={"X-Total-Count": str(total)},
    )
