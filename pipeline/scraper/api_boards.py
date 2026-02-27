"""Key-based API board scrapers — JSearch, CareerJet, The Muse, Findwork.

These require API keys (free tiers available). Each returns normalized
job dicts matching the same format as the existing aggregator scrapers.
"""

import asyncio
import json
import os
from datetime import datetime

import httpx

from core.logger import logger
from core.models import ProfileConfig
from scraper.registry import scraper
from scraper.utils import (
    is_short_description,
    parse_date_iso,
    parse_salary_value,
    strip_html,
)

# ─── JSearch (RapidAPI) ──────────────────────────────────────────────────────

@scraper("jsearch", group="api_boards", needs_key="RAPIDAPI_KEY")
async def scrape_jsearch(
    profile: ProfileConfig,
    limit: int = 20,
) -> list[dict]:
    """Scrape JSearch via RapidAPI — wraps Google for Jobs.

    GET https://jsearch.p.rapidapi.com/search
    Requires RAPIDAPI_KEY env var. Free tier: 500 req/month.
    Indexes Naukri, Indeed, LinkedIn, Glassdoor in one call.
    """
    api_key = os.getenv("RAPIDAPI_KEY", "")
    aggregator_cfg = profile.aggregators.get("jsearch")

    if aggregator_cfg and not aggregator_cfg.enabled:
        logger.info("JSearch: disabled in config, skipping.")
        return []

    if not api_key:
        logger.info("JSearch: no API key set (RAPIDAPI_KEY), skipping.")
        return []

    base_url = "https://jsearch.p.rapidapi.com/search"
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
    }

    # Build queries from profile
    search_terms = profile.skills.primary[:3] + ["software developer"]
    locations = profile.search_preferences.locations[:2]

    all_jobs = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for keyword in search_terms:
            for location in locations:
                try:
                    params = {
                        "query": f"{keyword} in {location}",
                        "page": "1",
                        "num_pages": "1",
                        "date_posted": "week",
                    }
                    resp = await client.get(base_url, params=params, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    raw_jobs = data.get("data", [])

                    for raw in raw_jobs[:limit]:
                        job = _normalize_jsearch(raw)
                        if job:
                            all_jobs.append(job)

                    logger.info(
                        f"JSearch: '{keyword}' in '{location}' → {len(raw_jobs)} results"
                    )
                except (httpx.HTTPError, json.JSONDecodeError) as e:
                    logger.error(f"JSearch API failed for '{keyword}' in '{location}': {e}")

    logger.info(f"JSearch total: {len(all_jobs)} jobs")
    return all_jobs


def _normalize_jsearch(raw: dict) -> dict | None:
    """Normalize a JSearch job object."""
    description = raw.get("job_description") or ""
    if is_short_description(description):
        return None

    job_url = raw.get("job_apply_link") or raw.get("job_google_link") or ""
    if not job_url:
        return None

    # Location
    city = raw.get("job_city") or ""
    state = raw.get("job_state") or ""
    country = raw.get("job_country") or ""
    location_parts = [p for p in [city, state, country] if p]
    location = ", ".join(location_parts)

    # Track original source for dedup
    publisher = raw.get("job_publisher") or ""
    source = publisher.lower() if publisher else "jsearch"

    return {
        "title": (raw.get("job_title") or "").strip(),
        "company": (raw.get("employer_name") or "").strip(),
        "location": location,
        "source": source,
        "discovered_via": "jsearch",
        "description": description.strip()[:5000],
        "job_url": job_url,
        "date_posted": parse_date_iso(raw.get("job_posted_at_datetime_utc")),
        "is_remote": bool(raw.get("job_is_remote", False)),
        "salary_min": parse_salary_value(raw.get("job_min_salary")),
        "salary_max": parse_salary_value(raw.get("job_max_salary")),
        "salary_currency": raw.get("job_salary_currency") or "INR",
    }


# ─── CareerJet ───────────────────────────────────────────────────────────────

@scraper("careerjet", group="api_boards", needs_key="CAREERJET_AFFILIATE_ID")
async def scrape_careerjet(
    profile: ProfileConfig,
    limit: int = 20,
) -> list[dict]:
    """Scrape CareerJet — free API via careerjet_api package or direct HTTP.

    GET https://public.api.careerjet.net/search
    Requires CAREERJET_AFFILIATE_ID env var.
    """
    affiliate_id = os.getenv("CAREERJET_AFFILIATE_ID", "")
    aggregator_cfg = profile.aggregators.get("careerjet")

    if aggregator_cfg and not aggregator_cfg.enabled:
        logger.info("CareerJet: disabled in config, skipping.")
        return []

    if not affiliate_id:
        logger.info("CareerJet: no affiliate ID set (CAREERJET_AFFILIATE_ID), skipping.")
        return []

    base_url = "https://public.api.careerjet.net/search"
    search_terms = profile.skills.primary[:3] + ["software developer"]
    locations = profile.search_preferences.locations[:2]

    all_jobs = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for keyword in search_terms:
            for location in locations:
                try:
                    params = {
                        "locale_code": "en_IN",
                        "keywords": keyword,
                        "location": location,
                        "affid": affiliate_id,
                        "pagesize": limit,
                        "page": 1,
                        "sort": "date",
                    }
                    resp = await client.get(base_url, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                    raw_jobs = data.get("jobs", [])

                    for raw in raw_jobs:
                        job = _normalize_careerjet(raw)
                        if job:
                            all_jobs.append(job)

                    logger.info(
                        f"CareerJet: '{keyword}' in '{location}' → {len(raw_jobs)} results"
                    )
                except (httpx.HTTPError, json.JSONDecodeError) as e:
                    logger.error(f"CareerJet API failed for '{keyword}' in '{location}': {e}")

    logger.info(f"CareerJet total: {len(all_jobs)} jobs")
    return all_jobs


def _normalize_careerjet(raw: dict) -> dict | None:
    """Normalize a CareerJet job object."""
    description = raw.get("description") or ""
    if is_short_description(description):
        return None

    job_url = raw.get("url") or ""
    if not job_url:
        return None

    # Parse date — CareerJet uses RFC 2822 format, fallback to ISO
    date_posted = None
    date_str = raw.get("date")
    if date_str:
        try:
            date_posted = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z").date()
        except (ValueError, AttributeError):
            date_posted = parse_date_iso(date_str)

    desc_plain = strip_html(description)

    return {
        "title": (raw.get("title") or "").strip(),
        "company": (raw.get("company") or "").strip(),
        "location": (raw.get("locations") or "").strip(),
        "source": "careerjet",
        "discovered_via": "careerjet",
        "description": desc_plain[:5000],
        "job_url": job_url,
        "date_posted": date_posted,
        "is_remote": "remote" in description.lower() or "remote" in (raw.get("title") or "").lower(),
        "salary_min": None,
        "salary_max": None,
        "salary_currency": "INR",
    }


# ─── The Muse ────────────────────────────────────────────────────────────────

@scraper("themuse", group="api_boards")
async def scrape_themuse(
    profile: ProfileConfig,
    limit: int = 30,
) -> list[dict]:
    """Scrape The Muse — free JSON API, optional key for higher limits.

    GET https://www.themuse.com/api/public/jobs?page=0&level=Entry+Level&category=...
    API key via THEMUSE_API_KEY env var (optional, increases rate limit).
    """
    api_key = os.getenv("THEMUSE_API_KEY", "")
    aggregator_cfg = profile.aggregators.get("themuse")

    if aggregator_cfg and not aggregator_cfg.enabled:
        logger.info("The Muse: disabled in config, skipping.")
        return []

    base_url = "https://www.themuse.com/api/public/jobs"
    # Categories relevant for software dev
    categories = [
        "Software Engineering",
        "Data Science",
        "IT",
    ]

    all_raw = []
    seen_ids = set()

    async with httpx.AsyncClient(timeout=30.0) as client:
        for category in categories:
            try:
                params = {
                    "page": 0,
                    "level": "Entry Level",
                    "category": category,
                    "location": "India",
                }
                if api_key:
                    params["api_key"] = api_key

                resp = await client.get(base_url, params=params)
                resp.raise_for_status()
                data = resp.json()
                results = data.get("results", [])

                for raw in results:
                    rid = raw.get("id")
                    if rid and rid not in seen_ids:
                        seen_ids.add(rid)
                        all_raw.append(raw)

                logger.info(f"The Muse: '{category}' → {len(results)} results")
            except (httpx.HTTPError, json.JSONDecodeError) as e:
                logger.error(f"The Muse API failed for '{category}': {e}")

    jobs = []
    for raw in all_raw:
        job = _normalize_themuse(raw)
        if job:
            jobs.append(job)
            if len(jobs) >= limit:
                break

    logger.info(f"The Muse: {len(jobs)} jobs (from {len(all_raw)} unique fetched)")
    return jobs


def _normalize_themuse(raw: dict) -> dict | None:
    """Normalize a The Muse job object."""
    description = raw.get("contents") or ""
    if is_short_description(description):
        return None

    desc_plain = strip_html(description)

    refs = raw.get("refs", {})
    job_url = refs.get("landing_page") or ""
    if not job_url:
        return None

    # Location
    locations = raw.get("locations", [])
    location_names = [loc.get("name", "") for loc in locations if isinstance(loc, dict)]
    location_str = ", ".join(location_names) if location_names else ""
    is_remote = any("remote" in loc.lower() for loc in location_names)

    # Company
    company_obj = raw.get("company", {})
    company = company_obj.get("name", "") if isinstance(company_obj, dict) else ""

    return {
        "title": (raw.get("name") or "").strip(),
        "company": company.strip(),
        "location": location_str,
        "source": "themuse",
        "discovered_via": "themuse",
        "description": desc_plain[:5000],
        "job_url": job_url,
        "date_posted": parse_date_iso(raw.get("publication_date")),
        "is_remote": is_remote,
        "salary_min": None,
        "salary_max": None,
        "salary_currency": "USD",
    }


# ─── Findwork ────────────────────────────────────────────────────────────────

@scraper("findwork", group="api_boards", needs_key="FINDWORK_TOKEN")
async def scrape_findwork(
    profile: ProfileConfig,
    limit: int = 30,
) -> list[dict]:
    """Scrape Findwork — free API with token.

    GET https://findwork.dev/api/jobs/?search=python&location=india
    Requires FINDWORK_TOKEN env var. Free tier: 50 req/month.
    """
    token = os.getenv("FINDWORK_TOKEN", "")
    aggregator_cfg = profile.aggregators.get("findwork")

    if aggregator_cfg and not aggregator_cfg.enabled:
        logger.info("Findwork: disabled in config, skipping.")
        return []

    if not token:
        logger.info("Findwork: no API token set (FINDWORK_TOKEN), skipping.")
        return []

    base_url = "https://findwork.dev/api/jobs/"
    headers = {
        "Authorization": f"Token {token}",
    }

    search_terms = profile.skills.primary[:3]
    locations = ["remote"] + profile.search_preferences.locations[:2]

    all_jobs = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for keyword in search_terms:
            for location in locations:
                try:
                    params = {
                        "search": keyword,
                        "location": location,
                        "sort_by": "relevance",
                    }
                    resp = await client.get(base_url, params=params, headers=headers)
                    if resp.status_code == 429:
                        logger.warning("Findwork: rate limited, stopping early")
                        break
                    resp.raise_for_status()
                    data = resp.json()
                    raw_jobs = data.get("results", [])

                    for raw in raw_jobs:
                        job = _normalize_findwork(raw)
                        if job:
                            all_jobs.append(job)

                    logger.info(f"Findwork: '{keyword}' in '{location}' → {len(raw_jobs)} results")
                    await asyncio.sleep(0.5)  # Respect rate limits (50 req/month free tier)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        logger.warning("Findwork: rate limited, stopping early")
                        break
                    logger.error(f"Findwork API failed for '{keyword}' in '{location}': {e}")
                except (httpx.HTTPError, json.JSONDecodeError) as e:
                    logger.error(f"Findwork API failed for '{keyword}' in '{location}': {e}")
            else:
                continue
            break  # Break outer loop if inner loop was broken (rate limited)

    # Deduplicate by URL
    seen_urls = set()
    unique_jobs = []
    for job in all_jobs:
        if job["job_url"] not in seen_urls:
            seen_urls.add(job["job_url"])
            unique_jobs.append(job)

    logger.info(f"Findwork total: {len(unique_jobs)} unique jobs")
    return unique_jobs[:limit]


def _normalize_findwork(raw: dict) -> dict | None:
    """Normalize a Findwork job object."""
    description = raw.get("text") or raw.get("description") or ""
    if is_short_description(description):
        return None

    job_url = raw.get("url") or ""
    if not job_url:
        return None

    location = raw.get("location") or ""
    is_remote = raw.get("remote", False) or "remote" in location.lower()

    return {
        "title": (raw.get("role") or "").strip(),
        "company": (raw.get("company_name") or "").strip(),
        "location": location if location else ("Remote" if is_remote else ""),
        "source": "findwork",
        "discovered_via": "findwork",
        "description": strip_html(description)[:5000],
        "job_url": job_url,
        "date_posted": parse_date_iso(raw.get("date_posted")),
        "is_remote": is_remote,
        "salary_min": None,
        "salary_max": None,
        "salary_currency": "USD",
    }


# ─── Master function ─────────────────────────────────────────────────────────

async def scrape_all_api_boards(
    profile: ProfileConfig,
    limit: int = 20,
) -> list[dict]:
    """Run all key-based API board scrapers concurrently and merge results."""
    from scraper.registry import run_group
    return await run_group("api_boards", profile, limit)


