"""Tests for scraper normalize functions — all normalizers."""

import os
import sys
from datetime import date
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.aggregator_scraper import _normalize_adzuna, _normalize_hiringcafe, _normalize_jooble, _normalize_remoteok
from scraper.api_boards import _normalize_careerjet, _normalize_findwork, _normalize_jsearch, _normalize_themuse
from scraper.ats_direct import _normalize_greenhouse, _normalize_lever
from scraper.remote_boards import _normalize_arbeitnow, _normalize_himalayas, _normalize_jobicy, _normalize_remotive
from scraper.startup_scouts import _batch_to_date, _parse_hn_comment

# ─── Helpers ──────────────────────────────────────────────

LONG_DESC = "This is a detailed job description. " * 10  # well over 50 chars
SHORT_DESC = "Short"


# ─── _normalize_remoteok ─────────────────────────────────

class TestNormalizeRemoteOK:
    """Normalize RemoteOK job objects."""

    def test_valid_job(self):
        """A valid RemoteOK job with matching skills should normalize."""
        raw = {
            "position": "Python Developer",
            "company": "Acme Corp",
            "description": LONG_DESC,
            "tags": ["python", "django"],
            "url": "/l/12345",
            "date": "2024-06-15",
            "salary_min": 50000,
            "salary_max": 80000,
        }
        skills = {"python", "django", "developer"}
        result = _normalize_remoteok(raw, skills)
        assert result is not None
        assert result["title"] == "Python Developer"
        assert result["company"] == "Acme Corp"
        assert result["source"] == "remoteok"
        assert result["is_remote"] is True
        assert result["job_url"].startswith("https://remoteok.com")
        assert result["salary_min"] == 50000
        assert result["salary_max"] == 80000

    def test_short_description_returns_none(self):
        """Jobs with too-short descriptions should be filtered out."""
        raw = {
            "position": "Python Dev",
            "company": "Acme",
            "description": SHORT_DESC,
            "tags": ["python"],
            "url": "/l/123",
        }
        skills = {"python"}
        assert _normalize_remoteok(raw, skills) is None

    def test_irrelevant_returns_none(self):
        """Jobs that don't match any skills should be filtered out."""
        raw = {
            "position": "Chef Cook",
            "company": "Restaurant",
            "description": "Looking for an experienced chef to run our kitchen operations daily.",
            "tags": ["cooking", "food"],
            "url": "/l/456",
        }
        skills = {"python", "django", "developer"}
        assert _normalize_remoteok(raw, skills) is None

    def test_full_url_not_prefixed(self):
        """If the URL already starts with http, it should not be prefixed."""
        raw = {
            "position": "Python Dev",
            "company": "Acme",
            "description": LONG_DESC,
            "tags": ["python"],
            "url": "https://example.com/job/123",
        }
        skills = {"python"}
        result = _normalize_remoteok(raw, skills)
        assert result is not None
        assert result["job_url"] == "https://example.com/job/123"


# ─── _normalize_jooble ──────────────────────────────────

class TestNormalizeJooble:
    """Normalize Jooble job objects."""

    def test_valid_job(self):
        """A valid Jooble job should normalize correctly."""
        raw = {
            "title": "Backend Developer",
            "company": "TechCo",
            "snippet": LONG_DESC,
            "link": "https://jooble.org/job/12345",
            "location": "Remote, India",
            "updated": "2024-07-01",
            "salary_min": 600000,
            "salary_max": 1000000,
        }
        result = _normalize_jooble(raw)
        assert result is not None
        assert result["title"] == "Backend Developer"
        assert result["company"] == "TechCo"
        assert result["source"] == "jooble"
        assert result["job_url"] == "https://jooble.org/job/12345"
        assert result["is_remote"] is True  # "remote" in location
        assert result["salary_currency"] == "INR"

    def test_no_url_returns_none(self):
        """Jobs without a link should be filtered out."""
        raw = {
            "title": "Developer",
            "company": "Co",
            "snippet": LONG_DESC,
            "link": "",
        }
        assert _normalize_jooble(raw) is None

    def test_short_description_returns_none(self):
        """Jobs with too-short snippet should be filtered out."""
        raw = {
            "title": "Developer",
            "company": "Co",
            "snippet": SHORT_DESC,
            "link": "https://jooble.org/job/1",
        }
        assert _normalize_jooble(raw) is None

    def test_not_remote_location(self):
        """Jobs without 'remote' in location should have is_remote=False."""
        raw = {
            "title": "Developer",
            "company": "Co",
            "snippet": LONG_DESC,
            "link": "https://jooble.org/job/2",
            "location": "Bengaluru, India",
        }
        result = _normalize_jooble(raw)
        assert result is not None
        assert result["is_remote"] is False


# ─── _normalize_remotive ────────────────────────────────

