"""Pipeline write endpoints — used by the scraping/analysis pipeline."""

import asyncio
import logging
import os
import uuid
from datetime import date

import asyncpg
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from api.deps import require_editor
from api.helpers import _rows
from api.models import (
    DedupCheckRequest,
    EnqueueEmailRequest,
    EnsureProfileRequest,
    PipelineCallbackPayload,
    PipelineRunRequest,
    SaveAnalysisRequest,
    SaveJobRequest,
    UpdateCoverLetterRequest,
    VerifyEmailRequest,
)

router = APIRouter(tags=["Pipeline"])
request_logger = logging.getLogger("jobbot.requests")
pipeline_logger = logging.getLogger("jobbot.pipeline")

PIPELINE_SERVICE_URL = os.getenv("PIPELINE_SERVICE_URL", "http://localhost:8002")


@router.post("/api/profiles/ensure")
async def ensure_profile(request: Request, body: EnsureProfileRequest):
    """Get or create a profile. Returns profile_id."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM profiles WHERE config_path = $1", body.config_path,
        )
        if row:
            return {"profile_id": row["id"]}
        profile_id = await conn.fetchval(
            "INSERT INTO profiles (name, email, config_path) VALUES ($1, $2, $3) RETURNING id",
            body.name, body.email, body.config_path,
        )
    return {"profile_id": profile_id}


@router.post("/api/jobs", status_code=201)
async def save_job(request: Request, body: SaveJobRequest):
    """Save a scraped job. Returns job_id (null if duplicate)."""
    pool = request.app.state.pool
    date_posted = None
    if body.date_posted:
        try:
            date_posted = date.fromisoformat(body.date_posted)
        except ValueError:
            date_posted = None

    async with pool.acquire() as conn:
        try:
            job_id = await conn.fetchval(
                """INSERT INTO jobs (
                    job_url, source, discovered_via, title, company,
                    location, is_remote, description, salary_min, salary_max,
                    salary_currency, date_posted, dedup_key
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                ON CONFLICT (dedup_key) DO NOTHING
                RETURNING id""",
                body.job_url, body.source, body.discovered_via, body.title, body.company,
                body.location, body.is_remote, body.description, body.salary_min, body.salary_max,
                body.salary_currency, date_posted, body.dedup_key,
            )
            return {"job_id": job_id}
        except asyncpg.UniqueViolationError:
            return {"job_id": None}
        except asyncpg.PostgresError as e:
            request_logger.error("DB error saving job: %s", e)
            raise HTTPException(status_code=500, detail="Database error saving job") from None


@router.post("/api/analyses", status_code=201)
async def save_analysis(request: Request, body: SaveAnalysisRequest):
    """Save an LLM analysis. Returns analysis_id."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        try:
            analysis_id = await conn.fetchval(
                """INSERT INTO job_analyses (
                    job_id, profile_id, match_score, embedding_score,
                    skills_required, skills_matched, skills_missing,
                    ats_keywords, experience_required, location_compatible,
                    remote_compatible, company_type, gap_tolerant,
                    red_flags, apply_decision, cold_email_angle,
                    gap_framing_for_this_role, route_action
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                         $11, $12, $13, $14, $15, $16, $17, $18)
                ON CONFLICT (job_id, profile_id) DO UPDATE SET
                    match_score = EXCLUDED.match_score,
                    embedding_score = EXCLUDED.embedding_score,
                    apply_decision = EXCLUDED.apply_decision,
                    analyzed_at = NOW()
                RETURNING id""",
                body.job_id, body.profile_id, body.match_score, body.embedding_score,
                body.skills_required, body.skills_matched, body.skills_missing,
                body.ats_keywords, body.experience_required, body.location_compatible,
                body.remote_compatible, body.company_type, body.gap_tolerant,
                body.red_flags, body.apply_decision, body.cold_email_angle,
                body.gap_framing_for_this_role, body.route_action,
            )
            return {"analysis_id": analysis_id}
        except asyncpg.PostgresError as e:
            request_logger.error("DB error saving analysis: %s", e)
            raise HTTPException(status_code=500, detail="Database error saving analysis") from None


@router.put("/api/analyses/cover-letter")
async def update_cover_letter(request: Request, body: UpdateCoverLetterRequest):
    """Update cover letter for an analysis."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE job_analyses SET cover_letter = $1 WHERE job_id = $2 AND profile_id = $3",
            body.cover_letter, body.job_id, body.profile_id,
        )
    return {"status": "ok"}


@router.post("/api/emails/enqueue", status_code=201)
async def enqueue_email(request: Request, body: EnqueueEmailRequest):
    """Queue a cold email. Returns email_id."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        try:
            email_id = await conn.fetchval(
                """INSERT INTO email_queue (
                    job_id, profile_id,
                    recipient_email, recipient_name, recipient_role, recipient_source,
                    subject, body_html, body_plain, signature, resume_path,
                    email_verified, email_verification_result, email_verification_provider,
                    status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                RETURNING id""",
                body.job_id, body.profile_id,
                body.recipient_email, body.recipient_name, body.recipient_role, body.recipient_source,
                body.subject, body.body_html, body.body_plain, body.signature,
                body.resume_path or None,
                body.email_verified, body.email_verification_result, body.email_verification_provider,
                "draft",
            )
            return {"email_id": email_id}
        except asyncpg.PostgresError as e:
            request_logger.error("DB error enqueueing email: %s", e)
            raise HTTPException(status_code=500, detail="Database error enqueueing email") from None


@router.put("/api/emails/{email_id}/verify")
async def verify_email(request: Request, email_id: int, body: VerifyEmailRequest):
    """Mark an email as verified."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE email_queue SET
                email_verified = true,
                email_verification_result = $1,
                email_verification_provider = $2,
                verified_at = NOW(),
                status = CASE WHEN status = 'draft' THEN 'verified' ELSE status END,
                updated_at = NOW()
               WHERE id = $3""",
            body.verification_result, body.verification_provider, email_id,
        )
    return {"status": "ok"}


