"""Tests for email verification pipeline — syntax, MX, disposable, API layers."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from emailer.verifier import (
    check_disposable,
    check_syntax,
    verify_email,
)

# ─── Layer 1: Syntax Check ───────────────────────────────

class TestCheckSyntax:
    """Regex-based email syntax validation."""

    def test_valid_email(self):
        result = check_syntax("john@example.com")
        assert result.is_valid is True
        assert result.provider == "regex"

    def test_valid_email_with_dots(self):
        result = check_syntax("john.doe@example.com")
        assert result.is_valid is True

    def test_valid_email_with_plus(self):
        result = check_syntax("john+tag@example.com")
        assert result.is_valid is True

    def test_missing_at_sign(self):
        result = check_syntax("johnexample.com")
        assert result.is_valid is False

    def test_missing_domain(self):
        result = check_syntax("john@")
        assert result.is_valid is False

    def test_missing_tld(self):
        result = check_syntax("john@example")
        assert result.is_valid is False

    def test_consecutive_dots(self):
        result = check_syntax("john..doe@example.com")
        assert result.is_valid is False
        assert "consecutive dots" in result.details

    def test_long_local_part(self):
        long_local = "a" * 65
        result = check_syntax(f"{long_local}@example.com")
        assert result.is_valid is False
        assert "64" in result.details

    def test_max_local_part_length(self):
        local_64 = "a" * 64
        result = check_syntax(f"{local_64}@example.com")
        assert result.is_valid is True

    def test_lowercases_email(self):
        result = check_syntax("JOHN@EXAMPLE.COM")
        assert result.email == "john@example.com"

    def test_strips_whitespace(self):
        result = check_syntax("  john@example.com  ")
        assert result.email == "john@example.com"


# ─── Layer 3: Disposable Check ───────────────────────────

class TestCheckDisposable:
    """Disposable/throwaway domain detection."""

    def test_disposable_domain(self):
        result = check_disposable("test@mailinator.com")
        assert result.is_valid is False
        assert "Disposable" in result.details

    def test_another_disposable(self):
        result = check_disposable("test@guerrillamail.com")
        assert result.is_valid is False

    def test_yopmail_disposable(self):
        result = check_disposable("test@yopmail.com")
        assert result.is_valid is False

    def test_legitimate_domain(self):
        result = check_disposable("test@gmail.com")
        assert result.is_valid is True

    def test_company_domain(self):
        result = check_disposable("hr@acme.com")
        assert result.is_valid is True


# ─── Full Pipeline ────────────────────────────────────────

class TestVerifyEmail:
    """Full verification pipeline (Layers 1-3, no API)."""

    @pytest.mark.asyncio
    async def test_invalid_syntax_stops_early(self):
        result = await verify_email("not-an-email")
        assert result.is_valid is False
        assert result.provider == "regex"

    @pytest.mark.asyncio
    async def test_disposable_caught(self):
        """Disposable domain should fail even with valid syntax."""
        result = await verify_email("test@mailinator.com")
        # MX check happens before disposable check, and mailinator.com may or may not have MX
        # If MX fails, it stops there; if MX passes, disposable check catches it
        assert result.is_valid is False

    @pytest.mark.asyncio
    async def test_consecutive_dots_caught(self):
        result = await verify_email("john..doe@example.com")
        assert result.is_valid is False
