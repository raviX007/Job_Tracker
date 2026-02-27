"""Scraper registry — decorator-based auto-discovery.

Adding a new scraper = 1 file + 1 @scraper decorator. No more editing
pipeline.py, dry_run.py, or test_scrapers.py.

Usage in scraper files:
    from scraper.registry import scraper

    @scraper("remotive", group="remote_boards")
    async def scrape_remotive(profile, limit=30):
        ...

Usage in pipeline/scripts:
    from scraper.registry import run_all, run_group, run_scraper, get_all_scrapers
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx

from core.logger import logger
from core.models import ProfileConfig


@dataclass
class ScraperEntry:
    name: str
    group: str
    func: Callable[..., Awaitable[list[dict]]]
    needs_key: str | None = None  # env var name, None if no auth needed


_REGISTRY: dict[str, ScraperEntry] = {}


def scraper(
    name: str,
    group: str = "misc",
    needs_key: str | None = None,
):
    """Decorator to register a scraper function.

    Args:
        name: Unique scraper name (e.g. "remotive", "greenhouse").
        group: Group name for batch execution (e.g. "remote_boards", "ats_direct").
        needs_key: Env var name required (e.g. "RAPIDAPI_KEY"). None if no auth.
    """
    def decorator(func):
        _REGISTRY[name] = ScraperEntry(
            name=name, group=group, func=func, needs_key=needs_key,
        )
        return func
    return decorator


def get_scraper(name: str) -> ScraperEntry | None:
    """Get a single scraper entry by name."""
    return _REGISTRY.get(name)


def get_all_scrapers() -> dict[str, ScraperEntry]:
    """Get all registered scrapers."""
    return dict(_REGISTRY)


def get_group(group: str) -> list[ScraperEntry]:
    """Get all scrapers in a group."""
    return [s for s in _REGISTRY.values() if s.group == group]


def get_groups() -> list[str]:
    """Get all unique group names."""
    return sorted(set(s.group for s in _REGISTRY.values()))


async def run_scraper(
    name: str,
    profile: ProfileConfig,
    limit: int = 20,
) -> list[dict]:
    """Run a single scraper by name."""
    entry = _REGISTRY.get(name)
    if not entry:
        logger.error(f"Unknown scraper: '{name}'. Available: {', '.join(sorted(_REGISTRY))}")
        return []

    try:
        return await entry.func(profile, limit=limit)
    except httpx.TimeoutException:
        logger.warning(f"Scraper '{name}' timed out")
        return []
    except httpx.ConnectError as e:
        logger.warning(f"Scraper '{name}' connection failed: {e}")
        return []
    except httpx.HTTPStatusError as e:
        logger.warning(f"Scraper '{name}' HTTP error {e.response.status_code}: {e}")
        return []
    except Exception as e:
        logger.error(f"Scraper '{name}' unexpected error: {e}", exc_info=True)
        return []


async def run_group(
    group: str,
    profile: ProfileConfig,
    limit: int = 20,
) -> list[dict]:
    """Run all scrapers in a group concurrently."""
    entries = get_group(group)
    if not entries:
        logger.info(f"No scrapers in group '{group}'")
        return []

    results = await asyncio.gather(
        *(entry.func(profile, limit=limit) for entry in entries),
        return_exceptions=True,
    )

    all_jobs = []
    for entry, result in zip(entries, results, strict=False):
        if isinstance(result, httpx.TimeoutException):
            logger.warning(f"Scraper '{entry.name}' timed out")
        elif isinstance(result, httpx.ConnectError):
            logger.warning(f"Scraper '{entry.name}' connection failed")
        elif isinstance(result, Exception):
            logger.error(f"Scraper '{entry.name}' failed: {result}")
        elif isinstance(result, list):
            all_jobs.extend(result)

    logger.info(f"Group '{group}': {len(all_jobs)} jobs from {len(entries)} scrapers")
    return all_jobs


async def run_all(
    profile: ProfileConfig,
    limit: int = 20,
) -> list[dict]:
    """Run ALL registered scrapers concurrently (grouped by group)."""
    groups = get_groups()

    # Run all groups concurrently
    results = await asyncio.gather(
        *(run_group(g, profile, limit) for g in groups),
        return_exceptions=True,
    )

    all_jobs = []
    for group_name, result in zip(groups, results, strict=False):
        if isinstance(result, Exception):
            logger.error(f"Group '{group_name}' failed: {result}")
        elif isinstance(result, list):
            all_jobs.extend(result)

    logger.info(f"All scrapers: {len(all_jobs)} total jobs from {len(groups)} groups")
    return all_jobs
