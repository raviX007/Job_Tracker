"""Tests for LLM client — initialization, call guards, singleton."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.constants import DEFAULT_LLM_MODEL

# ─── LLMClient ───────────────────────────────────────────

class TestLLMClient:
    """LLMClient init and call guards (no real API calls)."""

    def test_init_without_api_key_sets_client_none(self, monkeypatch):
        """Without OPENAI_API_KEY, openai_client should be None."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("LLM_MODEL", raising=False)

        # Re-import to pick up env change
        from core.llm import LLMClient
        client = LLMClient()
        assert client.openai_client is None

    def test_init_with_key_creates_client(self, monkeypatch):
        """With OPENAI_API_KEY set, openai_client should be created."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key-12345")
        monkeypatch.delenv("LLM_MODEL", raising=False)

        from core.llm import LLMClient
        client = LLMClient()
        assert client.openai_client is not None

    @pytest.mark.asyncio
    async def test_call_without_client_returns_none(self, monkeypatch):
        """call() should return None when no API key is configured."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        from core.llm import LLMClient
        client = LLMClient()
        result = await client.call("Hello")
        assert result is None

    @pytest.mark.asyncio
    async def test_call_json_without_client_returns_none(self, monkeypatch):
        """call_json() should return None when no API key is configured."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        from core.llm import LLMClient
        client = LLMClient()
        result = await client.call_json("Return JSON")
        assert result is None

    def test_model_defaults_to_gpt4o_mini(self, monkeypatch):
        """Model should default to DEFAULT_LLM_MODEL when LLM_MODEL not set."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("LLM_MODEL", raising=False)

        from core.llm import LLMClient
        client = LLMClient()
        assert client.model == DEFAULT_LLM_MODEL
        assert client.model == "gpt-4o-mini"

    def test_model_respects_env_var(self, monkeypatch):
        """Model should use LLM_MODEL env var when set."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("LLM_MODEL", "gpt-4o")

        from core.llm import LLMClient
        client = LLMClient()
        assert client.model == "gpt-4o"


# ─── Singleton ────────────────────────────────────────────

class TestGetLLMClient:
    """Singleton get_llm_client() function."""

    @pytest.mark.asyncio
    async def test_singleton_returns_same_instance(self, monkeypatch):
        """get_llm_client() should return the same instance on repeated calls."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        # Reset the singleton for a clean test
        import core.llm as llm_module
        llm_module._client = None

        from core.llm import get_llm_client
        client1 = await get_llm_client()
        client2 = await get_llm_client()
        assert client1 is client2

        # Clean up: reset singleton so other tests are not affected
        llm_module._client = None
