"""Central LLM client — OpenAI GPT-4o-mini.

Every component uses this module for LLM calls. All calls are async.
Uses GPT-4o-mini for all tasks (cheapest, fast, adequate for structured extraction).

Langfuse tracing: if langfuse is installed and configured, all OpenAI calls
are auto-traced via the langfuse.openai drop-in wrapper.
"""

import asyncio
import json
import os

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

# Use Langfuse-wrapped OpenAI for automatic tracing (falls back to regular if not installed)
_LANGFUSE_TRACING = False
try:
    from langfuse.openai import AsyncOpenAI
    _LANGFUSE_TRACING = True
except ImportError:
    from openai import AsyncOpenAI

from core.constants import (
    DEFAULT_LLM_MODEL,
    LLM_RETRY_ATTEMPTS,
    LLM_RETRY_MAX_WAIT,
    LLM_RETRY_MIN_WAIT,
)
from core.logger import logger

# Transient errors worth retrying
_LLM_RETRIABLE = (TimeoutError, ConnectionError, OSError)


class LLMClient:
    """OpenAI GPT-4o-mini client."""

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY", "")
        self.openai_client = AsyncOpenAI(api_key=api_key) if api_key else None
        self.model = os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL)

    async def call(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.3,
        max_tokens: int = 1000,
        name: str | None = None,
    ) -> str | None:
        """Make an LLM call. Returns response text or None on failure."""
        if not self.openai_client:
            logger.error("No OpenAI API key configured.")
            return None

        try:
            return await self._call_openai(
                prompt, system_prompt, temperature, max_tokens, name=name
            )
        except _LLM_RETRIABLE as e:
            logger.warning(f"OpenAI transient error: {e}")
        except Exception as e:
            logger.warning(f"OpenAI failed: {e}")

        return None

    async def call_json(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.2,
        max_tokens: int = 1500,
        name: str | None = None,
    ) -> dict | None:
        """Make an LLM call that returns structured JSON."""
        if not self.openai_client:
            logger.error("No OpenAI API key configured.")
            return None

        try:
            return await self._call_openai_json(
                prompt, system_prompt, temperature, max_tokens, name=name
            )
        except json.JSONDecodeError as e:
            logger.error(f"OpenAI returned invalid JSON: {e}")
        except _LLM_RETRIABLE as e:
            logger.warning(f"OpenAI JSON transient error: {e}")
        except Exception as e:
            logger.warning(f"OpenAI JSON failed: {e}")

        return None

    @retry(
        stop=stop_after_attempt(LLM_RETRY_ATTEMPTS),
        wait=wait_exponential(min=LLM_RETRY_MIN_WAIT, max=LLM_RETRY_MAX_WAIT),
        retry=retry_if_exception_type(_LLM_RETRIABLE),
        reraise=True,
    )
    async def _call_openai(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
        name: str | None = None,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs = dict(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if _LANGFUSE_TRACING and name:
            kwargs["name"] = name

        response = await self.openai_client.chat.completions.create(**kwargs)
        if not response.choices:
            raise ValueError("LLM returned no choices")
        return response.choices[0].message.content

    @retry(
        stop=stop_after_attempt(LLM_RETRY_ATTEMPTS),
        wait=wait_exponential(min=LLM_RETRY_MIN_WAIT, max=LLM_RETRY_MAX_WAIT),
        retry=retry_if_exception_type(_LLM_RETRIABLE),
        reraise=True,
    )
    async def _call_openai_json(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
        name: str | None = None,
    ) -> dict:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs = dict(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        if _LANGFUSE_TRACING and name:
            kwargs["name"] = name

        response = await self.openai_client.chat.completions.create(**kwargs)
        if not response.choices:
            raise ValueError("LLM returned no choices")
        return json.loads(response.choices[0].message.content)


# ─── Thread-safe singleton ──────────────────────────────
_client: LLMClient | None = None
_lock = asyncio.Lock()


async def get_llm_client() -> LLMClient:
    """Get or create the singleton LLM client (async, thread-safe)."""
    global _client
    if _client is None:
        async with _lock:
            if _client is None:
                _client = LLMClient()
    return _client
