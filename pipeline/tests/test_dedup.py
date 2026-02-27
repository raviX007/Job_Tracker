"""Tests for URL normalization and dedup key generation."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.dedup import make_dedup_key, normalize_url


class TestNormalizeURL:
    """Test URL normalization strips tracking params and normalizes."""

    def test_strips_utm_params(self):
        url = "https://example.com/job/123?utm_source=google&utm_medium=cpc&title=dev"
        result = normalize_url(url)
        assert "utm_source" not in result
        assert "utm_medium" not in result
        assert "title=dev" in result

    def test_strips_fbclid(self):
        url = "https://example.com/careers?fbclid=abc123&role=sde"
        result = normalize_url(url)
        assert "fbclid" not in result
        assert "role=sde" in result

    def test_strips_gclid(self):
        url = "https://example.com/apply?gclid=xyz&job_id=42"
        result = normalize_url(url)
        assert "gclid" not in result
        assert "job_id=42" in result

    def test_lowercases_domain(self):
        url = "https://WWW.Example.COM/job/456"
        result = normalize_url(url)
        assert "www.example.com" in result

    def test_strips_trailing_slash(self):
        url = "https://example.com/job/123/"
        result = normalize_url(url)
        assert not result.endswith("/")

    def test_drops_fragment(self):
        url = "https://example.com/job/123#apply-now"
        result = normalize_url(url)
        assert "#" not in result

    def test_empty_url_returns_empty(self):
        assert normalize_url("") == ""

    def test_preserves_path(self):
        url = "https://boards.greenhouse.io/company/jobs/12345"
        result = normalize_url(url)
        assert "/company/jobs/12345" in result

    def test_strips_multiple_tracking_params(self):
        url = "https://example.com/job?utm_source=x&ref=y&utm_campaign=z&id=1"
        result = normalize_url(url)
        assert "utm_source" not in result
        assert "ref" not in result
        assert "utm_campaign" not in result
        assert "id=1" in result


class TestMakeDedupKey:
    """Test dedup key generation."""

    def test_url_based_key(self):
        """Jobs with URLs should use URL-based dedup keys."""
        job = {"job_url": "https://example.com/job/123", "title": "SDE", "company": "Acme"}
        key = make_dedup_key(job)
        assert len(key) == 32
        assert key.isalnum()

    def test_same_url_same_key(self):
        """Same URL should produce same key."""
        job1 = {"job_url": "https://example.com/job/123"}
        job2 = {"job_url": "https://example.com/job/123"}
        assert make_dedup_key(job1) == make_dedup_key(job2)

    def test_tracking_params_ignored(self):
        """URLs differing only in tracking params should have same key."""
        job1 = {"job_url": "https://example.com/job/123"}
        job2 = {"job_url": "https://example.com/job/123?utm_source=google"}
        assert make_dedup_key(job1) == make_dedup_key(job2)

    def test_different_urls_different_keys(self):
        """Different URLs should produce different keys."""
        job1 = {"job_url": "https://example.com/job/123"}
        job2 = {"job_url": "https://example.com/job/456"}
        assert make_dedup_key(job1) != make_dedup_key(job2)

    def test_content_fallback(self):
        """Jobs without URLs should use content-based fallback."""
        job = {"company": "Acme", "title": "SDE", "location": "Remote"}
        key = make_dedup_key(job)
        assert len(key) == 32

    def test_content_fallback_same_job(self):
        """Same company+title+location should produce same key."""
        job1 = {"company": "Acme", "title": "SDE", "location": "Remote"}
        job2 = {"company": "Acme", "title": "SDE", "location": "Remote"}
        assert make_dedup_key(job1) == make_dedup_key(job2)

    def test_content_fallback_different_jobs(self):
        """Different content should produce different keys."""
        job1 = {"company": "Acme", "title": "SDE", "location": "Remote"}
        job2 = {"company": "Acme", "title": "DevOps", "location": "Remote"}
        assert make_dedup_key(job1) != make_dedup_key(job2)

    def test_empty_job_dict(self):
        """Empty job dict should still produce a key (content fallback)."""
        key = make_dedup_key({})
        assert len(key) == 32

    def test_case_insensitive_content(self):
        """Content-based dedup should be case-insensitive."""
        job1 = {"company": "ACME", "title": "SDE", "location": "Remote"}
        job2 = {"company": "acme", "title": "sde", "location": "remote"}
        assert make_dedup_key(job1) == make_dedup_key(job2)
