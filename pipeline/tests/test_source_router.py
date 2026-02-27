"""Tests for source routing — URL domain → action classification."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import PlatformConfig, ProfileConfig
from scraper.source_router import (
    _extract_domain,
    classify_source,
    route_job,
)

# ─── _extract_domain ─────────────────────────────────────

class TestExtractDomain:
    """Domain extraction from URLs."""

    def test_simple_url(self):
        assert _extract_domain("https://example.com/jobs") == "example.com"

    def test_strips_www(self):
        assert _extract_domain("https://www.example.com/jobs") == "example.com"

    def test_lowercases(self):
        assert _extract_domain("https://WWW.EXAMPLE.COM/jobs") == "example.com"

    def test_subdomain(self):
        assert _extract_domain("https://boards.greenhouse.io/company") == "boards.greenhouse.io"

    def test_empty_url(self):
        assert _extract_domain("") == ""

    def test_malformed_url(self):
        result = _extract_domain("not-a-url")
        assert isinstance(result, str)


# ─── classify_source ─────────────────────────────────────

class TestClassifySource:
    """URL → platform + category classification."""

    def test_naukri_auto_apply(self):
        result = classify_source("https://www.naukri.com/job/123")
        assert result["platform"] == "naukri"
        assert result["category"] == "auto_apply"
        assert result["auto_apply"] is True

    def test_indeed_auto_apply(self):
        result = classify_source("https://in.indeed.com/viewjob?jk=abc")
        assert result["platform"] == "indeed"
        assert result["auto_apply"] is True

    def test_foundit_auto_apply(self):
        result = classify_source("https://www.foundit.com/job/123")
        assert result["platform"] == "foundit"
        assert result["auto_apply"] is True

    def test_linkedin_manual_only(self):
        result = classify_source("https://www.linkedin.com/jobs/view/123")
        assert result["platform"] == "linkedin"
        assert result["category"] == "manual_only"
        assert result["auto_apply"] is False
        assert result["manual_alert"] is True

    def test_wellfound_manual_only(self):
        result = classify_source("https://wellfound.com/jobs/123")
        assert result["platform"] == "wellfound"
        assert result["category"] == "manual_only"

    def test_greenhouse_ats(self):
        result = classify_source("https://boards.greenhouse.io/company/jobs/123")
        assert result["platform"] == "greenhouse"
        assert result["category"] == "ats"
        assert result["cold_email"] is True

    def test_lever_ats(self):
        result = classify_source("https://jobs.lever.co/company/123")
        assert result["platform"] == "lever"
        assert result["category"] == "ats"

    def test_glassdoor_scrape_only(self):
        result = classify_source("https://www.glassdoor.com/job/123")
        assert result["platform"] == "glassdoor"
        assert result["category"] == "scrape_only"
        assert result["auto_apply"] is False

    def test_unknown_domain_company_page(self):
        result = classify_source("https://careers.acmecorp.com/job/sde")
        assert result["platform"] == "unknown"
        assert result["category"] == "company_page"
        assert result["cold_email"] is True

    def test_empty_url(self):
        result = classify_source("")
        assert result["platform"] == "unknown"
        assert result["category"] == "company_page"


# ─── route_job ────────────────────────────────────────────

def _minimal_profile(**overrides) -> ProfileConfig:
    """Create a minimal valid profile for testing."""
    data = {
        "candidate": {
            "name": "Test", "email": "t@t.com", "phone": "123",
            "resume_path": "/tmp/r.pdf", "location": "Bengaluru",
        },
        "search_preferences": {"locations": ["Bengaluru"]},
        "skills": {"primary": ["Python"]},
        "experience": {"graduation_year": 2023, "degree": "B.Tech"},
        "filters": {"must_have_any": ["python"]},
    }
    data.update(overrides)
    return ProfileConfig(**data)


class TestRouteJob:
    """End-to-end job routing with profile config."""

    def test_naukri_with_auto_apply_enabled(self):
        profile = _minimal_profile(platforms={
            "naukri": PlatformConfig(enabled=True, auto_apply=True),
        })
        job = {"job_url": "https://www.naukri.com/job/123"}
        result = route_job(job, profile)
        assert result["route_action"] == "auto_apply_and_cold_email"

    def test_naukri_with_auto_apply_disabled(self):
        profile = _minimal_profile(platforms={
            "naukri": PlatformConfig(enabled=True, auto_apply=False),
        })
        job = {"job_url": "https://www.naukri.com/job/123"}
        result = route_job(job, profile)
        assert result["route_action"] == "cold_email_only"

    def test_disabled_platform(self):
        profile = _minimal_profile(platforms={
            "naukri": PlatformConfig(enabled=False),
        })
        job = {"job_url": "https://www.naukri.com/job/123"}
        result = route_job(job, profile)
        # Disabled platform → no auto_apply, no cold_email → manual_alert
        assert result["route_action"] == "manual_alert"

    def test_linkedin_always_manual(self):
        profile = _minimal_profile()
        job = {"job_url": "https://www.linkedin.com/jobs/view/123"}
        result = route_job(job, profile)
        assert result["route_action"] == "manual_alert"

    def test_company_page_cold_email(self):
        profile = _minimal_profile()
        job = {"job_url": "https://careers.stripe.com/listing/sde"}
        result = route_job(job, profile)
        assert result["route_action"] == "cold_email_only"
