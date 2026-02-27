"""Tests for /api/jobs/{job_id}/check-link endpoint."""

from unittest.mock import AsyncMock, patch

from conftest import _mock_row


def test_check_link_alive(authed_client):
    """check-link returns alive=True for healthy URLs."""
    client, conn = authed_client
    conn.fetchrow.return_value = _mock_row({"job_url": "https://example.com/job/1"})

    mock_resp = AsyncMock()
    mock_resp.status_code = 200

    with patch("api.routers.jobs.httpx_client.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.head.return_value = mock_resp
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client_instance

        resp = client.get("/api/jobs/1/check-link")
        assert resp.status_code == 200
        data = resp.json()
        assert data["alive"] is True
        assert data["status_code"] == 200


def test_check_link_dead(authed_client):
    """check-link returns alive=False for 404 URLs."""
    client, conn = authed_client
    conn.fetchrow.return_value = _mock_row({"job_url": "https://example.com/gone"})

    mock_resp = AsyncMock()
    mock_resp.status_code = 404

    with patch("api.routers.jobs.httpx_client.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.head.return_value = mock_resp
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client_instance

        resp = client.get("/api/jobs/1/check-link")
        assert resp.status_code == 200
        data = resp.json()
        assert data["alive"] is False


def test_check_link_not_found(authed_client):
    """check-link returns 404 if job doesn't exist."""
    client, conn = authed_client
    conn.fetchrow.return_value = None

    resp = client.get("/api/jobs/999/check-link")
    assert resp.status_code == 404


def test_check_link_network_error(authed_client):
    """check-link returns alive=False on network errors."""
    client, conn = authed_client
    conn.fetchrow.return_value = _mock_row({"job_url": "https://unreachable.example.com"})

    with patch("api.routers.jobs.httpx_client.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        import httpx
        mock_client_instance.head.side_effect = httpx.ConnectError("refused")
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client_instance

        resp = client.get("/api/jobs/1/check-link")
        assert resp.status_code == 200
        data = resp.json()
        assert data["alive"] is False
        assert "error" in data