@router.put("/api/emails/{email_id}/advance")
async def advance_email(request: Request, email_id: int):
    """Advance an email to 'ready' status."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE email_queue SET status = 'ready', updated_at = NOW()
               WHERE id = $1 AND status IN ('draft', 'verified')""",
            email_id,
        )
    return {"status": "ok"}


@router.post("/api/jobs/dedup-check")
async def dedup_check(request: Request, body: DedupCheckRequest):
    """Check which URLs/dedup_keys already exist in DB."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        existing_keys = []
        existing_urls = []
        if body.dedup_keys:
            rows = await conn.fetch(
                "SELECT dedup_key FROM jobs WHERE dedup_key = ANY($1::text[])",
                body.dedup_keys,
            )
            existing_keys = [row["dedup_key"] for row in rows]
        if body.urls:
            rows = await conn.fetch(
                "SELECT job_url FROM jobs WHERE job_url = ANY($1::text[])",
                body.urls,
            )
            existing_urls = [row["job_url"] for row in rows]
    return {"existing_keys": existing_keys, "existing_urls": existing_urls}


## ─── Async Pipeline Run Endpoints ─────────────────────


async def _check_concurrent_run(pool: asyncpg.Pool, pipeline: str) -> bool:
    """Return True if a run of this pipeline type is already in progress."""
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM pipeline_runs WHERE pipeline = $1 AND status IN ('queued', 'running')",
            pipeline,
        )
    return count > 0


async def _start_pipeline_run(
    request: Request, pipeline: str, body: PipelineRunRequest,
) -> dict:
    """Shared logic for starting a pipeline run via the pipeline microservice."""
    pool = request.app.state.pool

    if await _check_concurrent_run(pool, pipeline):
        raise HTTPException(
            status_code=409,
            detail=f"A {pipeline} pipeline run is already in progress",
        )

    run_id = str(uuid.uuid4())

    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO pipeline_runs (run_id, pipeline, source, job_limit, status)
               VALUES ($1, $2, $3, $4, 'queued')""",
            run_id, pipeline, body.source, body.limit,
        )

    asyncio.create_task(
        _trigger_pipeline_service(request.app, run_id, pipeline, body.source, body.limit)
    )

    return {
        "run_id": run_id,
        "pipeline": pipeline,
        "source": body.source,
        "limit": body.limit,
        "status": "queued",
    }


