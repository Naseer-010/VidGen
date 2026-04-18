"""
DIME — LangGraph Pipeline Orchestrator.

Connects all pipeline phases into a directed acyclic graph (DAG):

  [Ingestion] → [Brain] → [Validator] → ║ [TTS]     ║ → [Template Match]
                                          ║ [Director] ║     ↓ (miss)
                                                         [Coder] ↔ [Error Loop]
                                                           ↓
                                                      [Render] → [Quality Gate]
                                                           ↓
                                                      [Assembly] → Done
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Optional

from src.config import settings
from src.database import update_job_status
from src.models import (
    BrainOutput,
    DirectorBlueprint,
    Job,
    JobStatus,
    PipelineState,
    Scene,
    TTSResult,
)
from src.pipeline.brain import run_brain
from src.pipeline.validator import validate_answer
from src.pipeline.tts import generate_tts_batch
from src.pipeline.director import run_director
from src.pipeline.template_matcher import match_template
from src.pipeline.coder import generate_scene_code
from src.pipeline.error_patcher import apply_known_fixes
from src.pipeline.sandbox import execute_in_sandbox, execute_locally
from src.pipeline.quality_gate import check_scene_quality
from src.pipeline.assembler import assemble_final_video
from src.storage.file_store import file_store

logger = logging.getLogger(__name__)


async def run_pipeline(
    job_id: str,
    question_text: Optional[str] = None,
    question_image_base64: Optional[str] = None,
) -> Optional[PipelineState]:
    """
    Execute the full video generation pipeline.

    This is the main entry point called by the API background task.
    """
    job = Job(
        job_id=job_id,
        question_text=question_text,
    )
    state = PipelineState(job=job)

    try:
        # ── Phase 1: Brain ───────────────────────────────────
        logger.info("▶ Phase 1: Brain — solving question...")
        update_job_status(job_id, JobStatus.PROCESSING)

        brain_output = await run_brain(
            question_text=question_text,
            question_image_base64=question_image_base64,
        )
        state.brain_output = brain_output
        update_job_status(
            job_id,
            JobStatus.BRAIN_COMPLETE,
            brain_output_json=brain_output.model_dump_json(),
        )

        logger.info(
            "Brain: %d scenes, topic=%s, answer=%s",
            len(brain_output.scenes),
            brain_output.topic,
            brain_output.final_answer,
        )

        # ── Phase 1.5: Validator (async, non-blocking) ──────
        logger.info("▶ Phase 1.5: Validating answer...")
        is_valid, wolfram_answer = await validate_answer(
            question_text=question_text or "",
            final_answer=brain_output.final_answer,
            topic=brain_output.topic,
        )

        if not is_valid:
            logger.warning(
                "Validator disagreed — retrying Brain with lower temperature"
            )
            brain_output = await run_brain(
                question_text=question_text,
                question_image_base64=question_image_base64,
                temperature=0.0,  # Deterministic retry
            )
            state.brain_output = brain_output

        # ── Phase 2: TTS + Director (parallel) ──────────────
        logger.info("▶ Phase 2: TTS + Director (parallel)...")
        job_dir = file_store.create_job_dir(job_id)
        audio_dir = str(job_dir / "audio")

        tts_task = generate_tts_batch(brain_output.scenes, audio_dir)
        director_task = run_director(brain_output)

        state.tts_results, state.director_blueprints = await asyncio.gather(
            tts_task, director_task
        )

        update_job_status(job_id, JobStatus.TTS_COMPLETE)
        logger.info(
            "TTS: %d audio files, Director: %d blueprints",
            len(state.tts_results),
            len(state.director_blueprints),
        )

        # ── Phase 3+4: Template Match / Coder + Render ──────
        logger.info("▶ Phase 3+4: Generating + rendering scenes...")
        update_job_status(job_id, JobStatus.RENDERING)

        render_dir = str(job_dir / "renders")
        os.makedirs(render_dir, exist_ok=True)

        # Process each scene
        scene_results = await _process_all_scenes(
            scenes=brain_output.scenes,
            blueprints=state.director_blueprints,
            tts_results=state.tts_results,
            render_dir=render_dir,
            state=state,
        )

        # Collect successful scene videos (in order)
        ordered_videos = []
        ordered_audios = []
        for scene in brain_output.scenes:
            video_path = state.scene_videos.get(scene.scene_id)
            if video_path:
                ordered_videos.append(video_path)
                # Find matching audio
                tts = next(
                    (t for t in state.tts_results if t.scene_id == scene.scene_id),
                    None,
                )
                if tts:
                    ordered_audios.append(tts.audio_path)
                else:
                    ordered_audios.append("")

        if not ordered_videos:
            logger.error("No scenes rendered successfully!")
            update_job_status(
                job_id, JobStatus.FAILED, error_message="All scenes failed to render"
            )
            return state

        # ── Phase 6: Assembly ────────────────────────────────
        logger.info("▶ Phase 6: Assembling final video...")
        update_job_status(job_id, JobStatus.ASSEMBLING)

        final_path = await assemble_final_video(
            scene_video_paths=ordered_videos,
            scene_audio_paths=ordered_audios,
            output_dir=str(job_dir),
            job_id=job_id,
        )

        if final_path:
            # Copy to output directory
            final_name = f"{job_id}_final.mp4"
            stored_path = file_store.save_file(final_path, final_name)
            state.final_video_path = stored_path
            logger.info("✅ Pipeline COMPLETE: %s", stored_path)
        else:
            logger.error("Assembly failed!")
            update_job_status(job_id, JobStatus.FAILED, error_message="Assembly failed")

        return state

    except Exception as e:
        logger.exception("Pipeline failed for job %s: %s", job_id, e)
        update_job_status(job_id, JobStatus.FAILED, error_message=str(e))
        return state


async def _process_all_scenes(
    scenes: list[Scene],
    blueprints: list[DirectorBlueprint],
    tts_results: list[TTSResult],
    render_dir: str,
    state: PipelineState,
) -> None:
    """Process all scenes: template match → coder → render → quality gate."""

    # Create tasks for parallel processing
    tasks = []
    for i, scene in enumerate(scenes):
        blueprint = blueprints[i] if i < len(blueprints) else blueprints[-1]
        tts_result = tts_results[i] if i < len(tts_results) else tts_results[-1]

        tasks.append(
            _process_single_scene(
                scene=scene,
                blueprint=blueprint,
                tts_result=tts_result,
                render_dir=render_dir,
                state=state,
            )
        )

    # Process with concurrency limit
    semaphore = asyncio.Semaphore(settings.active_render_workers)

    async def limited_task(task):
        async with semaphore:
            return await task

    await asyncio.gather(*(limited_task(t) for t in tasks), return_exceptions=True)


async def _process_single_scene(
    scene: Scene,
    blueprint: DirectorBlueprint,
    tts_result: TTSResult,
    render_dir: str,
    state: PipelineState,
) -> None:
    """Process a single scene through template/coder → render → quality gate."""

    scene_dir = os.path.join(render_dir, scene.scene_id)
    os.makedirs(scene_dir, exist_ok=True)

    # ── Phase 3: Template match ──────────────────────────────
    code = None
    if not scene.requires_codegen:
        code = match_template(scene, blueprint, tts_result)

    # ── Phase 4: Coder (if template missed) ──────────────────
    if code is None:
        logger.info("Template miss for %s — calling Coder LLM", scene.scene_id)
        try:
            # Get RAG context
            rag_context = await _get_rag_context(scene)

            code = await generate_scene_code(
                scene=scene,
                blueprint=blueprint,
                tts_result=tts_result,
                rag_context=rag_context,
            )
        except Exception as e:
            logger.error("Coder failed for %s: %s", scene.scene_id, e)
            state.scene_errors[scene.scene_id] = str(e)
            return

    state.scene_codes[scene.scene_id] = code

    # ── Render with retry loop ───────────────────────────────
    scene_class_name = "".join(p.capitalize() for p in scene.scene_id.split("_"))

    for attempt in range(settings.max_coder_retries + 1):
        state.retry_counts[scene.scene_id] = attempt

        # Try rendering
        try:
            success, result, stderr = await execute_locally(
                scene_code=code,
                scene_name=scene_class_name,
                output_dir=scene_dir,
            )
        except Exception as e:
            success = False
            result = str(e)
            stderr = str(e)

        if success:
            # ── Phase 5: Quality Gate ────────────────────────
            qg_result = check_scene_quality(
                video_path=result,
                scene_id=scene.scene_id,
                expected_duration=tts_result.duration_sec,
            )

            if qg_result.passed:
                state.scene_videos[scene.scene_id] = result
                logger.info(
                    "✅ %s rendered successfully (attempt %d)",
                    scene.scene_id,
                    attempt + 1,
                )
                return
            else:
                logger.warning(
                    "QG failed for %s: %s",
                    scene.scene_id,
                    qg_result.errors,
                )
                result = f"Quality gate failed: {'; '.join(qg_result.errors)}"

        # ── Error recovery ───────────────────────────────────
        if attempt < settings.max_coder_retries:
            error_text = result if isinstance(result, str) else str(result)

            # Try known fixes first
            patched_code, fixes_applied = apply_known_fixes(code, error_text)

            if fixes_applied:
                logger.info(
                    "Applied %d known fixes for %s", len(fixes_applied), scene.scene_id
                )
                code = patched_code
            else:
                # LLM retry with error context
                logger.info("LLM retry %d for %s", attempt + 1, scene.scene_id)
                try:
                    code = await generate_scene_code(
                        scene=scene,
                        blueprint=blueprint,
                        tts_result=tts_result,
                        error_context=error_text[:2000],
                    )
                except Exception as e:
                    logger.error("Coder retry failed: %s", e)
                    continue

            state.scene_codes[scene.scene_id] = code

    # All retries exhausted
    logger.error(
        "❌ %s FAILED after %d attempts", scene.scene_id, settings.max_coder_retries + 1
    )
    state.scene_errors[scene.scene_id] = (
        f"Failed after {settings.max_coder_retries + 1} attempts"
    )


async def _get_rag_context(scene: Scene) -> Optional[str]:
    """Retrieve RAG context from ChromaDB for the Coder."""
    try:
        from src.rag.store import query_manim_docs

        results = await query_manim_docs(
            query=f"{scene.visual_type.value} {scene.narration[:100]}",
            n_results=5,
        )
        if results:
            return "\n---\n".join(results)
    except Exception as e:
        logger.debug("RAG unavailable: %s", e)
    return None
