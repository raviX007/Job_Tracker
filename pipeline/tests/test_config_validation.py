"""Tests for config YAML validation with Pydantic models."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config_loader import load_and_validate_profile
from core.models import FiltersConfig, PlatformConfig


class TestProfileConfig:
    """Test that the Pydantic models correctly validate config."""

    def test_valid_ravi_profile(self):
        """Ravi's full profile should load without errors."""
        profile = load_and_validate_profile("config/profiles/ravi_raj.yaml")
        assert profile.candidate.name == "Ravi Raj"
        assert profile.candidate.location == "Bengaluru, India"
        assert "Python" in profile.skills.primary
        assert profile.experience.years == 0
        assert profile.experience.graduation_year == 2023

    def test_valid_example_profile(self):
        """Example profile template should load without errors."""
        profile = load_and_validate_profile("config/profiles/example_profile.yaml")
        assert profile.candidate.name == "Your Name"

    def test_valid_test_profile(self):
        """Test fixture profile should load without errors."""
        profile = load_and_validate_profile("tests/fixtures/sample_profile.yaml")
        assert profile.candidate.name == "Test User"
        assert len(profile.dream_companies) == 2

    def test_platform_config_delay_validation(self):
        """delay_max must be >= delay_min."""
        with pytest.raises(ValueError):
            PlatformConfig(enabled=True, auto_apply=True, max_daily=10, delay_min=5, delay_max=3)

    def test_platform_config_valid(self):
        """Valid platform config should pass."""
        cfg = PlatformConfig(enabled=True, auto_apply=True, max_daily=15, delay_min=4, delay_max=7)
        assert cfg.max_daily == 15
        assert cfg.delay_min == 4

    def test_filters_score_range(self):
        """Match scores should be 0-100."""
        filters = FiltersConfig(
            must_have_any=["python"],
            min_match_score=40,
            auto_apply_threshold=60,
        )
        assert filters.min_match_score == 40
        assert filters.auto_apply_threshold == 60

    def test_invalid_match_score(self):
        """Score > 100 should fail validation."""
        with pytest.raises(ValueError):
            FiltersConfig(must_have_any=["python"], min_match_score=150)


class TestAntiHallucination:
    """Test anti-hallucination config."""

    def test_allowed_companies(self):
        profile = load_and_validate_profile("config/profiles/ravi_raj.yaml")
        assert "Zelthy" in profile.anti_hallucination.allowed_companies
        assert "Upwork (Freelance)" in profile.anti_hallucination.allowed_companies
        assert profile.anti_hallucination.strict_mode is True


class TestDreamCompanies:
    """Test dream companies config."""

    def test_dream_companies_loaded(self):
        profile = load_and_validate_profile("config/profiles/ravi_raj.yaml")
        assert "Google" in profile.dream_companies
        assert "Razorpay" in profile.dream_companies
        assert len(profile.dream_companies) >= 5
