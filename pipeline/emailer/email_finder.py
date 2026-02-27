"""Email finder — 5-strategy priority chain for finding HR/recruiter emails.

Priority order:
1. Apollo.io API (100 credits/mo free)
2. Snov.io API (50 credits/mo free)
3. Hunter.io API (25 searches/mo free)
4. Company team page scraping (free, unlimited)
5. Pattern guessing (free, unlimited)

Removed strategies (ToS violations):
- GitHub commit emails — violates GitHub Acceptable Use Policies
- Google dorking — scrapes Google HTML with spoofed User-Agent, violates Google ToS

Each strategy returns a list of EmailCandidate objects.
The orchestrator tries each in order, stops when we have enough results.
"""

import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from core.constants import APOLLO_RESULTS_PER_PAGE, EMAIL_FINDER_TIMEOUT, GENERIC_EMAIL_PREFIXES
from core.logger import logger


@dataclass
class EmailCandidate:
    """A found email address with metadata."""
    email: str
    name: str = ""
    role: str = ""
    source: str = ""  # apollo, snov, hunter, team_page, pattern_guess
    confidence: str = "low"  # high, medium, low


# ─── Strategy 1: Apollo.io ─────────────────────────────

async def find_via_apollo(
    company_name: str,
    domain: str,
    role_keywords: list[str] | None = None,
) -> list[EmailCandidate]:
    """Search Apollo.io for people at a company.

    Uses the People Search API. Free tier: 100 credits/month.
    """
    api_key = os.getenv("APOLLO_API_KEY", "")
    if not api_key:
        return []

    if role_keywords is None:
        role_keywords = ["HR", "recruiter", "talent acquisition", "hiring manager", "people"]

    url = "https://api.apollo.io/v1/mixed_people/search"
    headers = {"Content-Type": "application/json", "Cache-Control": "no-cache"}

    results = []
    try:
        async with httpx.AsyncClient(timeout=EMAIL_FINDER_TIMEOUT) as client:
            body = {
                "api_key": api_key,
                "q_organization_domains": domain,
                "person_titles": role_keywords,
                "page": 1,
                "per_page": APOLLO_RESULTS_PER_PAGE,
            }
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            for person in data.get("people", []):
                email = person.get("email")
                if email:
                    results.append(EmailCandidate(
                        email=email,
                        name=f"{person.get('first_name', '')} {person.get('last_name', '')}".strip(),
                        role=person.get("title", ""),
                        source="apollo",
                        confidence="high",
                    ))

        logger.info(f"Apollo: found {len(results)} emails for {domain}")
    except httpx.HTTPError as e:
        logger.warning(f"Apollo API failed for {domain}: {e}")

    return results


# ─── Strategy 2: Snov.io ──────────────────────────────

async def _snov_get_access_token(client: httpx.AsyncClient) -> str | None:
    """Get Snov.io OAuth access token using client credentials."""
    user_id = os.getenv("SNOV_USER_ID", "")
    secret = os.getenv("SNOV_API_SECRET", "")
    if not user_id or not secret:
        return None

    resp = await client.post(
        "https://api.snov.io/v1/oauth/access_token",
        json={
            "grant_type": "client_credentials",
            "client_id": user_id,
            "client_secret": secret,
        },
    )
    resp.raise_for_status()
    return resp.json().get("access_token")


