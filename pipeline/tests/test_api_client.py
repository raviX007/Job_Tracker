"""Tests for core.api_client — APIClient class and module-level functions.

Covers initialization, context manager, HTTP helpers, all public methods,
and the backward-compatible module-level singleton pattern.
No real API calls are made; everything is mocked.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.api_client import APIClient
from core.constants import API_TIMEOUT

# ─── Helpers ──────────────────────────────────────────────


def _make_job(**overrides) -> dict:
    """Return a minimal job dict, with optional overrides."""
    base = {
        "job_url": "https://example.com/job/1",
        "source": "test",
        "discovered_via": "unit_test",
        "title": "Software Engineer",
        "company": "TestCo",
        "location": "Remote",
        "is_remote": True,
        "description": "Build stuff.",
        "dedup_key": "abc123",
    }
    base.update(overrides)
    return base


# ─── Initialization ──────────────────────────────────────


class TestAPIClientInit:
    """APIClient constructor defaults and env-var overrides."""

    def test_defaults(self, monkeypatch):
        monkeypatch.delenv("API_BASE_URL", raising=False)
        monkeypatch.delenv("API_SECRET_KEY", raising=False)

        client = APIClient()
        assert client.base_url == "http://localhost:8000"
        assert client.api_key == ""
        assert client.timeout == API_TIMEOUT
        assert client._client is None

    def test_explicit_args(self):
        client = APIClient(base_url="http://api:9000", api_key="secret", timeout=30)
        assert client.base_url == "http://api:9000"
        assert client.api_key == "secret"
        assert client.timeout == 30

    def test_env_var_overrides(self, monkeypatch):
        monkeypatch.setenv("API_BASE_URL", "http://prod:5000")
        monkeypatch.setenv("API_SECRET_KEY", "env-key-xyz")

        client = APIClient()
        assert client.base_url == "http://prod:5000"
        assert client.api_key == "env-key-xyz"

    def test_explicit_args_take_precedence_over_env(self, monkeypatch):
        monkeypatch.setenv("API_BASE_URL", "http://env-url")
        monkeypatch.setenv("API_SECRET_KEY", "env-key")

        client = APIClient(base_url="http://explicit", api_key="explicit-key")
        assert client.base_url == "http://explicit"
        assert client.api_key == "explicit-key"


# ─── Context Manager ─────────────────────────────────────


class TestAPIClientContext:
    """Async context manager creates and tears down the httpx client."""

    @pytest.mark.asyncio
    async def test_aenter_creates_client(self):
        api = APIClient()
        assert api._client is None

        async with api:
            assert api._client is not None
            assert isinstance(api._client, httpx.AsyncClient)

    @pytest.mark.asyncio
    async def test_aexit_closes_client(self):
        api = APIClient()
        async with api:
            inner_client = api._client
            assert inner_client is not None

        # After exit, _client should be None
        assert api._client is None


# ─── Headers ──────────────────────────────────────────────


class TestHeaders:
    """_headers() returns the expected dict."""

    def test_headers_include_api_key(self):
        api = APIClient(api_key="my-secret")
        headers = api._headers()
        assert headers == {
            "Content-Type": "application/json",
            "X-API-Key": "my-secret",
        }

    def test_headers_with_empty_key(self):
        api = APIClient(api_key="")
        headers = api._headers()
        assert headers["X-API-Key"] == ""


# ─── _post / _put guards ────────────────────────────────


class TestHTTPHelpers:
    """_post and _put raise RuntimeError when the client is not initialized."""

    @pytest.mark.asyncio
    async def test_post_raises_when_not_initialized(self):
        api = APIClient()
        with pytest.raises(RuntimeError, match="not initialized"):
            await api._post("/test", {})

    @pytest.mark.asyncio
    async def test_put_raises_when_not_initialized(self):
        api = APIClient()
        with pytest.raises(RuntimeError, match="not initialized"):
            await api._put("/test", {})


# ─── ensure_profile ──────────────────────────────────────


class TestEnsureProfile:
    """ensure_profile delegates to _post and returns the profile_id."""

    @pytest.mark.asyncio
    async def test_returns_profile_id(self):
        api = APIClient()
        with patch.object(APIClient, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"profile_id": 42}
            result = await api.ensure_profile("Alice", "alice@example.com", "/cfg/alice.toml")

        assert result == 42
        mock_post.assert_awaited_once_with("/api/profiles/ensure", {
            "name": "Alice",
            "email": "alice@example.com",
            "config_path": "/cfg/alice.toml",
        })


# ─── save_job ─────────────────────────────────────────────


class TestSaveJob:
    """save_job returns job_id on success, None on HTTP/network errors."""

    @pytest.mark.asyncio
    async def test_success_returns_job_id(self):
        api = APIClient()
        with patch.object(APIClient, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"job_id": 101}
            job = _make_job()
            result = await api.save_job(job)

        assert result == 101

    @pytest.mark.asyncio
    async def test_http_error_returns_none(self):
        api = APIClient()
        mock_response = httpx.Response(status_code=409, request=httpx.Request("POST", "/api/jobs"))
        with patch.object(APIClient, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.HTTPStatusError(
                "Conflict", request=mock_response.request, response=mock_response,
            )
            result = await api.save_job(_make_job())

        assert result is None

    @pytest.mark.asyncio
    async def test_network_error_returns_none(self):
        api = APIClient()
        with patch.object(APIClient, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.ConnectError("refused")
            result = await api.save_job(_make_job())

        assert result is None

    @pytest.mark.asyncio
    async def test_timeout_error_returns_none(self):
        api = APIClient()
        with patch.object(APIClient, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.TimeoutException("timed out")
            result = await api.save_job(_make_job())

        assert result is None


# ─── save_jobs_batch ──────────────────────────────────────


class TestSaveJobsBatch:
    """save_jobs_batch iterates over jobs and collects saved IDs."""

    @pytest.mark.asyncio
    async def test_saves_multiple_jobs(self):
        api = APIClient()
        with patch.object(APIClient, "save_job", new_callable=AsyncMock) as mock_save:
            mock_save.side_effect = [10, 20, 30]
            result = await api.save_jobs_batch([_make_job(), _make_job(), _make_job()])

        assert result == [10, 20, 30]
        assert mock_save.await_count == 3

    @pytest.mark.asyncio
    async def test_skips_none_results(self):
        api = APIClient()
        with patch.object(APIClient, "save_job", new_callable=AsyncMock) as mock_save:
            mock_save.side_effect = [10, None, 30]
            result = await api.save_jobs_batch([_make_job(), _make_job(), _make_job()])

        assert result == [10, 30]

    @pytest.mark.asyncio
    async def test_empty_list(self):
        api = APIClient()
        with patch.object(APIClient, "save_job", new_callable=AsyncMock) as mock_save:
            result = await api.save_jobs_batch([])

        assert result == []
        mock_save.assert_not_awaited()


# ─── filter_new_jobs ──────────────────────────────────────


class TestFilterNewJobs:
    """filter_new_jobs uses dedup_check to remove known jobs."""

    @pytest.mark.asyncio
    async def test_empty_list_returns_empty(self):
        api = APIClient()
        result = await api.filter_new_jobs([])
        assert result == []

    @pytest.mark.asyncio
    async def test_filters_existing_keys(self):
        api = APIClient()
        jobs = [
            _make_job(dedup_key="key-1", job_url="https://a.com/1"),
            _make_job(dedup_key="key-2", job_url="https://a.com/2"),
            _make_job(dedup_key="key-3", job_url="https://a.com/3"),
        ]
        with patch.object(APIClient, "dedup_check", new_callable=AsyncMock) as mock_dedup:
            mock_dedup.return_value = {
                "existing_keys": ["key-1", "key-3"],
                "existing_urls": [],
            }
            result = await api.filter_new_jobs(jobs)

        assert len(result) == 1
        assert result[0]["dedup_key"] == "key-2"

    @pytest.mark.asyncio
    async def test_filters_existing_urls(self):
        api = APIClient()
        jobs = [
            _make_job(dedup_key="key-a", job_url="https://example.com/job/1"),
            _make_job(dedup_key="key-b", job_url="https://example.com/job/2"),
        ]
        with patch.object(APIClient, "dedup_check", new_callable=AsyncMock) as mock_dedup:
            mock_dedup.return_value = {
                "existing_keys": [],
                "existing_urls": ["https://example.com/job/1"],
            }
            result = await api.filter_new_jobs(jobs)

        assert len(result) == 1
        assert result[0]["dedup_key"] == "key-b"

    @pytest.mark.asyncio
    async def test_adds_dedup_key_if_missing(self):
        """Jobs without dedup_key get one generated via make_dedup_key."""
        api = APIClient()
        job = {"job_url": "https://example.com/job/99", "title": "Dev", "company": "Co"}
        assert "dedup_key" not in job

        with patch.object(APIClient, "dedup_check", new_callable=AsyncMock) as mock_dedup:
            mock_dedup.return_value = {"existing_keys": [], "existing_urls": []}
            result = await api.filter_new_jobs([job])

        # After filter_new_jobs, the job dict should have a dedup_key
        assert "dedup_key" in result[0]
        assert len(result[0]["dedup_key"]) > 0

    @pytest.mark.asyncio
    async def test_deduplicates_within_batch(self):
        """Duplicate dedup_keys within the same batch are collapsed."""
        api = APIClient()
        jobs = [
            _make_job(dedup_key="dup-key", job_url="https://a.com/1"),
            _make_job(dedup_key="dup-key", job_url="https://a.com/2"),
        ]
        with patch.object(APIClient, "dedup_check", new_callable=AsyncMock) as mock_dedup:
            mock_dedup.return_value = {"existing_keys": [], "existing_urls": []}
            result = await api.filter_new_jobs(jobs)

        assert len(result) == 1


# ─── save_analysis ────────────────────────────────────────


class TestSaveAnalysis:
    """save_analysis returns analysis_id on success, None on error."""

    @pytest.mark.asyncio
    async def test_success_returns_analysis_id(self):
        api = APIClient()
        analysis = {
            "match_score": 85,
            "required_skills": ["Python"],
            "matching_skills": ["Python"],
            "missing_skills": [],
            "ats_keywords": ["python", "api"],
            "apply_decision": "apply",
        }
        with patch.object(APIClient, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"analysis_id": 201}
            result = await api.save_analysis(
                job_id=1, profile_id=2, analysis=analysis,
                embedding_score=0.92, route_action="apply",
            )

        assert result == 201

    @pytest.mark.asyncio
    async def test_http_error_returns_none(self):
        api = APIClient()
        mock_response = httpx.Response(status_code=500, request=httpx.Request("POST", "/api/analyses"))
        with patch.object(APIClient, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.HTTPStatusError(
                "Server Error", request=mock_response.request, response=mock_response,
            )
            result = await api.save_analysis(1, 2, {})

        assert result is None

    @pytest.mark.asyncio
    async def test_network_error_returns_none(self):
        api = APIClient()
        with patch.object(APIClient, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.ConnectError("refused")
            result = await api.save_analysis(1, 2, {})

        assert result is None


# ─── enqueue_email ────────────────────────────────────────


class TestEmailQueue:
    """enqueue_email returns email_id or None."""

    @pytest.mark.asyncio
    async def test_success_returns_email_id(self):
        api = APIClient()
        with patch.object(APIClient, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"email_id": 301}
            result = await api.enqueue_email(
                job_id=1, profile_id=2,
                recipient_email="hr@co.com", recipient_name="HR",
                recipient_role="recruiter", recipient_source="team_page",
                subject="Hello", body_html="<p>Hi</p>", body_plain="Hi",
            )

        assert result == 301

    @pytest.mark.asyncio
    async def test_http_error_returns_none(self):
        api = APIClient()
        mock_response = httpx.Response(status_code=422, request=httpx.Request("POST", "/api/emails/enqueue"))
        with patch.object(APIClient, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.HTTPStatusError(
                "Unprocessable", request=mock_response.request, response=mock_response,
            )
            result = await api.enqueue_email(
                job_id=1, profile_id=2,
                recipient_email="hr@co.com", recipient_name="HR",
                recipient_role="recruiter", recipient_source="team_page",
                subject="Hello", body_html="<p>Hi</p>", body_plain="Hi",
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_network_error_returns_none(self):
        api = APIClient()
        with patch.object(APIClient, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.TimeoutException("timed out")
            result = await api.enqueue_email(
                job_id=1, profile_id=2,
                recipient_email="hr@co.com", recipient_name="HR",
                recipient_role="recruiter", recipient_source="team_page",
                subject="Hello", body_html="<p>Hi</p>", body_plain="Hi",
            )

        assert result is None


# ─── mark_verified / advance_to_ready ─────────────────────


class TestEmailStatusMethods:
    """mark_verified and advance_to_ready call the correct endpoints."""

    @pytest.mark.asyncio
    async def test_mark_verified_calls_put(self):
        api = APIClient()
        with patch.object(APIClient, "_put", new_callable=AsyncMock) as mock_put:
            mock_put.return_value = {"status": "ok"}
            await api.mark_verified(99, "deliverable", "hunter")

        mock_put.assert_awaited_once_with("/api/emails/99/verify", {
            "verification_result": "deliverable",
            "verification_provider": "hunter",
        })

    @pytest.mark.asyncio
    async def test_advance_to_ready_calls_put(self):
        api = APIClient()
        with patch.object(APIClient, "_put", new_callable=AsyncMock) as mock_put:
            mock_put.return_value = {"status": "ok"}
            await api.advance_to_ready(55)

        mock_put.assert_awaited_once_with("/api/emails/55/advance")


# ─── save_startup_profile ─────────────────────────────────


class TestSaveStartupProfile:
    """save_startup_profile returns startup_profile_id or None."""

    @pytest.mark.asyncio
    async def test_success_returns_id(self):
        api = APIClient()
        with patch.object(APIClient, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"startup_profile_id": 501}
            result = await api.save_startup_profile({"name": "NewCo", "domain": "newco.io"})

        assert result == 501
        mock_post.assert_awaited_once_with("/api/startup-profiles", {"name": "NewCo", "domain": "newco.io"})

    @pytest.mark.asyncio
    async def test_http_error_returns_none(self):
        api = APIClient()
        mock_response = httpx.Response(status_code=500, request=httpx.Request("POST", "/api/startup-profiles"))
        with patch.object(APIClient, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.HTTPStatusError(
                "Server Error", request=mock_response.request, response=mock_response,
            )
            result = await api.save_startup_profile({"name": "FailCo"})

        assert result is None

    @pytest.mark.asyncio
    async def test_network_error_returns_none(self):
        api = APIClient()
        with patch.object(APIClient, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.ConnectError("refused")
            result = await api.save_startup_profile({"name": "DownCo"})

        assert result is None


# ─── update_cover_letter ──────────────────────────────────


class TestUpdateCoverLetter:
    """update_cover_letter calls _put with the correct payload."""

    @pytest.mark.asyncio
    async def test_calls_put_with_correct_payload(self):
        api = APIClient()
        with patch.object(APIClient, "_put", new_callable=AsyncMock) as mock_put:
            mock_put.return_value = {"status": "ok"}
            await api.update_cover_letter(job_id=5, profile_id=3, cover_letter="Dear Hiring Manager...")

        mock_put.assert_awaited_once_with("/api/analyses/cover-letter", {
            "job_id": 5,
            "profile_id": 3,
            "cover_letter": "Dear Hiring Manager...",
        })


# ─── Module-level functions (backward compat) ────────────


class TestModuleLevelFunctions:
    """Module-level functions use a lazy singleton APIClient."""

    @pytest.mark.asyncio
    async def test_get_default_creates_singleton(self):
        """_get_default() should create an APIClient and call __aenter__."""
        import core.api_client as mod

        # Reset the global singleton
        mod._default = None

        with patch.object(APIClient, "__aenter__", new_callable=AsyncMock) as mock_enter:
            mock_enter.return_value = MagicMock(spec=APIClient)
            result = await mod._get_default()
            assert result is not None
            mock_enter.assert_awaited_once()

        # Clean up
        mod._default = None

    @pytest.mark.asyncio
    async def test_get_default_returns_same_instance(self):
        """Repeated calls to _get_default() return the same singleton."""
        import core.api_client as mod

        mod._default = None

        with patch.object(APIClient, "__aenter__", new_callable=AsyncMock) as mock_enter:
            mock_enter.return_value = APIClient()
            first = await mod._get_default()
            second = await mod._get_default()
            assert first is second
            # __aenter__ should only be called once
            mock_enter.assert_awaited_once()

        mod._default = None

    @pytest.mark.asyncio
    async def test_module_save_job_delegates_to_instance(self):
        """Module-level save_job() should delegate to the singleton's save_job."""
        import core.api_client as mod

        mock_api = AsyncMock(spec=APIClient)
        mock_api.save_job.return_value = 77
        mod._default = mock_api

        result = await mod.save_job({"title": "SDE"})
        assert result == 77
        mock_api.save_job.assert_awaited_once_with({"title": "SDE"})

        mod._default = None

    @pytest.mark.asyncio
    async def test_module_ensure_profile_delegates(self):
        """Module-level ensure_profile() should delegate to the singleton."""
        import core.api_client as mod

        mock_api = AsyncMock(spec=APIClient)
        mock_api.ensure_profile.return_value = 10
        mod._default = mock_api

        result = await mod.ensure_profile("Bob", "bob@test.com", "/cfg")
        assert result == 10
        mock_api.ensure_profile.assert_awaited_once_with("Bob", "bob@test.com", "/cfg")

        mod._default = None

    @pytest.mark.asyncio
    async def test_module_enqueue_email_delegates(self):
        """Module-level enqueue_email() should delegate to the singleton."""
        import core.api_client as mod

        mock_api = AsyncMock(spec=APIClient)
        mock_api.enqueue_email.return_value = 88
        mod._default = mock_api

        result = await mod.enqueue_email(
            job_id=1, profile_id=2,
            recipient_email="a@b.com", recipient_name="A",
            recipient_role="eng", recipient_source="guess",
            subject="Hi", body_html="<p>Hi</p>", body_plain="Hi",
        )
        assert result == 88

        mod._default = None