class TestNormalizeRemotive:
    """Normalize Remotive job objects."""

    def test_valid_job(self):
        """A valid Remotive job with matching skills should normalize."""
        raw = {
            "title": "Full Stack Developer",
            "company_name": "StartupX",
            "description": LONG_DESC,
            "tags": ["python", "react"],
            "url": "https://remotive.com/remote-jobs/software-dev/12345",
            "candidate_required_location": "Worldwide",
            "publication_date": "2024-08-01",
            "salary": "$60,000 - $90,000",
        }
        skills = {"python", "react", "developer"}
        result = _normalize_remotive(raw, skills)
        assert result is not None
        assert result["title"] == "Full Stack Developer"
        assert result["company"] == "StartupX"
        assert result["source"] == "remotive"
        assert result["is_remote"] is True
        assert result["job_url"] == "https://remotive.com/remote-jobs/software-dev/12345"
        assert result["salary_min"] == 60000
        assert result["salary_max"] == 90000

    def test_no_match_returns_none(self):
        """Jobs that don't match any skills should be filtered out."""
        raw = {
            "title": "Marketing Manager",
            "company_name": "AdCo",
            "description": "Managing advertising campaigns and brand strategy for the team.",
            "tags": ["marketing", "advertising"],
            "url": "https://remotive.com/remote-jobs/marketing/999",
        }
        skills = {"python", "django", "developer"}
        assert _normalize_remotive(raw, skills) is None

    def test_no_url_returns_none(self):
        """Jobs without a URL should be filtered out."""
        raw = {
            "title": "Python Developer",
            "company_name": "Co",
            "description": LONG_DESC,
            "tags": ["python"],
            "url": "",
        }
        skills = {"python"}
        assert _normalize_remotive(raw, skills) is None

    def test_short_description_returns_none(self):
        """Jobs with too-short descriptions should be filtered out."""
        raw = {
            "title": "Dev",
            "company_name": "Co",
            "description": SHORT_DESC,
            "tags": ["python"],
            "url": "https://remotive.com/job/1",
        }
        skills = {"python"}
        assert _normalize_remotive(raw, skills) is None


# ─── _normalize_jobicy ──────────────────────────────────

class TestNormalizeJobicy:
    """Normalize Jobicy job objects."""

    def test_valid_job(self):
        """A valid Jobicy job should normalize correctly."""
        raw = {
            "jobTitle": "Django Developer",
            "companyName": "WebCo",
            "jobDescription": LONG_DESC,
            "url": "https://jobicy.com/jobs/12345",
            "jobGeo": "India",
            "pubDate": "2024-09-01",
            "annualSalaryMin": 40000,
            "annualSalaryMax": 60000,
            "salaryCurrency": "USD",
        }
        result = _normalize_jobicy(raw)
        assert result is not None
        assert result["title"] == "Django Developer"
        assert result["company"] == "WebCo"
        assert result["source"] == "jobicy"
        assert result["is_remote"] is True
        assert result["location"] == "India"
        assert result["salary_min"] == 40000
        assert result["salary_max"] == 60000
        assert result["salary_currency"] == "USD"

    def test_no_url_returns_none(self):
        """Jobs without a URL should be filtered out."""
        raw = {
            "jobTitle": "Dev",
            "companyName": "Co",
            "jobDescription": LONG_DESC,
            "url": "",
        }
        assert _normalize_jobicy(raw) is None

    def test_short_description_returns_none(self):
        """Jobs with too-short descriptions should be filtered out."""
        raw = {
            "jobTitle": "Dev",
            "companyName": "Co",
            "jobDescription": SHORT_DESC,
            "url": "https://jobicy.com/jobs/1",
        }
        assert _normalize_jobicy(raw) is None

    def test_missing_geo_defaults_to_remote(self):
        """Jobs with no jobGeo should default location to 'Remote'."""
        raw = {
            "jobTitle": "Dev",
            "companyName": "Co",
            "jobDescription": LONG_DESC,
            "url": "https://jobicy.com/jobs/2",
            "jobGeo": "",
        }
        result = _normalize_jobicy(raw)
        assert result is not None
        assert result["location"] == "Remote"


# ─── Helpers for profile-based normalizers ─────────────────

def _make_mock_profile():
    """Create a mock ProfileConfig with filters.skip_titles."""
    profile = MagicMock()
    profile.filters.skip_titles = ["Senior", "Lead", "Director"]
    return profile


# ─── _normalize_adzuna ──────────────────────────────────

