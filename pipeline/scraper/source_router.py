"""Source router — classify jobs by platform and determine action.

URL domain parsing → decide whether a job gets:
- auto_apply (Naukri, Indeed, Foundit — have auto-apply support)
- cold_email (company career pages, Greenhouse, Lever — find HR contact)
- manual_alert (LinkedIn, Wellfound — send Telegram alert for human action)
"""

from urllib.parse import urlparse

import httpx

from core.logger import logger
from core.models import ProfileConfig

# Domain classification maps
AUTO_APPLY_DOMAINS = {
    "naukri.com": "naukri",
    "indeed.com": "indeed",
    "foundit.com": "foundit",
    "in.indeed.com": "indeed",
}

MANUAL_ONLY_DOMAINS = {
    "linkedin.com": "linkedin",
    "wellfound.com": "wellfound",
    "angel.co": "wellfound",
    "internshala.com": "internshala",
    "instahyre.com": "instahyre",
}

ATS_DOMAINS = {
    "greenhouse.io": "greenhouse",
    "lever.co": "lever",
    "boards.greenhouse.io": "greenhouse",
    "jobs.lever.co": "lever",
    "workday.com": "workday",
    "myworkdayjobs.com": "workday",
    "smartrecruiters.com": "smartrecruiters",
    "ashbyhq.com": "ashby",
}

SCRAPE_ONLY_DOMAINS = {
    "glassdoor.com": "glassdoor",
    "glassdoor.co.in": "glassdoor",
    "cutshort.io": "cutshort",
    "hirist.pro": "hirist",
    "hiristpro.com": "hirist",
    "remoteok.com": "remoteok",
    "jooble.org": "jooble",
    "adzuna.com": "adzuna",
    "adzuna.co.in": "adzuna",
}


def _extract_domain(url: str) -> str:
    """Extract the domain from a URL, stripping www."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace("www.", "")
        return domain
    except (ValueError, AttributeError):
        return ""


def classify_source(job_url: str) -> dict:
    """Classify a job URL into source category and platform name.

    Returns dict with: platform, category, auto_apply, cold_email, manual_alert
    """
    domain = _extract_domain(job_url)

    # Check each category
    for domain_pattern, platform in AUTO_APPLY_DOMAINS.items():
        if domain_pattern in domain:
            return {
                "platform": platform,
                "category": "auto_apply",
                "auto_apply": True,
                "cold_email": True,
                "manual_alert": False,
            }

    for domain_pattern, platform in MANUAL_ONLY_DOMAINS.items():
        if domain_pattern in domain:
            return {
                "platform": platform,
                "category": "manual_only",
                "auto_apply": False,
                "cold_email": False,
                "manual_alert": True,
            }

    for domain_pattern, platform in ATS_DOMAINS.items():
        if domain_pattern in domain:
            return {
                "platform": platform,
                "category": "ats",
                "auto_apply": False,
                "cold_email": True,
                "manual_alert": True,
            }

    for domain_pattern, platform in SCRAPE_ONLY_DOMAINS.items():
        if domain_pattern in domain:
            return {
                "platform": platform,
                "category": "scrape_only",
                "auto_apply": False,
                "cold_email": False,
                "manual_alert": True,
            }

    # Unknown domain — likely a company career page
    return {
        "platform": "unknown",
        "category": "company_page",
        "auto_apply": False,
        "cold_email": True,
        "manual_alert": True,
    }


def route_job(job: dict, profile: ProfileConfig) -> dict:
    """Determine the action route for a job based on URL and profile config.

    Returns the job dict with added routing fields:
    - route_classification: dict from classify_source()
    - route_action: str — the recommended action
    """
    job_url = job.get("job_url", "")
    classification = classify_source(job_url)

    # Check if the platform is enabled in profile
    platform = classification["platform"]
    platform_cfg = profile.platforms.get(platform)

    if platform_cfg and not platform_cfg.enabled:
        classification["auto_apply"] = False
        classification["cold_email"] = False

    # Determine primary action
    if classification["auto_apply"] and platform_cfg and platform_cfg.auto_apply:
        route_action = "auto_apply_and_cold_email"
    elif classification["cold_email"]:
        route_action = "cold_email_only"
    else:
        route_action = "manual_alert"

    job["route_classification"] = classification
    job["route_action"] = route_action
    return job


async def verify_job_alive(url: str, timeout: float = 10.0) -> bool:
    """Check if a job URL is still active (not 404/410/301 to homepage).

    Uses HEAD request to minimize bandwidth.
    """
    if not url:
        return False

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; JobBot/1.0)"},
        ) as client:
            resp = await client.head(url)

            # Dead job indicators
            if resp.status_code in (404, 410, 403):
                logger.debug(f"Job URL dead ({resp.status_code}): {url}")
                return False

            # Check if redirected to a generic page (homepage, search page)
            final_url = str(resp.url)
            if final_url != url:
                domain = _extract_domain(url)
                final_domain = _extract_domain(final_url)
                # Redirected to completely different domain = suspicious
                if domain != final_domain:
                    logger.debug(f"Job URL redirected to different domain: {url} → {final_url}")
                    return False

            return True
    except httpx.HTTPError as e:
        logger.debug(f"Job URL check failed for {url}: {e}")
        # Assume alive if we can't check (network issue)
        return True


async def resolve_final_url(url: str, timeout: float = 10.0) -> str:
    """Follow redirects and return the final URL.

    Useful for aggregator URLs that redirect to the actual job posting.
    """
    if not url:
        return url

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; JobBot/1.0)"},
        ) as client:
            resp = await client.head(url)
            final = str(resp.url)
            if final != url:
                logger.debug(f"URL resolved: {url} → {final}")
            return final
    except httpx.HTTPError:
        return url
