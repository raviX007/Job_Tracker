"""Shared fixtures for API tests.

Uses FastAPI's TestClient with a mocked database pool so tests
run without a real PostgreSQL instance.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class MockAsyncContextManager:
    """Async context manager that yields a mock connection."""

    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *args):
        pass


@pytest.fixture()
def mock_pool():
    """Create a mock asyncpg pool with async context manager support."""
    conn = AsyncMock()
    pool = MagicMock()
    pool.acquire.return_value = MockAsyncContextManager(conn)
    pool.close = AsyncMock()
    return pool, conn


@pytest.fixture()
def client(mock_pool):
    """Create a test client with the mocked pool injected."""
    pool, conn = mock_pool

    @asynccontextmanager
    async def mock_lifespan(app):
        app.state.pool = pool
        yield
        await pool.close()

    with patch.dict("os.environ", {"DATABASE_URL": "postgresql://test:test@localhost/test"}):
        from api.server import app

        original_lifespan = app.router.lifespan_context
        app.router.lifespan_context = mock_lifespan

        with TestClient(app) as c:
            yield c, conn

        app.router.lifespan_context = original_lifespan


@pytest.fixture()
def authed_client(client):
    """Client with auth bypassed (API_SECRET_KEY patched to empty)."""
    c, conn = client
    with patch("api.deps.API_SECRET_KEY", ""):
        yield c, conn


def _mock_row(data: dict):
    """Create a mock asyncpg Record that supports dict() and key access."""
    class MockRecord(dict):
        def __getitem__(self, key):
            return super().__getitem__(key)
        def get(self, key, default=None):
            return super().get(key, default)
    return MockRecord(data)
