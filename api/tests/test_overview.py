"""Tests for /api/overview/stats endpoint."""

from conftest import _mock_row


def test_overview_stats_returns_all_fields(authed_client):
    """GET /api/overview/stats returns all expected stat fields."""
    client, conn = authed_client

    conn.fetchrow.return_value = _mock_row({
        "today_jobs": 10,
        "today_analyzed": 5,
        "today_emails": 3,
        "today_applied": 2,
        "total_jobs": 100,
        "total_analyzed": 80,
        "total_yes": 40,
        "total_emails": 25,
        "avg_score": 75,
        "jobs_with_emails": 20,
        "week_jobs": 50,
    })

    resp = client.get("/api/overview/stats", params={"profile_id": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert data["today_jobs"] == 10
    assert data["total_jobs"] == 100
    assert data["avg_score"] == 75
    assert data["week_jobs"] == 50


def test_overview_stats_requires_profile_id(authed_client):
    """GET /api/overview/stats returns 422 without profile_id."""
    client, _ = authed_client
    resp = client.get("/api/overview/stats")
    assert resp.status_code == 422


def test_overview_stats_rejects_invalid_profile_id(authed_client):
    """GET /api/overview/stats rejects profile_id <= 0."""
    client, _ = authed_client
    resp = client.get("/api/overview/stats", params={"profile_id": 0})
    assert resp.status_code == 422

    resp = client.get("/api/overview/stats", params={"profile_id": -5})
    assert resp.status_code == 422
