"""Tests for /api/analytics endpoints."""

from datetime import date
from decimal import Decimal

from conftest import _mock_row

# ─── Daily Trends ────────────────────────────────────

def test_daily_trends_returns_list(authed_client):
    """GET /api/analytics/daily-trends returns trend data."""
    client, conn = authed_client

    rows = [
        _mock_row({"date": date(2025, 1, 15), "jobs_scraped": 5, "jobs_analyzed": 3, "emails_queued": 1}),
        _mock_row({"date": date(2025, 1, 16), "jobs_scraped": 8, "jobs_analyzed": 6, "emails_queued": 2}),
    ]
    conn.fetch.return_value = rows

    resp = client.get("/api/analytics/daily-trends", params={"profile_id": 1, "days": 7})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["jobs_scraped"] == 5


def test_daily_trends_validates_days_range(authed_client):
    """GET /api/analytics/daily-trends rejects days outside 1–365."""
    client, _ = authed_client

    resp = client.get("/api/analytics/daily-trends", params={"profile_id": 1, "days": 0})
    assert resp.status_code == 422

    resp = client.get("/api/analytics/daily-trends", params={"profile_id": 1, "days": 500})
    assert resp.status_code == 422


def test_daily_trends_requires_profile_id(authed_client):
    """GET /api/analytics/daily-trends returns 422 without profile_id."""
    client, _ = authed_client
    resp = client.get("/api/analytics/daily-trends")
    assert resp.status_code == 422


# ─── Score Distribution ────────────────────────────

def test_score_distribution(authed_client):
    """GET /api/analytics/score-distribution returns brackets."""
    client, conn = authed_client

    rows = [
        _mock_row({"bracket": "80-100 (High)", "count": 15}),
        _mock_row({"bracket": "60-79 (Good)", "count": 25}),
    ]
    conn.fetch.return_value = rows

    resp = client.get("/api/analytics/score-distribution", params={"profile_id": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["bracket"] == "80-100 (High)"


# ─── Source Breakdown ──────────────────────────────

def test_source_breakdown(authed_client):
    """GET /api/analytics/source-breakdown returns per-source stats."""
    client, conn = authed_client

    rows = [
        _mock_row({"source": "linkedin", "count": 50, "avg_score": Decimal("72"), "yes_count": 20}),
        _mock_row({"source": "wellfound", "count": 30, "avg_score": Decimal("68"), "yes_count": 10}),
    ]
    conn.fetch.return_value = rows

    resp = client.get("/api/analytics/source-breakdown", params={"profile_id": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["source"] == "linkedin"
    # Decimal should be serialized to float
    assert isinstance(data[0]["avg_score"], (int, float))


# ─── Company Types ─────────────────────────────────

def test_company_types(authed_client):
    """GET /api/analytics/company-types returns type breakdown."""
    client, conn = authed_client

    rows = [
        _mock_row({"company_type": "startup", "count": 40, "avg_score": Decimal("78"), "gap_tolerant_count": 30}),
    ]
    conn.fetch.return_value = rows

    resp = client.get("/api/analytics/company-types", params={"profile_id": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["company_type"] == "startup"


# ─── Response Rates ────────────────────────────────

def test_response_rates(authed_client):
    """GET /api/analytics/response-rates returns method-level stats."""
    client, conn = authed_client

    rows = [
        _mock_row({
            "method": "cold_email", "total": 20, "responded": 5,
            "interviews": 2, "rejections": 3, "offers": 0,
        }),
    ]
    conn.fetch.return_value = rows

    resp = client.get("/api/analytics/response-rates", params={"profile_id": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["method"] == "cold_email"
    assert data[0]["total"] == 20


# ─── Route Breakdown ──────────────────────────────

def test_route_breakdown(authed_client):
    """GET /api/analytics/route-breakdown returns action counts."""
    client, conn = authed_client

    rows = [
        _mock_row({"route_action": "cold_email_only", "count": 15}),
        _mock_row({"route_action": "auto_apply_and_cold_email", "count": 10}),
    ]
    conn.fetch.return_value = rows

    resp = client.get("/api/analytics/route-breakdown", params={"profile_id": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert data["cold_email_only"] == 15


def test_route_breakdown_empty(authed_client):
    """GET /api/analytics/route-breakdown returns empty dict when no data."""
    client, conn = authed_client
    conn.fetch.return_value = []

    resp = client.get("/api/analytics/route-breakdown", params={"profile_id": 1})
    assert resp.status_code == 200
    assert resp.json() == {}
