"""Startup profile endpoints."""

import json as _json
import logging
from typing import Literal

import asyncpg
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from api.helpers import _ParamBuilder, _parse_date_or_none, _rows
from api.models import SaveStartupProfileRequest

router = APIRouter(tags=["Startup Profiles"])
request_logger = logging.getLogger("jobbot.requests")

_SORT_OPTIONS = Literal["match_score", "founding_date", "data_completeness", "age"]


@router.post("/api/startup-profiles")
async def save_startup_profile(request: Request, body: SaveStartupProfileRequest):
    """Save or update a startup profile. Returns startup_profile_id."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        try:
            sp_id = await conn.fetchval(
                """INSERT INTO startup_profiles (
                    job_id, startup_name, website_url, yc_url, ph_url,
                    founding_date, founding_date_source, age_months,
                    founder_names, founder_emails, founder_roles,
                    employee_count, employee_count_source,
                    one_liner, product_description, tech_stack, topics,
                    has_customers, has_customers_evidence,
                    funding_amount, funding_round, funding_date, funding_source,
                    source, yc_batch, ph_launch_date, ph_votes_count, ph_maker_info, hn_thread_date,
                    llm_extracted, llm_extraction_raw, data_completeness
                ) VALUES (
                    $1, $2, $3, $4, $5,
                    $6, $7, $8,
                    $9, $10, $11,
                    $12, $13,
                    $14, $15, $16, $17,
                    $18, $19,
                    $20, $21, $22, $23,
                    $24, $25, $26, $27, $28, $29,
                    $30, $31, $32
                )
                ON CONFLICT (job_id) DO UPDATE SET
                    startup_name = EXCLUDED.startup_name,
                    website_url = EXCLUDED.website_url,
                    yc_url = EXCLUDED.yc_url,
                    ph_url = EXCLUDED.ph_url,
                    founding_date = EXCLUDED.founding_date,
                    founding_date_source = EXCLUDED.founding_date_source,
                    age_months = EXCLUDED.age_months,
                    founder_names = EXCLUDED.founder_names,
                    founder_emails = EXCLUDED.founder_emails,
                    founder_roles = EXCLUDED.founder_roles,
                    employee_count = EXCLUDED.employee_count,
                    employee_count_source = EXCLUDED.employee_count_source,
                    one_liner = EXCLUDED.one_liner,
                    product_description = EXCLUDED.product_description,
                    tech_stack = EXCLUDED.tech_stack,
                    topics = EXCLUDED.topics,
                    has_customers = EXCLUDED.has_customers,
                    has_customers_evidence = EXCLUDED.has_customers_evidence,
                    funding_amount = EXCLUDED.funding_amount,
                    funding_round = EXCLUDED.funding_round,
                    funding_date = EXCLUDED.funding_date,
                    funding_source = EXCLUDED.funding_source,
                    llm_extracted = EXCLUDED.llm_extracted,
                    llm_extraction_raw = EXCLUDED.llm_extraction_raw,
                    data_completeness = EXCLUDED.data_completeness,
                    updated_at = NOW()
                RETURNING id""",
                body.job_id, body.startup_name, body.website_url, body.yc_url, body.ph_url,
                _parse_date_or_none(body.founding_date), body.founding_date_source, body.age_months,
                body.founder_names, body.founder_emails, body.founder_roles,
                body.employee_count, body.employee_count_source,
                body.one_liner, body.product_description, body.tech_stack, body.topics,
                body.has_customers, body.has_customers_evidence,
                body.funding_amount, body.funding_round,
                _parse_date_or_none(body.funding_date), body.funding_source,
                body.source, body.yc_batch,
                _parse_date_or_none(body.ph_launch_date), body.ph_votes_count, body.ph_maker_info,
                _parse_date_or_none(body.hn_thread_date),
                body.llm_extracted,
                _json.dumps(body.llm_extraction_raw) if body.llm_extraction_raw else None,
                body.data_completeness,
            )
            return {"startup_profile_id": sp_id}
        except asyncpg.PostgresError as e:
            request_logger.error("DB error saving startup profile: %s", e)
            raise HTTPException(status_code=500, detail="Database error saving startup profile") from None


@router.get("/api/startup-profiles")
async def get_startup_profiles(
    request: Request,
    profile_id: int = Query(..., gt=0),
    source: str = Query("All"),
    funding_round: str = Query("All"),
    min_age: int = Query(0, ge=0),
    max_age: int = Query(24, ge=0),
    has_funding: Literal["All", "Yes", "No"] = Query("All"),
    search: str = Query("", max_length=200),
    sort_by: _SORT_OPTIONS = Query("match_score"),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Get startup profiles with associated analysis and email data."""
    pool = request.app.state.pool
    p = _ParamBuilder()
    profile_ph = p.add(profile_id)
    p.conditions.append(f"ja.profile_id = {profile_ph}")

    if source != "All":
        p.conditions.append(f"sp.source = {p.add(source)}")
    if funding_round != "All":
        p.conditions.append(f"sp.funding_round = {p.add(funding_round)}")

    if has_funding == "Yes":
        p.conditions.append("sp.funding_round IS NOT NULL AND sp.funding_round != 'unknown'")
    elif has_funding == "No":
        p.conditions.append(
            "(sp.funding_round IS NULL OR sp.funding_round = 'unknown' OR sp.funding_round = 'bootstrapped')"
        )

    if search:
        like = p.add(f"%{search.lower()}%")
        p.conditions.append(f"(LOWER(sp.startup_name) LIKE {like} OR LOWER(sp.one_liner) LIKE {like})")

    # Age filter — only apply to startups with known age
    age_min_ph = p.add(min_age)
    age_max_ph = p.add(max_age)
    p.conditions.append(f"(sp.age_months IS NULL OR (sp.age_months >= {age_min_ph} AND sp.age_months <= {age_max_ph}))")

    sort_map = {
        "match_score": "ja.match_score DESC NULLS LAST",
        "founding_date": "sp.founding_date DESC NULLS LAST",
        "data_completeness": "sp.data_completeness DESC NULLS LAST",
        "age": "sp.age_months ASC NULLS LAST",
    }
    order_by = sort_map.get(sort_by, "ja.match_score DESC NULLS LAST")

    count_sql = f"""
        SELECT COUNT(*)
        FROM startup_profiles sp
        JOIN jobs j ON j.id = sp.job_id
        LEFT JOIN job_analyses ja ON ja.job_id = sp.job_id AND ja.profile_id = {profile_ph}
        WHERE {p.where_sql}
    """
    count_params = list(p.params)  # snapshot before LIMIT/OFFSET

    sql = f"""
        SELECT sp.*,
               j.company, j.location, j.is_remote, j.job_url, j.date_scraped,
               ja.match_score, ja.apply_decision, ja.cold_email_angle,
               ja.skills_matched AS matching_skills, ja.skills_missing AS missing_skills,
               ja.route_action, ja.gap_framing_for_this_role,
               eq.id AS email_id, eq.status AS email_status,
               eq.recipient_email, eq.recipient_name AS email_recipient_name
        FROM startup_profiles sp
        JOIN jobs j ON j.id = sp.job_id
        LEFT JOIN job_analyses ja ON ja.job_id = sp.job_id AND ja.profile_id = {profile_ph}
        LEFT JOIN LATERAL (
            SELECT id, status, recipient_email, recipient_name
            FROM email_queue
            WHERE job_id = sp.job_id AND profile_id = {profile_ph}
            ORDER BY created_at DESC LIMIT 1
        ) eq ON TRUE
        WHERE {p.where_sql}
        ORDER BY {order_by}
        LIMIT {p.add(limit)} OFFSET {p.add(offset)}
    """
    async with pool.acquire() as conn:
        total = await conn.fetchval(count_sql, *count_params)
        rows = await conn.fetch(sql, *p.params)
    return JSONResponse(
        content=_rows(rows),
        headers={"X-Total-Count": str(total)},
    )


