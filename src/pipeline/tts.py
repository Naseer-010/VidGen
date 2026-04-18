"""
DIME — Phase 2A: TTS (Kokoro-82M).

Text-to-Speech generation with word-level timestamps.
Processes all scene narrations in batch.
Runs on CPU — does not consume GPU VRAM.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf

from src.config import settings
from src.models import Scene, TTSResult, WordTimestamp

logger = logging.getLogger(__name__)

# ── Lazy-loaded TTS engine ───────────────────────────────────
_tts_pipeline = None


def _get_tts():
    """Lazy-load the Kokoro TTS pipeline."""
    global _tts_pipeline
    if _tts_pipeline is None:
        try:
            from kokoro import KPipeline

            _tts_pipeline = KPipeline(lang_code="a")
            logger.info("Kokoro TTS loaded (voice=%s)", settings.tts_voice)
        except ImportError:
            logger.error("kokoro not installed. Install with: pip install kokoro")
            raise
    return _tts_pipeline


async def generate_tts_batch(
    scenes: list[Scene],
    output_dir: str,
) -> list[TTSResult]:
    """
    Generate TTS audio for all scenes in batch.

    Args:
        scenes: List of Scene objects with narration text
        output_dir: Directory to save .wav files

    Returns:
        List of TTSResult with audio paths and timestamps
    """
    os.makedirs(output_dir, exist_ok=True)
    results = []

    for scene in scenes:
        try:
            result = await _generate_single_tts(
                scene_id=scene.scene_id,
                narration=scene.narration,
                output_dir=output_dir,
            )
            results.append(result)
            logger.info(
                "TTS: %s → %.1fs audio",
                scene.scene_id,
                result.duration_sec,
            )
        except Exception as e:
            logger.error("TTS failed for %s: %s", scene.scene_id, e)
            # Create a silence placeholder
            result = _create_silence(scene, output_dir)
            results.append(result)

    return results


async def _generate_single_tts(
    scene_id: str,
    narration: str,
    output_dir: str,
) -> TTSResult:
    """Generate TTS audio for a single scene narration."""
    tts = _get_tts()
    output_path = os.path.join(output_dir, f"{scene_id}.wav")

    # Generate audio from narration using Kokoro
    audio_segments = []
    word_timestamps = []
    current_time = 0.0

    generator = tts(
        narration,
        voice=settings.tts_voice,
        speed=1.0,
    )

    for i, (gs, ps, audio) in enumerate(generator):
        audio_segments.append(audio)
        # Build word-level timestamps from graphemes/phonemes
        segment_duration = len(audio) / settings.tts_sample_rate
        words = gs.split() if gs else []

        for j, word in enumerate(words):
            word_start = current_time + (j / max(len(words), 1)) * segment_duration
            word_end = current_time + ((j + 1) / max(len(words), 1)) * segment_duration
            word_timestamps.append(
                WordTimestamp(
                    word=word, start=round(word_start, 3), end=round(word_end, 3)
                )
            )

        current_time += segment_duration

    # Concatenate all audio segments
    if audio_segments:
        full_audio = np.concatenate(audio_segments)
    else:
        # Generate 3 seconds of silence as fallback
        full_audio = np.zeros(int(settings.tts_sample_rate * 3.0), dtype=np.float32)

    # Write WAV file
    sf.write(output_path, full_audio, settings.tts_sample_rate)
    duration = len(full_audio) / settings.tts_sample_rate

    return TTSResult(
        scene_id=scene_id,
        audio_path=output_path,
        duration_sec=round(duration, 2),
        word_timestamps=word_timestamps,
    )


def _create_silence(scene: Scene, output_dir: str) -> TTSResult:
    """Create a silence audio file as TTS fallback."""
    output_path = os.path.join(output_dir, f"{scene.scene_id}.wav")
    duration = scene.duration_estimate_sec

    silence = np.zeros(int(settings.tts_sample_rate * duration), dtype=np.float32)
    sf.write(output_path, silence, settings.tts_sample_rate)

    return TTSResult(
        scene_id=scene.scene_id,
        audio_path=output_path,
        duration_sec=round(duration, 2),
        word_timestamps=[],
    )
