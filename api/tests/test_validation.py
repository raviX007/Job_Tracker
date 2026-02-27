"""Tests for input validation — enum params, offset, decision/status Literal types."""


def test_applications_rejects_invalid_decision(authed_client):
    """GET /api/applications rejects decision values not in the Literal enum."""
    client, _ = authed_client
    resp = client.get("/api/applications", params={
        "profile_id": 1, "decision": "INVALID",
    })
    assert resp.status_code == 422


def test_applications_accepts_valid_decisions(authed_client):
    """GET /api/applications accepts all valid decision values."""
    client, conn = authed_client
    conn.fetch.return_value = []

    for decision in ("All", "YES", "NO", "MAYBE", "MANUAL"):
        resp = client.get("/api/applications", params={
            "profile_id": 1, "decision": decision,
        })
        assert resp.status_code == 200, f"Failed for decision={decision}"


def test_applications_offset_parameter(authed_client):
    """GET /api/applications supports offset for pagination."""
    client, conn = authed_client
    conn.fetch.return_value = []

    resp = client.get("/api/applications", params={
        "profile_id": 1, "offset": 50,
    })
    assert resp.status_code == 200


def test_applications_rejects_negative_offset(authed_client):
    """GET /api/applications rejects negative offset."""
    client, _ = authed_client
    resp = client.get("/api/applications", params={
        "profile_id": 1, "offset": -1,
    })
    assert resp.status_code == 422


def test_email_queue_rejects_invalid_status(authed_client):
    """GET /api/emails/queue rejects invalid status values."""
    client, _ = authed_client
    resp = client.get("/api/emails/queue", params={
        "profile_id": 1, "status": "nonexistent",
    })
    assert resp.status_code == 422


def test_email_queue_accepts_valid_statuses(authed_client):
    """GET /api/emails/queue accepts all valid email status values."""
    client, conn = authed_client
    conn.fetch.return_value = []

    for status in ("All", "draft", "verified", "ready", "queued", "sent", "delivered", "bounced", "failed"):
        resp = client.get("/api/emails/queue", params={
            "profile_id": 1, "status": status,
        })
        assert resp.status_code == 200, f"Failed for status={status}"


def test_email_queue_pagination(authed_client):
    """GET /api/emails/queue supports limit and offset."""
    client, conn = authed_client
    conn.fetch.return_value = []

    resp = client.get("/api/emails/queue", params={
        "profile_id": 1, "limit": 10, "offset": 20,
    })
    assert resp.status_code == 200


def test_delete_all_emails_rejects_invalid_profile(authed_client):
    """DELETE /api/emails rejects profile_id <= 0."""
    client, _ = authed_client
    resp = client.delete("/api/emails", params={"profile_id": 0})
    assert resp.status_code == 422


def test_delete_all_emails(authed_client):
    """DELETE /api/emails returns deleted count."""
    client, conn = authed_client
    conn.execute.return_value = "DELETE 5"

    resp = client.delete("/api/emails", params={"profile_id": 1})
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 5
