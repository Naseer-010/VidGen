"""
DIME — BGE-M3 Embedding Service.

Generates embeddings for RAG retrieval using BGE-M3.
Runs on CPU — does not consume GPU VRAM.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

_model = None


def get_embedding_model():
    """Lazy-load the BGE-M3 embedding model."""
    global _model
    if _model is None:
        try:
            from FlagEmbedding import BGEM3FlagModel

            _model = BGEM3FlagModel(
                "BAAI/bge-m3",
                use_fp16=False,  # CPU mode
            )
            logger.info("BGE-M3 embedding model loaded")
        except ImportError:
            logger.warning(
                "FlagEmbedding not installed. Install with: pip install FlagEmbedding"
            )
            # Fallback to sentence-transformers
            try:
                from sentence_transformers import SentenceTransformer

                _model = SentenceTransformer("BAAI/bge-m3")
                logger.info("BGE-M3 loaded via sentence-transformers (fallback)")
            except ImportError:
                logger.error("No embedding library available!")
                raise
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for a list of texts.

    Returns:
        List of embedding vectors (each a list of floats)
    """
    model = get_embedding_model()

    try:
        # Try FlagEmbedding API first
        if hasattr(model, "encode"):
            result = model.encode(texts)
            # Handle different return types
            if isinstance(result, dict):
                # FlagEmbedding returns dict with 'dense_vecs'
                embeddings = result.get("dense_vecs", result.get("dense", []))
            else:
                embeddings = result

            if isinstance(embeddings, np.ndarray):
                return embeddings.tolist()
            return [e.tolist() if isinstance(e, np.ndarray) else e for e in embeddings]
        else:
            raise ValueError("Model has no encode method")

    except Exception as e:
        logger.error("Embedding failed: %s", e)
        # Return zero vectors as fallback
        dim = 1024  # BGE-M3 dimension
        return [[0.0] * dim for _ in texts]


def embed_query(query: str) -> list[float]:
    """Generate embedding for a single query."""
    results = embed_texts([query])
    return results[0] if results else [0.0] * 1024