class TestNormalizeAdzuna:
    """Normalize Adzuna job objects."""

    def test_valid_job(self):
        """A valid Adzuna job should normalize correctly."""
        raw = {
            "title": "Python Developer",
            "company": {"display_name": "TechCorp"},
            "description": LONG_DESC,
            "redirect_url": "https://adzuna.co.in/job/12345",
            "location": {"area": ["India", "Karnataka", "Bengaluru"]},
            "created": "2024-08-01T10:00:00Z",
            "salary_min": 500000,
            "salary_max": 900000,
        }
        result = _normalize_adzuna(raw)
        assert result is not None
        assert result["title"] == "Python Developer"
        assert result["company"] == "TechCorp"
        assert result["source"] == "adzuna"
        assert result["job_url"] == "https://adzuna.co.in/job/12345"
        assert result["location"] == "India, Karnataka, Bengaluru"
        assert result["salary_min"] == 500000
        assert result["salary_max"] == 900000
        assert result["salary_currency"] == "INR"

    def test_short_description_returns_none(self):
        """Jobs with too-short descriptions should be filtered out."""
        raw = {
            "title": "Dev",
            "company": {"display_name": "Co"},
            "description": SHORT_DESC,
            "redirect_url": "https://adzuna.co.in/job/1",
        }
        assert _normalize_adzuna(raw) is None

    def test_no_url_returns_none(self):
        """Jobs without a redirect_url should be filtered out."""
        raw = {
            "title": "Dev",
            "company": {"display_name": "Co"},
            "description": LONG_DESC,
            "redirect_url": "",
        }
        assert _normalize_adzuna(raw) is None

    def test_company_as_string(self):
        """Company can be a plain string instead of a dict."""
        raw = {
            "title": "Python Developer",
            "company": "PlainString Corp",
            "description": LONG_DESC,
            "redirect_url": "https://adzuna.co.in/job/99",
        }
        result = _normalize_adzuna(raw)
        assert result is not None
        assert result["company"] == "PlainString Corp"

    def test_remote_in_title_sets_is_remote(self):
        """Jobs with 'remote' in title should have is_remote=True."""
        raw = {
            "title": "Remote Python Developer",
            "company": {"display_name": "Co"},
            "description": LONG_DESC,
            "redirect_url": "https://adzuna.co.in/job/10",
        }
        result = _normalize_adzuna(raw)
        assert result is not None
        assert result["is_remote"] is True


# ─── _normalize_hiringcafe ──────────────────────────────

class TestNormalizeHiringCafe:
    """Normalize HiringCafe job objects."""

    def _build_raw(self, **overrides):
        """Build a valid HiringCafe raw job dict with overrides."""
        base = {
            "job_information": {
                "description": f"<p>{LONG_DESC}</p>",
                "title": "Python Developer",
            },
            "v5_processed_job_data": {
                "min_industry_and_role_yoe": 1,
                "seniority_level": "Entry Level",
                "technical_tools": ["python", "django"],
                "job_category": "Software Engineering",
                "estimated_publish_date": "2024-09-01",
                "company_name": "StartupCo",
                "formatted_workplace_location": "Bengaluru, India",
                "workplace_type": "Remote",
                "yearly_min_compensation": 600000,
                "yearly_max_compensation": 1200000,
                "listed_compensation_currency": "INR",
            },
            "apply_url": "https://hiring.cafe/apply/12345",
            "is_expired": False,
        }
        # Apply overrides at top level
        for key, val in overrides.items():
            if key in base:
                if isinstance(base[key], dict) and isinstance(val, dict):
                    base[key].update(val)
                else:
                    base[key] = val
            else:
                base[key] = val
        return base

    def test_valid_job(self):
        """A valid HiringCafe job with matching skills should normalize."""
        raw = self._build_raw()
        skills = {"python", "django"}
        profile = _make_mock_profile()
        result = _normalize_hiringcafe(raw, skills, profile)
        assert result is not None
        assert result["title"] == "Python Developer"
        assert result["company"] == "StartupCo"
        assert result["source"] == "hiringcafe"
        assert result["is_remote"] is True
        assert result["salary_min"] == 600000
        assert result["salary_max"] == 1200000

    def test_short_description_returns_none(self):
        """Jobs with too-short descriptions should be filtered out."""
        raw = self._build_raw()
        raw["job_information"]["description"] = SHORT_DESC
        skills = {"python"}
        profile = _make_mock_profile()
        assert _normalize_hiringcafe(raw, skills, profile) is None

    def test_no_url_returns_none(self):
        """Jobs without an apply_url should be filtered out."""
        raw = self._build_raw()
        raw["apply_url"] = ""
        skills = {"python"}
        profile = _make_mock_profile()
        assert _normalize_hiringcafe(raw, skills, profile) is None

    def test_expired_returns_none(self):
        """Expired jobs should be filtered out."""
        raw = self._build_raw()
        raw["is_expired"] = True
        skills = {"python"}
        profile = _make_mock_profile()
        assert _normalize_hiringcafe(raw, skills, profile) is None

    def test_senior_seniority_returns_none(self):
        """Senior-level seniority should be filtered out."""
        raw = self._build_raw()
        raw["v5_processed_job_data"]["seniority_level"] = "Senior Level"
        skills = {"python"}
        profile = _make_mock_profile()
        assert _normalize_hiringcafe(raw, skills, profile) is None

    def test_high_yoe_returns_none(self):
        """Jobs requiring > 4 years of experience should be filtered out."""
        raw = self._build_raw()
        raw["v5_processed_job_data"]["min_industry_and_role_yoe"] = 6
        skills = {"python"}
        profile = _make_mock_profile()
        assert _normalize_hiringcafe(raw, skills, profile) is None

    def test_irrelevant_category_returns_none(self):
        """Jobs in non-tech categories should be filtered out."""
        raw = self._build_raw()
        raw["v5_processed_job_data"]["job_category"] = "Sales"
        skills = {"python"}
        profile = _make_mock_profile()
        assert _normalize_hiringcafe(raw, skills, profile) is None

    def test_no_tool_or_title_match_returns_none(self):
        """Jobs with no matching tools or title terms should be filtered out."""
        raw = self._build_raw()
        raw["v5_processed_job_data"]["technical_tools"] = ["java", "spring"]
        raw["job_information"]["title"] = "Marketing Coordinator"
        skills = {"python", "django"}
        profile = _make_mock_profile()
        assert _normalize_hiringcafe(raw, skills, profile) is None


