"""ATS direct scrapers — Greenhouse, Lever.

Poll dream companies' career pages directly via their public board APIs.
No authentication needed. Returns normalized job dicts.
"""

import json

import httpx

from core.logger import logger
from core.models import ProfileConfig
from scraper.registry import scraper
from scraper.utils import (
    build_skill_set,
    is_short_description,
    parse_date_iso,
    parse_date_timestamp,
    strip_html,
)

# ─── Greenhouse ──────────────────────────────────────────────────────────────

@scraper("greenhouse", group="ats_direct")
async def scrape_greenhouse(
    profile: ProfileConfig,
    limit: int = 20,
) -> list[dict]:
    """Scrape Greenhouse public board API for dream companies.

    GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true
    Free, no auth. Each company has a unique board token (URL slug).
    """
    aggregator_cfg = profile.aggregators.get("greenhouse")
    if aggregator_cfg and not aggregator_cfg.enabled:
        logger.info("Greenhouse: disabled in config, skipping.")
        return []

    # Get board tokens from config — map of company name → greenhouse slug
    greenhouse_boards = _get_greenhouse_boards(profile)
    if not greenhouse_boards:
        logger.info("Greenhouse: no board tokens configured, skipping.")
        return []

    headers = {"User-Agent": "JobApplicationBot/1.0"}

    all_skills = build_skill_set(profile)

    all_jobs = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for company_name, board_token in greenhouse_boards.items():
            try:
                url = (
                    f"https://boards-api.greenhouse.io/v1/boards"
                    f"/{board_token}/jobs?content=true"
                )
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                raw_jobs = data.get("jobs", [])

                count = 0
                for raw in raw_jobs:
                    if count >= limit:
                        break
                    job = _normalize_greenhouse(raw, company_name, all_skills, profile)
                    if job:
                        all_jobs.append(job)
                        count += 1

                logger.info(
                    f"Greenhouse [{company_name}]: {count} relevant "
                    f"(from {len(raw_jobs)} total)"
                )
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    logger.warning(
                        f"Greenhouse [{company_name}]: board '{board_token}' not found (404)"
                    )
                else:
                    logger.error(f"Greenhouse [{company_name}] API failed: {e}")
            except (httpx.RequestError, json.JSONDecodeError) as e:
                logger.error(f"Greenhouse [{company_name}] API failed: {e}")

    logger.info(f"Greenhouse total: {len(all_jobs)} jobs from {len(greenhouse_boards)} companies")
    return all_jobs


def _normalize_greenhouse(
    raw: dict,
    company_name: str,
    relevant_skills: set[str],
    profile: ProfileConfig,
) -> dict | None:
    """Normalize a Greenhouse job object."""
    description = raw.get("content") or ""
    if is_short_description(description):
        return None

    desc_plain = strip_html(description)

    # Relevance check
    title = (raw.get("title") or "").lower()
    desc_lower = desc_plain.lower()

    has_match = any(
        skill in desc_lower or skill in title
        for skill in relevant_skills
    )
    if not has_match:
        return None

    # Skip senior roles
    skip_titles = {s.lower() for s in profile.filters.skip_titles}
    if any(skip in title for skip in skip_titles):
        return None

    # Location
    location_obj = raw.get("location", {})
    location = location_obj.get("name", "") if isinstance(location_obj, dict) else ""

    job_url = raw.get("absolute_url") or ""
    if not job_url:
        return None

    return {
        "title": (raw.get("title") or "").strip(),
        "company": company_name,
        "location": location,
        "source": "greenhouse",
        "discovered_via": "greenhouse_direct",
        "description": desc_plain[:5000],
        "job_url": job_url,
        "date_posted": parse_date_iso(raw.get("updated_at") or raw.get("first_published")),
        "is_remote": "remote" in location.lower() if location else False,
        "salary_min": None,
        "salary_max": None,
        "salary_currency": "INR",
    }


# ─── Lever ───────────────────────────────────────────────────────────────────

@scraper("lever", group="ats_direct")
async def scrape_lever(
    profile: ProfileConfig,
    limit: int = 20,
) -> list[dict]:
    """Scrape Lever public postings API for dream companies.

    GET https://api.lever.co/v0/postings/{company}?mode=json
    Free, no auth. Each company has a unique slug.
    """
    aggregator_cfg = profile.aggregators.get("lever")
    if aggregator_cfg and not aggregator_cfg.enabled:
        logger.info("Lever: disabled in config, skipping.")
        return []

    # Get company slugs from config
    lever_boards = _get_lever_boards(profile)
    if not lever_boards:
        logger.info("Lever: no company slugs configured, skipping.")
        return []

    headers = {"User-Agent": "JobApplicationBot/1.0"}

    all_skills = build_skill_set(profile)

    all_jobs = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for company_name, slug in lever_boards.items():
            try:
                url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                raw_jobs = resp.json()

                if not isinstance(raw_jobs, list):
                    logger.warning(f"Lever [{company_name}]: unexpected response format")
                    continue

                count = 0
                for raw in raw_jobs:
                    if count >= limit:
                        break
                    job = _normalize_lever(raw, company_name, all_skills, profile)
                    if job:
                        all_jobs.append(job)
                        count += 1

                logger.info(
                    f"Lever [{company_name}]: {count} relevant "
                    f"(from {len(raw_jobs)} total)"
                )
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    logger.warning(
                        f"Lever [{company_name}]: slug '{slug}' not found (404)"
                    )
                else:
                    logger.error(f"Lever [{company_name}] API failed: {e}")
            except (httpx.RequestError, json.JSONDecodeError) as e:
                logger.error(f"Lever [{company_name}] API failed: {e}")

    logger.info(f"Lever total: {len(all_jobs)} jobs from {len(lever_boards)} companies")
    return all_jobs