async def find_via_snov(
    company_name: str,
    domain: str,
) -> list[EmailCandidate]:
    """Search Snov.io for emails at a domain.

    Uses OAuth + Domain Search API. Free tier: 50 credits/month.
    """
    user_id = os.getenv("SNOV_USER_ID", "")
    secret = os.getenv("SNOV_API_SECRET", "")
    if not user_id or not secret:
        return []

    results = []

    try:
        async with httpx.AsyncClient(timeout=EMAIL_FINDER_TIMEOUT) as client:
            token = await _snov_get_access_token(client)
            if not token:
                return []

            params = {
                "domain": domain,
                "type": "all",
                "limit": 5,
                "access_token": token,
            }
            resp = await client.get(
                "https://api.snov.io/v2/domain-emails-with-info",
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("emails", []):
                email = item.get("email")
                if email:
                    results.append(EmailCandidate(
                        email=email,
                        name=f"{item.get('firstName', '')} {item.get('lastName', '')}".strip(),
                        role=item.get("position", ""),
                        source="snov",
                        confidence="high",
                    ))

        logger.info(f"Snov: found {len(results)} emails for {domain}")
    except httpx.HTTPError as e:
        logger.warning(f"Snov API failed for {domain}: {e}")

    return results


# ─── Strategy 3: Hunter.io ─────────────────────────────

async def find_via_hunter(
    company_name: str,
    domain: str,
) -> list[EmailCandidate]:
    """Search Hunter.io for email pattern + contacts at a domain.

    Free tier: 25 searches/month. Use sparingly — only for high-value targets.
    """
    api_key = os.getenv("HUNTER_API_KEY", "")
    if not api_key:
        return []

    url = "https://api.hunter.io/v2/domain-search"
    results = []

    try:
        async with httpx.AsyncClient(timeout=EMAIL_FINDER_TIMEOUT) as client:
            params = {
                "domain": domain,
                "api_key": api_key,
                "limit": 5,
            }
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json().get("data", {})

            for item in data.get("emails", []):
                email = item.get("value")
                if email:
                    results.append(EmailCandidate(
                        email=email,
                        name=f"{item.get('first_name', '')} {item.get('last_name', '')}".strip(),
                        role=item.get("position", ""),
                        source="hunter",
                        confidence="high" if item.get("confidence", 0) > 80 else "medium",
                    ))

        logger.info(f"Hunter: found {len(results)} emails for {domain}")
    except httpx.HTTPError as e:
        logger.warning(f"Hunter API failed for {domain}: {e}")

    return results


# ─── Strategy 4: Company Team Page Scraping ────────────

# Common team/about page paths to try
_TEAM_PATHS = [
    "/team", "/about", "/about-us", "/our-team", "/people",
    "/company", "/careers", "/about/team",
]

# Patterns that indicate HR/recruiting roles
_HR_ROLE_PATTERNS = re.compile(
    r"(?i)(hr|human\s*resource|recruit|talent|hiring|people\s*ops|people\s*&\s*culture)",
)


async def find_via_team_page(
    company_name: str,
    domain: str,
) -> list[EmailCandidate]:
    """Scrape company team/about pages for HR contact info.

    Looks for email addresses and names+roles on team pages.
    Free, unlimited, no API key needed.
    """
    results = []
    base_url = f"https://{domain}"

    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; JobSearchBot/1.0)"},
        ) as client:
            for path in _TEAM_PATHS:
                try:
                    resp = await client.get(f"{base_url}{path}")
                    if resp.status_code != 200:
                        continue

                    soup = BeautifulSoup(resp.text, "lxml")
                    text = soup.get_text(separator=" ")

                    # Find all email addresses on the page
                    emails_found = re.findall(
                        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                        text,
                    )

                    for email in emails_found:
                        # Skip generic addresses
                        if any(g in email.lower() for g in ["noreply", "no-reply", "info@", "support@", "contact@"]):
                            continue
                        results.append(EmailCandidate(
                            email=email,
                            source="team_page",
                            confidence="medium",
                        ))

                    # If we found emails, no need to check more paths
                    if results:
                        break

                except httpx.HTTPError:
                    continue

        logger.info(f"Team page: found {len(results)} emails for {domain}")
    except httpx.HTTPError as e:
        logger.debug(f"Team page scraping failed for {domain}: {e}")

    return results


# ─── Strategy 5: Pattern Guessing ──────────────────────

def guess_email_patterns(
    first_name: str,
    last_name: str,
    domain: str,
) -> list[EmailCandidate]:
    """Generate common email pattern guesses.

    Most companies use one of these formats:
    - firstname@company.com (most common in Indian startups)
    - first.last@company.com
    - firstlast@company.com
    - f.last@company.com
    - first_last@company.com
    """
    first = first_name.lower().strip()
    last = last_name.lower().strip()

    if not first or not domain:
        return []

    patterns = [
        f"{first}@{domain}",
        f"{first}.{last}@{domain}" if last else None,
        f"{first}{last}@{domain}" if last else None,
        f"{first[0]}.{last}@{domain}" if last else None,
        f"{first}_{last}@{domain}" if last else None,
    ]

    return [
        EmailCandidate(
            email=p,
            name=f"{first_name} {last_name}".strip(),
            source="pattern_guess",
            confidence="low",
        )
        for p in patterns if p
    ]


