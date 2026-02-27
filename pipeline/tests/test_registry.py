"""Tests for scraper registry — decorator registration, lookup, and execution."""

import os
import sys

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import ProfileConfig
from scraper.registry import (
    _REGISTRY,
    ScraperEntry,
    get_all_scrapers,
    get_group,
    get_groups,
    get_scraper,
    run_scraper,
    scraper,
)

# ─── Helpers ──────────────────────────────────────────────

def _make_profile() -> ProfileConfig:
    """Create a minimal valid ProfileConfig for testing."""
    return ProfileConfig(
        candidate={
            "name": "Test User",
            "email": "test@example.com",
            "phone": "1234567890",
            "resume_path": "/tmp/resume.pdf",
            "location": "Bengaluru",
        },
        search_preferences={"locations": ["Bengaluru"]},
        skills={"primary": ["Python"]},
        experience={"graduation_year": 2023, "degree": "B.Tech"},
        filters={"must_have_any": ["python"]},
    )


# Track test scrapers registered by these tests so we can clean up
_TEST_SCRAPER_NAMES = []


def _cleanup_test_scrapers():
    """Remove test scrapers from registry."""
    for name in _TEST_SCRAPER_NAMES:
        _REGISTRY.pop(name, None)
    _TEST_SCRAPER_NAMES.clear()


# ─── Registry Registration ───────────────────────────────

class TestRegistry:
    """Decorator-based registration and lookups."""

    def setup_method(self):
        """Track scrapers we register."""
        pass

    def teardown_method(self):
        """Clean up test scrapers from global registry."""
        _cleanup_test_scrapers()

    def test_scraper_decorator_registers(self):
        """@scraper() should register the function in _REGISTRY."""
        @scraper("_test_alpha", group="_test_group")
        async def scrape_alpha(profile, limit=10):
            return []

        _TEST_SCRAPER_NAMES.append("_test_alpha")

        assert "_test_alpha" in _REGISTRY
        entry = _REGISTRY["_test_alpha"]
        assert entry.name == "_test_alpha"
        assert entry.group == "_test_group"
        assert entry.func is scrape_alpha

    def test_get_scraper_returns_entry(self):
        """get_scraper() should return the ScraperEntry for a known name."""
        @scraper("_test_beta", group="_test_group")
        async def scrape_beta(profile, limit=10):
            return []

        _TEST_SCRAPER_NAMES.append("_test_beta")

        entry = get_scraper("_test_beta")
        assert entry is not None
        assert entry.name == "_test_beta"

    def test_get_scraper_unknown_returns_none(self):
        """get_scraper() for an unknown name should return None."""
        assert get_scraper("_nonexistent_scraper_xyz") is None

    def test_get_group(self):
        """get_group() should return all scrapers in a given group."""
        @scraper("_test_g1", group="_test_grp_x")
        async def scrape_g1(profile, limit=10):
            return []

        @scraper("_test_g2", group="_test_grp_x")
        async def scrape_g2(profile, limit=10):
            return []

        @scraper("_test_g3", group="_test_grp_y")
        async def scrape_g3(profile, limit=10):
            return []

        _TEST_SCRAPER_NAMES.extend(["_test_g1", "_test_g2", "_test_g3"])

        group = get_group("_test_grp_x")
        names = [e.name for e in group]
        assert "_test_g1" in names
        assert "_test_g2" in names
        assert "_test_g3" not in names

    def test_get_groups(self):
        """get_groups() should return sorted unique group names."""
        @scraper("_test_gg1", group="_test_gg_a")
        async def scrape_gg1(profile, limit=10):
            return []

        @scraper("_test_gg2", group="_test_gg_b")
        async def scrape_gg2(profile, limit=10):
            return []

        _TEST_SCRAPER_NAMES.extend(["_test_gg1", "_test_gg2"])

        groups = get_groups()
        assert "_test_gg_a" in groups
        assert "_test_gg_b" in groups
        # Should be sorted
        assert groups == sorted(groups)

    def test_get_all_scrapers_includes_registered(self):
        """get_all_scrapers() should include all registered scrapers."""
        @scraper("_test_all", group="_test_all_grp")
        async def scrape_all_test(profile, limit=10):
            return []

        _TEST_SCRAPER_NAMES.append("_test_all")

        all_scrapers = get_all_scrapers()
        assert "_test_all" in all_scrapers
        assert isinstance(all_scrapers["_test_all"], ScraperEntry)


