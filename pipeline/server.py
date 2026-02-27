"""Pipeline microservice — runs heavy pipeline workloads, reports status to API via callback.

Run:
    uvicorn server:app --port 8002
    uvicorn server:app --reload --port 8002  (dev)
"""

import asyncio
import io
import json
import logging
import os
import sys
import time
from contextlib import asynccontextmanager

import httpx
from dotenv import load_dotenv

load_dotenv()

import sentry_sdk

SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=os.getenv("SENTRY_ENVIRONMENT", "development"),
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0")),
        send_default_pii=False,
    )

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from config.settings import load_settings
from core.api_client import APIClient, ensure_profile
from core.config_loader import load_and_validate_profile, load_profile_from_api
from core.pipeline import JobPipeline, StartupScoutPipeline
from scraper.dedup import make_dedup_key

logger = logging.getLogger("jobbot.pipeline-server")

# ─── Request Model ───────────────────────────────────


class RunRequest(BaseModel):
    run_id: str
    pipeline: str       # "main" or "startup_scout"
    source: str
    limit: int


# ─── State ───────────────────────────────────────────

active_runs: dict[str, str] = {}  # run_id -> pipeline type


# ─── Lifespan ────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()

    # Try DB-backed profile first (if PROFILE_ID is set)
    profile = None
    if settings.profile_id:
        profile = await load_profile_from_api(
            settings.profile_id, settings.api_base_url, settings.api_secret_key,
        )

    # Fall back to YAML file
    if not profile:
        profile = load_and_validate_profile(settings.profile_path)

    app.state.settings = settings
    app.state.profile = profile
    logger.info("Pipeline server ready (profile: %s)", profile.candidate.name)
    yield


app = FastAPI(title="Pipeline Runner", version="1.0.0", lifespan=lifespan)


# ─── Endpoints ───────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "active_runs": len(active_runs)}


@app.post("/run", status_code=202)
async def start_run(body: RunRequest):
    if body.pipeline not in ("main", "startup_scout"):
        raise HTTPException(400, f"Unknown pipeline: {body.pipeline}")

    for rid, ptype in active_runs.items():
        if ptype == body.pipeline:
            raise HTTPException(409, f"Pipeline '{body.pipeline}' already running (run_id={rid})")

    active_runs[body.run_id] = body.pipeline
    asyncio.create_task(_execute_pipeline(body))
    return {"status": "accepted", "run_id": body.run_id}


# ─── Callback Reporter ──────────────────────────────

async def _report_status(
    api_base_url: str, api_key: str, run_id: str, payload: dict, retries: int = 3,
):
    """Send status update back to the API with retry."""
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.patch(
                    f"{api_base_url}/api/pipeline/runs/{run_id}/callback",
                    json=payload,
                    headers={"X-API-Key": api_key, "Content-Type": "application/json"},
                )
                resp.raise_for_status()
                return
        except Exception as e:
            if attempt == retries - 1:
                logger.error("All callback retries failed for %s: %s", run_id, e)
                sentry_sdk.capture_exception(e)
            else:
                await asyncio.sleep(2 ** attempt)


# ─── Sample Jobs Loader ─────────────────────────────

async def _load_sample_jobs(count: int) -> list[dict]:
    """Load sample JDs from test fixtures."""
    fixtures_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "tests", "fixtures", "sample_jds.json",
    )
    with open(fixtures_path) as f:
        jobs = json.load(f)

    for job in jobs:
        job["discovered_via"] = "sample"
        job["is_remote"] = "remote" in (job.get("location") or "").lower()
        job["salary_min"] = None
        job["salary_max"] = None
        job["salary_currency"] = None
        job["dedup_key"] = make_dedup_key(job)

    return jobs[:count]


# ─── Main Pipeline Execution ────────────────────────