# ─── _normalize_himalayas ───────────────────────────────

class TestNormalizeHimalayas:
    """Normalize Himalayas job objects."""

    def test_valid_job(self):
        """A valid Himalayas job with matching skills should normalize."""
        raw = {
            "title": "Python Backend Developer",
            "description": LONG_DESC,
            "categories": ["Engineering", "Python"],
            "seniority": "Junior",
            "applicationUrl": "https://himalayas.app/jobs/12345/apply",
            "companyName": "CloudCo",
            "location": "Worldwide",
            "pubDate": "2024-10-01",
            "minSalary": 50000,
            "maxSalary": 80000,
        }
        skills = {"python", "backend", "developer"}
        result = _normalize_himalayas(raw, skills)
        assert result is not None
        assert result["title"] == "Python Backend Developer"
        assert result["company"] == "CloudCo"
        assert result["source"] == "himalayas"
        assert result["is_remote"] is True
        assert result["salary_min"] == 50000
        assert result["salary_max"] == 80000

    def test_short_description_returns_none(self):
        """Jobs with too-short descriptions should be filtered out."""
        raw = {
            "title": "Dev",
            "description": SHORT_DESC,
            "applicationUrl": "https://himalayas.app/jobs/1/apply",
            "companyName": "Co",
        }
        skills = {"python"}
        assert _normalize_himalayas(raw, skills) is None

    def test_irrelevant_returns_none(self):
        """Jobs that don't match any skills should be filtered out."""
        raw = {
            "title": "Chef Manager",
            "description": "Managing the restaurant kitchen operations and culinary team in downtown.",
            "categories": ["Food"],
            "applicationUrl": "https://himalayas.app/jobs/2/apply",
            "companyName": "FoodCo",
        }
        skills = {"python", "django", "developer"}
        assert _normalize_himalayas(raw, skills) is None

    def test_senior_seniority_returns_none(self):
        """Senior-seniority jobs should be filtered out."""
        raw = {
            "title": "Python Developer",
            "description": LONG_DESC,
            "categories": ["Python"],
            "seniority": "Senior",
            "applicationUrl": "https://himalayas.app/jobs/3/apply",
            "companyName": "Co",
        }
        skills = {"python", "developer"}
        assert _normalize_himalayas(raw, skills) is None

    def test_no_url_returns_none(self):
        """Jobs without a URL should be filtered out."""
        raw = {
            "title": "Python Developer",
            "description": LONG_DESC,
            "categories": ["Python"],
            "companyName": "Co",
        }
        skills = {"python", "developer"}
        assert _normalize_himalayas(raw, skills) is None

    def test_company_from_nested_dict(self):
        """Company name should be extracted from nested company dict."""
        raw = {
            "title": "Python Developer",
            "description": LONG_DESC,
            "categories": ["Python"],
            "seniority": "Junior",
            "applicationUrl": "https://himalayas.app/jobs/4/apply",
            "company": {"name": "NestedCo"},
            "companyName": "",
        }
        skills = {"python", "developer"}
        result = _normalize_himalayas(raw, skills)
        assert result is not None
        assert result["company"] == "NestedCo"

    def test_seniority_as_list(self):
        """Seniority field may be a list; senior entries should still filter."""
        raw = {
            "title": "Python Developer",
            "description": LONG_DESC,
            "categories": ["Python"],
            "seniority": ["Senior", "Lead"],
            "applicationUrl": "https://himalayas.app/jobs/5/apply",
            "companyName": "Co",
        }
        skills = {"python", "developer"}
        assert _normalize_himalayas(raw, skills) is None


# ─── _normalize_arbeitnow ──────────────────────────────

