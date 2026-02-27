"""Integration tests — job save → analysis → email enqueue flow.

Tests multi-endpoint flows that the pipeline executes sequentially.
Uses mock DB (no real PostgreSQL), but exercises the real HTTP layer.
"""

import pytest
from unittest.mock import AsyncMock

from conftest import _mock_row


@pytest.mark.integration
def test_save_job_then_analyze_then_enqueue_email(authed_client):
    """Full pipeline data flow: save job → save analysis → enqueue email."""
    client, conn = authed_client

    # Step 1: Save a job
    conn.fetchval.return_value = 42  # job_id

    resp = client.post("/api/jobs", json={
        "job_url": "https://example.com/jobs/backend-dev",
        "source": "remotive",
        "discovered_via": "remotive",
        "title": "Backend Developer",
        "company": "TechStartup Inc",
        "location": "Remote",
        "is_remote": True,
        "dedup_key": "techstartup-backend-dev-remote",
    })
    assert resp.status_code == 201
    assert resp.json()["job_id"] == 42

    # Step 2: Save analysis for that job
    conn.fetchval.return_value = 10  # analysis_id

    resp = client.post("/api/analyses", json={
        "job_id": 42,
        "profile_id": 1,
        "match_score": 78,
        "embedding_score": 0.65,
        "skills_matched": ["python", "fastapi", "postgresql"],
        "skills_missing": ["kubernetes"],
        "apply_decision": "YES",
        "route_action": "cold_email_only",
        "cold_email_angle": "Fellow Python developer interested in your API platform",
    })
    assert resp.status_code == 201
    assert resp.json()["analysis_id"] == 10

    # Step 3: Enqueue cold email
    conn.fetchval.return_value = 5  # email_id

    resp = client.post("/api/emails/enqueue", json={
        "job_id": 42,
        "profile_id": 1,
        "recipient_email": "hr@techstartup.com",
        "recipient_name": "Hiring Manager",
        "recipient_role": "HR",
        "recipient_source": "hunter",
        "subject": "Backend Developer — Python + FastAPI experience",
        "body_html": "<p>Hi, I noticed your Backend Developer role...</p>",
        "body_plain": "Hi, I noticed your Backend Developer role...",
        "email_verified": True,
        "email_verification_result": "valid",
        "email_verification_provider": "hunter",
    })
    assert resp.status_code == 201
    assert resp.json()["email_id"] == 5


@pytest.mark.integration
def test_dedup_check_finds_existing_job(authed_client):
    """POST /api/jobs/dedup-check correctly identifies existing entries."""
    client, conn = authed_client

    # Simulate: one key exists, one URL exists
    conn.fetch.side_effect = [
        [_mock_row({"dedup_key": "existing-key"})],
        [_mock_row({"job_url": "https://example.com/existing"})],
    ]

    resp = client.post("/api/jobs/dedup-check", json={
        "dedup_keys": ["existing-key", "new-key"],
        "urls": ["https://example.com/existing", "https://example.com/new"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "existing-key" in data["existing_keys"]
    assert "new-key" not in data["existing_keys"]
    assert "https://example.com/existing" in data["existing_urls"]
    assert "https://example.com/new" not in data["existing_urls"]


@pytest.mark.integration
def test_ensure_profile_then_save_job(authed_client):
    """Profile creation followed by job save — simulates pipeline startup."""
    client, conn = authed_client

    # Step 1: Ensure profile (new user)
    conn.fetchrow.return_value = None  # no existing profile
    conn.fetchval.return_value = 3  # new profile_id

    resp = client.post("/api/profiles/ensure", json={
        "name": "Test User",
        "email": "test@example.com",
        "config_path": "/home/user/config.yaml",
    })
    assert resp.status_code == 200
    assert resp.json()["profile_id"] == 3

    # Step 2: Save a job with that profile's context
    conn.fetchval.return_value = 100  # job_id

    resp = client.post("/api/jobs", json={
        "job_url": "https://company.com/careers/dev",
        "source": "greenhouse",
        "title": "Software Engineer",
        "company": "Dream Company",
        "dedup_key": "dream-company-swe",
    })
    assert resp.status_code == 201
    assert resp.json()["job_id"] == 100


@pytest.mark.integration
def test_save_analysis_then_update_cover_letter(authed_client):
    """Analysis save followed by cover letter update."""
    client, conn = authed_client

    # Step 1: Save analysis
    conn.fetchval.return_value = 15  # analysis_id

    resp = client.post("/api/analyses", json={
        "job_id": 1,
        "profile_id": 1,
        "match_score": 85,
        "apply_decision": "YES",
    })
    assert resp.status_code == 201

    # Step 2: Update cover letter for that analysis
    conn.execute = AsyncMock()

    resp = client.put("/api/analyses/cover-letter", json={
        "job_id": 1,
        "profile_id": 1,
        "cover_letter": "Dear Hiring Manager, I am excited to apply...",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.integration
def test_enqueue_email_then_verify(authed_client):
    """Email enqueue followed by verification update."""
    client, conn = authed_client

    # Step 1: Enqueue email
    conn.fetchval.return_value = 8  # email_id

    resp = client.post("/api/emails/enqueue", json={
        "job_id": 1,
        "profile_id": 1,
        "recipient_email": "founder@startup.com",
        "subject": "Interested in joining your team",
        "body_html": "<p>Hello</p>",
        "body_plain": "Hello",
    })
    assert resp.status_code == 201
    email_id = resp.json()["email_id"]

    # Step 2: Mark email as verified
    conn.execute = AsyncMock()

    resp = client.put(f"/api/emails/{email_id}/verify", json={
        "verification_result": "valid",
        "verification_provider": "hunter",
    })
    assert resp.status_code == 200

    # Step 3: Advance to ready
    conn.execute = AsyncMock()

    resp = client.put(f"/api/emails/{email_id}/advance")
    assert resp.status_code == 200
