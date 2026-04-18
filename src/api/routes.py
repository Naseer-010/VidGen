"""
DIME — API Routes.

POST /generate       — Submit question (text or image), get job_id
GET  /status/{id}    — Poll job status
GET  /video/{id}     — Get video URL once complete
POST /generate/sync  — Synchronous generation (waits for result)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File, Form

from src.config import settings
from src.database import create_job, get_job, find_job_by_hash, update_job_status
from src.models import (
    GenerateRequest,
    GenerateResponse,
    Job,
    JobStatus,
    JobStatusResponse,
)
from src.pipeline.ingestion import compute_text_hash, compute_image_hash
from src.pipeline.orchestrator import run_pipeline
from src.storage.cache import get_cached_video, set_cached_video

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["generation"])


# ═════════════════════════════════════════════════════════════
# POST /generate — Queue a video generation job
# ═════════════════════════════════════════════════════════════


@router.post("/generate", response_model=GenerateResponse)
async def generate_video(
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
):
    """
    Accept a JEE question (text and/or image) and queue video generation.
    Returns a job_id for polling.
    """
    if not request.has_input():
        raise HTTPException(400, "Provide question_text or question_image_base64")

    # ── Compute hash ─────────────────────────────────────────
    if request.question_text:
        q_hash = compute_text_hash(request.question_text)
    elif request.question_image_base64:
        q_hash = compute_image_hash(request.question_image_base64)
    else:
        q_hash = "unknown"

    # ── Cache check ──────────────────────────────────────────
    cached_url = await get_cached_video(q_hash)
    if cached_url:
        logger.info("Cache HIT for hash %s", q_hash[:12])
        job = Job(
            status=JobStatus.COMPLETED,
            question_hash=q_hash,
            video_url=cached_url,
        )
        return GenerateResponse(
            job_id=job.job_id,
            status=JobStatus.COMPLETED,
            message="Video found in cache!",
            poll_url=f"/api/v1/status/{job.job_id}",
            video_url=cached_url,
        )

    # ── Check DB for completed job with same hash ────────────
    existing = find_job_by_hash(q_hash)
    if existing and existing.video_url:
        logger.info("DB cache HIT for hash %s", q_hash[:12])
        return GenerateResponse(
            job_id=existing.job_id,
            status=JobStatus.COMPLETED,
            message="Video previously generated!",
            poll_url=f"/api/v1/status/{existing.job_id}",
            video_url=existing.video_url,
        )

    # ── Create new job ───────────────────────────────────────
    job = Job(
        question_text=request.question_text,
        question_hash=q_hash,
    )

    # Persist to DB
    create_job(
        job_id=job.job_id,
        question_text=request.question_text,
        question_hash=q_hash,
    )

    # ── Queue pipeline in background ─────────────────────────
    background_tasks.add_task(
        _run_pipeline_task,
        job_id=job.job_id,
        question_text=request.question_text,
        question_image_base64=request.question_image_base64,
        question_hash=q_hash,
    )

    logger.info("Job %s queued for hash %s", job.job_id, q_hash[:12])

    return GenerateResponse(
        job_id=job.job_id,
        status=JobStatus.QUEUED,
        message="Video generation queued. Poll /status for updates.",
        poll_url=f"/api/v1/status/{job.job_id}",
    )


# ═════════════════════════════════════════════════════════════
# GET /status/{job_id} — Poll job status
# ═════════════════════════════════════════════════════════════


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Poll the status of a video generation job."""
    record = get_job(job_id)
    if not record:
        raise HTTPException(404, f"Job {job_id} not found")

    return JobStatusResponse(
        job_id=record.job_id,
        status=JobStatus(record.status),
        progress=record.status,
        video_url=record.video_url,
        error=record.error_message,
    )


# ═════════════════════════════════════════════════════════════
# GET /video/{job_id} — Get video URL
# ═════════════════════════════════════════════════════════════


@router.get("/video/{job_id}")
async def get_video(job_id: str):
    """Get the video URL for a completed job."""
    record = get_job(job_id)
    if not record:
        raise HTTPException(404, f"Job {job_id} not found")

    if record.status != JobStatus.COMPLETED.value:
        raise HTTPException(
            202,
            f"Video not ready yet. Status: {record.status}",
        )

    if not record.video_url:
        raise HTTPException(500, "Video completed but URL not found")

    return {"job_id": job_id, "video_url": record.video_url}


# ═════════════════════════════════════════════════════════════
# Background task runner
# ═════════════════════════════════════════════════════════════


async def _run_pipeline_task(
    job_id: str,
    question_text: Optional[str],
    question_image_base64: Optional[str],
    question_hash: str,
):
    """Run the full pipeline in background."""
    try:
        update_job_status(job_id, JobStatus.PROCESSING)

        result = await run_pipeline(
            job_id=job_id,
            question_text=question_text,
            question_image_base64=question_image_base64,
        )

        if result and result.final_video_path:
            video_url = f"/videos/{result.final_video_path.split('/')[-1]}"
            update_job_status(
                job_id,
                JobStatus.COMPLETED,
                final_video_path=result.final_video_path,
                video_url=video_url,
            )
            # Write to cache
            await set_cached_video(question_hash, video_url)
            logger.info("Job %s COMPLETED → %s", job_id, video_url)
        else:
            update_job_status(
                job_id,
                JobStatus.FAILED,
                error_message="Pipeline returned no output",
            )

    except Exception as e:
        logger.exception("Job %s FAILED: %s", job_id, e)
        update_job_status(job_id, JobStatus.FAILED, error_message=str(e))
