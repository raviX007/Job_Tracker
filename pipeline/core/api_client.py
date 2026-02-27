"""HTTP client for pipeline → FastAPI communication.

Uses a single shared httpx.AsyncClient for connection pooling (instead of
creating a new client per request). Includes retry logic with exponential
backoff for transient failures.

All functions are async and mirror the signatures of their DB counterparts.
"""

import os

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from core.constants import API_TIMEOUT, RETRY_MAX_ATTEMPTS, RETRY_MAX_WAIT, RETRY_MIN_WAIT
from core.logger import logger
from core.utils import mask_email

_RETRIABLE = (httpx.TimeoutException, httpx.ConnectError)


class APIClient:
    """Async HTTP client with connection pooling and retry logic.

    Usage:
        async with APIClient(base_url, api_key) as api:
            profile_id = await api.ensure_profile(...)
            await api.save_job(...)
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: int = API_TIMEOUT,
    ):
        self.base_url = base_url or os.getenv("API_BASE_URL", "http://localhost:8000")
        self.api_key = api_key or os.getenv("API_SECRET_KEY", "")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "APIClient":
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)
        return self

    async def __aexit__(self, *args) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
        }

    # ─── Low-level HTTP with retry ──────────────────────

    @retry(
        stop=stop_after_attempt(RETRY_MAX_ATTEMPTS),
        wait=wait_exponential(min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
        retry=retry_if_exception_type(_RETRIABLE),
        reraise=True,
    )
    async def _post(self, path: str, json: dict) -> dict:
        if not self._client:
            raise RuntimeError("APIClient not initialized — use 'async with APIClient() as api:'")
        resp = await self._client.post(path, json=json, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    @retry(
        stop=stop_after_attempt(RETRY_MAX_ATTEMPTS),
        wait=wait_exponential(min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
        retry=retry_if_exception_type(_RETRIABLE),
        reraise=True,
    )
    async def _put(self, path: str, json: dict | None = None) -> dict:
        if not self._client:
            raise RuntimeError("APIClient not initialized — use 'async with APIClient() as api:'")
        resp = await self._client.put(path, json=json or {}, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    # ─── Profile ────────────────────────────────────────

    async def ensure_profile(self, name: str, email: str, config_path: str) -> int:
        """Get or create a profile. Returns profile_id."""
        data = await self._post("/api/profiles/ensure", {
            "name": name, "email": email, "config_path": config_path,
        })
        profile_id = data["profile_id"]
        logger.info(f"Profile ensured: {name} (id={profile_id})")
        return profile_id

    # ─── Jobs ───────────────────────────────────────────

    async def save_job(self, job: dict) -> int | None:
        """Save a scraped job via API. Returns job_id or None if duplicate."""
        payload = {
            "job_url": job.get("job_url"),
            "source": job.get("source"),
            "discovered_via": job.get("discovered_via"),
            "title": job.get("title"),
            "company": job.get("company"),
            "location": job.get("location"),
            "is_remote": job.get("is_remote", False),
            "description": job.get("description"),
            "salary_min": job.get("salary_min"),
            "salary_max": job.get("salary_max"),
            "salary_currency": job.get("salary_currency"),
            "date_posted": str(job["date_posted"]) if job.get("date_posted") else None,
            "dedup_key": job.get("dedup_key"),
        }
        try:
            data = await self._post("/api/jobs", payload)
            return data.get("job_id")
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to save job (HTTP {e.response.status_code}): {e}")
            return None
        except _RETRIABLE as e:
            logger.error(f"Failed to save job (network): {e}")
            return None

    async def save_jobs_batch(self, jobs: list[dict]) -> list[int]:
        """Save a batch of jobs. Returns list of new job IDs."""
        saved_ids = []
        for job in jobs:
            job_id = await self.save_job(job)
            if job_id:
                saved_ids.append(job_id)
        logger.info(f"Saved {len(saved_ids)} new jobs via API (from {len(jobs)} total)")
        return saved_ids

    # ─── Dedup ──────────────────────────────────────────

    async def dedup_check(self, urls: list[str], dedup_keys: list[str]) -> dict:
        """Check which URLs/dedup_keys already exist."""
        data = await self._post("/api/jobs/dedup-check", {
            "urls": urls, "dedup_keys": dedup_keys,
        })
        return data

    async def filter_new_jobs(self, jobs: list[dict]) -> list[dict]:
        """Filter out jobs that already exist in the database (via API)."""
        if not jobs:
            return []

        from scraper.dedup import make_dedup_key, normalize_url

        for job in jobs:
            if "dedup_key" not in job:
                job["dedup_key"] = make_dedup_key(job)

        dedup_keys = [j["dedup_key"] for j in jobs]
        urls = [normalize_url(j.get("job_url", "")) for j in jobs]

        data = await self.dedup_check([u for u in urls if u], dedup_keys)
        existing_key_set = set(data.get("existing_keys", []))
        existing_url_set = set(data.get("existing_urls", []))

        new_jobs = []
        seen_keys: set[str] = set()
        for job in jobs:
            key = job["dedup_key"]
            url = normalize_url(job.get("job_url", ""))

            if key in existing_key_set:
                continue
            if url and url in existing_url_set:
                continue
            if key in seen_keys:
                continue

            seen_keys.add(key)
            new_jobs.append(job)

        skipped = len(jobs) - len(new_jobs)
        if skipped > 0:
            logger.info(f"Dedup (API): {skipped} duplicates filtered, {len(new_jobs)} new jobs")
        else:
            logger.info(f"Dedup (API): all {len(new_jobs)} jobs are new")

        return new_jobs

    # ─── Analyses ───────────────────────────────────────

    async def save_analysis(
        self,
        job_id: int,
        profile_id: int,
        analysis: dict,
        embedding_score: float | None = None,
        route_action: str | None = None,
    ) -> int | None:
        """Save a job analysis via API. Returns analysis_id."""
        payload = {
            "job_id": job_id,
            "profile_id": profile_id,
            "match_score": analysis.get("match_score"),
            "embedding_score": embedding_score,
            "skills_required": analysis.get("required_skills", []),
            "skills_matched": analysis.get("matching_skills", []),
            "skills_missing": analysis.get("missing_skills", []),
            "ats_keywords": analysis.get("ats_keywords", []),
            "experience_required": analysis.get("experience_required"),
            "location_compatible": analysis.get("location_compatible"),
            "remote_compatible": analysis.get("remote_compatible"),
            "company_type": analysis.get("company_type"),
            "gap_tolerant": analysis.get("gap_tolerant"),
            "red_flags": analysis.get("red_flags", []),
            "apply_decision": analysis.get("apply_decision"),
            "cold_email_angle": analysis.get("cold_email_angle"),
            "gap_framing_for_this_role": analysis.get("gap_framing_for_this_role"),
            "route_action": route_action,
        }
        try:
            data = await self._post("/api/analyses", payload)
            return data.get("analysis_id")
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to save analysis (HTTP {e.response.status_code}): {e}")
            return None
        except _RETRIABLE as e:
            logger.error(f"Failed to save analysis (network): {e}")
            return None

    async def update_cover_letter(self, job_id: int, profile_id: int, cover_letter: str) -> None:
        """Update cover letter for an analysis."""
        await self._put("/api/analyses/cover-letter", {
            "job_id": job_id, "profile_id": profile_id, "cover_letter": cover_letter,
        })

    # ─── Email Queue ────────────────────────────────────

    async def enqueue_email(
        self,
        job_id: int,
        profile_id: int,
        recipient_email: str,
        recipient_name: str,
        recipient_role: str,
        recipient_source: str,
        subject: str,
        body_html: str,
        body_plain: str,
        signature: str = "",
        resume_path: str = "",
        email_verified: bool = False,
        verification_result: str = "unverified",
        verification_provider: str = "",
    ) -> int | None:
        """Queue a cold email via API. Returns email_id."""
        payload = {
            "job_id": job_id,
            "profile_id": profile_id,
            "recipient_email": recipient_email,
            "recipient_name": recipient_name,
            "recipient_role": recipient_role,
            "recipient_source": recipient_source,
            "subject": subject,
            "body_html": body_html,
            "body_plain": body_plain,
            "signature": signature,
            "resume_path": resume_path,
            "email_verified": email_verified,
            "email_verification_result": verification_result,
            "email_verification_provider": verification_provider,
        }
        try:
            data = await self._post("/api/emails/enqueue", payload)
            email_id = data.get("email_id")
            logger.info(f"Email queued via API: {mask_email(recipient_email)} (id={email_id})")
            return email_id
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to enqueue email (HTTP {e.response.status_code}): {e}")
            return None
        except _RETRIABLE as e:
            logger.error(f"Failed to enqueue email (network): {e}")
            return None

    async def mark_verified(
        self,
        email_id: int,
        verification_result: str,
        verification_provider: str,
    ) -> None:
        """Mark an email as verified via API."""
        await self._put(f"/api/emails/{email_id}/verify", {
            "verification_result": verification_result,
            "verification_provider": verification_provider,
        })

    async def advance_to_ready(self, email_id: int) -> None:
        """Advance an email to 'ready' status via API."""
        await self._put(f"/api/emails/{email_id}/advance")

    # ─── Startup Profiles ──────────────────────────────

    async def save_startup_profile(self, profile_data: dict) -> int | None:
        """Save a startup profile via API. Returns startup_profile_id."""
        try:
            data = await self._post("/api/startup-profiles", profile_data)
            return data.get("startup_profile_id")
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to save startup profile (HTTP {e.response.status_code}): {e}")
            return None
        except _RETRIABLE as e:
            logger.error(f"Failed to save startup profile (network): {e}")
            return None


# ─── Backward-compatible module-level functions ─────────
# These use a lazily-initialized default client. Prefer using
# APIClient as a context manager in new code.

_default: APIClient | None = None


async def _get_default() -> APIClient:
    global _default
    if _default is None:
        _default = APIClient()
        await _default.__aenter__()
    return _default


async def ensure_profile(name: str, email: str, config_path: str) -> int:
    api = await _get_default()
    return await api.ensure_profile(name, email, config_path)


async def save_job(job: dict) -> int | None:
    api = await _get_default()
    return await api.save_job(job)


async def save_jobs_batch(jobs: list[dict]) -> list[int]:
    api = await _get_default()
    return await api.save_jobs_batch(jobs)


async def filter_new_jobs(jobs: list[dict]) -> list[dict]:
    api = await _get_default()
    return await api.filter_new_jobs(jobs)


async def save_analysis(
    job_id: int, profile_id: int, analysis: dict,
    embedding_score: float | None = None, route_action: str | None = None,
) -> int | None:
    api = await _get_default()
    return await api.save_analysis(job_id, profile_id, analysis, embedding_score, route_action)


async def update_cover_letter(job_id: int, profile_id: int, cover_letter: str) -> None:
    api = await _get_default()
    return await api.update_cover_letter(job_id, profile_id, cover_letter)


async def enqueue_email(
    job_id: int, profile_id: int, recipient_email: str,
    recipient_name: str, recipient_role: str, recipient_source: str,
    subject: str, body_html: str, body_plain: str,
    signature: str = "", resume_path: str = "",
    email_verified: bool = False, verification_result: str = "unverified",
    verification_provider: str = "",
) -> int | None:
    api = await _get_default()
    return await api.enqueue_email(
        job_id, profile_id, recipient_email, recipient_name, recipient_role,
        recipient_source, subject, body_html, body_plain, signature,
        resume_path, email_verified, verification_result, verification_provider,
    )


async def mark_verified(email_id: int, verification_result: str, verification_provider: str) -> None:
    api = await _get_default()
    return await api.mark_verified(email_id, verification_result, verification_provider)


async def advance_to_ready(email_id: int) -> None:
    api = await _get_default()
    return await api.advance_to_ready(email_id)


async def save_startup_profile(profile_data: dict) -> int | None:
    api = await _get_default()
    return await api.save_startup_profile(profile_data)
