#!/usr/bin/env python3
"""Startup Scout: Scrape early-stage startups → LLM relevance → cold email founders.

Unlike dry_run.py (which processes formal JDs from job boards), this pipeline:
- Targets startups found on HN, YC, ProductHunt (no formal JDs)
- Does lightweight relevance scoring (no embedding filter)
- Generates founder-to-developer cold emails (peer tone)
- Finds CEO/CTO emails from public domains

All DB writes go through the FastAPI backend (API_BASE_URL).

Usage:
    uv run python scripts/startup_scout.py --source startup_scout --limit 50   # all sources
    uv run python scripts/startup_scout.py --source hn_hiring --limit 20       # HN only
    uv run python scripts/startup_scout.py --source yc_directory --limit 30    # YC only
    uv run python scripts/startup_scout.py --source producthunt --limit 20     # ProductHunt only
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

import httpx

from config.settings import load_settings
from core.api_client import APIClient, ensure_profile
from core.config_loader import load_and_validate_profile
from core.pipeline import StartupScoutPipeline
from core.startup_utils import _build_startup_profile, _compute_completeness  # noqa: F401


def _parse_args() -> tuple[str, int]:
    """Parse --source and --limit from sys.argv."""
    source = "startup_scout"
    limit = 50
    if "--source" in sys.argv:
        source = sys.argv[sys.argv.index("--source") + 1]
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    return source, limit


def _print_results(relevant: list[dict], raw_count: int, new_count: int, emails_queued: int):
    """Print formatted startup scout results."""
    relevant.sort(key=lambda s: s.get("analysis", {}).get("match_score", 0), reverse=True)

    for startup in relevant:
        analysis = startup.get("analysis", {})
        score = analysis.get("match_score", 0)
        decision = analysis.get("apply_decision", "?")
        founder = analysis.get("founder_name", "")

        print(f"\n[{decision:>5}] [{score:3d}] {startup.get('company', 'N/A')}")
        print(f"         Source:   {startup.get('source', 'N/A')}")
        print(f"         Founder:  {founder or 'unknown'} ({analysis.get('founder_role', '')})")
        print(f"         Skills:   {', '.join(analysis.get('matching_skills', []))}")
        print(f"         Angle:    {analysis.get('cold_email_angle', 'N/A')[:100]}")
        if analysis.get("gap_framing_for_this_role"):
            print(f"         Gap:      {analysis['gap_framing_for_this_role'][:100]}")

    yes_count = sum(1 for s in relevant if s.get("analysis", {}).get("apply_decision") == "YES")
    maybe_count = sum(1 for s in relevant if s.get("analysis", {}).get("apply_decision") == "MAYBE")

    print(f"\n{'=' * 60}")
    print(f"SUMMARY: {len(relevant)} relevant startups | YES={yes_count} MAYBE={maybe_count}")
    print(f"Pipeline: {raw_count} scraped → {new_count} new → "
          f"{len(relevant)} relevant → {emails_queued} emails queued")
    print(f"{'=' * 60}")


async def main():
    source, limit = _parse_args()
    settings = load_settings()

    print("=" * 60)
    print("STARTUP SCOUT PIPELINE")
    print("=" * 60)
    print(f"Source: {source}")
    print(f"Limit:  {limit}")
    print()

    # Step 1: Load profile
    profile = load_and_validate_profile(settings.profile_path)
    print(f"[1/6] Profile: {profile.candidate.name}")

    # Step 2: Connect to API
    api_ok = False
    profile_id = None
    api_client = APIClient()
    api_base = api_client.base_url
    print(f"[2/6] Connecting to API at {api_base}...")
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
                print(f"[2/6] API connected (profile_id={profile_id})")
            else:
                print(f"[2/6] API degraded: {health}")
    except Exception as e:
        print(f"[2/6] API connection failed: {e}")
        print("       Cannot proceed without API. Start the API server first.")
        return

    if not api_ok or not profile_id:
        print("\nAPI not available. Exiting.")
        return

    # Create pipeline
    pipeline = StartupScoutPipeline(profile, profile_id, settings)

    # Step 3: Scrape
    print(f"\n[3/6] Scraping startups from '{source}'...")
    raw_startups = await pipeline.scrape(source, limit)
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

    # Print results
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    _print_results(relevant, len(raw_startups), len(startups), emails_queued)

    # Flush Langfuse traces
    from core.langfuse_client import flush
    flush()


if __name__ == "__main__":
    asyncio.run(main())
