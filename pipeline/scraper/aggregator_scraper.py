"""Aggregator scrapers — Jooble, RemoteOK, Adzuna, HiringCafe.

These are API-based scrapers (no browser needed). Each returns normalized
job dicts matching the same format as JobSpy output.

All use httpx async client. Gracefully skip if API keys are missing.
"""

import json
import os
import urllib.parse

import httpx

from core.logger import logger
from core.models import ProfileConfig
from scraper.registry import scraper
from scraper.utils import (
    build_skill_set,
    is_short_description,
    parse_date_iso,
    parse_salary_value,
    strip_html,
)


@scraper("remoteok", group="aggregators")
async def scrape_remoteok(profile: ProfileConfig, limit: int = 30) -> list[dict]:
    """Scrape RemoteOK — free JSON API, no key needed.

    GET https://remoteok.com/api — returns JSON array.
    First item is metadata (skip it). Rest are job objects.
    """
    aggregator_cfg = profile.aggregators.get("remoteok")
    if aggregator_cfg and not aggregator_cfg.enabled:
        logger.info("RemoteOK: disabled in config, skipping.")
        return []

    url = "https://remoteok.com/api"
    headers = {"User-Agent": "JobApplicationBot/1.0"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, json.JSONDecodeError) as e:
        logger.error(f"RemoteOK API failed: {e}")
        return []

    if not data or len(data) < 2:
        logger.info("RemoteOK: no jobs returned.")
        return []

    # First item is metadata, skip it
    raw_jobs = data[1:]

    # Filter by relevant tags/keywords from profile
    all_skills = build_skill_set(profile)
    all_skills |= {"web developer", "data engineer"}

    jobs = []
    for raw in raw_jobs:  # Check ALL jobs, not just first N
        job = _normalize_remoteok(raw, all_skills)
        if job:
            jobs.append(job)
            if len(jobs) >= limit:
                break

    logger.info(f"RemoteOK: {len(jobs)} relevant jobs found (from {len(raw_jobs)} total)")
    return jobs


def _normalize_remoteok(raw: dict, relevant_skills: set[str]) -> dict | None:
    """Normalize a RemoteOK job object."""
    description = raw.get("description") or ""
    if is_short_description(description):
        return None

    # Check relevance — at least one tag should match our skills
    tags = [t.lower() for t in (raw.get("tags") or [])]
    position = (raw.get("position") or "").lower()
    desc_lower = description.lower()

    has_match = any(
        skill in desc_lower or skill in position or skill in tags
        for skill in relevant_skills
    )
    if not has_match:
        return None

    date_posted = parse_date_iso(raw.get("date"))

    job_url = raw.get("url") or raw.get("apply_url") or ""
    if job_url and not job_url.startswith("http"):
        job_url = f"https://remoteok.com{job_url}"

    return {
        "title": (raw.get("position") or "").strip(),
        "company": (raw.get("company") or "").strip(),
        "location": "Remote",
        "source": "remoteok",
        "discovered_via": "remoteok",
        "description": description.strip(),
        "job_url": job_url,
        "date_posted": date_posted,
        "is_remote": True,
        "salary_min": parse_salary_value(raw.get("salary_min")),
        "salary_max": parse_salary_value(raw.get("salary_max")),
        "salary_currency": "USD",
    }


@scraper("jooble", group="aggregators", needs_key="JOOBLE_API_KEY")
async def scrape_jooble(
    profile: ProfileConfig,
    limit: int = 20,
) -> list[dict]:
    """Scrape Jooble — free API, 500 requests/day.

    POST https://jooble.org/api/{api_key}
    Body: {"keywords": "...", "location": "...", "page": 1}
    """
    api_key = os.getenv("JOOBLE_API_KEY", "")
    aggregator_cfg = profile.aggregators.get("jooble")

    if aggregator_cfg and not aggregator_cfg.enabled:
        logger.info("Jooble: disabled in config, skipping.")
        return []

    if not api_key:
        logger.info("Jooble: no API key set (JOOBLE_API_KEY), skipping.")
        return []

    url = f"https://jooble.org/api/{api_key}"
    search_terms = [
        f"{s} developer" for s in profile.skills.primary[:2]
    ] + ["software developer"]
    # Jooble only works with country-level locations (cities return 0)
    locations = ["India"]

    all_jobs = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for keyword in search_terms:
            for location in locations:
                try:
                    body = {
                        "keywords": keyword,
                        "location": location,
                        "page": 1,
                    }
                    resp = await client.post(url, json=body)
                    resp.raise_for_status()
                    data = resp.json()
                    raw_jobs = data.get("jobs", [])

                    for raw in raw_jobs[:limit]:
                        job = _normalize_jooble(raw)
                        if job:
                            all_jobs.append(job)

                    logger.info(
                        f"Jooble: '{keyword}' in '{location}' → {len(raw_jobs)} results"
                    )
                except (httpx.HTTPError, json.JSONDecodeError) as e:
                    logger.error(f"Jooble API failed for '{keyword}' in '{location}': {e}")

    logger.info(f"Jooble total: {len(all_jobs)} jobs")
    return all_jobs