class TestNormalizeArbeitnow:
    """Normalize Arbeitnow job objects."""

    def test_valid_job(self):
        """A valid Arbeitnow job with matching skills should normalize."""
        raw = {
            "title": "Python Developer",
            "description": LONG_DESC,
            "tags": ["python", "django"],
            "url": "https://www.arbeitnow.com/view/python-dev-123",
            "created_at": 1719792000,
            "company_name": "EuroCorp",
            "location": "Berlin, Germany",
            "remote": True,
        }
        skills = {"python", "django", "developer"}
        result = _normalize_arbeitnow(raw, skills)
        assert result is not None
        assert result["title"] == "Python Developer"
        assert result["company"] == "EuroCorp"
        assert result["source"] == "arbeitnow"
        assert result["is_remote"] is True
        assert result["salary_currency"] == "EUR"

    def test_short_description_returns_none(self):
        """Jobs with too-short descriptions should be filtered out."""
        raw = {
            "title": "Dev",
            "description": SHORT_DESC,
            "tags": ["python"],
            "url": "https://www.arbeitnow.com/view/1",
            "company_name": "Co",
        }
        skills = {"python"}
        assert _normalize_arbeitnow(raw, skills) is None

    def test_irrelevant_returns_none(self):
        """Jobs that don't match any skills should be filtered out."""
        raw = {
            "title": "Sales Manager",
            "description": "Responsible for managing the sales team and quarterly revenue targets.",
            "tags": ["sales", "management"],
            "url": "https://www.arbeitnow.com/view/sales-mgr",
            "company_name": "SalesCo",
        }
        skills = {"python", "django", "developer"}
        assert _normalize_arbeitnow(raw, skills) is None

    def test_slug_gets_prefixed(self):
        """Slugs without http should get the arbeitnow prefix."""
        raw = {
            "title": "Python Developer",
            "description": LONG_DESC,
            "tags": ["python"],
            "slug": "python-dev-456",
            "company_name": "Co",
        }
        skills = {"python", "developer"}
        result = _normalize_arbeitnow(raw, skills)
        assert result is not None
        assert result["job_url"] == "https://www.arbeitnow.com/view/python-dev-456"

    def test_no_url_or_slug_returns_none(self):
        """Jobs without a URL or slug should be filtered out."""
        raw = {
            "title": "Python Developer",
            "description": LONG_DESC,
            "tags": ["python"],
            "company_name": "Co",
        }
        skills = {"python", "developer"}
        assert _normalize_arbeitnow(raw, skills) is None


# ─── _normalize_jsearch ─────────────────────────────────

class TestNormalizeJSearch:
    """Normalize JSearch job objects."""

    def test_valid_job(self):
        """A valid JSearch job should normalize correctly."""
        raw = {
            "job_title": "Backend Developer",
            "employer_name": "MegaCorp",
            "job_description": LONG_DESC,
            "job_apply_link": "https://megacorp.com/apply/123",
            "job_city": "Bengaluru",
            "job_state": "Karnataka",
            "job_country": "India",
            "job_publisher": "Naukri",
            "job_posted_at_datetime_utc": "2024-09-15T08:00:00Z",
            "job_is_remote": True,
            "job_min_salary": 600000,
            "job_max_salary": 1000000,
            "job_salary_currency": "INR",
        }
        result = _normalize_jsearch(raw)
        assert result is not None
        assert result["title"] == "Backend Developer"
        assert result["company"] == "MegaCorp"
        assert result["source"] == "naukri"
        assert result["discovered_via"] == "jsearch"
        assert result["location"] == "Bengaluru, Karnataka, India"
        assert result["is_remote"] is True
        assert result["salary_min"] == 600000
        assert result["salary_max"] == 1000000

    def test_short_description_returns_none(self):
        """Jobs with too-short descriptions should be filtered out."""
        raw = {
            "job_title": "Dev",
            "employer_name": "Co",
            "job_description": SHORT_DESC,
            "job_apply_link": "https://example.com/apply/1",
        }
        assert _normalize_jsearch(raw) is None

    def test_no_url_returns_none(self):
        """Jobs without any apply link should be filtered out."""
        raw = {
            "job_title": "Dev",
            "employer_name": "Co",
            "job_description": LONG_DESC,
            "job_apply_link": "",
            "job_google_link": "",
        }
        assert _normalize_jsearch(raw) is None

    def test_fallback_to_google_link(self):
        """If apply_link is missing, fallback to google_link."""
        raw = {
            "job_title": "Dev",
            "employer_name": "Co",
            "job_description": LONG_DESC,
            "job_google_link": "https://google.com/jobs/result/abc",
        }
        result = _normalize_jsearch(raw)
        assert result is not None
        assert result["job_url"] == "https://google.com/jobs/result/abc"

    def test_no_publisher_uses_jsearch(self):
        """If publisher is empty, source should default to 'jsearch'."""
        raw = {
            "job_title": "Dev",
            "employer_name": "Co",
            "job_description": LONG_DESC,
            "job_apply_link": "https://example.com/apply/2",
            "job_publisher": "",
        }
        result = _normalize_jsearch(raw)
        assert result is not None
        assert result["source"] == "jsearch"


# ─── _normalize_careerjet ───────────────────────────────