def _normalize_lever(
    raw: dict,
    company_name: str,
    relevant_skills: set[str],
    profile: ProfileConfig,
) -> dict | None:
    """Normalize a Lever job posting."""
    # Lever puts description in "descriptionPlain" or structured "lists"
    description = raw.get("descriptionPlain") or ""
    for lst in raw.get("lists", []):
        description += " " + (lst.get("text") or "")
        description += " " + " ".join(lst.get("content") or "")

    if is_short_description(description):
        return None

    # Relevance check
    title = (raw.get("text") or "").lower()
    desc_lower = description.lower()

    has_match = any(
        skill in desc_lower or skill in title
        for skill in relevant_skills
    )
    if not has_match:
        return None

    # Skip senior roles
    skip_titles = {s.lower() for s in profile.filters.skip_titles}
    if any(skip in title for skip in skip_titles):
        return None

    # Location
    categories = raw.get("categories", {})
    location = categories.get("location", "") if isinstance(categories, dict) else ""

    job_url = raw.get("hostedUrl") or raw.get("applyUrl") or ""
    if not job_url:
        return None

    return {
        "title": (raw.get("text") or "").strip(),
        "company": company_name,
        "location": location,
        "source": "lever",
        "discovered_via": "lever_direct",
        "description": description.strip()[:5000],
        "job_url": job_url,
        "date_posted": parse_date_timestamp(raw.get("createdAt"), milliseconds=True),
        "is_remote": "remote" in location.lower() if location else False,
        "salary_min": None,
        "salary_max": None,
        "salary_currency": "INR",
    }


# ─── Board token mappings ────────────────────────────────────────────────────

def _get_greenhouse_boards(profile: ProfileConfig) -> dict[str, str]:
    """Get Greenhouse board tokens for dream companies.

    Returns dict of {company_name: board_token}.
    Board tokens are the URL slugs companies use on Greenhouse.
    These can be overridden in the aggregator config.
    """
    # Dream companies that use Greenhouse — verified board tokens
    # Flipkart=Darwinbox, Swiggy=HirExp, Atlassian=iCIMS, Zerodha=custom
    known_boards = {
        "Razorpay": "razorpaysoftwareprivatelimited",
        "Groww": "groww",
        "Stripe": "stripe",
        "Coinbase": "coinbase",
        "Figma": "figma",
        "Notion": "notion",
        "Discord": "discord",
        "Cloudflare": "cloudflare",
    }

    # Only include dream companies that have known Greenhouse boards
    boards = {}
    for company in profile.dream_companies:
        if company in known_boards:
            boards[company] = known_boards[company]

    # Allow override via aggregator config custom boards
    aggregator_cfg = profile.aggregators.get("greenhouse")
    if aggregator_cfg and aggregator_cfg.api_key:
        # Use api_key field to store comma-separated "company:slug" pairs
        for pair in aggregator_cfg.api_key.split(","):
            pair = pair.strip()
            if ":" in pair:
                name, slug = pair.split(":", 1)
                boards[name.strip()] = slug.strip()

    return boards


def _get_lever_boards(profile: ProfileConfig) -> dict[str, str]:
    """Get Lever company slugs for dream companies.

    Returns dict of {company_name: lever_slug}.
    """
    # Dream companies that use Lever — verified slugs
    known_boards = {
        "CRED": "cred",
        "Netflix": "netflix",
        "Spotify": "spotify",
    }

    boards = {}
    for company in profile.dream_companies:
        if company in known_boards:
            boards[company] = known_boards[company]

    # Allow override via aggregator config
    aggregator_cfg = profile.aggregators.get("lever")
    if aggregator_cfg and aggregator_cfg.api_key:
        for pair in aggregator_cfg.api_key.split(","):
            pair = pair.strip()
            if ":" in pair:
                name, slug = pair.split(":", 1)
                boards[name.strip()] = slug.strip()

    return boards


# ─── Master function ─────────────────────────────────────────────────────────

async def scrape_all_ats_direct(profile: ProfileConfig, limit: int = 20) -> list[dict]:
    """Run all ATS direct scrapers concurrently and merge results."""
    from scraper.registry import run_group
    return await run_group("ats_direct", profile, limit)