def _normalize_jooble(raw: dict) -> dict | None:
    """Normalize a Jooble job object."""
    description = raw.get("snippet") or ""
    if is_short_description(description):
        return None

    job_url = raw.get("link") or ""
    if not job_url:
        return None

    return {
        "title": (raw.get("title") or "").strip(),
        "company": (raw.get("company") or "").strip(),
        "location": (raw.get("location") or "").strip(),
        "source": "jooble",
        "discovered_via": "jooble",
        "description": strip_html(description),
        "job_url": job_url,
        "date_posted": parse_date_iso(raw.get("updated")),
        "is_remote": "remote" in (raw.get("location") or "").lower(),
        "salary_min": parse_salary_value(raw.get("salary_min")),
        "salary_max": parse_salary_value(raw.get("salary_max")),
        "salary_currency": "INR",
    }


@scraper("adzuna", group="aggregators", needs_key="ADZUNA_APP_ID")
async def scrape_adzuna(
    profile: ProfileConfig,
    limit: int = 20,
) -> list[dict]:
    """Scrape Adzuna — free tier, country='in' (India).

    GET https://api.adzuna.com/v1/api/jobs/{country}/search/{page}
    """
    app_id = os.getenv("ADZUNA_APP_ID", "")
    app_key = os.getenv("ADZUNA_APP_KEY", "")
    aggregator_cfg = profile.aggregators.get("adzuna")

    if aggregator_cfg and not aggregator_cfg.enabled:
        logger.info("Adzuna: disabled in config, skipping.")
        return []

    if not app_id or not app_key:
        logger.info("Adzuna: no API keys set (ADZUNA_APP_ID/KEY), skipping.")
        return []

    base_url = "https://api.adzuna.com/v1/api/jobs/in/search/1"
    search_terms = profile.skills.primary[:2] + ["python developer"]

    all_jobs = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for keyword in search_terms:
            try:
                params = {
                    "app_id": app_id,
                    "app_key": app_key,
                    "what": keyword,
                    "where": "India",
                    "results_per_page": limit,
                    "max_days_old": 7,
                    "sort_by": "date",
                }
                resp = await client.get(base_url, params=params)
                resp.raise_for_status()
                data = resp.json()
                raw_jobs = data.get("results", [])

                for raw in raw_jobs:
                    job = _normalize_adzuna(raw)
                    if job:
                        all_jobs.append(job)

                logger.info(f"Adzuna: '{keyword}' → {len(raw_jobs)} results")
            except (httpx.HTTPError, json.JSONDecodeError) as e:
                logger.error(f"Adzuna API failed for '{keyword}': {e}")

    logger.info(f"Adzuna total: {len(all_jobs)} jobs")
    return all_jobs


def _normalize_adzuna(raw: dict) -> dict | None:
    """Normalize an Adzuna job object."""
    description = raw.get("description") or ""
    if is_short_description(description):
        return None

    job_url = raw.get("redirect_url") or ""
    if not job_url:
        return None

    location_parts = []
    loc = raw.get("location", {})
    for area in loc.get("area", []):
        location_parts.append(area)
    location_str = ", ".join(location_parts) if location_parts else ""

    company = ""
    company_obj = raw.get("company", {})
    if isinstance(company_obj, dict):
        company = company_obj.get("display_name", "")
    elif isinstance(company_obj, str):
        company = company_obj

    return {
        "title": (raw.get("title") or "").strip(),
        "company": company.strip(),
        "location": location_str,
        "source": "adzuna",
        "discovered_via": "adzuna",
        "description": description.strip(),
        "job_url": job_url,
        "date_posted": parse_date_iso(raw.get("created")),
        "is_remote": "remote" in description.lower() or "remote" in (raw.get("title") or "").lower(),
        "salary_min": parse_salary_value(raw.get("salary_min")),
        "salary_max": parse_salary_value(raw.get("salary_max")),
        "salary_currency": "INR",
    }


