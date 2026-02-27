"""JobSpy scraper — wraps python-jobspy for Indeed, Naukri, Glassdoor, LinkedIn.

Returns normalized job dicts ready for dedup and analysis.
Respects platform enable/disable flags and rate limits from profile config.
"""

import asyncio
from datetime import date, datetime

from jobspy import scrape_jobs

from core.logger import logger
from core.models import ProfileConfig
from scraper.registry import scraper
from scraper.utils import is_short_description, parse_salary_value


def _scrape_sync(
    search_term: str,
    location: str,
    site_names: list[str],
    results_wanted: int = 20,
    hours_old: int = 24,
) -> list[dict]:
    """Synchronous JobSpy call (it uses requests internally)."""
    try:
        df = scrape_jobs(
            site_name=site_names,
            search_term=search_term,
            location=location,
            results_wanted=results_wanted,
            hours_old=hours_old,
            country_indeed="India",
        )
        if df is None or df.empty:
            return []
        # Convert DataFrame to list of dicts, handling NaN values
        records = df.where(df.notna(), None).to_dict("records")
        return records
    except Exception as e:
        logger.error(f"JobSpy scrape failed for '{search_term}' in '{location}': {e}")
        return []


def _normalize_job(raw: dict, discovered_via: str = "jobspy") -> dict | None:
    """Convert a JobSpy row into our standard job dict.

    Returns None if the job has no usable description (< 50 chars).
    """
    description = raw.get("description") or ""
    if is_short_description(description):
        return None

    title = raw.get("title") or ""
    company = raw.get("company_name") or raw.get("company") or ""
    location = raw.get("location") or ""
    job_url = raw.get("job_url") or raw.get("link") or ""

    if not job_url:
        return None

    # Parse source from site column
    source = str(raw.get("site", "")).lower()

    # Parse date
    date_posted = raw.get("date_posted")
    if isinstance(date_posted, str):
        try:
            date_posted = datetime.strptime(date_posted, "%Y-%m-%d").date()
        except ValueError:
            date_posted = None
    elif isinstance(date_posted, datetime):
        date_posted = date_posted.date()
    elif not isinstance(date_posted, date):
        date_posted = None

    # Parse remote flag
    is_remote = bool(raw.get("is_remote"))

    # Parse salary
    salary_min = parse_salary_value(raw.get("min_amount"))
    salary_max = parse_salary_value(raw.get("max_amount"))
    salary_currency = raw.get("currency") or raw.get("salary_currency")

    return {
        "title": title.strip(),
        "company": company.strip(),
        "location": location.strip(),
        "source": source,
        "discovered_via": discovered_via,
        "description": description.strip(),
        "job_url": str(job_url).strip(),
        "date_posted": date_posted,
        "is_remote": is_remote,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": salary_currency,
    }


@scraper("jobspy", group="jobspy")
async def scrape_jobspy(
    profile: ProfileConfig,
    limit: int = 20,
    hours_old: int = 24,
) -> list[dict]:
    """Scrape jobs from all enabled JobSpy-supported platforms.

    Runs synchronous JobSpy in a thread pool to keep the event loop free.
    Returns a list of normalized job dicts.
    """
    # Determine which JobSpy-supported sites are enabled
    jobspy_sites_map = {
        "indeed": "indeed",
        "glassdoor": "glassdoor",
        "linkedin": "linkedin",
    }

    enabled_sites = []
    for platform_key, jobspy_name in jobspy_sites_map.items():
        platform_cfg = profile.platforms.get(platform_key)
        if platform_cfg and platform_cfg.enabled:
            enabled_sites.append(jobspy_name)

    if not enabled_sites:
        logger.info("No JobSpy-supported platforms enabled, skipping JobSpy scraper.")
        return []

    # Build search terms from profile
    search_terms = profile.skills.primary[:3]  # Top 3 primary skills
    if profile.filters.must_have_any:
        # Add a few key filter terms
        for term in ["python developer", "software engineer", "full stack developer"]:
            if term not in [s.lower() for s in search_terms]:
                search_terms.append(term)
                if len(search_terms) >= 5:
                    break

    locations = profile.search_preferences.locations

    all_jobs = []
    loop = asyncio.get_event_loop()

    for search_term in search_terms:
        for location in locations:
            logger.info(
                f"JobSpy: scraping '{search_term}' in '{location}' "
                f"from {enabled_sites}"
            )
            raw_jobs = await loop.run_in_executor(
                None,
                _scrape_sync,
                search_term,
                location,
                enabled_sites,
                limit,
                hours_old,
            )

            normalized = 0
            for raw in raw_jobs:
                job = _normalize_job(raw)
                if job:
                    all_jobs.append(job)
                    normalized += 1

            logger.info(
                f"JobSpy: got {len(raw_jobs)} raw → {normalized} valid "
                f"for '{search_term}' in '{location}'"
            )

    logger.info(f"JobSpy total: {len(all_jobs)} jobs scraped")
    return all_jobs