async def _run_main_pipeline(
    req: RunRequest, profile, profile_id: int, settings,
) -> None:
    """Run the main pipeline with stage-by-stage output (mirrors dry_run.py)."""
    pipeline = JobPipeline(profile, profile_id, settings)

    print("=" * 60)
    print("DRY RUN PIPELINE")
    print("=" * 60)
    print(f"Source: {req.source}")
    print(f"Limit:  {req.limit}")
    print(f"DRY_RUN: {settings.dry_run}")
    print()
    print(f"[1/8] Profile: {profile.candidate.name}")
    print(f"[2/8] API connected (profile_id={profile_id})")

    # Step 3: Scrape
    print(f"\n[3/8] Scraping from '{req.source}'...")
    if req.source == "sample":
        raw_jobs = await _load_sample_jobs(req.limit)
    else:
        raw_jobs = await pipeline.scrape(req.source, req.limit)
    print(f"       Scraped: {len(raw_jobs)} jobs")

    if not raw_jobs:
        print("\nNo jobs found. Exiting.")
        return

    # Step 4: Dedup
    jobs = await pipeline.dedup(raw_jobs)
    print(f"[4/8] After dedup: {len(jobs)} jobs")

    # Step 5: Pre-filter
    filtered, filtered_out = pipeline.prefilter(jobs)
    print(f"[5/8] After pre-filters: {len(filtered)} passed, {len(filtered_out)} filtered")

    if not filtered:
        print("\nAll jobs filtered out. Exiting.")
        return

    # Step 6: Embedding filter
    print("\n[6/8] Running embedding filter (loading model on first run)...")
    passed, embed_filtered = await pipeline.embed(filtered)
    print(f"       Embedding: {len(passed)} passed, {len(embed_filtered)} filtered")

    if not passed:
        print("\nNo jobs passed embedding filter. Try lowering fast_filter_threshold.")
        return

    # Step 7: LLM analysis
    print(f"\n[7/8] Running LLM analysis on {len(passed)} jobs...")
    analyzed = await pipeline.analyze(passed)
    print(f"       Analyzed: {len(analyzed)} jobs")

    # Save via API
    saved = await pipeline.save(analyzed)
    print(f"\n       Saved {saved} jobs + analyses via API")

    # Step 8: Generate emails
    if not settings.dry_run:
        print("\n[8/8] Generating cold emails...")
    else:
        print("\n[8/8] Generating cold emails (DRY_RUN=true, emails still queued as drafts)...")

    emails_queued = await pipeline.generate_emails(analyzed)
    print(f"\n       Emails queued: {emails_queued}")

    # Results summary
    analyzed.sort(key=lambda j: j.get("analysis", {}).get("match_score") or 0, reverse=True)
    for job in analyzed:
        analysis = job.get("analysis", {})
        score = analysis.get("match_score") or 0
        decision = analysis.get("apply_decision", "?")
        route = job.get("route_action", "?")

        indicators = {"YES": "[YES]", "MAYBE": "[MBY]", "MANUAL": "[MAN]"}
        indicator = indicators.get(decision, "[NO ]")

        print(f"\n{indicator} [{score:3d}] {job.get('title', 'N/A')}")
        print(f"         Company:  {job.get('company', 'N/A')}")
        print(f"         Location: {job.get('location', 'N/A')}")
        print(f"         Route:    {route}")
        print(f"         Embed:    {job.get('embedding_score', 'N/A')}")
        print(f"         Matching: {', '.join(analysis.get('matching_skills', []))}")
        print(f"         Missing:  {', '.join(analysis.get('missing_skills', []))}")
        if analysis.get("cold_email_angle"):
            print(f"         Email:    {analysis['cold_email_angle'][:100]}")

    yes_count = sum(1 for j in analyzed if j.get("analysis", {}).get("apply_decision") == "YES")
    maybe_count = sum(1 for j in analyzed if j.get("analysis", {}).get("apply_decision") == "MAYBE")
    no_count = sum(1 for j in analyzed if j.get("analysis", {}).get("apply_decision") == "NO")
    manual_count = sum(1 for j in analyzed if j.get("analysis", {}).get("apply_decision") == "MANUAL")

    print(f"\n{'=' * 60}")
    print(f"SUMMARY: {len(analyzed)} analyzed | YES={yes_count} MAYBE={maybe_count} MANUAL={manual_count} NO={no_count}")
    print(f"Pipeline: {len(raw_jobs)} scraped → {len(filtered)} pre-filtered → {len(passed)} embed-passed → {len(analyzed)} analyzed")
    print(f"{'=' * 60}")

    # Flush Langfuse traces
    from core.langfuse_client import flush
    flush()


# ─── Startup Scout Pipeline Execution ───────────────

