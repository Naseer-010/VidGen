"""
DIME — FastAPI Application.

Main app with lifespan management for startup/shutdown
of Redis, database, and background workers.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.config import settings
from src.database import init_db

logger = logging.getLogger(__name__)

# ── Configure logging ────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-25s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup & shutdown hooks."""
    # ── Startup ──────────────────────────────────────────────
    logger.info("🚀 DIME Video Generation System starting...")
    logger.info("   Backend: %s", settings.inference_backend.value)
    logger.info("   Brain URL: %s", settings.brain_url)
    logger.info("   Coder URL: %s", settings.coder_url)

    # Initialize database
    init_db()

    # Ensure output directory exists
    settings.output_path.mkdir(parents=True, exist_ok=True)

    logger.info("✅ DIME ready to serve requests")

    yield

    # ── Shutdown ─────────────────────────────────────────────
    logger.info("🛑 DIME shutting down...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="DIME — Video Generation System",
        description=(
            "Automated explanatory video pipeline for JEE-level questions. "
            "Submit a question → receive a narrated Manim animation video."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount static files for serving generated videos
    from pathlib import Path

    output_dir = Path(settings.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/videos", StaticFiles(directory=str(output_dir)), name="videos")

    # Register API routes
    from src.api.routes import router

    app.include_router(router)

    return app


# ── App instance ─────────────────────────────────────────────
app = create_app()
