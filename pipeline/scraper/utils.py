"""Shared utilities for all scrapers.

Extracted from duplicated code across aggregator_scraper.py, remote_boards.py,
api_boards.py, ats_direct.py, and jobspy_scraper.py. Import these instead of
re-implementing in each scraper file.
"""

import html
import re
from datetime import date, datetime

from core.constants import GENERIC_JOB_TERMS
from core.models import ProfileConfig


def strip_html(text: str) -> str:
    """Strip HTML tags and decode entities. Returns plain text."""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_date_iso(date_str: str | None) -> date | None:
    """Parse ISO 8601 date string (handles 'Z' suffix)."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
    except (ValueError, AttributeError):
        return None


def parse_date_timestamp(ts: int | float | None, milliseconds: bool = False) -> date | None:
    """Parse a Unix timestamp to date.

    Args:
        ts: Unix timestamp (seconds by default, milliseconds if flag set).
        milliseconds: If True, divide by 1000 before converting.
    """
    if ts is None:
        return None
    try:
        if milliseconds:
            ts = ts / 1000
        return datetime.fromtimestamp(int(ts)).date()
    except (ValueError, TypeError, OSError):
        return None


def parse_salary_value(val) -> int | None:
    """Parse a salary value to int, handling strings/floats/None."""
    if val is None:
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def parse_salary_range(salary_str: str) -> tuple[int | None, int | None]:
    """Parse a salary range string like '$60,000 - $80,000' into (min, max)."""
    if not salary_str:
        return None, None
    numbers = re.findall(r"[\d,]+", salary_str.replace(",", ""))
    if len(numbers) >= 2:
        return parse_salary_value(numbers[0]), parse_salary_value(numbers[1])
    elif len(numbers) == 1:
        return parse_salary_value(numbers[0]), None
    return None, None


def build_skill_set(profile: ProfileConfig) -> set[str]:
    """Build lowercase skill set from profile (primary + secondary + generic terms)."""
    primary_lower = {s.lower() for s in profile.skills.primary}
    secondary_lower = {s.lower() for s in profile.skills.secondary}
    all_skills = primary_lower | secondary_lower
    all_skills |= GENERIC_JOB_TERMS
    return all_skills


def check_relevance(title: str, description: str, skills: set[str]) -> bool:
    """Check if job title/description matches any skill."""
    title_lower = title.lower()
    desc_lower = description.lower()
    return any(
        skill in desc_lower or skill in title_lower
        for skill in skills
    )


def is_short_description(desc: str, min_length: int = 50) -> bool:
    """Return True if description is too short to be useful."""
    return len(desc.strip()) < min_length
