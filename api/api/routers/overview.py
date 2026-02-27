"""Overview / dashboard KPI endpoint."""

from fastapi import APIRouter, Query, Request

router = APIRouter(tags=["Overview"])


@router.get("/api/overview/stats")
async def overview_stats(request: Request, profile_id: int = Query(..., gt=0)):
    """Return dashboard KPI stats for today, this week, and all-time.

    Uses a single query with subqueries instead of 11 separate round-trips.
    """
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT
                (SELECT COUNT(*) FROM jobs WHERE date_scraped::date = CURRENT_DATE) AS today_jobs,
                (SELECT COUNT(*) FROM job_analyses WHERE profile_id = $1
                    AND analyzed_at::date = CURRENT_DATE) AS today_analyzed,
                (SELECT COUNT(*) FROM email_queue WHERE profile_id = $1
                    AND created_at::date = CURRENT_DATE) AS today_emails,
                (SELECT COUNT(*) FROM applications WHERE profile_id = $1
                    AND applied_at::date = CURRENT_DATE) AS today_applied,
                (SELECT COUNT(*) FROM jobs) AS total_jobs,
                (SELECT COUNT(*) FROM job_analyses WHERE profile_id = $1) AS total_analyzed,
                (SELECT COUNT(*) FROM job_analyses WHERE profile_id = $1
                    AND apply_decision = 'YES') AS total_yes,
                (SELECT COUNT(*) FROM email_queue WHERE profile_id = $1) AS total_emails,
                (SELECT COALESCE(ROUND(AVG(match_score)), 0)
                    FROM job_analyses WHERE profile_id = $1) AS avg_score,
                (SELECT COUNT(DISTINCT job_id)
                    FROM email_queue WHERE profile_id = $1) AS jobs_with_emails,
                (SELECT COUNT(*) FROM jobs
                    WHERE date_scraped >= CURRENT_DATE - INTERVAL '7 days') AS week_jobs
        """, profile_id)

    return {
        "today_jobs": row["today_jobs"],
        "today_analyzed": row["today_analyzed"],
        "today_emails": row["today_emails"],
        "today_applied": row["today_applied"],
        "total_jobs": row["total_jobs"],
        "total_analyzed": row["total_analyzed"],
        "total_yes": row["total_yes"],
        "total_emails": row["total_emails"],
        "jobs_with_emails": row["jobs_with_emails"],
        "avg_score": int(row["avg_score"]),
        "week_jobs": row["week_jobs"],
    }