class TestNormalizeCareerJet:
    """Normalize CareerJet job objects."""

    def test_valid_job(self):
        """A valid CareerJet job should normalize correctly."""
        raw = {
            "title": "Django Developer",
            "company": "WebShop",
            "description": f"<p>{LONG_DESC}</p>",
            "url": "https://careerjet.co.in/job/12345",
            "locations": "Mumbai, India",
            "date": "Mon, 01 Jul 2024 00:00:00 GMT",
        }
        result = _normalize_careerjet(raw)
        assert result is not None
        assert result["title"] == "Django Developer"
        assert result["company"] == "WebShop"
        assert result["source"] == "careerjet"
        assert result["location"] == "Mumbai, India"
        assert result["salary_currency"] == "INR"

    def test_short_description_returns_none(self):
        """Jobs with too-short descriptions should be filtered out."""
        raw = {
            "title": "Dev",
            "company": "Co",
            "description": SHORT_DESC,
            "url": "https://careerjet.co.in/job/1",
        }
        assert _normalize_careerjet(raw) is None

    def test_no_url_returns_none(self):
        """Jobs without a URL should be filtered out."""
        raw = {
            "title": "Dev",
            "company": "Co",
            "description": f"<p>{LONG_DESC}</p>",
            "url": "",
        }
        assert _normalize_careerjet(raw) is None

    def test_remote_in_title_sets_is_remote(self):
        """Jobs with 'remote' in the title should have is_remote=True."""
        raw = {
            "title": "Remote Python Developer",
            "company": "Co",
            "description": f"<p>{LONG_DESC}</p>",
            "url": "https://careerjet.co.in/job/2",
            "locations": "India",
        }
        result = _normalize_careerjet(raw)
        assert result is not None
        assert result["is_remote"] is True


# ─── _normalize_themuse ─────────────────────────────────

class TestNormalizeTheMuse:
    """Normalize The Muse job objects."""

    def test_valid_job(self):
        """A valid Muse job should normalize correctly."""
        raw = {
            "name": "Software Engineer",
            "contents": f"<div>{LONG_DESC}</div>",
            "refs": {"landing_page": "https://www.themuse.com/jobs/techco/software-engineer"},
            "company": {"name": "TheMuse TechCo"},
            "locations": [{"name": "Bengaluru, India"}],
            "publication_date": "2024-10-01T00:00:00Z",
        }
        result = _normalize_themuse(raw)
        assert result is not None
        assert result["title"] == "Software Engineer"
        assert result["company"] == "TheMuse TechCo"
        assert result["source"] == "themuse"
        assert result["location"] == "Bengaluru, India"

    def test_short_description_returns_none(self):
        """Jobs with too-short contents should be filtered out."""
        raw = {
            "name": "Dev",
            "contents": SHORT_DESC,
            "refs": {"landing_page": "https://www.themuse.com/jobs/co/dev"},
            "company": {"name": "Co"},
        }
        assert _normalize_themuse(raw) is None

    def test_no_url_returns_none(self):
        """Jobs without a landing_page ref should be filtered out."""
        raw = {
            "name": "Dev",
            "contents": f"<div>{LONG_DESC}</div>",
            "refs": {},
            "company": {"name": "Co"},
        }
        assert _normalize_themuse(raw) is None

    def test_remote_location_sets_is_remote(self):
        """Jobs with 'Remote' in a location name should have is_remote=True."""
        raw = {
            "name": "Dev",
            "contents": f"<div>{LONG_DESC}</div>",
            "refs": {"landing_page": "https://www.themuse.com/jobs/co/dev"},
            "company": {"name": "Co"},
            "locations": [{"name": "Remote"}],
        }
        result = _normalize_themuse(raw)
        assert result is not None
        assert result["is_remote"] is True

    def test_multiple_locations_joined(self):
        """Multiple locations should be comma-joined."""
        raw = {
            "name": "Dev",
            "contents": f"<div>{LONG_DESC}</div>",
            "refs": {"landing_page": "https://www.themuse.com/jobs/co/dev2"},
            "company": {"name": "Co"},
            "locations": [{"name": "Bengaluru"}, {"name": "Mumbai"}],
        }
        result = _normalize_themuse(raw)
        assert result is not None
        assert result["location"] == "Bengaluru, Mumbai"


# ─── _normalize_findwork ────────────────────────────────

class TestNormalizeFindwork:
    """Normalize Findwork job objects."""

    def test_valid_job(self):
        """A valid Findwork job should normalize correctly."""
        raw = {
            "role": "Full Stack Developer",
            "company_name": "DevShop",
            "text": LONG_DESC,
            "url": "https://findwork.dev/job/12345",
            "location": "Remote, India",
            "remote": True,
            "date_posted": "2024-11-01",
        }
        result = _normalize_findwork(raw)
        assert result is not None
        assert result["title"] == "Full Stack Developer"
        assert result["company"] == "DevShop"
        assert result["source"] == "findwork"
        assert result["is_remote"] is True

    def test_short_description_returns_none(self):
        """Jobs with too-short text should be filtered out."""
        raw = {
            "role": "Dev",
            "company_name": "Co",
            "text": SHORT_DESC,
            "url": "https://findwork.dev/job/1",
        }
        assert _normalize_findwork(raw) is None

    def test_no_url_returns_none(self):
        """Jobs without a URL should be filtered out."""
        raw = {
            "role": "Dev",
            "company_name": "Co",
            "text": LONG_DESC,
            "url": "",
        }
        assert _normalize_findwork(raw) is None

    def test_fallback_to_description_field(self):
        """If 'text' is missing, use 'description' field."""
        raw = {
            "role": "Dev",
            "company_name": "Co",
            "description": LONG_DESC,
            "url": "https://findwork.dev/job/2",
        }
        result = _normalize_findwork(raw)
        assert result is not None
        assert result["title"] == "Dev"

    def test_remote_in_location_sets_is_remote(self):
        """Jobs with 'remote' in location should have is_remote=True even if remote flag is False."""
        raw = {
            "role": "Dev",
            "company_name": "Co",
            "text": LONG_DESC,
            "url": "https://findwork.dev/job/3",
            "location": "Remote",
            "remote": False,
        }
        result = _normalize_findwork(raw)
        assert result is not None
        assert result["is_remote"] is True


