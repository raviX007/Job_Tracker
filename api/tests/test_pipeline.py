"""Tests for pipeline write endpoints (save_job, save_analysis, etc.)."""

import asyncpg
from conftest import _mock_row


def test_save_job_success(authed_client):
    """POST /api/jobs saves a job and returns job_id."""
    client, conn = authed_client
    conn.fetchval.return_value = 42

    resp = client.post("/api/jobs", json={
        "job_url": "https://example.com/job/1",
        "source": "linkedin",
        "title": "Backend Developer",
        "company": "Acme Corp",
        "dedup_key": "acme-backend-dev",
    })
    assert resp.status_code == 201
    assert resp.json()["job_id"] == 42


def test_save_job_duplicate(authed_client):
    """POST /api/jobs returns null job_id for duplicate dedup_key."""
    client, conn = authed_client
    conn.fetchval.side_effect = asyncpg.UniqueViolationError()

    resp = client.post("/api/jobs", json={
        "dedup_key": "duplicate-key",
    })
    assert resp.status_code == 201
    assert resp.json()["job_id"] is None


def test_save_job_db_error(authed_client):
    """POST /api/jobs returns 500 on database error."""
    client, conn = authed_client
    conn.fetchval.side_effect = asyncpg.PostgresError("connection lost")

    resp = client.post("/api/jobs", json={
        "title": "Test Job",
    })
    assert resp.status_code == 500


def test_save_analysis_success(authed_client):
    """POST /api/analyses saves an analysis."""
    client, conn = authed_client
    conn.fetchval.return_value = 10

    resp = client.post("/api/analyses", json={
        "job_id": 1,
        "profile_id": 1,
        "match_score": 85,
        "apply_decision": "YES",
        "skills_matched": ["python", "fastapi"],
        "skills_missing": ["kubernetes"],
    })
    assert resp.status_code == 201
    assert resp.json()["analysis_id"] == 10


def test_save_analysis_invalid_score(authed_client):
    """POST /api/analyses rejects score > 100."""
    client, _ = authed_client

    resp = client.post("/api/analyses", json={
        "job_id": 1,
        "profile_id": 1,
        "match_score": 150,
    })
    assert resp.status_code == 422


def test_ensure_profile_existing(authed_client):
    """POST /api/profiles/ensure returns existing profile."""
    client, conn = authed_client
    conn.fetchrow.return_value = _mock_row({"id": 5})

    resp = client.post("/api/profiles/ensure", json={
        "name": "Test User",
        "email": "test@example.com",
        "config_path": "/path/to/config.yaml",
    })
    assert resp.status_code == 200
    assert resp.json()["profile_id"] == 5


def test_ensure_profile_new(authed_client):
    """POST /api/profiles/ensure creates a new profile."""
    client, conn = authed_client
    conn.fetchrow.return_value = None
    conn.fetchval.return_value = 7

    resp = client.post("/api/profiles/ensure", json={
        "name": "New User",
        "email": "new@example.com",
        "config_path": "/path/to/new.yaml",
    })
    assert resp.status_code == 200
    assert resp.json()["profile_id"] == 7


def test_dedup_check(authed_client):
    """POST /api/jobs/dedup-check returns existing keys and URLs."""
    client, conn = authed_client

    # First fetch for dedup_keys, second for urls
    conn.fetch.side_effect = [
        [_mock_row({"dedup_key": "key-1"})],
        [_mock_row({"job_url": "https://example.com/1"})],
    ]

    resp = client.post("/api/jobs/dedup-check", json={
        "dedup_keys": ["key-1", "key-2"],
        "urls": ["https://example.com/1", "https://example.com/2"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "key-1" in data["existing_keys"]
    assert "https://example.com/1" in data["existing_urls"]
