"""Tests for /api/emails endpoints."""

from datetime import datetime

from conftest import _mock_row


def _email_row(**overrides):
    """Helper to create a standard email mock row with optional overrides."""
    defaults = {
        "id": 1, "recipient_email": "a@b.com", "recipient_name": "Alice",
        "recipient_role": "CTO", "recipient_source": "apollo",
        "subject": "Hello", "body_plain": "Hi there",
        "email_verified": True, "email_verification_result": "valid",
        "status": "ready", "sent_at": None,
        "created_at": datetime(2025, 1, 15),
        "job_title": "Backend Dev", "job_company": "Acme",
        "job_url": "https://example.com", "job_source": "linkedin",
        "match_score": 85, "route_action": "cold_email_only",
    }
    defaults.update(overrides)
    return _mock_row(defaults)


def test_email_queue_returns_list(authed_client):
    """GET /api/emails/queue returns emails with X-Total-Count header."""
    client, conn = authed_client

    conn.fetchval.return_value = 1
    conn.fetch.return_value = [_email_row()]

    resp = client.get("/api/emails/queue", params={"profile_id": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["recipient_email"] == "a@b.com"
    assert resp.headers["X-Total-Count"] == "1"


def test_email_statuses(authed_client):
    """GET /api/emails/statuses returns status counts."""
    client, conn = authed_client

    rows = [
        _mock_row({"status": "draft", "count": 5}),
        _mock_row({"status": "sent", "count": 3}),
    ]
    conn.fetch.return_value = rows

    resp = client.get("/api/emails/statuses", params={"profile_id": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert data["draft"] == 5
    assert data["sent"] == 3


def test_get_email_by_id_found(authed_client):
    """GET /api/emails/{id} returns the email."""
    client, conn = authed_client

    conn.fetchrow.return_value = _mock_row({
        "id": 42, "recipient_email": "a@b.com", "subject": "Hello",
        "body_plain": "Hi", "status": "draft",
    })

    resp = client.get("/api/emails/42")
    assert resp.status_code == 200
    assert resp.json()["id"] == 42


def test_get_email_by_id_not_found(authed_client):
    """GET /api/emails/{id} returns 404 when not found."""
    client, conn = authed_client
    conn.fetchrow.return_value = None

    resp = client.get("/api/emails/999")
    assert resp.status_code == 404


def test_delete_email(authed_client):
    """DELETE /api/emails/{id} deletes an email."""
    client, conn = authed_client
    conn.execute.return_value = "DELETE 1"

    resp = client.delete("/api/emails/42")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_update_email_content(authed_client):
    """PUT /api/emails/{id}/content updates subject and body."""
    client, conn = authed_client
    conn.execute.return_value = "UPDATE 1"

    resp = client.put("/api/emails/42/content", json={
        "subject": "New Subject",
        "body_plain": "New body text",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_update_email_rejects_empty_subject(authed_client):
    """PUT /api/emails/{id}/content rejects empty subject."""
    client, _ = authed_client

    resp = client.put("/api/emails/42/content", json={
        "subject": "",
        "body_plain": "Body text",
    })
    assert resp.status_code == 422


# ─── Pagination Tests ────────────────────────────────


def test_email_queue_x_total_count_header(authed_client):
    """X-Total-Count header reflects total matching emails."""
    client, conn = authed_client
    conn.fetchval.return_value = 15
    conn.fetch.return_value = [_email_row(id=i) for i in range(5)]

    resp = client.get("/api/emails/queue", params={
        "profile_id": 1, "limit": 5, "offset": 0,
    })
    assert resp.status_code == 200
    assert len(resp.json()) == 5
    assert resp.headers["X-Total-Count"] == "15"


def test_email_queue_filters_with_pagination(authed_client):
    """Status and source filters work alongside pagination."""
    client, conn = authed_client
    conn.fetchval.return_value = 8
    conn.fetch.return_value = [_email_row(status="ready")]

    resp = client.get("/api/emails/queue", params={
        "profile_id": 1,
        "status": "ready",
        "source": "linkedin",
        "limit": 10,
        "offset": 5,
    })
    assert resp.status_code == 200
    assert resp.headers["X-Total-Count"] == "8"
    assert conn.fetchval.called
    assert conn.fetch.called


def test_email_queue_empty_with_count(authed_client):
    """Empty result set still returns X-Total-Count: 0."""
    client, conn = authed_client
    conn.fetchval.return_value = 0
    conn.fetch.return_value = []

    resp = client.get("/api/emails/queue", params={"profile_id": 1})
    assert resp.status_code == 200
    assert resp.json() == []
    assert resp.headers["X-Total-Count"] == "0"
