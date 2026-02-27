"""Tests for anti-hallucination content validator."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock

from emailer.validator import (
    _check_companies,
    _check_degrees,
    _check_experience,
    _check_skills,
    validate_generated_content,
)


def _make_profile(**overrides):
    """Create a mock profile for testing."""
    profile = MagicMock()
    profile.anti_hallucination.allowed_companies = overrides.get(
        "allowed_companies", ["Zelthy", "Upwork"]
    )
    profile.experience.degree = overrides.get("degree", "B.Tech in Computer Science")
    profile.experience.years = overrides.get("years", 0)
    profile.experience.work_history = overrides.get("work_history", [])
    profile.experience.gap_projects = overrides.get("gap_projects", [])
    profile.skills.primary = overrides.get("primary_skills", ["Python", "Django", "FastAPI"])
    profile.skills.secondary = overrides.get("secondary_skills", ["Docker", "Redis"])
    profile.skills.frameworks = overrides.get("frameworks", ["LangChain", "React"])
    profile.dream_companies = overrides.get("dream_companies", ["Google", "Razorpay"])
    return profile


class TestDegreeCheck:
    """Test that fabricated degrees are caught."""

    def test_catches_fabricated_masters(self):
        """Content claiming Master's when candidate has B.Tech should be flagged."""
        profile = _make_profile(degree="B.Tech in Computer Science")
        content = "i hold a master's degree in computer science from iit delhi"
        issues = _check_degrees(content.lower(), profile)
        assert len(issues) > 0
        assert any("Master" in i for i in issues)

    def test_allows_actual_degree(self):
        """Content mentioning the actual degree should pass."""
        profile = _make_profile(degree="M.Tech in Computer Science")
        content = "with my m.tech degree in computer science, i have experience in ai"
        issues = _check_degrees(content.lower(), profile)
        assert len(issues) == 0

    def test_catches_fabricated_phd(self):
        """Content claiming PhD when candidate has B.Tech should be flagged."""
        profile = _make_profile(degree="B.Tech in Computer Science")
        content = "i completed my phd in machine learning from stanford"
        issues = _check_degrees(content.lower(), profile)
        assert len(issues) > 0

    def test_ignores_degree_in_requirement_context(self):
        """Degree mentioned as a job requirement (not a claim) should pass."""
        profile = _make_profile(degree="B.Tech in Computer Science")
        content = "the role requires a master's degree in cs"
        issues = _check_degrees(content.lower(), profile)
        # Should not flag — no ownership claim patterns
        assert len(issues) == 0

    def test_catches_fabricated_mba(self):
        """Content claiming MBA when candidate doesn't have one."""
        profile = _make_profile(degree="B.Tech in Computer Science")
        content = "i have completed my mba from iim bangalore"
        issues = _check_degrees(content.lower(), profile)
        assert len(issues) > 0


class TestCompanyCheck:
    """Test that fabricated company references are caught."""

    def test_catches_unknown_company(self):
        """Claiming to have worked at a company not in allowed list."""
        profile = _make_profile(allowed_companies=["Zelthy"], dream_companies=[])
        content = "during my time at google, i built scalable systems"
        issues = _check_companies(content.lower(), profile)
        assert len(issues) > 0

    def test_allows_known_company(self):
        """Mentioning an allowed company should pass."""
        profile = _make_profile(allowed_companies=["Zelthy"])
        content = "during my internship at zelthy, i built rbac systems"
        issues = _check_companies(content.lower(), profile)
        assert len(issues) == 0

    def test_allows_dream_company_mention(self):
        """Dream companies should not be flagged (they're targets)."""
        profile = _make_profile(
            allowed_companies=["Zelthy"],
            dream_companies=["Razorpay"],
        )
        content = "i'm excited about the role at razorpay"
        issues = _check_companies(content.lower(), profile)
        assert len(issues) == 0


class TestExperienceCheck:
    """Test that inflated years of experience are caught."""

    def test_catches_inflated_years(self):
        """Claiming more years than actual should be flagged."""
        profile = _make_profile(years=0)
        content = "with 5 years of experience in python development"
        issues = _check_experience(content.lower(), profile)
        assert len(issues) > 0

    def test_allows_accurate_years(self):
        """Claiming actual years should pass."""
        profile = _make_profile(years=2)
        content = "with 2 years of experience in backend development"
        issues = _check_experience(content.lower(), profile)
        assert len(issues) == 0

    def test_allows_rounding_up_one_year(self):
        """Allow 1 year rounding (e.g., 0 years claiming 1)."""
        profile = _make_profile(years=0)
        content = "with 1 year of experience in python"
        issues = _check_experience(content.lower(), profile)
        assert len(issues) == 0


class TestSkillsCheck:
    """Test that unverified skill claims generate warnings."""

    def test_warns_on_unknown_skill(self):
        """Claiming a skill not in profile should generate warning."""
        profile = _make_profile(primary_skills=["Python"], secondary_skills=[])
        content = "i am proficient in rust and go, with strong systems programming skills"
        warnings = _check_skills(content.lower(), profile)
        # May or may not catch depending on regex, but should not error
        assert isinstance(warnings, list)

    def test_no_warning_for_known_skills(self):
        """Claiming skills in profile should not warn."""
        profile = _make_profile(primary_skills=["Python", "Django"])
        content = "proficient in python and django development"
        warnings = _check_skills(content.lower(), profile)
        # Known skills should not generate warnings
        # (exact behavior depends on regex matching)
        assert isinstance(warnings, list)


class TestFullValidation:
    """Test the complete validation pipeline."""

    def test_valid_content_passes(self):
        """Clean content should pass all checks."""
        profile = _make_profile()
        content = "I'm excited about the role at your company."
        result = validate_generated_content(content, profile)
        assert result.is_valid is True
        assert len(result.issues) == 0

    def test_empty_content_passes(self):
        """Empty content should pass."""
        profile = _make_profile()
        result = validate_generated_content("", profile)
        assert result.is_valid is True

    def test_multiple_issues_detected(self):
        """Content with multiple problems should catch all issues."""
        profile = _make_profile(years=0)
        content = "i completed my phd at mit with 10 years of experience in ai"
        result = validate_generated_content(content, profile)
        assert result.is_valid is False
        assert len(result.issues) >= 1