# ─── _normalize_greenhouse ──────────────────────────────

class TestNormalizeGreenhouse:
    """Normalize Greenhouse job objects."""

    def test_valid_job(self):
        """A valid Greenhouse job with matching skills should normalize."""
        raw = {
            "title": "Python Developer",
            "content": f"<div>{LONG_DESC}</div>",
            "location": {"name": "Bengaluru, India"},
            "absolute_url": "https://boards.greenhouse.io/techco/jobs/12345",
            "updated_at": "2024-10-15T10:00:00Z",
        }
        skills = {"python", "developer"}
        profile = _make_mock_profile()
        result = _normalize_greenhouse(raw, "TechCo", skills, profile)
        assert result is not None
        assert result["title"] == "Python Developer"
        assert result["company"] == "TechCo"
        assert result["source"] == "greenhouse"
        assert result["discovered_via"] == "greenhouse_direct"
        assert result["location"] == "Bengaluru, India"

    def test_short_description_returns_none(self):
        """Jobs with too-short content should be filtered out."""
        raw = {
            "title": "Dev",
            "content": SHORT_DESC,
            "absolute_url": "https://boards.greenhouse.io/co/jobs/1",
        }
        skills = {"python"}
        profile = _make_mock_profile()
        assert _normalize_greenhouse(raw, "Co", skills, profile) is None

    def test_irrelevant_returns_none(self):
        """Jobs that don't match any skills should be filtered out."""
        raw = {
            "title": "Marketing Manager",
            "content": "<div>Managing marketing campaigns and brand awareness for the company.</div>",
            "absolute_url": "https://boards.greenhouse.io/co/jobs/2",
        }
        skills = {"python", "django", "developer"}
        profile = _make_mock_profile()
        assert _normalize_greenhouse(raw, "Co", skills, profile) is None

    def test_skip_titles_returns_none(self):
        """Jobs matching skip_titles should be filtered out."""
        raw = {
            "title": "Senior Python Developer",
            "content": f"<div>{LONG_DESC}</div>",
            "absolute_url": "https://boards.greenhouse.io/co/jobs/3",
        }
        skills = {"python", "developer"}
        profile = _make_mock_profile()
        assert _normalize_greenhouse(raw, "Co", skills, profile) is None

    def test_no_url_returns_none(self):
        """Jobs without an absolute_url should be filtered out."""
        raw = {
            "title": "Python Developer",
            "content": f"<div>{LONG_DESC}</div>",
            "absolute_url": "",
        }
        skills = {"python", "developer"}
        profile = _make_mock_profile()
        assert _normalize_greenhouse(raw, "Co", skills, profile) is None

    def test_remote_location_sets_is_remote(self):
        """Jobs with 'Remote' in location name should have is_remote=True."""
        raw = {
            "title": "Python Developer",
            "content": f"<div>{LONG_DESC}</div>",
            "location": {"name": "Remote - India"},
            "absolute_url": "https://boards.greenhouse.io/co/jobs/4",
        }
        skills = {"python", "developer"}
        profile = _make_mock_profile()
        result = _normalize_greenhouse(raw, "Co", skills, profile)
        assert result is not None
        assert result["is_remote"] is True


# ─── _normalize_lever ───────────────────────────────────