# ─── Run Scraper ─────────────────────────────────────────

class TestRunScraper:
    """Running individual scrapers by name."""

    def teardown_method(self):
        _cleanup_test_scrapers()

    @pytest.mark.asyncio
    async def test_run_scraper_with_mock_function(self):
        """run_scraper() should call the registered async function."""
        mock_jobs = [{"title": "Python Dev", "company": "TestCo"}]

        @scraper("_test_run", group="_test_run_grp")
        async def scrape_run_test(profile, limit=10):
            return mock_jobs

        _TEST_SCRAPER_NAMES.append("_test_run")

        profile = _make_profile()
        result = await run_scraper("_test_run", profile, limit=5)
        assert result == mock_jobs

    @pytest.mark.asyncio
    async def test_run_scraper_unknown_returns_empty(self):
        """run_scraper() with unknown name should return empty list."""
        profile = _make_profile()
        result = await run_scraper("_nonexistent_scraper_abc", profile)
        assert result == []

    @pytest.mark.asyncio
    async def test_run_scraper_handles_httpx_timeout(self):
        """run_scraper() should catch httpx.TimeoutException and return []."""
        @scraper("_test_timeout", group="_test_timeout_grp")
        async def scrape_timeout(profile, limit=10):
            raise httpx.TimeoutException("Connection timed out")

        _TEST_SCRAPER_NAMES.append("_test_timeout")

        profile = _make_profile()
        result = await run_scraper("_test_timeout", profile)
        assert result == []

    @pytest.mark.asyncio
    async def test_run_scraper_handles_connect_error(self):
        """run_scraper() should catch httpx.ConnectError and return []."""
        @scraper("_test_conn_err", group="_test_conn_grp")
        async def scrape_conn_err(profile, limit=10):
            raise httpx.ConnectError("Connection refused")

        _TEST_SCRAPER_NAMES.append("_test_conn_err")

        profile = _make_profile()
        result = await run_scraper("_test_conn_err", profile)
        assert result == []

    @pytest.mark.asyncio
    async def test_run_scraper_handles_http_status_error(self):
        """run_scraper() should catch httpx.HTTPStatusError and return []."""
        @scraper("_test_http_err", group="_test_http_grp")
        async def scrape_http_err(profile, limit=10):
            response = httpx.Response(status_code=500, request=httpx.Request("GET", "https://example.com"))
            raise httpx.HTTPStatusError("Server Error", request=response.request, response=response)

        _TEST_SCRAPER_NAMES.append("_test_http_err")

        profile = _make_profile()
        result = await run_scraper("_test_http_err", profile)
        assert result == []

    @pytest.mark.asyncio
    async def test_run_scraper_handles_unexpected_error(self):
        """run_scraper() should catch unexpected exceptions and return []."""
        @scraper("_test_unexpected", group="_test_unexpected_grp")
        async def scrape_unexpected(profile, limit=10):
            raise RuntimeError("Something went terribly wrong")

        _TEST_SCRAPER_NAMES.append("_test_unexpected")

        profile = _make_profile()
        result = await run_scraper("_test_unexpected", profile)
        assert result == []

    @pytest.mark.asyncio
    async def test_run_scraper_passes_limit(self):
        """run_scraper() should pass the limit parameter to the function."""
        received_limit = None

        @scraper("_test_limit", group="_test_limit_grp")
        async def scrape_limit_test(profile, limit=10):
            nonlocal received_limit
            received_limit = limit
            return []

        _TEST_SCRAPER_NAMES.append("_test_limit")

        profile = _make_profile()
        await run_scraper("_test_limit", profile, limit=42)
        assert received_limit == 42
