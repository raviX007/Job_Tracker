"""Job deduplication — URL-based + content-based.

Prevents the same job from being processed multiple times, even if
discovered from different sources (e.g., Jooble linking to Naukri).
"""

import hashlib
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

# Tracking params to strip from job URLs
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "fbclid", "gclid", "li_fat_id", "mc_cid", "mc_eid",
    "source", "clickId", "trackingId", "stm_source", "stm_medium",
}


def normalize_url(url: str) -> str:
    """Strip tracking parameters and normalize a job URL.

    - Removes utm_*, ref, fbclid, gclid, etc.
    - Lowercases the domain
    - Strips trailing slashes
    """
    if not url:
        return ""

    try:
        parsed = urlparse(url.strip())
        # Lowercase domain
        netloc = parsed.netloc.lower()
        # Strip tracking params
        params = parse_qs(parsed.query, keep_blank_values=False)
        clean_params = {
            k: v for k, v in params.items()
            if k.lower() not in _TRACKING_PARAMS
        }
        clean_query = urlencode(clean_params, doseq=True)
        # Rebuild URL
        cleaned = urlunparse((
            parsed.scheme,
            netloc,
            parsed.path.rstrip("/"),
            parsed.params,
            clean_query,
            "",  # Drop fragment
        ))
        return cleaned
    except (ValueError, AttributeError):
        return url.strip()


def make_dedup_key(job: dict) -> str:
    """Generate a dedup key for a job.

    Primary: normalized URL hash.
    Fallback: company|title|location hash (catches same job from different URLs).
    """
    url = normalize_url(job.get("job_url", ""))
    if url:
        return hashlib.sha256(url.encode()).hexdigest()[:32]

    # Fallback: content-based dedup
    company = (job.get("company") or "").strip().lower()
    title = (job.get("title") or "").strip().lower()
    location = (job.get("location") or "").strip().lower()
    content = f"{company}|{title}|{location}"
    return hashlib.sha256(content.encode()).hexdigest()[:32]
