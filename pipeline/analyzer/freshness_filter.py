"""Freshness filter — skip stale job postings.

Jobs older than max_job_age_days (default 7) are filtered out.
Also applies title-based and company-based skip filters from profile config.
"""

from datetime import date

from core.logger import logger
from core.models import ProfileConfig


def is_stale_job(job: dict, max_age_days: int = 7) -> bool:
    """Check if a job is too old to be worth applying to."""
    date_posted = job.get("date_posted")
    if date_posted is None:
        # No date info — assume fresh (don't filter)
        return False

    if isinstance(date_posted, str):
        try:
            date_posted = date.fromisoformat(date_posted)
        except ValueError:
            return False

    age = (date.today() - date_posted).days
    return age > max_age_days


def matches_skip_title(title: str, skip_titles: list[str]) -> bool:
    """Check if a job title matches any skip pattern."""
    title_lower = title.lower()
    return any(skip.lower() in title_lower for skip in skip_titles)


def matches_skip_company(company: str, skip_companies: list[str]) -> bool:
    """Check if a company matches any skip pattern."""
    company_lower = company.lower()
    return any(skip.lower() in company_lower for skip in skip_companies)


def has_required_keyword(description: str, must_have_any: list[str]) -> bool:
    """Check if the description contains at least one required keyword."""
    if not must_have_any:
        return True  # No filter = everything passes

    desc_lower = description.lower()
    return any(kw.lower() in desc_lower for kw in must_have_any)


def apply_pre_filters(
    jobs: list[dict],
    profile: ProfileConfig,
) -> tuple[list[dict], list[dict]]:
    """Apply all pre-LLM filters: freshness, title skip, company skip, keyword match.

    These are cheap (no API calls) and run before embedding + LLM stages.

    Returns: (passed_jobs, filtered_out_jobs)
    """
    max_age = profile.matching.max_job_age_days
    skip_titles = profile.filters.skip_titles
    skip_companies = profile.filters.skip_companies
    must_have = profile.filters.must_have_any

    passed = []
    filtered_out = []

    for job in jobs:
        title = job.get("title", "")
        company = job.get("company", "")
        description = job.get("description", "")
        reason = None

        # Filter 1: Stale job
        if is_stale_job(job, max_age):
            reason = "stale"

        # Filter 2: Skip title
        elif matches_skip_title(title, skip_titles):
            reason = "skip_title"

        # Filter 3: Skip company
        elif matches_skip_company(company, skip_companies):
            reason = "skip_company"

        # Filter 4: Must have at least one keyword
        elif not has_required_keyword(description, must_have):
            reason = "no_required_keyword"

        if reason:
            job["filter_reason"] = reason
            filtered_out.append(job)
        else:
            passed.append(job)

    if filtered_out:
        # Log filter breakdown
        reasons = {}
        for j in filtered_out:
            r = j.get("filter_reason", "unknown")
            reasons[r] = reasons.get(r, 0) + 1
        logger.info(f"Pre-filters: {len(passed)} passed, {len(filtered_out)} filtered — {reasons}")
    else:
        logger.info(f"Pre-filters: all {len(passed)} jobs passed")

    return passed, filtered_out
