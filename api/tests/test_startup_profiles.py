"""Tests for /api/startup-profiles endpoints."""

from datetime import date, datetime
from decimal import Decimal

from conftest import _mock_row


def _startup_row(**overrides):
    """Helper to create a standard startup profile mock row with optional overrides."""
    defaults = {
        "id": 1, "job_id": 10, "startup_name": "CoolAI",
        "website_url": "https://coolai.com", "yc_url": None, "ph_url": None,
        "founding_date": date(2024, 3, 1), "founding_date_source": "yc",
        "age_months": 12, "founder_names": ["Alice"], "founder_emails": ["alice@coolai.com"],
        "founder_roles": ["CEO"], "employee_count": 5, "employee_count_source": "linkedin",
        "one_liner": "AI for everything", "product_description": "Cool product",
        "tech_stack": ["python", "react"], "topics": ["ai"],
        "has_customers": True, "has_customers_evidence": "10+ paying",
        "funding_amount": "$2M", "funding_round": "seed",
        "funding_date": date(2024, 6, 1), "funding_source": "crunchbase",
        "source": "yc", "yc_batch": "W24",
        "ph_launch_date": None, "ph_votes_count": None, "ph_maker_info": None,
        "hn_thread_date": None,
        "llm_extracted": True, "llm_extraction_raw": None,
        "data_completeness": 85,
        "created_at": datetime(2025, 1, 1), "updated_at": datetime(2025, 1, 1),
        "company": "CoolAI Inc", "location": "SF", "is_remote": True,
        "job_url": "https://example.com/job/10", "date_scraped": datetime(2025, 1, 1),
        "match_score": 90, "apply_decision": "YES",
        "cold_email_angle": "Angle", "matching_skills": ["python"],
        "missing_skills": [], "route_action": "cold_email_only",
        "gap_framing_for_this_role": None,
        "email_id": 5, "email_status": "draft",
        "recipient_email": "alice@coolai.com", "email_recipient_name": "Alice",
    }
    defaults.update(overrides)
    return _mock_row(defaults)


def test_startup_profiles_returns_list(authed_client):
    """GET /api/startup-profiles returns startup data with X-Total-Count header."""
    client, conn = authed_client

    conn.fetchval.return_value = 1
    conn.fetch.return_value = [_startup_row()]

    resp = client.get("/api/startup-profiles", params={"profile_id": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["startup_name"] == "CoolAI"
    assert resp.headers["X-Total-Count"] == "1"


def test_startup_profiles_validates_sort(authed_client):
    """GET /api/startup-profiles rejects invalid sort_by values."""
    client, _ = authed_client
    resp = client.get("/api/startup-profiles", params={
        "profile_id": 1, "sort_by": "invalid_sort",
    })
    assert resp.status_code == 422


def test_startup_profiles_validates_has_funding(authed_client):
    """GET /api/startup-profiles rejects invalid has_funding values."""
    client, _ = authed_client
    resp = client.get("/api/startup-profiles", params={
        "profile_id": 1, "has_funding": "invalid",
    })
    assert resp.status_code == 422


def test_startup_profiles_pagination(authed_client):
    """GET /api/startup-profiles supports limit and offset with X-Total-Count."""
    client, conn = authed_client
    conn.fetchval.return_value = 0
    conn.fetch.return_value = []

    resp = client.get("/api/startup-profiles", params={
        "profile_id": 1, "limit": 10, "offset": 20,
    })
    assert resp.status_code == 200
    assert resp.json() == []
    assert resp.headers["X-Total-Count"] == "0"


def test_startup_profiles_requires_profile_id(authed_client):
    """GET /api/startup-profiles returns 422 without profile_id."""
    client, _ = authed_client
    resp = client.get("/api/startup-profiles")
    assert resp.status_code == 422


def test_startup_profile_stats(authed_client):
    """GET /api/startup-profiles/stats returns summary stats."""
    client, conn = authed_client

    conn.fetchval.side_effect = [
        50,     # total
        Decimal("75"),   # avg_score
        20,     # with_emails
        Decimal("70"),   # avg_completeness
    ]
    conn.fetch.side_effect = [
        [_mock_row({"source": "yc", "count": 30}), _mock_row({"source": "ph", "count": 20})],
        [_mock_row({"round": "seed", "count": 25}), _mock_row({"round": "unknown", "count": 25})],
    ]

    resp = client.get("/api/startup-profiles/stats", params={"profile_id": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 50
    assert data["avg_score"] == 75


def test_startup_profile_sources(authed_client):
    """GET /api/startup-profiles/sources returns distinct sources."""
    client, conn = authed_client

    conn.fetch.return_value = [
        _mock_row({"source": "yc"}),
        _mock_row({"source": "ph"}),
    ]

    resp = client.get("/api/startup-profiles/sources", params={"profile_id": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert "yc" in data
    assert "ph" in data


# ─── Pagination Tests ────────────────────────────────


def test_startup_profiles_x_total_count_header(authed_client):
    """X-Total-Count header reflects total matching startups."""
    client, conn = authed_client
    conn.fetchval.return_value = 100
    conn.fetch.return_value = [_startup_row(id=i, job_id=i) for i in range(5)]

    resp = client.get("/api/startup-profiles", params={
        "profile_id": 1, "limit": 5, "offset": 0,
    })
    assert resp.status_code == 200
    assert len(resp.json()) == 5
    assert resp.headers["X-Total-Count"] == "100"


def test_startup_profiles_filters_with_count(authed_client):
    """Filters combined with pagination return correct count."""
    client, conn = authed_client
    conn.fetchval.return_value = 12
    conn.fetch.return_value = [_startup_row(source="yc")]

    resp = client.get("/api/startup-profiles", params={
        "profile_id": 1,
        "source": "yc",
        "has_funding": "Yes",
        "limit": 10,
        "offset": 0,
    })
    assert resp.status_code == 200
    assert resp.headers["X-Total-Count"] == "12"
    assert conn.fetchval.called
    assert conn.fetch.called
