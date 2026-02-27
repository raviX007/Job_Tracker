"""Remote job board scrapers — Remotive, Jobicy, Himalayas, Arbeitnow.

All are free, no-auth APIs. Each returns normalized job dicts matching
the same format as the existing aggregator scrapers.
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
    parse_salary_range,
    parse_salary_value,
    strip_html,
)

# ─── Remotive ────────────────────────────────────────────────────────────────

@scraper("remotive", group="remote_boards")
async def scrape_remotive(profile: ProfileConfig, limit: int = 30) -> list[dict]:
    """Scrape Remotive — free JSON API, no key needed.

    GET https://remotive.com/api/remote-jobs?category=software-dev&limit=N
    Returns JSON with "jobs" array.
    """
    aggregator_cfg = profile.aggregators.get("remotive")
    if aggregator_cfg and not aggregator_cfg.enabled:
        logger.info("Remotive: disabled in config, skipping.")
        return []

    # Remotive categories relevant to this profile
    categories = ["software-dev", "data", "devops"]

    headers = {"User-Agent": "JobApplicationBot/1.0"}
    all_raw = []
    seen_ids = set()

    async with httpx.AsyncClient(timeout=30.0) as client:
        for category in categories:
            try:
                url = f"https://remotive.com/api/remote-jobs?category={category}&limit=100"
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                for raw in data.get("jobs", []):
                    rid = raw.get("id")
                    if rid and rid not in seen_ids:
                        seen_ids.add(rid)
                        all_raw.append(raw)
                logger.info(f"Remotive: '{category}' → {len(data.get('jobs', []))} results")
            except (httpx.HTTPError, json.JSONDecodeError) as e:
                logger.error(f"Remotive API failed for '{category}': {e}")

    # Build skill set for relevance filtering
    all_skills = build_skill_set(profile)
    all_skills |= {"web developer"}

    jobs = []
    for raw in all_raw:
        job = _normalize_remotive(raw, all_skills)
        if job:
            jobs.append(job)
            if len(jobs) >= limit:
                break

    logger.info(f"Remotive: {len(jobs)} relevant jobs (from {len(all_raw)} unique fetched)")
    return jobs


def _normalize_remotive(raw: dict, relevant_skills: set[str]) -> dict | None:
    """Normalize a Remotive job object."""
    description = raw.get("description") or ""
    if is_short_description(description):
        return None

    # Relevance check
    title = (raw.get("title") or "").lower()
    tags = [t.lower() for t in (raw.get("tags") or [])]
    desc_lower = description.lower()

    has_match = any(
        skill in desc_lower or skill in title or skill in tags
        for skill in relevant_skills
    )
    if not has_match:
        return None

    job_url = raw.get("url") or ""
    if not job_url:
        return None

    desc_plain = strip_html(description)
    salary_min, salary_max = parse_salary_range(raw.get("salary") or "")

    return {
        "title": (raw.get("title") or "").strip(),
        "company": (raw.get("company_name") or "").strip(),
        "location": (raw.get("candidate_required_location") or "Remote").strip(),
        "source": "remotive",
        "discovered_via": "remotive",
        "description": desc_plain[:5000],
        "job_url": job_url,
        "date_posted": parse_date_iso(raw.get("publication_date")),
        "is_remote": True,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": "USD",
    }


# ─── Jobicy ──────────────────────────────────────────────────────────────────

@scraper("jobicy", group="remote_boards")
async def scrape_jobicy(profile: ProfileConfig, limit: int = 30) -> list[dict]:
    """Scrape Jobicy — free JSON API, no key needed.

    GET https://jobicy.com/api/v2/remote-jobs?count=N&geo=india&industry=tech&tag=python
    Returns JSON with "jobs" array.
    """
    aggregator_cfg = profile.aggregators.get("jobicy")
    if aggregator_cfg and not aggregator_cfg.enabled:
        logger.info("Jobicy: disabled in config, skipping.")
        return []

    # Build tag queries from primary skills
    tags = [s.lower().replace(" ", "-") for s in profile.skills.primary[:4]]
    if "python" not in tags:
        tags.append("python")

    headers = {"User-Agent": "JobApplicationBot/1.0"}
    all_raw = []
    seen_ids = set()

    async with httpx.AsyncClient(timeout=30.0) as client:
        for tag in tags:
            try:
                url = (
                    f"https://jobicy.com/api/v2/remote-jobs"
                    f"?count=50&geo=india&industry=tech&tag={tag}"
                )
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                for raw in data.get("jobs", []):
                    rid = raw.get("id")
                    if rid and rid not in seen_ids:
                        seen_ids.add(rid)
                        all_raw.append(raw)
                logger.info(f"Jobicy: tag '{tag}' → {len(data.get('jobs', []))} results")
            except (httpx.HTTPError, json.JSONDecodeError) as e:
                logger.error(f"Jobicy API failed for tag '{tag}': {e}")

    jobs = []
    for raw in all_raw:
        job = _normalize_jobicy(raw)
        if job:
            jobs.append(job)
            if len(jobs) >= limit:
                break

    logger.info(f"Jobicy: {len(jobs)} jobs (from {len(all_raw)} unique fetched)")
    return jobs


def _normalize_jobicy(raw: dict) -> dict | None:
    """Normalize a Jobicy job object."""
    description = raw.get("jobDescription") or ""
    if is_short_description(description):
        return None

    job_url = raw.get("url") or ""
    if not job_url:
        return None

    desc_plain = strip_html(description)
    geo = raw.get("jobGeo") or ""

    return {
        "title": (raw.get("jobTitle") or "").strip(),
        "company": (raw.get("companyName") or "").strip(),
        "location": geo if geo else "Remote",
        "source": "jobicy",
        "discovered_via": "jobicy",
        "description": desc_plain[:5000],
        "job_url": job_url,
        "date_posted": parse_date_iso(raw.get("pubDate")),
        "is_remote": True,
        "salary_min": parse_salary_value(raw.get("annualSalaryMin")),
        "salary_max": parse_salary_value(raw.get("annualSalaryMax")),
        "salary_currency": raw.get("salaryCurrency") or "USD",
    }


# ─── Himalayas ───────────────────────────────────────────────────────────────

@scraper("himalayas", group="remote_boards")
async def scrape_himalayas(profile: ProfileConfig, limit: int = 30) -> list[dict]:
    """Scrape Himalayas — free JSON API, no key needed.

    GET https://himalayas.app/jobs/api?limit=50
    Returns JSON with "jobs" array.
    """
    aggregator_cfg = profile.aggregators.get("himalayas")
    if aggregator_cfg and not aggregator_cfg.enabled:
        logger.info("Himalayas: disabled in config, skipping.")
        return []

    headers = {"User-Agent": "JobApplicationBot/1.0"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = "https://himalayas.app/jobs/api?limit=100"
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            raw_jobs = data.get("jobs", [])
    except (httpx.HTTPError, json.JSONDecodeError) as e:
        logger.error(f"Himalayas API failed: {e}")
        return []

    if not raw_jobs:
        logger.info("Himalayas: no jobs returned.")
        return []

    all_skills = build_skill_set(profile)

    jobs = []
    for raw in raw_jobs:
        job = _normalize_himalayas(raw, all_skills)
        if job:
            jobs.append(job)
            if len(jobs) >= limit:
                break

    logger.info(f"Himalayas: {len(jobs)} relevant jobs (from {len(raw_jobs)} total)")
    return jobs


def _normalize_himalayas(raw: dict, relevant_skills: set[str]) -> dict | None:
    """Normalize a Himalayas job object."""
    description = raw.get("description") or ""
    if is_short_description(description):
        return None

    # Relevance check
    title = (raw.get("title") or "").lower()
    categories = [c.lower() for c in (raw.get("categories") or [])]
    desc_lower = description.lower()

    has_match = any(
        skill in desc_lower or skill in title or any(skill in c for c in categories)
        for skill in relevant_skills
    )
    if not has_match:
        return None

    # Skip senior roles
    seniority_raw = raw.get("seniority") or ""
    if isinstance(seniority_raw, list):
        seniority = " ".join(s.lower() for s in seniority_raw if isinstance(s, str))
    else:
        seniority = str(seniority_raw).lower()
    if any(s in seniority for s in ("senior", "lead", "director", "executive", "principal")):
        return None

    job_url = raw.get("applicationUrl") or raw.get("url") or ""
    if not job_url:
        return None

    desc_plain = strip_html(description)

    company_name = raw.get("companyName") or ""
    if isinstance(raw.get("company"), dict):
        company_name = raw["company"].get("name", company_name)

    return {
        "title": (raw.get("title") or "").strip(),
        "company": company_name.strip(),
        "location": raw.get("location") or "Remote",
        "source": "himalayas",
        "discovered_via": "himalayas",
        "description": desc_plain[:5000],
        "job_url": job_url,
        "date_posted": parse_date_iso(raw.get("pubDate") or raw.get("publishedDate")),
        "is_remote": True,
        "salary_min": parse_salary_value(raw.get("minSalary")),
        "salary_max": parse_salary_value(raw.get("maxSalary")),
        "salary_currency": "USD",
    }


# ─── Arbeitnow ───────────────────────────────────────────────────────────────

@scraper("arbeitnow", group="remote_boards")
async def scrape_arbeitnow(profile: ProfileConfig, limit: int = 30) -> list[dict]:
    """Scrape Arbeitnow — free JSON API, no key needed.

    GET https://www.arbeitnow.com/api/job-board-api
    Returns JSON with "data" array. Paginated via "links.next".
    """
    aggregator_cfg = profile.aggregators.get("arbeitnow")
    if aggregator_cfg and not aggregator_cfg.enabled:
        logger.info("Arbeitnow: disabled in config, skipping.")
        return []

    headers = {"User-Agent": "JobApplicationBot/1.0"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = "https://www.arbeitnow.com/api/job-board-api"
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            raw_jobs = data.get("data", [])
    except (httpx.HTTPError, json.JSONDecodeError) as e:
        logger.error(f"Arbeitnow API failed: {e}")
        return []

    if not raw_jobs:
        logger.info("Arbeitnow: no jobs returned.")
        return []

    all_skills = build_skill_set(profile)

    jobs = []
    for raw in raw_jobs:
        job = _normalize_arbeitnow(raw, all_skills)
        if job:
            jobs.append(job)
            if len(jobs) >= limit:
                break

    logger.info(f"Arbeitnow: {len(jobs)} relevant jobs (from {len(raw_jobs)} total)")
    return jobs


def _normalize_arbeitnow(raw: dict, relevant_skills: set[str]) -> dict | None:
    """Normalize an Arbeitnow job object."""
    description = raw.get("description") or ""
    if is_short_description(description):
        return None

    # Relevance check
    title = (raw.get("title") or "").lower()
    tags = [t.lower() for t in (raw.get("tags") or [])]
    desc_lower = description.lower()

    has_match = any(
        skill in desc_lower or skill in title or skill in tags
        for skill in relevant_skills
    )
    if not has_match:
        return None

    job_url = raw.get("url") or raw.get("slug") or ""
    if not job_url:
        return None
    if not job_url.startswith("http"):
        job_url = f"https://www.arbeitnow.com/view/{job_url}"

    # Arbeitnow uses Unix timestamp, fallback to ISO
    date_posted = parse_date_timestamp(raw.get("created_at"))
    if not date_posted:
        date_posted = parse_date_iso(str(raw.get("created_at", "")))

    desc_plain = strip_html(description)
    is_remote = raw.get("remote", False)
    location = raw.get("location") or ""

    return {
        "title": (raw.get("title") or "").strip(),
        "company": (raw.get("company_name") or "").strip(),
        "location": location if location else ("Remote" if is_remote else ""),
        "source": "arbeitnow",
        "discovered_via": "arbeitnow",
        "description": desc_plain[:5000],
        "job_url": job_url,
        "date_posted": date_posted,
        "is_remote": bool(is_remote),
        "salary_min": None,
        "salary_max": None,
        "salary_currency": "EUR",
    }


# ─── Master function ─────────────────────────────────────────────────────────

async def scrape_all_remote_boards(profile: ProfileConfig, limit: int = 30) -> list[dict]:
    """Run all remote board scrapers concurrently and merge results."""
    from scraper.registry import run_group
    return await run_group("remote_boards", profile, limit)


