"""Tests for /api/tracker and job action endpoints."""

from conftest import _mock_row


def _tracker_row(**overrides):
    """Helper to create a standard tracker mock row with optional overrides."""
    defaults = {
        "job_id": 1, "title": "Backend Dev", "company": "Acme",
        "location": "Remote", "source": "linkedin", "is_remote": True,
        "job_url": "https://example.com/1", "is_obsolete": False,
        "match_score": 85, "apply_decision": "YES",
        "route_action": "cold_email_only",
        "skills_matched": ["python"], "skills_missing": [],
        "embedding_score": 0.9,
        "app_id": None, "app_method": None, "app_platform": None,
        "applied_at": None, "response_type": None, "app_notes": None,
    }
    defaults.update(overrides)
    return _mock_row(defaults)


# ─── Tracker Data ────────────────────────────────────

def test_tracker_data_returns_list(authed_client):
    """GET /api/tracker returns actionable jobs with X-Total-Count header."""
    client, conn = authed_client

    conn.fetchval.return_value = 1
    conn.fetch.return_value = [_tracker_row()]

    resp = client.get("/api/tracker", params={"profile_id": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Backend Dev"
    assert resp.headers["X-Total-Count"] == "1"


def test_tracker_data_requires_profile_id(authed_client):
    """GET /api/tracker returns 422 without profile_id."""
    client, _ = authed_client
    resp = client.get("/api/tracker")
    assert resp.status_code == 422


# ─── Mark Job Obsolete ──────────────────────────────

def test_mark_job_obsolete(authed_client):
    """PUT /api/jobs/{id}/obsolete toggles status."""
    client, conn = authed_client
    conn.fetchrow.return_value = _mock_row({"is_obsolete": False})
    conn.execute.return_value = "UPDATE 1"

    resp = client.put("/api/jobs/1/obsolete")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_obsolete"] is True


def test_mark_job_obsolete_not_found(authed_client):
    """PUT /api/jobs/{id}/obsolete returns 404 for missing job."""
    client, conn = authed_client
    conn.fetchrow.return_value = None

    resp = client.put("/api/jobs/999/obsolete")
    assert resp.status_code == 404


# ─── Upsert Application ─────────────────────────────

def test_upsert_application_insert(authed_client):
    """POST /api/applications/upsert inserts a new application."""
    client, conn = authed_client
    conn.execute.return_value = "INSERT 0 1"

    resp = client.post("/api/applications/upsert", json={
        "job_id": 1, "profile_id": 1, "method": "cold_email",
        "platform": "email",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_upsert_application_update(authed_client):
    """POST /api/applications/upsert updates an existing application."""
    client, conn = authed_client
    conn.execute.return_value = "UPDATE 1"

    resp = client.post("/api/applications/upsert", json={
        "job_id": 1, "profile_id": 1, "method": "manual_apply",
        "platform": "linkedin", "app_id": 42,
        "response_type": "interview", "notes": "Scheduled for Monday",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ─── Application Sources ────────────────────────────

def test_application_sources(authed_client):
    """GET /api/applications/sources returns source list."""
    client, conn = authed_client

    rows = [
        _mock_row({"source": "linkedin"}),
        _mock_row({"source": "wellfound"}),
    ]
    conn.fetch.return_value = rows

    resp = client.get("/api/applications/sources", params={"profile_id": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert "All" in data
    assert "linkedin" in data


# ─── Update Outcome ──────────────────────────────────

def test_update_outcome(authed_client):
    """PUT /api/applications/{id}/outcome updates response info."""
    client, conn = authed_client
    conn.execute.return_value = "UPDATE 1"

    resp = client.put("/api/applications/1/outcome", json={
        "response_type": "interview",
        "response_date": "2025-02-01",
        "notes": "Phone screen scheduled",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_update_outcome_rejects_empty_type(authed_client):
    """PUT /api/applications/{id}/outcome rejects empty response_type."""
    client, _ = authed_client

    resp = client.put("/api/applications/1/outcome", json={
        "response_type": "",
        "notes": "",
    })
    assert resp.status_code == 422


# ─── Pagination Tests ────────────────────────────────


def test_tracker_x_total_count_header(authed_client):
    """X-Total-Count header reflects the total matching rows."""
    client, conn = authed_client
    conn.fetchval.return_value = 25
    conn.fetch.return_value = [_tracker_row(job_id=i) for i in range(10)]

    resp = client.get("/api/tracker", params={
        "profile_id": 1, "limit": 10, "offset": 0,
    })
    assert resp.status_code == 200
    assert len(resp.json()) == 10
    assert resp.headers["X-Total-Count"] == "25"


def test_tracker_pagination_params(authed_client):
    """Pagination params are forwarded to the database query."""
    client, conn = authed_client
    conn.fetchval.return_value = 100
    conn.fetch.return_value = []

    resp = client.get("/api/tracker", params={
        "profile_id": 1, "limit": 10, "offset": 30,
    })
    assert resp.status_code == 200
    assert resp.headers["X-Total-Count"] == "100"
    assert conn.fetchval.called
    assert conn.fetch.called


def test_tracker_empty_with_count(authed_client):
    """Empty tracker returns X-Total-Count: 0."""
    client, conn = authed_client
    conn.fetchval.return_value = 0
    conn.fetch.return_value = []

    resp = client.get("/api/tracker", params={"profile_id": 1})
    assert resp.status_code == 200
    assert resp.json() == []
    assert resp.headers["X-Total-Count"] == "0"
