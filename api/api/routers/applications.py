"""Application tracking endpoints."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from api.deps import require_editor
from fastapi.responses import JSONResponse

from api.helpers import _ParamBuilder, _rows
from api.models import (
    CreateApplicationRequest,
    UpdateOutcomeRequest,
    UpsertApplicationRequest,
)

router = APIRouter(tags=["Applications"])


@router.get("/api/applications")
async def applications(
    request: Request,
    profile_id: int = Query(..., gt=0),
    min_score: int = Query(0, ge=0, le=100),
    max_score: int = Query(100, ge=0, le=100),
    decision: Literal["All", "YES", "NO", "MAYBE", "MANUAL"] = Query("All"),
    source: str = Query("All"),
    search: str = Query("", max_length=200),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List analyzed jobs with filters for score, decision, source, and text search."""
    pool = request.app.state.pool
    p = _ParamBuilder()
    p.conditions.append(f"ja.profile_id = {p.add(profile_id)}")
    p.conditions.append(f"ja.match_score >= {p.add(min_score)}")
    p.conditions.append(f"ja.match_score <= {p.add(max_score)}")

    if decision != "All":
        p.conditions.append(f"ja.apply_decision = {p.add(decision)}")
    if source != "All":
        p.conditions.append(f"j.source = {p.add(source)}")
    if search:
        like = p.add(f"%{search.lower()}%")
        p.conditions.append(f"(LOWER(j.title) LIKE {like} OR LOWER(j.company) LIKE {like})")

    count_sql = f"""
        SELECT COUNT(*)
        FROM job_analyses ja
        JOIN jobs j ON j.id = ja.job_id
        WHERE {p.where_sql}
    """
    count_params = list(p.params)  # snapshot before LIMIT/OFFSET

    sql = f"""
        SELECT j.id as job_id, j.title, j.company, j.location, j.source,
               j.is_remote, j.job_url, j.date_posted, j.date_scraped,
               ja.match_score, ja.embedding_score, ja.apply_decision,
               ja.skills_matched, ja.skills_missing, ja.ats_keywords,
               ja.gap_tolerant, ja.company_type, ja.route_action,
               ja.cold_email_angle, ja.cover_letter,
               ja.experience_required, ja.red_flags
        FROM job_analyses ja
        JOIN jobs j ON j.id = ja.job_id
        WHERE {p.where_sql}
        ORDER BY ja.match_score DESC, ja.analyzed_at DESC
        LIMIT {p.add(limit)} OFFSET {p.add(offset)}
    """
    async with pool.acquire() as conn:
        total = await conn.fetchval(count_sql, *count_params)
        rows = await conn.fetch(sql, *p.params)
    return JSONResponse(
        content=_rows(rows),
        headers={"X-Total-Count": str(total)},
    )


@router.get("/api/applications/sources")
async def application_sources(request: Request, profile_id: int = Query(..., gt=0)):
    """Get distinct job sources available for filtering."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT DISTINCT j.source FROM job_analyses ja JOIN jobs j ON j.id = ja.job_id WHERE ja.profile_id = $1",
            profile_id,
        )
    sources = sorted(row["source"] for row in rows if row["source"])
    return ["All"] + sources


@router.get("/api/applications/for-update")
async def applications_for_update(request: Request, profile_id: int = Query(..., gt=0)):
    """Get applications with their current outcome status for the update page."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT a.id as app_id, a.job_id, a.method, a.applied_at,
                   a.response_type, a.response_date, a.notes,
                   j.title, j.company, j.job_url,
                   ja.match_score
            FROM applications a
            JOIN jobs j ON j.id = a.job_id
            LEFT JOIN job_analyses ja ON ja.job_id = a.job_id AND ja.profile_id = a.profile_id
            WHERE a.profile_id = $1
            ORDER BY a.applied_at DESC
        """, profile_id)
    return _rows(rows)


@router.get("/api/applications/analyzed-for-update")
async def analyzed_jobs_for_update(request: Request, profile_id: int = Query(..., gt=0)):
    """Get analyzed jobs that don't have an application record yet."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT j.id as job_id, j.title, j.company, j.location, j.job_url,
                   ja.match_score, ja.apply_decision, ja.route_action
            FROM job_analyses ja
            JOIN jobs j ON j.id = ja.job_id
            LEFT JOIN applications a ON a.job_id = j.id AND a.profile_id = ja.profile_id
            WHERE ja.profile_id = $1
            AND ja.apply_decision IN ('YES', 'MAYBE', 'MANUAL')
            AND a.id IS NULL
            ORDER BY ja.match_score DESC
        """, profile_id)
    return _rows(rows)


@router.post("/api/applications", status_code=201, dependencies=[Depends(require_editor)])
async def create_application(request: Request, body: CreateApplicationRequest):
    """Create a new application record (idempotent)."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO applications (job_id, profile_id, method, platform)
               VALUES ($1, $2, $3, $4)
               ON CONFLICT (job_id, profile_id, method) DO NOTHING""",
            body.job_id, body.profile_id, body.method, body.platform,
        )
    return {"status": "created"}


@router.post("/api/applications/upsert", dependencies=[Depends(require_editor)])
async def upsert_application(request: Request, body: UpsertApplicationRequest):
    """Create or update an application with optional outcome info."""
    pool = request.app.state.pool
    rtype = body.response_type or None
    notes = body.notes or None
    has_response = rtype is not None and rtype != ""

    async with pool.acquire() as conn:
        if body.app_id:
            await conn.execute(
                """UPDATE applications SET
                    method = $1, platform = $2,
                    response_type = $3,
                    response_received = $4,
                    notes = $5
                   WHERE id = $6""",
                body.method, body.platform, rtype, has_response, notes, body.app_id,
            )
        else:
            await conn.execute(
                """INSERT INTO applications (job_id, profile_id, method, platform, notes,
                       response_type, response_received)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)
                   ON CONFLICT (job_id, profile_id, method) DO UPDATE SET
                       platform = EXCLUDED.platform,
                       response_type = EXCLUDED.response_type,
                       response_received = EXCLUDED.response_received,
                       notes = EXCLUDED.notes""",
                body.job_id, body.profile_id, body.method, body.platform,
                notes, rtype, has_response,
            )
    return {"status": "ok"}


@router.put("/api/applications/{app_id}/outcome", dependencies=[Depends(require_editor)])
async def update_outcome(request: Request, app_id: int, body: UpdateOutcomeRequest):
    """Record an application outcome (interview, rejection, offer, etc.)."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        result = await conn.execute(
            """UPDATE applications SET
                response_received = true,
                response_type = $1,
                response_date = $2,
                notes = $3
               WHERE id = $4""",
            body.response_type, body.response_date, body.notes, app_id,
        )
    if result.endswith(" 0"):
        raise HTTPException(status_code=404, detail="Application not found")
    return {"status": "ok"}
