"""
DIME — LLM Backend Abstraction Layer.

Reads INFERENCE_BACKEND env var and provides AsyncOpenAI clients
pointing to the correct vLLM endpoints [dgx | local].

Usage:
    from src.backend import brain_client, coder_client, get_brain_client
"""

from __future__ import annotations

import logging
from openai import AsyncOpenAI

from src.config import settings

logger = logging.getLogger(__name__)


def _make_client(base_url: str) -> AsyncOpenAI:
    """Create an AsyncOpenAI client pointing at a vLLM endpoint."""
    return AsyncOpenAI(
        base_url=base_url,
        api_key="EMPTY",  # vLLM doesn't need a real API key
        timeout=120.0,
    )


# ── Pre-built client singletons ─────────────────────────────
brain_client: AsyncOpenAI = _make_client(settings.brain_url)
coder_client: AsyncOpenAI = _make_client(settings.coder_url)

logger.info(
    "Backend initialized: %s → brain=%s, coder=%s",
    settings.inference_backend.value,
    settings.brain_url,
    settings.coder_url,
)


def get_brain_client() -> AsyncOpenAI:
    """Return the Brain model client (useful for dependency injection)."""
    return brain_client


def get_coder_client() -> AsyncOpenAI:
    """Return the Coder model client (useful for dependency injection)."""
    return coder_client


def switch_backend(backend: str) -> tuple[AsyncOpenAI, AsyncOpenAI]:
    """
    Hot-switch the backend at runtime. Returns (brain, coder) clients.
    Primarily useful for testing or dynamic fallback.
    """
    global brain_client, coder_client

    import os

    os.environ["INFERENCE_BACKEND"] = backend

    # Re-derive URLs based on new backend
    if backend == "dgx":
        brain_url = settings.dgx_brain_url
        coder_url = settings.dgx_coder_url
    else:
        brain_url = settings.local_brain_url
        coder_url = settings.local_coder_url

    brain_client = _make_client(brain_url)
    coder_client = _make_client(coder_url)

    logger.info("Backend switched to: %s", backend)
    return brain_client, coder_client
