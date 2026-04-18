#!/usr/bin/env python3
"""
DIME — Manim Documentation Ingestion Script.

One-time setup to populate ChromaDB with Manim API docs.
Run this before first use to enable RAG for the Coder.

Usage:
    python scripts/ingest_manim_docs.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rag.ingest_docs import ingest_curated_docs, ingest_from_urls

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-25s │ %(levelname)-7s │ %(message)s",
)

logger = logging.getLogger(__name__)


async def main():
    logger.info("🚀 Starting Manim documentation ingestion...")

    # Step 1: Ingest curated API docs (always available)
    logger.info("Step 1: Ingesting curated Manim API reference...")
    ingest_curated_docs()

    # Step 2: Scrape official docs (requires internet)
    logger.info("Step 2: Scraping official Manim documentation...")
    try:
        await ingest_from_urls()
    except Exception as e:
        logger.warning("URL ingestion failed (will use curated docs only): %s", e)

    logger.info("✅ Documentation ingestion complete!")


if __name__ == "__main__":
    asyncio.run(main())