class TestNormalizeLever:
    """Normalize Lever job postings."""

    def test_valid_job(self):
        """A valid Lever job with matching skills should normalize."""
        raw = {
            "text": "Python Developer",
            "descriptionPlain": LONG_DESC,
            "lists": [
                {"text": "Requirements", "content": ["Python experience", "Django knowledge"]},
            ],
            "categories": {"location": "Bengaluru, India"},
            "hostedUrl": "https://jobs.lever.co/techco/abc-123",
            "createdAt": 1697500000000,
        }
        skills = {"python", "developer"}
        profile = _make_mock_profile()
        result = _normalize_lever(raw, "TechCo", skills, profile)
        assert result is not None
        assert result["title"] == "Python Developer"
        assert result["company"] == "TechCo"
        assert result["source"] == "lever"
        assert result["discovered_via"] == "lever_direct"
        assert result["location"] == "Bengaluru, India"

    def test_short_description_returns_none(self):
        """Jobs with too-short description should be filtered out."""
        raw = {
            "text": "Dev",
            "descriptionPlain": SHORT_DESC,
            "lists": [],
            "hostedUrl": "https://jobs.lever.co/co/abc",
        }
        skills = {"python"}
        profile = _make_mock_profile()
        assert _normalize_lever(raw, "Co", skills, profile) is None

    def test_irrelevant_returns_none(self):
        """Jobs that don't match any skills should be filtered out."""
        raw = {
            "text": "Culinary Chef",
            "descriptionPlain": "Managing the restaurant kitchen operations and preparing meals daily.",
            "lists": [],
            "hostedUrl": "https://jobs.lever.co/co/def",
        }
        skills = {"python", "django", "developer"}
        profile = _make_mock_profile()
        assert _normalize_lever(raw, "Co", skills, profile) is None

    def test_skip_titles_returns_none(self):
        """Jobs matching skip_titles should be filtered out."""
        raw = {
            "text": "Lead Backend Engineer",
            "descriptionPlain": LONG_DESC,
            "lists": [],
            "hostedUrl": "https://jobs.lever.co/co/ghi",
        }
        skills = {"python", "backend", "engineer"}
        profile = _make_mock_profile()
        assert _normalize_lever(raw, "Co", skills, profile) is None

    def test_no_url_returns_none(self):
        """Jobs without hostedUrl or applyUrl should be filtered out."""
        raw = {
            "text": "Python Developer",
            "descriptionPlain": LONG_DESC,
            "lists": [],
            "hostedUrl": "",
            "applyUrl": "",
        }
        skills = {"python", "developer"}
        profile = _make_mock_profile()
        assert _normalize_lever(raw, "Co", skills, profile) is None

    def test_fallback_to_apply_url(self):
        """If hostedUrl is missing, use applyUrl."""
        raw = {
            "text": "Python Developer",
            "descriptionPlain": LONG_DESC,
            "lists": [],
            "applyUrl": "https://jobs.lever.co/co/apply/xyz",
            "createdAt": 1697500000000,
        }
        skills = {"python", "developer"}
        profile = _make_mock_profile()
        result = _normalize_lever(raw, "Co", skills, profile)
        assert result is not None
        assert result["job_url"] == "https://jobs.lever.co/co/apply/xyz"


# ─── _parse_hn_comment ──────────────────────────────────

class TestParseHnComment:
    """Parse HN Who's Hiring comments into normalized job dicts."""

    def test_valid_comment(self):
        """A well-formed HN hiring comment should parse correctly."""
        comment = {
            "comment_text": (
                "Acme Corp | Remote | Full Stack Engineer | Python, React\n"
                "We are building the next generation of developer tools. "
                "Looking for a full-stack engineer with Python and React experience. "
                "Check us out at https://acmecorp.com/careers "
                "We offer competitive salaries and full remote work."
            ),
            "objectID": "99999",
            "created_at_i": 1700000000,
            "parent_id": "88888",
        }
        result = _parse_hn_comment(comment)
        assert result is not None
        assert result["company"] == "Acme Corp"
        assert result["source"] == "hn_hiring"
        assert result["is_remote"] is True
        assert "acmecorp.com" in result["job_url"]

    def test_short_comment_returns_none(self):
        """Comments shorter than 100 chars should be filtered out."""
        comment = {
            "comment_text": "Short comment that does not have enough info.",
            "objectID": "11111",
            "created_at_i": 1700000000,
        }
        assert _parse_hn_comment(comment) is None

    def test_empty_comment_returns_none(self):
        """Empty comment_text should return None."""
        comment = {
            "comment_text": "",
            "objectID": "22222",
        }
        assert _parse_hn_comment(comment) is None

    def test_missing_comment_text_returns_none(self):
        """Missing comment_text key should return None."""
        comment = {
            "objectID": "33333",
        }
        assert _parse_hn_comment(comment) is None

    def test_fallback_url_to_hn_item(self):
        """If no company URL is found, fall back to the HN item link."""
        long_text = (
            "StartupXYZ | San Francisco | Backend Engineer\n"
            "We are a small team building something exciting. "
            "We need a backend engineer with strong fundamentals. " * 5
        )
        comment = {
            "comment_text": long_text,
            "objectID": "44444",
            "created_at_i": 1700000000,
            "parent_id": "88888",
        }
        result = _parse_hn_comment(comment)
        assert result is not None
        assert "news.ycombinator.com/item?id=44444" in result["job_url"]


# ─── _batch_to_date ─────────────────────────────────────

class TestBatchToDate:
    """Convert YC batch strings to dates."""

    def test_winter_batch(self):
        """W25 should map to January 15, 2025."""
        assert _batch_to_date("W25") == date(2025, 1, 15)

    def test_summer_batch(self):
        """S24 should map to June 15, 2024."""
        assert _batch_to_date("S24") == date(2024, 6, 15)

    def test_invalid_batch_returns_today(self):
        """Invalid batch strings should return today's date."""
        assert _batch_to_date("XYZ") == date.today()

    def test_empty_string_returns_today(self):
        """Empty string should return today's date."""
        assert _batch_to_date("") == date.today()