async def _run_startup_scout(
    req: RunRequest, profile, profile_id: int, settings,
) -> None:
    """Run the startup scout pipeline with stage-by-stage output (mirrors startup_scout.py)."""
    pipeline = StartupScoutPipeline(profile, profile_id, settings)

    print("=" * 60)
    print("STARTUP SCOUT PIPELINE")
    print("=" * 60)
    print(f"Source: {req.source}")
    print(f"Limit:  {req.limit}")
    print()
    print(f"[1/6] Profile: {profile.candidate.name}")
    print(f"[2/6] API connected (profile_id={profile_id})")

    # Step 3: Scrape
    print(f"\n[3/6] Scraping startups from '{req.source}'...")
    raw_startups = await pipeline.scrape(req.source, req.limit)
    print(f"       Scraped: {len(raw_startups)} startups")

    if not raw_startups:
        print("\nNo startups found. Exiting.")
        return

    # Step 4: Dedup
    startups = await pipeline.dedup(raw_startups)
    print(f"[4/6] After dedup: {len(startups)} new startups")

    if not startups:
        print("\nAll startups already in database. Exiting.")
        return

    # Step 5: LLM analysis + save
    print(f"\n[5/6] Running LLM relevance analysis on {len(startups)} startups...")
    relevant, email_eligible = await pipeline.analyze_and_save(startups)
    print(f"       Relevant: {len(relevant)} / {len(startups)}")
    print(f"       Email eligible: {len(email_eligible)} (age filter applied)")

    if not relevant:
        print("\nNo relevant startups found. Exiting.")
        return

    # Step 6: Find emails + generate cold emails
    print("\n[6/6] Finding founder emails + generating cold emails...")
    emails_queued = await pipeline.find_and_email(email_eligible)

    # Results summary
    relevant.sort(key=lambda s: s.get("analysis", {}).get("match_score") or 0, reverse=True)
    for startup in relevant:
        analysis = startup.get("analysis", {})
        score = analysis.get("match_score") or 0
        decision = analysis.get("apply_decision", "?")
        founder = analysis.get("founder_name", "")

        print(f"\n[{decision:>5}] [{score:3d}] {startup.get('company', 'N/A')}")
        print(f"         Source:   {startup.get('source', 'N/A')}")
        print(f"         Founder:  {founder or 'unknown'} ({analysis.get('founder_role', '')})")
        print(f"         Skills:   {', '.join(analysis.get('matching_skills', []))}")
        print(f"         Angle:    {analysis.get('cold_email_angle', 'N/A')[:100]}")

    yes_count = sum(1 for s in relevant if s.get("analysis", {}).get("apply_decision") == "YES")
    maybe_count = sum(1 for s in relevant if s.get("analysis", {}).get("apply_decision") == "MAYBE")

    print(f"\n{'=' * 60}")
    print(f"SUMMARY: {len(relevant)} relevant startups | YES={yes_count} MAYBE={maybe_count}")
    print(f"Pipeline: {len(raw_startups)} scraped → {len(startups)} new → "
          f"{len(relevant)} relevant → {emails_queued} emails queued")
    print(f"{'=' * 60}")

    # Flush Langfuse traces
    from core.langfuse_client import flush
    flush()


# ─── Orchestrator ────────────────────────────────────

async def _execute_pipeline(req: RunRequest) -> None:
    """Run the requested pipeline, capture stdout, report progress via callbacks."""
    settings = app.state.settings
    profile = app.state.profile
    api_base_url = settings.api_base_url
    api_key = settings.api_secret_key
    start_time = time.monotonic()
    captured = io.StringIO()
    old_stdout = sys.stdout

    try:
        # Report: running
        await _report_status(api_base_url, api_key, req.run_id, {
            "status": "running",
            "started_at": True,
        })

        # Get profile_id: use DB profile ID if set, otherwise ensure via API
        if settings.profile_id:
            profile_id = settings.profile_id
        else:
            async with APIClient() as api:
                profile_id = await api.ensure_profile(
                    profile.candidate.name,
                    profile.candidate.email,
                    settings.profile_path,
                )

        # Redirect stdout to capture print output
        sys.stdout = captured
        output_snapshot = ""

        async def periodic_flush():
            """Flush captured output to API every 5 seconds."""
            nonlocal output_snapshot
            while True:
                await asyncio.sleep(5)
                current = captured.getvalue()
                if current != output_snapshot:
                    output_snapshot = current
                    await _report_status(api_base_url, api_key, req.run_id, {
                        "output": output_snapshot,
                    })

        flush_task = asyncio.create_task(periodic_flush())

        try:
            if req.pipeline == "main":
                await _run_main_pipeline(req, profile, profile_id, settings)
            elif req.pipeline == "startup_scout":
                await _run_startup_scout(req, profile, profile_id, settings)
        finally:
            sys.stdout = old_stdout
            flush_task.cancel()
            try:
                await flush_task
            except asyncio.CancelledError:
                pass

        duration = round(time.monotonic() - start_time, 2)
        full_output = captured.getvalue()

        await _report_status(api_base_url, api_key, req.run_id, {
            "status": "completed",
            "output": full_output,
            "duration_seconds": duration,
            "return_code": 0,
        })

        logger.info("Pipeline run %s completed (%.1fs)", req.run_id, duration)

    except Exception as e:
        duration = round(time.monotonic() - start_time, 2)
        full_output = captured.getvalue() if captured else ""
        logger.exception("Pipeline run %s failed: %s", req.run_id, e)
        sentry_sdk.capture_exception(e)

        # Restore stdout if still redirected
        if sys.stdout is not sys.__stdout__ and sys.stdout is not old_stdout:
            sys.stdout = sys.__stdout__

        await _report_status(api_base_url, api_key, req.run_id, {
            "status": "failed",
            "output": full_output,
            "duration_seconds": duration,
            "error": str(e),
        })

    finally:
        active_runs.pop(req.run_id, None)