async def _trigger_pipeline_service(
    app, run_id: str, pipeline: str, source: str, limit: int,
) -> None:
    """Send a run request to the pipeline microservice."""
    pool = app.state.pool
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{PIPELINE_SERVICE_URL}/run",
                json={
                    "run_id": run_id,
                    "pipeline": pipeline,
                    "source": source,
                    "limit": limit,
                },
            )
            if resp.status_code != 202:
                raise Exception(f"Pipeline service returned {resp.status_code}: {resp.text}")
            pipeline_logger.info("Pipeline run %s dispatched to service", run_id)
    except Exception as e:
        pipeline_logger.error("Failed to trigger pipeline service for %s: %s", run_id, e)
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """UPDATE pipeline_runs SET
                           status = 'failed', error = $1, finished_at = NOW()
                       WHERE run_id = $2""",
                    f"Pipeline service unreachable: {e}", run_id,
                )
        except Exception:
            pipeline_logger.exception("Failed to mark run %s as failed", run_id)


@router.post("/api/pipeline/main/run", status_code=202, dependencies=[Depends(require_editor)])
async def run_main_pipeline(request: Request, body: PipelineRunRequest):
    """Start the main pipeline via the pipeline microservice.

    Returns immediately with a run_id for polling.
    """
    return await _start_pipeline_run(request, "main", body)


@router.post("/api/pipeline/startup-scout/run", status_code=202, dependencies=[Depends(require_editor)])
async def run_startup_scout(request: Request, body: PipelineRunRequest):
    """Start the startup scout pipeline via the pipeline microservice.

    Returns immediately with a run_id for polling.
    """
    return await _start_pipeline_run(request, "startup_scout", body)


@router.patch("/api/pipeline/runs/{run_id}/callback")
async def pipeline_callback(request: Request, run_id: str, body: PipelineCallbackPayload):
    """Callback endpoint for the pipeline service to report status updates."""
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM pipeline_runs WHERE run_id = $1", run_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Pipeline run not found")

    # Build dynamic UPDATE from non-null fields
    sets: list[str] = []
    params: list = []
    idx = 1

    if body.status is not None:
        sets.append(f"status = ${idx}")
        params.append(body.status)
        idx += 1

    if body.output is not None:
        sets.append(f"output = ${idx}")
        params.append(body.output)
        idx += 1

    if body.duration_seconds is not None:
        sets.append(f"duration_seconds = ${idx}")
        params.append(body.duration_seconds)
        idx += 1

    if body.return_code is not None:
        sets.append(f"return_code = ${idx}")
        params.append(body.return_code)
        idx += 1

    if body.error is not None:
        sets.append(f"error = ${idx}")
        params.append(body.error)
        idx += 1

    if body.started_at:
        sets.append("started_at = NOW()")

    if body.status in ("completed", "failed"):
        sets.append("finished_at = NOW()")

    if not sets:
        return {"status": "no-op"}

    params.append(run_id)
    query = f"UPDATE pipeline_runs SET {', '.join(sets)} WHERE run_id = ${idx}"

    async with pool.acquire() as conn:
        await conn.execute(query, *params)

    return {"status": "ok"}


@router.get("/api/pipeline/runs")
async def list_pipeline_runs(
    request: Request,
    pipeline: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    """List recent pipeline runs, newest first."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        if pipeline:
            rows = await conn.fetch(
                """SELECT * FROM pipeline_runs
                   WHERE pipeline = $1
                   ORDER BY created_at DESC LIMIT $2""",
                pipeline, limit,
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM pipeline_runs ORDER BY created_at DESC LIMIT $1",
                limit,
            )
    return _rows(rows)


@router.get("/api/pipeline/runs/{run_id}")
async def get_pipeline_run(request: Request, run_id: str):
    """Poll pipeline run status by run_id."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM pipeline_runs WHERE run_id = $1", run_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return _rows([row])[0]
