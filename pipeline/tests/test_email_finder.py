"""Tests for email finder — domain extraction, pattern guessing, orchestrator."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from emailer.email_finder import (
    extract_domain_from_url,
    find_emails,
    guess_company_domain,
    guess_email_patterns,
    guess_generic_emails,
)

# ─── extract_domain_from_url ─────────────────────────────

class TestExtractDomainFromURL:
    """Extract company domain from job URLs."""

    def test_company_career_page(self):
        assert extract_domain_from_url("https://careers.stripe.com/listing/123") == "careers.stripe.com"

    def test_strips_www(self):
        assert extract_domain_from_url("https://www.acme.com/jobs") == "acme.com"

    def test_job_board_returns_empty(self):
        """Known job boards should return empty (we want company domain, not board)."""
        assert extract_domain_from_url("https://www.naukri.com/job/123") == ""
        assert extract_domain_from_url("https://www.indeed.com/viewjob?jk=abc") == ""
        assert extract_domain_from_url("https://www.linkedin.com/jobs/view/123") == ""

    def test_greenhouse_returns_empty(self):
        assert extract_domain_from_url("https://boards.greenhouse.io/company/jobs/123") == ""

    def test_empty_url(self):
        assert extract_domain_from_url("") == ""

    def test_malformed_url(self):
        result = extract_domain_from_url("not-a-url")
        assert isinstance(result, str)


# ─── guess_company_domain ─────────────────────────────────

class TestGuessCompanyDomain:
    """Guess domain from company name."""

    def test_simple_company(self):
        assert guess_company_domain("Stripe") == "stripe.com"

    def test_strips_pvt_ltd(self):
        assert guess_company_domain("Acme Pvt Ltd") == "acme.com"

    def test_strips_technologies(self):
        assert guess_company_domain("Infosys Technologies") == "infosys.com"

    def test_strips_spaces_and_special_chars(self):
        assert guess_company_domain("Open AI") == "openai.com"

    def test_empty_name(self):
        assert guess_company_domain("") == ""

    def test_only_special_chars(self):
        # After cleaning, nothing left → returns ""
        assert guess_company_domain("---") == ""


# ─── guess_email_patterns ─────────────────────────────────

class TestGuessEmailPatterns:
    """Generate email pattern guesses from name + domain."""

    def test_generates_patterns(self):
        results = guess_email_patterns("John", "Doe", "acme.com")
        emails = [r.email for r in results]
        assert "john@acme.com" in emails
        assert "john.doe@acme.com" in emails
        assert "johndoe@acme.com" in emails
        assert "j.doe@acme.com" in emails
        assert "john_doe@acme.com" in emails

    def test_all_low_confidence(self):
        results = guess_email_patterns("John", "Doe", "acme.com")
        assert all(r.confidence == "low" for r in results)
        assert all(r.source == "pattern_guess" for r in results)

    def test_first_name_only(self):
        results = guess_email_patterns("John", "", "acme.com")
        emails = [r.email for r in results]
        assert "john@acme.com" in emails
        # No last name → only first@domain pattern
        assert len(emails) == 1

    def test_empty_first_name(self):
        assert guess_email_patterns("", "Doe", "acme.com") == []

    def test_empty_domain(self):
        assert guess_email_patterns("John", "Doe", "") == []


# ─── guess_generic_emails ─────────────────────────────────

class TestGuessGenericEmails:
    """Generate generic HR email guesses."""

    def test_generates_generic_emails(self):
        results = guess_generic_emails("acme.com")
        emails = [r.email for r in results]
        assert "hr@acme.com" in emails
        assert "careers@acme.com" in emails
        assert "hiring@acme.com" in emails

    def test_all_pattern_guess_source(self):
        results = guess_generic_emails("acme.com")
        assert all(r.source == "pattern_guess" for r in results)


# ─── find_emails orchestrator ─────────────────────────────

class TestFindEmails:
    """Test the orchestrator logic (with mocked API calls)."""

    @pytest.mark.asyncio
    async def test_no_domain_returns_empty(self):
        """If we can't determine domain, return empty list."""
        result = await find_emails("", job_url="")
        assert result == []

    @pytest.mark.asyncio
    async def test_guesses_domain_from_company(self, monkeypatch):
        """Falls back to guessed domain when URL gives no domain."""
        # Disable API calls (no env vars set)
        monkeypatch.delenv("APOLLO_API_KEY", raising=False)
        result = await find_emails(
            "Acme Corp",
            job_url="https://www.indeed.com/job/123",  # job board → empty domain
            recruiter_name="Jane Smith",
        )
        # Should fall back to pattern guessing with guessed domain
        assert len(result) > 0
        assert all(r.email.endswith("@acme.com") for r in result)

    @pytest.mark.asyncio
    async def test_generic_fallback_when_no_recruiter(self, monkeypatch):
        """Without recruiter name, falls back to generic email guesses."""
        monkeypatch.delenv("APOLLO_API_KEY", raising=False)
        result = await find_emails(
            "Stripe",
            job_url="https://careers.stripe.com/listing/123",
        )
        # Should include generic emails like hr@, careers@
        emails = [r.email for r in result]
        assert any("hr@" in e or "careers@" in e for e in emails)

    @pytest.mark.asyncio
    async def test_deduplicates_results(self, monkeypatch):
        """Duplicate emails should be deduplicated."""
        monkeypatch.delenv("APOLLO_API_KEY", raising=False)
        # Pattern guessing with a name will generate emails, then generic will too
        # They shouldn't overlap, but if they did, dedup would catch it
        result = await find_emails("Stripe", job_url="https://careers.stripe.com/listing/123")
        emails = [r.email for r in result]
        assert len(emails) == len(set(e.lower() for e in emails))

    @pytest.mark.asyncio
    async def test_max_results_limit(self, monkeypatch):
        """Results should be capped at max_results."""
        monkeypatch.delenv("APOLLO_API_KEY", raising=False)
        result = await find_emails(
            "Stripe",
            job_url="https://careers.stripe.com/listing/123",
            max_results=2,
        )
        assert len(result) <= 2
