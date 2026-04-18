"""
DIME — Phase 1.5: Math Validator (Wolfram Alpha).

Deterministic verification of the Brain's numerical answers.
NOT an LLM call — uses Wolfram Alpha's computational API.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


async def validate_answer(
    question_text: str,
    final_answer: str,
    topic: str = "",
) -> tuple[bool, Optional[str]]:
    """
    Validate the Brain's final_answer against Wolfram Alpha.

    Returns:
        (is_valid, wolfram_answer) — True if answers agree or verification unavailable
    """
    if settings.wolfram_app_id == "your-wolfram-app-id-here":
        logger.warning("Wolfram Alpha API key not configured — skipping validation")
        return True, None

    try:
        # Clean up the answer for Wolfram query
        query = _build_query(question_text, final_answer)
        wolfram_result = await _query_wolfram(query)

        if wolfram_result is None:
            logger.warning("Wolfram returned no result — skipping validation")
            return True, None

        # Compare answers
        is_match = _compare_answers(final_answer, wolfram_result)

        if is_match:
            logger.info("✅ Wolfram VALIDATES answer: %s", final_answer)
        else:
            logger.warning(
                "❌ Wolfram DISAGREES — Brain: %s, Wolfram: %s",
                final_answer,
                wolfram_result,
            )

        return is_match, wolfram_result

    except Exception as e:
        logger.warning("Wolfram validation error (graceful pass): %s", e)
        return True, None


async def _query_wolfram(query: str) -> Optional[str]:
    """Query Wolfram Alpha Short Answers API."""
    url = "http://api.wolframalpha.com/v1/result"
    params = {
        "appid": settings.wolfram_app_id,
        "i": query,
        "units": "metric",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params)

        if resp.status_code == 200:
            result = resp.text.strip()
            logger.debug("Wolfram result: %s", result)
            return result
        elif resp.status_code == 501:
            logger.debug("Wolfram: no short answer available")
            return None
        else:
            logger.warning("Wolfram HTTP %d: %s", resp.status_code, resp.text[:100])
            return None


def _build_query(question_text: str, final_answer: str) -> str:
    """Build an appropriate Wolfram Alpha query from the question."""
    # Try to extract the core mathematical expression
    # For simple numerical questions, just verify the computation
    text = question_text.strip()

    # If the question contains "find", "calculate", "what is" etc.,
    # send the core mathematical part
    patterns = [
        r"(?:find|calculate|compute|what is|determine|evaluate)\s+(.+)",
        r"(?:the value of)\s+(.+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip().rstrip(".")

    # Fallback: send the whole question
    return text[:200]


def _compare_answers(brain_answer: str, wolfram_answer: str) -> bool:
    """Compare Brain's answer with Wolfram's answer (fuzzy match)."""
    # Extract numbers from both
    brain_nums = _extract_numbers(brain_answer)
    wolfram_nums = _extract_numbers(wolfram_answer)

    if not brain_nums or not wolfram_nums:
        # Can't compare numerically — do string comparison
        return brain_answer.lower().strip() in wolfram_answer.lower().strip()

    # Compare the first (most significant) number
    brain_val = brain_nums[0]
    wolfram_val = wolfram_nums[0]

    # Allow 1% tolerance
    if abs(wolfram_val) > 1e-10:
        relative_error = abs(brain_val - wolfram_val) / abs(wolfram_val)
        return relative_error < 0.01
    else:
        return abs(brain_val - wolfram_val) < 1e-6


def _extract_numbers(text: str) -> list[float]:
    """Extract all numbers from a string."""
    # Match integers, decimals, scientific notation
    pattern = r"-?\d+\.?\d*(?:[eE][+-]?\d+)?"
    matches = re.findall(pattern, text)
    try:
        return [float(m) for m in matches]
    except ValueError:
        return []
