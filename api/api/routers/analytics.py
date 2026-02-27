"""Analytics and data visualization endpoints."""

from fastapi import APIRouter, Query, Request

from api.helpers import _rows

router = APIRouter(tags=["Analytics"])


@router.get("/api/analytics/daily-trends")
async def daily_trends(request: Request, profile_id: int = Query(..., gt=0), days: int = Query(30, ge=1, le=365)):
    """Get daily counts of jobs scraped, analyzed, and emails queued."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            WITH dates AS (
                SELECT generate_series(
                    CURRENT_DATE - $2 * INTERVAL '1 day',
                    CURRENT_DATE,
                    '1 day'
                )::date as dt
            )
            SELECT d.dt as date,
                   COALESCE(j.job_count, 0) as jobs_scraped,
                   COALESCE(a.analyzed_count, 0) as jobs_analyzed,
                   COALESCE(e.email_count, 0) as emails_queued
            FROM dates d
            LEFT JOIN (
                SELECT date_scraped::date as dt, COUNT(*) as job_count
                FROM jobs GROUP BY dt
            ) j ON j.dt = d.dt
            LEFT JOIN (
                SELECT analyzed_at::date as dt, COUNT(*) as analyzed_count
                FROM job_analyses WHERE profile_id = $1 GROUP BY dt
            ) a ON a.dt = d.dt
            LEFT JOIN (
                SELECT created_at::date as dt, COUNT(*) as email_count
                FROM email_queue WHERE profile_id = $1 GROUP BY dt
            ) e ON e.dt = d.dt
            ORDER BY d.dt
        """, profile_id, days)
    return _rows(rows)


@router.get("/api/analytics/score-distribution")
async def score_distribution(request: Request, profile_id: int = Query(..., gt=0)):
    """Get match score distribution grouped into brackets."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                CASE
                    WHEN match_score >= 80 THEN '80-100 (High)'
                    WHEN match_score >= 60 THEN '60-79 (Good)'
                    WHEN match_score >= 40 THEN '40-59 (Maybe)'
                    ELSE '0-39 (Low)'
                END as bracket,
                COUNT(*) as count
            FROM job_analyses
            WHERE profile_id = $1
            GROUP BY bracket
            ORDER BY bracket
        """, profile_id)
    return _rows(rows)


@router.get("/api/analytics/source-breakdown")
async def source_breakdown(request: Request, profile_id: int = Query(..., gt=0)):
    """Get job counts, average scores, and YES counts per source."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT j.source, COUNT(*) as count,
                   ROUND(AVG(ja.match_score)) as avg_score,
                   SUM(CASE WHEN ja.apply_decision = 'YES' THEN 1 ELSE 0 END) as yes_count
            FROM job_analyses ja
            JOIN jobs j ON j.id = ja.job_id
            WHERE ja.profile_id = $1
            GROUP BY j.source
            ORDER BY count DESC
        """, profile_id)
    return _rows(rows)


@router.get("/api/analytics/company-types")
async def company_types(request: Request, profile_id: int = Query(..., gt=0)):
    """Get analysis counts and scores grouped by company type."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT company_type, COUNT(*) as count,
                   ROUND(AVG(match_score)) as avg_score,
                   SUM(CASE WHEN gap_tolerant THEN 1 ELSE 0 END) as gap_tolerant_count
            FROM job_analyses
            WHERE profile_id = $1 AND company_type IS NOT NULL
            GROUP BY company_type
            ORDER BY count DESC
        """, profile_id)
    return _rows(rows)


@router.get("/api/analytics/response-rates")
async def response_rates(request: Request, profile_id: int = Query(..., gt=0)):
    """Get application response rates grouped by method."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT method,
                   COUNT(*) as total,
                   SUM(CASE WHEN response_received THEN 1 ELSE 0 END) as responded,
                   SUM(CASE WHEN response_type = 'interview' THEN 1 ELSE 0 END) as interviews,
                   SUM(CASE WHEN response_type = 'rejection' THEN 1 ELSE 0 END) as rejections,
                   SUM(CASE WHEN response_type = 'offer' THEN 1 ELSE 0 END) as offers
            FROM applications
            WHERE profile_id = $1
            GROUP BY method
        """, profile_id)
    return _rows(rows)


@router.get("/api/analytics/route-breakdown")
async def route_breakdown(request: Request, profile_id: int = Query(..., gt=0)):
    """Get route action distribution for actionable jobs."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT ja.route_action, COUNT(*) as count
               FROM job_analyses ja
               WHERE ja.profile_id = $1 AND ja.apply_decision IN ('YES', 'MAYBE', 'MANUAL')
               GROUP BY ja.route_action""",
            profile_id,
        )
    if not rows:
        return {}
    return {(row["route_action"] or "unknown"): row["count"] for row in rows}
