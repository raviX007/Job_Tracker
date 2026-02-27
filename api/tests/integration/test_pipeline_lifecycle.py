"""Integration tests — pipeline run lifecycle across multiple endpoints.

Tests the full flow: trigger run → callback updates → poll status.
Uses mock DB (no real PostgreSQL), but exercises the real HTTP layer.
"""

import pytest
from unittest.mock import AsyncMock, patch

from conftest import _mock_row


@pytest.mark.integration
def test_pipeline_run_then_callback_then_poll(authed_client):
    """Full lifecycle: POST run → PATCH callback (running) → PATCH callback (completed) → GET poll."""
    client, conn = authed_client

    # Step 1: No concurrent runs
    conn.fetchval.return_value = 0  # _check_concurrent_run returns 0
    conn.execute = AsyncMock()

    with patch("api.routers.pipeline.asyncio.create_task"):
        resp = client.post("/api/pipeline/main/run", json={"source": "remotive", "limit": 5})

    assert resp.status_code == 202
    data = resp.json()
    run_id = data["run_id"]
    assert data["pipeline"] == "main"
    assert data["status"] == "queued"

    # Step 2: Pipeline service reports "running" via callback
    conn.fetchrow.return_value = _mock_row({"id": 1})
    conn.execute = AsyncMock()

    resp = client.patch(f"/api/pipeline/runs/{run_id}/callback", json={
        "status": "running",
        "started_at": True,
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    # Step 3: Pipeline service reports "completed" via callback
    conn.fetchrow.return_value = _mock_row({"id": 1})
    conn.execute = AsyncMock()

    resp = client.patch(f"/api/pipeline/runs/{run_id}/callback", json={
        "status": "completed",
        "output": "[1/8] Scraping...\n[8/8] Done. 5 jobs analyzed.",
        "duration_seconds": 45.2,
        "return_code": 0,
    })
    assert resp.status_code == 200

    # Step 4: Poll the run status
    conn.fetchrow.return_value = _mock_row({
        "id": 1,
        "run_id": run_id,
        "pipeline": "main",
        "source": "remotive",
        "job_limit": 5,
        "status": "completed",
        "pid": None,
        "started_at": "2026-02-23T10:00:00",
        "finished_at": "2026-02-23T10:00:45",
        "duration_seconds": 45.2,
        "return_code": 0,
        "output": "[1/8] Scraping...\n[8/8] Done. 5 jobs analyzed.",
        "error": None,
        "created_at": "2026-02-23T10:00:00",
    })

    resp = client.get(f"/api/pipeline/runs/{run_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["duration_seconds"] == 45.2
    assert "5 jobs analyzed" in data["output"]


@pytest.mark.integration
def test_concurrent_run_blocked(authed_client):
    """Starting a second run of the same pipeline type returns 409."""
    client, conn = authed_client

    # Simulate an active run exists
    conn.fetchval.return_value = 1  # _check_concurrent_run returns 1

    resp = client.post("/api/pipeline/main/run", json={"source": "all", "limit": 10})
    assert resp.status_code == 409
    assert "already in progress" in resp.json()["detail"]


@pytest.mark.integration
def test_callback_unknown_run_id(authed_client):
    """Callback with non-existent run_id returns 404."""
    client, conn = authed_client

    conn.fetchrow.return_value = None  # run not found

    resp = client.patch("/api/pipeline/runs/nonexistent-id/callback", json={
        "status": "running",
    })
    assert resp.status_code == 404


@pytest.mark.integration
def test_callback_noop_empty_body(authed_client):
    """Callback with all-null fields returns no-op."""
    client, conn = authed_client

    conn.fetchrow.return_value = _mock_row({"id": 1})

    resp = client.patch("/api/pipeline/runs/some-run-id/callback", json={})
    assert resp.status_code == 200
    assert resp.json()["status"] == "no-op"


@pytest.mark.integration
def test_poll_nonexistent_run(authed_client):
    """GET /api/pipeline/runs/{run_id} with bad ID returns 404."""
    client, conn = authed_client

    conn.fetchrow.return_value = None

    resp = client.get("/api/pipeline/runs/does-not-exist")
    assert resp.status_code == 404


@pytest.mark.integration
def test_list_pipeline_runs(authed_client):
    """GET /api/pipeline/runs returns recent runs."""
    client, conn = authed_client

    conn.fetch.return_value = [
        _mock_row({
            "id": 1, "run_id": "run-1", "pipeline": "main", "source": "all",
            "job_limit": 10, "status": "completed", "pid": None,
            "started_at": None, "finished_at": None, "duration_seconds": None,
            "return_code": None, "output": "", "error": None,
            "created_at": "2026-02-23T10:00:00",
        }),
    ]

    resp = client.get("/api/pipeline/runs?limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["run_id"] == "run-1"
