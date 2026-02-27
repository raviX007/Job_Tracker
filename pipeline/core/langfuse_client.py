"""Langfuse prompt management + tracing client.

Fetches versioned prompts from Langfuse at runtime. Falls back gracefully
if Langfuse is not configured or unavailable — callers use hardcoded prompts.

Also exports:
- observe: decorator for tracing functions (no-op if langfuse not installed)
- flush: flush pending traces at end of pipeline run

Env vars: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST
"""

import os
import threading

from core.logger import logger

# Export observe decorator (no-op fallback if langfuse not installed)
try:
    from langfuse import observe
except ImportError:
    def observe(*args, **kwargs):
        """No-op decorator when langfuse is not installed."""
        def decorator(func):
            return func
        if args and callable(args[0]):
            return args[0]
        return decorator

# Thread-safe lazy singleton
_client = None
_initialized = False
_lock = threading.Lock()


def _get_client():
    """Get or create the Langfuse client singleton. Returns None if not configured."""
    global _client, _initialized

    if _initialized:
        return _client

    with _lock:
        if _initialized:
            return _client

        _initialized = True

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not public_key or not secret_key:
        logger.info("Langfuse: no keys configured, using hardcoded prompts")
        return None

    try:
        from langfuse import Langfuse

        _client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
        logger.info("Langfuse: client initialized")
        return _client
    except Exception as e:
        logger.warning(f"Langfuse: failed to initialize client: {e}")
        return None


def get_prompt_messages(
    prompt_name: str,
    variables: dict,
) -> tuple[str, str, dict] | None:
    """Fetch a chat prompt from Langfuse, compile with variables.

    Args:
        prompt_name: Prompt name in Langfuse (e.g. "job-analysis")
        variables: Template variables to substitute (e.g. {"name": "Ravi", "company": "Google"})

    Returns:
        (system_content, user_content, config_dict) or None if unavailable.
        config_dict contains model parameters like temperature, max_tokens, model.
    """
    client = _get_client()
    if not client:
        return None

    try:
        prompt = client.get_prompt(prompt_name, type="chat", cache_ttl_seconds=300)
        messages = prompt.compile(**variables)
        config = prompt.config or {}

        # Extract system and user messages
        system_content = ""
        user_content = ""
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "system":
                system_content = content
            elif role == "user":
                user_content = content

        logger.debug(f"Langfuse: fetched prompt '{prompt_name}' (v{prompt.version})")
        return system_content, user_content, config

    except Exception as e:
        logger.warning(f"Langfuse: failed to fetch prompt '{prompt_name}': {e}")
        return None


def flush():
    """Flush pending Langfuse traces. Call at end of pipeline run."""
    client = _get_client()
    if client:
        try:
            client.flush()
            logger.debug("Langfuse: traces flushed")
        except Exception as e:
            logger.warning(f"Langfuse: flush failed: {e}")
