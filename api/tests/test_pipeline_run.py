"""Tests for pipeline run and dedup-check endpoints."""

from unittest.mock import AsyncMock, patch

from conftest import _mock_row


def test_run_main_pipeline_valid_source(authed_client):
    """POST /api/pipeline/main/run with valid source returns 202."""
    client, conn = authed_client

    conn.fetchval.return_value = 0  # no concurrent runs
    conn.execute = AsyncMock()

    with patch("api.routers.pipeline.asyncio.create_task"):
        resp = client.post("/api/pipeline/main/run", json={"source": "remotive", "limit": 5})

    assert resp.status_code == 202
    data = resp.json()
    assert data["pipeline"] == "main"
    assert data["status"] == "queued"
    assert "run_id" in data


def test_run_pipeline_invalid_source(authed_client):
    """POST /api/pipeline/main/run rejects invalid source values."""
    client, _ = authed_client
    resp = client.post("/api/pipeline/main/run", json={"source": "invalid_source"})
    assert resp.status_code == 422


def test_run_pipeline_limit_bounds(authed_client):
    """POST /api/pipeline/main/run rejects out-of-range limits."""
    client, _ = authed_client
    resp = client.post("/api/pipeline/main/run", json={"source": "all", "limit": 0})
    assert resp.status_code == 422

    resp = client.post("/api/pipeline/main/run", json={"source": "all", "limit": 999})
    assert resp.status_code == 422


def test_run_startup_scout_valid(authed_client):
    """POST /api/pipeline/startup-scout/run returns 202."""
    client, conn = authed_client

    conn.fetchval.return_value = 0
    conn.execute = AsyncMock()

    with patch("api.routers.pipeline.asyncio.create_task"):
        resp = client.post("/api/pipeline/startup-scout/run", json={"source": "hn_hiring", "limit": 10})

    assert resp.status_code == 202
    data = resp.json()
    assert data["pipeline"] == "startup_scout"


def test_dedup_check(authed_client):
    """POST /api/jobs/dedup-check returns existing keys and URLs."""
    client, conn = authed_client

    conn.fetch.side_effect = [
        [_mock_row({"dedup_key": "key1"})],
        [_mock_row({"job_url": "https://example.com/1"})],
    ]

    resp = client.post("/api/jobs/dedup-check", json={
        "dedup_keys": ["key1", "key2"],
        "urls": ["https://example.com/1", "https://example.com/2"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "key1" in data["existing_keys"]
    assert "https://example.com/1" in data["existing_urls"]


def test_dedup_check_size_limit(authed_client):
    """POST /api/jobs/dedup-check rejects oversized lists."""
    client, _ = authed_client
    resp = client.post("/api/jobs/dedup-check", json={
        "urls": ["https://example.com"] * 1001,
    })
    assert resp.status_code == 422
