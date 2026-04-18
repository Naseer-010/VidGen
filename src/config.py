"""
DIME — Centralized Configuration.
All settings loaded from .env via Pydantic BaseSettings.
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class InferenceBackend(str, Enum):
    LOCAL = "local"
    DGX = "dgx"


class Settings(BaseSettings):
    """Application-wide settings, loaded from .env file."""

    # ── Inference backend ────────────────────────────────────
    inference_backend: InferenceBackend = InferenceBackend.LOCAL

    # ── vLLM endpoints ───────────────────────────────────────
    local_brain_url: str = "http://localhost:8001/v1"
    local_coder_url: str = "http://localhost:8002/v1"
    dgx_brain_url: str = "http://172.16.10.220:8001/v1"
    dgx_coder_url: str = "http://172.16.10.220:8002/v1"

    # ── Model names ──────────────────────────────────────────
    brain_model_name: str = "Qwen/Qwen2.5-VL-7B-Instruct"
    coder_model_name: str = "Qwen/Qwen2.5-Coder-7B-Instruct"

    # ── Redis ────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Database ─────────────────────────────────────────────
    database_url: str = "sqlite:///./data/vidgen.db"

    # ── Wolfram Alpha ────────────────────────────────────────
    wolfram_app_id: str = "your-wolfram-app-id-here"

    # ── TTS ──────────────────────────────────────────────────
    tts_model: str = "kokoro"
    tts_voice: str = "af_heart"
    tts_sample_rate: int = 24000

    # ── Manim ────────────────────────────────────────────────
    manim_quality: str = "h"
    manim_resolution: str = "1920x1080"
    manim_timeout_seconds: int = 90
    max_render_workers: int = 6
    max_render_workers_fallback: int = 3

    # ── ChromaDB ─────────────────────────────────────────────
    chroma_persist_dir: str = "./data/chromadb"
    chroma_collection_docs: str = "manim_docs"
    chroma_collection_examples: str = "validated_examples"

    # ── Storage ──────────────────────────────────────────────
    output_dir: str = "./output"
    video_cache_ttl_seconds: int = 15552000  # 6 months

    # ── Docker Sandbox ───────────────────────────────────────
    docker_image_name: str = "dime-manim-sandbox"
    docker_memory_limit: str = "4g"
    docker_cpu_limit: int = 2

    # ── API ──────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # ── Coder Retry ──────────────────────────────────────────
    max_coder_retries: int = 4

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # ── Derived helpers ──────────────────────────────────────

    @property
    def brain_url(self) -> str:
        if self.inference_backend == InferenceBackend.DGX:
            return self.dgx_brain_url
        return self.local_brain_url

    @property
    def coder_url(self) -> str:
        if self.inference_backend == InferenceBackend.DGX:
            return self.dgx_coder_url
        return self.local_coder_url

    @property
    def active_render_workers(self) -> int:
        if self.inference_backend == InferenceBackend.LOCAL:
            return self.max_render_workers_fallback
        return self.max_render_workers

    @property
    def output_path(self) -> Path:
        p = Path(self.output_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def chroma_path(self) -> Path:
        p = Path(self.chroma_persist_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


# Singleton — import this everywhere
settings = Settings()
