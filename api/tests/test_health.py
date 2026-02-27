"""Tests for the /api/health endpoint."""

import asyncpg


def test_health_ok(authed_client):
    """Health check returns ok when DB is reachable."""
    client, conn = authed_client
    conn.fetchval.return_value = 1

    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["db"] is True


def test_health_degraded_postgres_error(authed_client):
    """Health check returns degraded when DB raises PostgresError."""
    client, conn = authed_client
    conn.fetchval.side_effect = asyncpg.PostgresError("connection lost")

    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "degraded"
    assert data["db"] is False


def test_health_degraded_connection_error(authed_client):
    """Health check returns degraded on network errors."""
    client, conn = authed_client
    conn.fetchval.side_effect = OSError("connection refused")

    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "degraded"
    assert data["db"] is False


def test_health_degraded_timeout(authed_client):
    """Health check returns degraded on timeout."""
    client, conn = authed_client
    conn.fetchval.side_effect = TimeoutError("query timed out")

    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "degraded"
    assert data["db"] is False