@scraper("hiringcafe", group="aggregators")
async def scrape_hiringcafe(
    profile: ProfileConfig,
    limit: int = 50,
) -> list[dict]:
    """Scrape HiringCafe — free GET API, no key needed.

    GET https://hiring.cafe/api/search-jobs?searchState={...}&page=0&size=N
    Returns structured job data with pre-processed fields (seniority, YOE, tools).
    """
    aggregator_cfg = profile.aggregators.get("hiringcafe")
    if aggregator_cfg and not aggregator_cfg.enabled:
        logger.info("HiringCafe: disabled in config, skipping.")
        return []

    # Build search terms from profile
    search_queries = profile.skills.primary[:3] + ["software developer"]

    # Build the searchState for India + fresher-appropriate seniority
    base_search_state = {
        "locations": profile.search_preferences.locations[:3],
        "workplaceTypes": ["Remote", "Hybrid", "Onsite"],
        "seniorityLevel": ["No Experience Required", "Entry Level", "Mid Level"],
        "dateFetchedPastNDays": profile.matching.max_job_age_days or 7,
        "commitmentTypes": ["Full Time", "Internship"],
        "sortBy": "default",
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://hiring.cafe/",
    }

    all_raw = []
    seen_ids = set()

    async with httpx.AsyncClient(timeout=30.0) as client:
        for query in search_queries:
            try:
                search_state = {**base_search_state, "searchQuery": query}
                encoded = urllib.parse.quote(json.dumps(search_state))
                url = f"https://hiring.cafe/api/search-jobs?searchState={encoded}&page=0&size=200"

                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                results = data.get("results", [])

                for raw in results:
                    rid = raw.get("id", "")
                    if rid and rid not in seen_ids:
                        seen_ids.add(rid)
                        all_raw.append(raw)

                logger.info(f"HiringCafe: '{query}' → {len(results)} results")
            except (httpx.HTTPError, json.JSONDecodeError) as e:
                logger.error(f"HiringCafe API failed for '{query}': {e}")

    # Build keyword set for relevance filtering
    all_skills = build_skill_set(profile)
    # Also include frameworks for HiringCafe's structured matching
    all_skills |= {s.lower() for s in profile.skills.frameworks}

    # Filter and normalize
    jobs = []
    for raw in all_raw:
        job = _normalize_hiringcafe(raw, all_skills, profile)
        if job:
            jobs.append(job)
            if len(jobs) >= limit:
                break

    logger.info(f"HiringCafe: {len(jobs)} relevant jobs (from {len(all_raw)} unique fetched)")
    return jobs


def _normalize_hiringcafe(raw: dict, relevant_skills: set[str], profile: ProfileConfig) -> dict | None:
    """Normalize a HiringCafe job object."""
    ji = raw.get("job_information", {})
    jpd = raw.get("v5_processed_job_data", {})

    description = ji.get("description") or ""
    description_plain = strip_html(description)

    if is_short_description(description_plain):
        return None

    # Skip expired jobs
    if raw.get("is_expired"):
        return None

    # Skip senior roles based on YOE
    min_yoe = jpd.get("min_industry_and_role_yoe")
    if min_yoe is not None and min_yoe > 4:
        return None

    seniority = (jpd.get("seniority_level") or "").lower()
    if seniority in ("senior level", "executive level", "director"):
        return None

    # Relevance check — use structured technical_tools and job_category
    title = (ji.get("title") or "").lower()
    tools = [t.lower() for t in (jpd.get("technical_tools") or [])]
    job_category = (jpd.get("job_category") or "").lower()

    # Only allow tech-relevant job categories
    relevant_categories = {
        "software development", "software engineering", "information technology",
        "data and analytics", "data science", "engineering",
        "research and development (r&d)", "product management",
    }
    if job_category and job_category not in relevant_categories:
        return None

    # Require at least 1 tool match with our skills (strongest signal)
    # For title matching, only use specific tech terms, not generic "engineer"/"developer"
    tool_matches = sum(1 for skill in relevant_skills if skill in tools)
    specific_title_terms = relevant_skills - {
        "developer", "engineer", "fullstack", "full-stack",
        "backend", "frontend", "software",
    }
    title_matches = sum(1 for skill in specific_title_terms if skill in title)

    if tool_matches == 0 and title_matches == 0:
        return None

    date_posted = parse_date_iso(jpd.get("estimated_publish_date"))

    apply_url = raw.get("apply_url") or ""
    if not apply_url:
        return None

    company = (jpd.get("company_name") or "").strip()
    location = (jpd.get("formatted_workplace_location") or "").strip()
    workplace_type = (jpd.get("workplace_type") or "").lower()
    is_remote = workplace_type in ("remote", "hybrid")

    # Salary
    salary_min = jpd.get("yearly_min_compensation")
    salary_max = jpd.get("yearly_max_compensation")
    salary_currency = jpd.get("listed_compensation_currency") or "INR"

    return {
        "title": (ji.get("title") or "").strip(),
        "company": company,
        "location": location,
        "source": "hiringcafe",
        "discovered_via": "hiringcafe",
        "description": description_plain[:5000],
        "job_url": apply_url,
        "date_posted": date_posted,
        "is_remote": is_remote,
        "salary_min": parse_salary_value(salary_min),
        "salary_max": parse_salary_value(salary_max),
        "salary_currency": salary_currency,
    }


async def scrape_all_aggregators(
    profile: ProfileConfig,
    limit: int = 20,
) -> list[dict]:
    """Run all aggregator scrapers concurrently and merge results."""
    from scraper.registry import run_group
    return await run_group("aggregators", profile, limit)


# Need asyncio for gather


