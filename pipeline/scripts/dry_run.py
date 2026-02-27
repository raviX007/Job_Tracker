#!/usr/bin/env python3
"""Dry run: Full pipeline — scrape → dedup → pre-filter → embed → LLM analyze → save via API.

No applications submitted, no emails sent. Just scrapes, scores, and logs results.
All DB writes go through the FastAPI backend (API_BASE_URL).

Usage:
    uv run python scripts/dry_run.py --limit 10
    uv run python scripts/dry_run.py --source sample --limit 5
    uv run python scripts/dry_run.py --source jobspy --limit 10
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

import httpx

from config.settings import load_settings
from core.api_client import APIClient, ensure_profile
from core.config_loader import load_and_validate_profile
from core.pipeline import JobPipeline
from scraper.dedup import make_dedup_key


async def load_sample_jobs(count: int) -> list[dict]:
    """Load sample JDs from test fixtures."""
    fixtures_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "tests", "fixtures", "sample_jds.json"
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


def _parse_args() -> tuple[str, int]:
    """Parse --source and --limit from sys.argv."""
    source = "sample"
    limit = 10
    if "--source" in sys.argv:
        source = sys.argv[sys.argv.index("--source") + 1]
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    return source, limit


def _print_results(analyzed: list[dict], raw_count: int, filtered_count: int, passed_count: int):
    """Print formatted pipeline results."""
    analyzed.sort(key=lambda j: j.get("analysis", {}).get("match_score", 0), reverse=True)

    for job in analyzed:
        analysis = job.get("analysis", {})
        score = analysis.get("match_score", 0)
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
        if analysis.get("gap_framing_for_this_role"):
            print(f"         Gap:      {analysis['gap_framing_for_this_role'][:100]}")

    # Summary
    yes_count = sum(1 for j in analyzed if j.get("analysis", {}).get("apply_decision") == "YES")
    maybe_count = sum(1 for j in analyzed if j.get("analysis", {}).get("apply_decision") == "MAYBE")
    no_count = sum(1 for j in analyzed if j.get("analysis", {}).get("apply_decision") == "NO")
    manual_count = sum(1 for j in analyzed if j.get("analysis", {}).get("apply_decision") == "MANUAL")

    print(f"\n{'=' * 60}")
    print(f"SUMMARY: {len(analyzed)} analyzed | YES={yes_count} MAYBE={maybe_count} MANUAL={manual_count} NO={no_count}")
    print(f"Pipeline: {raw_count} scraped → {filtered_count} pre-filtered → {passed_count} embed-passed → {len(analyzed)} analyzed")
    print(f"{'=' * 60}")


async def main():
    source, limit = _parse_args()
    settings = load_settings()

    print("=" * 60)
    print("DRY RUN PIPELINE")
    print("=" * 60)
    print(f"Source: {source}")
    print(f"Limit:  {limit}")
    print(f"DRY_RUN: {settings.dry_run}")
    print()

    # Step 1: Load profile
    profile = load_and_validate_profile(settings.profile_path)
    print(f"[1/8] Profile: {profile.candidate.name}")

    # Step 2: Connect to API
    api_ok = False
    profile_id = None
    api_client = APIClient()
    api_base = api_client.base_url
    print(f"[2/8] Connecting to API at {api_base}...")
    try:
        async with httpx.AsyncClient(base_url=api_base, timeout=60) as client:
            resp = await client.get("/api/health", headers=api_client._headers())
            health = resp.json()
            if health.get("status") == "ok":
                api_ok = True
                profile_id = await ensure_profile(
                    profile.candidate.name,
                    profile.candidate.email, settings.profile_path,
                )
                print(f"[2/8] API connected (profile_id={profile_id})")
            else:
                print(f"[2/8] API degraded: {health} — will skip save operations")
    except Exception as e:
        print(f"[2/8] API connection failed: {e} — will skip save operations")

    if not api_ok or not profile_id:
        print("\nAPI not available. Cannot proceed.")
        return

    # Create pipeline and run staged
    pipeline = JobPipeline(profile, profile_id, settings)

    # Step 3: Scrape
    print(f"\n[3/8] Scraping from '{source}'...")
    if source == "sample":
        raw_jobs = await load_sample_jobs(limit)
    else:
        raw_jobs = await pipeline.scrape(source, limit)
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

    # Print results
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    _print_results(analyzed, len(raw_jobs), len(filtered), len(passed))

    # Flush Langfuse traces
    from core.langfuse_client import flush
    flush()


if __name__ == "__main__":
    asyncio.run(main())
