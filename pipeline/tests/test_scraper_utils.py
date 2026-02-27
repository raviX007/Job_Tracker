"""Tests for scraper/utils.py — comprehensive coverage of all utility functions."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import ProfileConfig
from scraper.utils import (
    build_skill_set,
    check_relevance,
    is_short_description,
    parse_date_iso,
    parse_date_timestamp,
    parse_salary_range,
    parse_salary_value,
    strip_html,
)

# ─── strip_html ──────────────────────────────────────────

class TestStripHtml:
    """Strip HTML tags and decode entities."""

    def test_removes_tags(self):
        assert strip_html("<p>Hello <b>World</b></p>") == "Hello World"

    def test_handles_entities(self):
        """HTML entities like &amp; should be decoded."""
        result = strip_html("Tom &amp; Jerry")
        assert result == "Tom & Jerry"

    def test_entities_then_tag_strip(self):
        """&lt;/&gt; decode to </>  which are then stripped as HTML tags."""
        result = strip_html("a &lt;b&gt;bold&lt;/b&gt; z")
        # <b>bold</b> is stripped as tags → "a bold z"
        assert "bold" in result
        assert "<" not in result

    def test_handles_nested_tags(self):
        html = "<div><p>Outer <span><em>inner</em></span></p></div>"
        result = strip_html(html)
        assert "Outer" in result
        assert "inner" in result
        assert "<" not in result
        assert ">" not in result

    def test_empty_string(self):
        assert strip_html("") == ""

    def test_plain_text_unchanged(self):
        assert strip_html("Hello World") == "Hello World"


# ─── parse_date_iso ──────────────────────────────────────

class TestParseDateIso:
    """Parse ISO 8601 date strings."""

    def test_valid_iso_date(self):
        result = parse_date_iso("2024-01-15")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_date_with_z_suffix(self):
        """ISO dates with 'Z' (UTC) suffix should parse correctly."""
        result = parse_date_iso("2024-06-20T10:30:00Z")
        assert result is not None
        assert result.year == 2024
        assert result.month == 6
        assert result.day == 20

    def test_date_with_timezone_offset(self):
        result = parse_date_iso("2024-03-10T08:00:00+05:30")
        assert result is not None
        assert result.year == 2024

    def test_none_returns_none(self):
        assert parse_date_iso(None) is None

    def test_empty_string_returns_none(self):
        assert parse_date_iso("") is None

    def test_invalid_returns_none(self):
        assert parse_date_iso("not-a-date") is None
        assert parse_date_iso("2024-13-40") is None


# ─── parse_date_timestamp ────────────────────────────────

class TestParseDateTimestamp:
    """Parse Unix timestamps to date."""

    def test_valid_seconds_timestamp(self):
        # 2024-01-01 00:00:00 UTC = 1704067200
        result = parse_date_timestamp(1704067200)
        assert result is not None
        assert result.year == 2024

    def test_milliseconds_flag(self):
        """When milliseconds=True, timestamp is divided by 1000."""
        result = parse_date_timestamp(1704067200000, milliseconds=True)
        assert result is not None
        assert result.year == 2024

    def test_none_returns_none(self):
        assert parse_date_timestamp(None) is None

    def test_float_timestamp(self):
        result = parse_date_timestamp(1704067200.5)
        assert result is not None
        assert result.year == 2024

    def test_invalid_returns_none(self):
        """Extremely large or invalid timestamps should return None."""
        assert parse_date_timestamp(-99999999999999) is None


# ─── parse_salary_value ──────────────────────────────────

class TestParseSalaryValue:
    """Parse salary values from various types."""

    def test_int(self):
        assert parse_salary_value(50000) == 50000

    def test_float(self):
        assert parse_salary_value(60000.75) == 60000

    def test_string(self):
        assert parse_salary_value("70000") == 70000

    def test_float_string(self):
        assert parse_salary_value("80000.99") == 80000

    def test_none(self):
        assert parse_salary_value(None) is None

    def test_invalid_string(self):
        assert parse_salary_value("not-a-number") is None

    def test_zero(self):
        assert parse_salary_value(0) == 0


# ─── parse_salary_range ─────────────────────────────────

class TestParseSalaryRange:
    """Parse salary range strings."""

    def test_range_string(self):
        """Standard range like '$60,000 - $80,000' should parse to (60000, 80000)."""
        lo, hi = parse_salary_range("$60,000 - $80,000")
        assert lo == 60000
        assert hi == 80000

    def test_single_value(self):
        """A single number should return (value, None)."""
        lo, hi = parse_salary_range("$50,000")
        assert lo == 50000
        assert hi is None

    def test_empty(self):
        lo, hi = parse_salary_range("")
        assert lo is None
        assert hi is None

    def test_no_numbers(self):
        lo, hi = parse_salary_range("Competitive salary")
        assert lo is None
        assert hi is None

    def test_range_without_dollar_signs(self):
        lo, hi = parse_salary_range("60000 - 80000")
        assert lo == 60000
        assert hi == 80000


# ─── build_skill_set ────────────────────────────────────

class TestBuildSkillSet:
    """Build lowercase skill set from profile."""

    def test_builds_from_profile(self):
        """Should include primary, secondary, and GENERIC_JOB_TERMS."""
        profile = ProfileConfig(
            candidate={
                "name": "Test User",
                "email": "test@example.com",
                "phone": "1234567890",
                "resume_path": "/tmp/resume.pdf",
                "location": "Bengaluru",
            },
            search_preferences={"locations": ["Bengaluru"]},
            skills={"primary": ["Python", "Django"], "secondary": ["FastAPI"]},
            experience={"graduation_year": 2023, "degree": "B.Tech"},
            filters={"must_have_any": ["python"]},
        )
        skills = build_skill_set(profile)
        # Primary skills (lowercased)
        assert "python" in skills
        assert "django" in skills
        # Secondary skills (lowercased)
        assert "fastapi" in skills
        # Generic job terms from constants
        assert "developer" in skills
        assert "engineer" in skills
        assert "software" in skills

    def test_empty_secondary_still_has_generics(self):
        """Even with no secondary skills, generic terms should be present."""
        profile = ProfileConfig(
            candidate={
                "name": "Test",
                "email": "t@t.com",
                "phone": "123",
                "resume_path": "/tmp/r.pdf",
                "location": "Bengaluru",
            },
            search_preferences={"locations": ["Bengaluru"]},
            skills={"primary": ["Go"]},
            experience={"graduation_year": 2023, "degree": "B.Tech"},
            filters={"must_have_any": ["go"]},
        )
        skills = build_skill_set(profile)
        assert "go" in skills
        assert "developer" in skills
        assert "frontend" in skills


# ─── check_relevance ────────────────────────────────────

class TestCheckRelevance:
    """Check if job matches skill set."""

    def test_matching_title(self):
        skills = {"python", "django", "developer"}
        assert check_relevance("Python Developer", "", skills) is True

    def test_matching_description(self):
        skills = {"python", "django", "developer"}
        assert check_relevance("", "We need a python developer", skills) is True

    def test_no_match(self):
        skills = {"python", "django", "developer"}
        assert check_relevance("Chef Cook", "Restaurant kitchen work", skills) is False

    def test_case_insensitive(self):
        skills = {"python"}
        assert check_relevance("PYTHON Engineer", "", skills) is True

    def test_empty_skills_returns_false(self):
        assert check_relevance("Python Developer", "Some desc", set()) is False


# ─── is_short_description ───────────────────────────────

class TestIsShortDescription:
    """Check if description is too short."""

    def test_short(self):
        assert is_short_description("short") is True

    def test_long_enough(self):
        assert is_short_description("x" * 100) is False

    def test_exactly_at_threshold(self):
        assert is_short_description("x" * 50) is False

    def test_custom_min_length(self):
        assert is_short_description("x" * 20, min_length=30) is True
        assert is_short_description("x" * 30, min_length=30) is False

    def test_whitespace_only(self):
        """Whitespace-only strings should be treated as short after strip."""
        assert is_short_description("   ") is True