@router.get("/api/startup-profiles/stats")
async def startup_profile_stats(request: Request, profile_id: int = Query(..., gt=0)):
    """Summary stats for startup profiles."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM startup_profiles") or 0
        avg_score = await conn.fetchval(
            """SELECT ROUND(AVG(ja.match_score))
               FROM startup_profiles sp
               JOIN job_analyses ja ON ja.job_id = sp.job_id AND ja.profile_id = $1""",
            profile_id,
        ) or 0
        with_emails = await conn.fetchval(
            """SELECT COUNT(DISTINCT sp.job_id)
               FROM startup_profiles sp
               JOIN email_queue eq ON eq.job_id = sp.job_id AND eq.profile_id = $1""",
            profile_id,
        ) or 0
        avg_completeness = await conn.fetchval(
            "SELECT ROUND(AVG(data_completeness)) FROM startup_profiles"
        ) or 0
        by_source = await conn.fetch(
            "SELECT source, COUNT(*) as count FROM startup_profiles GROUP BY source ORDER BY count DESC"
        )
        by_funding = await conn.fetch(
            """SELECT COALESCE(funding_round, 'unknown') as round, COUNT(*) as count
               FROM startup_profiles GROUP BY funding_round ORDER BY count DESC"""
        )

    return {
        "total": total,
        "avg_score": int(avg_score),
        "with_emails": with_emails,
        "avg_completeness": int(avg_completeness),
        "by_source": {row["source"]: row["count"] for row in by_source if row["source"]},
        "by_funding": {row["round"]: row["count"] for row in by_funding},
    }


@router.get("/api/startup-profiles/sources")
async def startup_profile_sources(request: Request, profile_id: int = Query(..., gt=0)):
    """Get distinct sources for startup profiles."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT DISTINCT source FROM startup_profiles WHERE source IS NOT NULL ORDER BY source"
        )
    return [row["source"] for row in rows]
