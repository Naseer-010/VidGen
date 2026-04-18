"""
DIME — Phase 0: Input Ingestion & Hash Computation.

Handles:
- SHA-256 hashing for text questions
- Perceptual hashing (pHash) for image questions
- Cache lookup via Redis
- Job creation in database
"""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import re
from typing import Optional

from PIL import Image
import imagehash

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """Normalize question text for consistent hashing."""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)  # collapse whitespace
    text = re.sub(r"[^\w\s+\-*/=().,]", "", text)  # remove special chars
    return text


def compute_text_hash(text: str) -> str:
    """Compute SHA-256 of normalized question text."""
    normalized = normalize_text(text)
    h = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    logger.debug("Text hash: %s → %s", text[:50], h[:12])
    return h


def compute_image_hash(image_base64: str) -> str:
    """Compute perceptual hash (pHash) of a question image."""
    try:
        image_bytes = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_bytes))
        phash = str(imagehash.phash(image, hash_size=16))
        logger.debug("Image pHash: %s", phash[:12])
        return phash
    except Exception as e:
        logger.warning("Image hash failed, falling back to SHA-256: %s", e)
        return hashlib.sha256(image_base64.encode()).hexdigest()


def compute_hash(
    text: Optional[str] = None,
    image_base64: Optional[str] = None,
) -> str:
    """Compute hash for either text or image input."""
    if text:
        return compute_text_hash(text)
    if image_base64:
        return compute_image_hash(image_base64)
    raise ValueError("Either text or image_base64 must be provided")