def guess_generic_emails(domain: str) -> list[EmailCandidate]:
    """Generate generic HR/careers email guesses for a domain."""
    return [
        EmailCandidate(
            email=f"{prefix}@{domain}",
            source="pattern_guess",
            confidence="low",
        )
        for prefix in GENERIC_EMAIL_PREFIXES
    ]


# ─── Orchestrator ──────────────────────────────────────

def extract_domain_from_url(url: str) -> str:
    """Extract the company domain from a job URL or company website."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace("www.", "")
        # Strip known job board domains — we want the company domain
        job_boards = {
            "naukri.com", "indeed.com", "linkedin.com", "glassdoor.com",
            "wellfound.com", "internshala.com", "cutshort.io", "hirist.pro",
            "greenhouse.io", "lever.co", "boards.greenhouse.io", "jobs.lever.co",
            "remoteok.com", "jooble.org", "adzuna.com", "foundit.com",
        }
        if any(jb in domain for jb in job_boards):
            return ""
        return domain
    except (ValueError, AttributeError):
        return ""


def guess_company_domain(company_name: str) -> str:
    """Guess the company domain from the company name.

    Simple heuristic: lowercase, remove spaces/special chars, add .com
    """
    if not company_name:
        return ""
    # Clean company name
    clean = company_name.lower().strip()
    # Remove common suffixes
    for suffix in [" pvt ltd", " private limited", " ltd", " inc", " llc", " corp", " technologies", " tech", " software", " solutions"]:
        clean = clean.replace(suffix, "")
    # Remove special chars and spaces
    clean = re.sub(r"[^a-z0-9]", "", clean)
    if not clean:
        return ""
    return f"{clean}.com"


async def find_emails(
    company_name: str,
    job_url: str = "",
    recruiter_name: str = "",
    high_value: bool = False,
    max_results: int = 5,
) -> list[EmailCandidate]:
    """Main orchestrator: find emails using the 5-strategy priority chain.

    Args:
        company_name: The company to find emails for
        job_url: The job posting URL (used to extract domain)
        recruiter_name: If known (from LinkedIn etc.), used for pattern guessing
        high_value: If True, use all strategies including API credits
        max_results: Maximum number of email candidates to return

    Returns:
        List of EmailCandidate objects, sorted by confidence (high → low)
    """
    # Determine company domain
    domain = extract_domain_from_url(job_url)
    if not domain:
        domain = guess_company_domain(company_name)
    if not domain:
        logger.warning(f"Could not determine domain for {company_name}")
        return []

    logger.info(f"Finding emails for {company_name} (domain: {domain})")

    all_candidates = []

    # Strategy 1-3: API-based (only if high_value or we have credits)
    if high_value:
        # Try all API services
        for strategy in [find_via_apollo, find_via_snov, find_via_hunter]:
            candidates = await strategy(company_name, domain)
            all_candidates.extend(candidates)
            if len(all_candidates) >= max_results:
                break
    else:
        # Just try Apollo (most generous free tier)
        candidates = await find_via_apollo(company_name, domain)
        all_candidates.extend(candidates)

    # Strategy 4: Free scraping (team page only — GitHub/Google removed for ToS)
    if len(all_candidates) < max_results:
        candidates = await find_via_team_page(company_name, domain)
        all_candidates.extend(candidates)

    # Strategy 7: Pattern guessing (always as fallback)
    if len(all_candidates) < max_results:
        if recruiter_name:
            parts = recruiter_name.strip().split()
            first = parts[0] if parts else ""
            last = parts[-1] if len(parts) > 1 else ""
            all_candidates.extend(guess_email_patterns(first, last, domain))
        else:
            all_candidates.extend(guess_generic_emails(domain))

    # Deduplicate by email
    seen = set()
    unique = []
    for c in all_candidates:
        email_lower = c.email.lower()
        if email_lower not in seen:
            seen.add(email_lower)
            unique.append(c)

    # Sort by confidence: high > medium > low
    confidence_order = {"high": 0, "medium": 1, "low": 2}
    unique.sort(key=lambda c: confidence_order.get(c.confidence, 3))

    result = unique[:max_results]
    logger.info(
        f"Email finder: {len(result)} candidates for {company_name} "
        f"({', '.join(c.source for c in result)})"
    )
    return result
