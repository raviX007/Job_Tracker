"""Tests for /api/applications endpoints."""

from datetime import date, datetime

from conftest import _mock_row


def test_applications_returns_list(authed_client):
    """GET /api/applications returns a list of jobs with X-Total-Count header."""
    client, conn = authed_client

    rows = [
        _mock_row({
            "job_id": 1, "title": "Backend Dev", "company": "Acme",
            "location": "Remote", "source": "linkedin", "is_remote": True,
            "job_url": "https://example.com/1", "date_posted": date(2025, 1, 15),
            "date_scraped": datetime(2025, 1, 16), "match_score": 85,
            "embedding_score": 0.92, "apply_decision": "YES",
            "skills_matched": ["python", "fastapi"], "skills_missing": [],
            "ats_keywords": ["python"], "gap_tolerant": True,
            "company_type": "startup", "route_action": "cold_email_only",
            "cold_email_angle": "Angle text", "cover_letter": "CL text",
            "experience_required": "1-3 years", "red_flags": [],
        }),
    ]
    conn.fetchval.return_value = 1
    conn.fetch.return_value = rows

    resp = client.get("/api/applications", params={"profile_id": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Backend Dev"
    assert data[0]["match_score"] == 85
    assert resp.headers["X-Total-Count"] == "1"


def test_applications_empty(authed_client):
    """GET /api/applications returns empty list when no matches."""
    client, conn = authed_client
    conn.fetchval.return_value = 0
    conn.fetch.return_value = []

    resp = client.get("/api/applications", params={"profile_id": 1})
    assert resp.status_code == 200
    assert resp.json() == []
    assert resp.headers["X-Total-Count"] == "0"


def test_applications_requires_profile_id(authed_client):
    """GET /api/applications returns 422 without profile_id."""
    client, _ = authed_client
    resp = client.get("/api/applications")
    assert resp.status_code == 422


def test_applications_validates_score_range(authed_client):
    """GET /api/applications rejects invalid score range."""
    client, _ = authed_client

    # min_score > 100
    resp = client.get("/api/applications", params={"profile_id": 1, "min_score": 150})
    assert resp.status_code == 422

    # negative min_score
    resp = client.get("/api/applications", params={"profile_id": 1, "min_score": -10})
    assert resp.status_code == 422


def test_applications_validates_limit(authed_client):
    """GET /api/applications rejects limit > 500 or limit < 1."""
    client, _ = authed_client

    resp = client.get("/api/applications", params={"profile_id": 1, "limit": 999})
    assert resp.status_code == 422

    resp = client.get("/api/applications", params={"profile_id": 1, "limit": 0})
    assert resp.status_code == 422


def test_create_application(authed_client):
    """POST /api/applications creates an application."""
    client, conn = authed_client
    conn.execute.return_value = "INSERT 0 1"

    resp = client.post("/api/applications", json={
        "job_id": 1, "profile_id": 1, "method": "cold_email", "platform": "email",
    })
    assert resp.status_code == 201
    assert resp.json()["status"] == "created"


def test_create_application_rejects_invalid_ids(authed_client):
    """POST /api/applications rejects non-positive IDs."""
    client, _ = authed_client

    resp = client.post("/api/applications", json={
        "job_id": 0, "profile_id": 1, "method": "cold_email", "platform": "email",
    })
    assert resp.status_code == 422


# ─── Pagination Tests ────────────────────────────────


def test_applications_x_total_count_header(authed_client):
    """X-Total-Count header reflects the total matching rows, not the page size."""
    client, conn = authed_client
    conn.fetchval.return_value = 42
    conn.fetch.return_value = [
        _mock_row({
            "job_id": i, "title": f"Job {i}", "company": "Co",
            "location": None, "source": "linkedin", "is_remote": False,
            "job_url": None, "date_posted": None, "date_scraped": None,
            "match_score": 80, "embedding_score": None, "apply_decision": "YES",
            "skills_matched": [], "skills_missing": [], "ats_keywords": [],
            "gap_tolerant": None, "company_type": None, "route_action": None,
            "cold_email_angle": None, "cover_letter": None,
            "experience_required": None, "red_flags": [],
        })
        for i in range(5)
    ]

    resp = client.get("/api/applications", params={
        "profile_id": 1, "limit": 5, "offset": 0,
    })
    assert resp.status_code == 200
    assert len(resp.json()) == 5
    assert resp.headers["X-Total-Count"] == "42"


def test_applications_pagination_params(authed_client):
    """Pagination params limit and offset are forwarded to the query."""
    client, conn = authed_client
    conn.fetchval.return_value = 100
    conn.fetch.return_value = []

    resp = client.get("/api/applications", params={
        "profile_id": 1, "limit": 10, "offset": 20,
    })
    assert resp.status_code == 200
    assert resp.headers["X-Total-Count"] == "100"
    # Verify both count and data queries were called
    assert conn.fetchval.called
    assert conn.fetch.called


def test_applications_filter_with_pagination(authed_client):
    """Filters combined with pagination still return correct count."""
    client, conn = authed_client
    conn.fetchval.return_value = 3
    conn.fetch.return_value = [
        _mock_row({
            "job_id": 1, "title": "Engineer", "company": "StartupCo",
            "location": "NYC", "source": "linkedin", "is_remote": False,
            "job_url": None, "date_posted": None, "date_scraped": None,
            "match_score": 90, "embedding_score": None, "apply_decision": "YES",
            "skills_matched": ["python"], "skills_missing": [],
            "ats_keywords": [], "gap_tolerant": None, "company_type": None,
            "route_action": None, "cold_email_angle": None,
            "cover_letter": None, "experience_required": None, "red_flags": [],
        }),
    ]

    resp = client.get("/api/applications", params={
        "profile_id": 1,
        "decision": "YES",
        "source": "linkedin",
        "min_score": 80,
        "limit": 5,
    })
    assert resp.status_code == 200
    assert resp.headers["X-Total-Count"] == "3"
    assert len(resp.json()) == 1
