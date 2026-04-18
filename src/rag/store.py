"""
DIME — ChromaDB Vector Store.

Two collections:
1. manim_docs — Official Manim Community documentation
2. validated_examples — Manim code that has successfully rendered
"""

from __future__ import annotations

import logging
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from src.config import settings
from src.rag.embeddings import embed_texts, embed_query

logger = logging.getLogger(__name__)

_client: Optional[chromadb.Client] = None


def get_chroma_client() -> chromadb.Client:
    """Get or create ChromaDB persistent client."""
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=str(settings.chroma_path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        logger.info("ChromaDB initialized at %s", settings.chroma_path)
    return _client


def get_docs_collection():
    """Get the Manim documentation collection."""
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=settings.chroma_collection_docs,
        metadata={"description": "Manim Community API documentation"},
    )


def get_examples_collection():
    """Get the validated examples collection."""
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=settings.chroma_collection_examples,
        metadata={"description": "Successfully rendered Manim code examples"},
    )


def add_documents(
    texts: list[str],
    ids: list[str],
    metadatas: Optional[list[dict]] = None,
    collection_name: str = "manim_docs",
) -> None:
    """Add documents to a ChromaDB collection."""
    collection = (
        get_docs_collection()
        if collection_name == settings.chroma_collection_docs
        else get_examples_collection()
    )

    embeddings = embed_texts(texts)

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas or [{}] * len(texts),
    )
    logger.info("Added %d documents to %s", len(texts), collection_name)


def add_validated_example(
    code: str,
    scene_type: str,
    scene_id: str,
) -> None:
    """
    Add a successfully rendered Manim code example to the examples collection.
    This collection grows over time and improves RAG quality.
    """
    add_documents(
        texts=[code],
        ids=[f"example_{scene_id}"],
        metadatas=[{"scene_type": scene_type, "scene_id": scene_id}],
        collection_name=settings.chroma_collection_examples,
    )


async def query_manim_docs(
    query: str,
    n_results: int = 5,
) -> list[str]:
    """
    Query the Manim docs collection for relevant documentation.

    Returns:
        List of relevant document chunks
    """
    try:
        collection = get_docs_collection()
        query_embedding = embed_query(query)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
        )

        if results and results.get("documents"):
            docs = results["documents"][0]
            logger.info("RAG: retrieved %d docs for query: %s", len(docs), query[:50])
            return docs
        return []

    except Exception as e:
        logger.warning("RAG query failed: %s", e)
        return []


async def query_validated_examples(
    query: str,
    n_results: int = 3,
) -> list[str]:
    """Query validated examples for similar successful code."""
    try:
        collection = get_examples_collection()
        query_embedding = embed_query(query)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
        )

        if results and results.get("documents"):
            return results["documents"][0]
        return []

    except Exception as e:
        logger.debug("Examples query failed: %s", e)
        return []
