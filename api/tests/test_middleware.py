"""Tests for middleware — request logging and X-Request-ID header."""


def test_response_has_request_id_header(authed_client):
    """Every response should include an X-Request-ID header."""
    client, conn = authed_client
    conn.fetchval.return_value = 1

    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert "X-Request-ID" in resp.headers
    # Request ID should be an 8-char hex-like string
    assert len(resp.headers["X-Request-ID"]) == 8


def test_cors_headers_present(authed_client):
    """CORS preflight should work with configured origins."""
    client, _ = authed_client

    resp = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:8501",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-API-Key",
        },
    )
    # FastAPI CORS middleware responds to preflight requests
    assert resp.status_code == 200
