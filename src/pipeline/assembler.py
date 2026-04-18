"""
DIME — Phase 6: Assembly (FFmpeg Mux + Concat).

Handles:
1. Muxing audio (TTS .wav) into each scene video
2. Concatenating all scene videos into final output
3. Generating HLS playlist for streaming (future)
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


async def mux_audio_video(
    video_path: str,
    audio_path: str,
    output_path: str,
) -> bool:
    """
    Mux audio track into a video file.

    ffmpeg -i scene.mp4 -i scene.wav -c:v copy -c:a aac -shortest output.mp4
    """
    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-i",
            audio_path,
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-movflags",
            "+faststart",
            output_path,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0 and os.path.exists(output_path):
            logger.info("✅ Muxed: %s + %s → %s", video_path, audio_path, output_path)
            return True
        else:
            logger.warning("❌ Mux failed: %s", result.stderr[:200])
            return False

    except Exception as e:
        logger.error("Mux error: %s", e)
        return False


async def concat_videos(
    video_paths: list[str],
    output_path: str,
) -> bool:
    """
    Concatenate multiple scene videos into a single output.

    Uses FFmpeg concat demuxer for lossless concatenation.
    """
    if not video_paths:
        logger.error("No videos to concatenate")
        return False

    if len(video_paths) == 1:
        # Single scene — just copy
        import shutil

        shutil.copy2(video_paths[0], output_path)
        return True

    try:
        # Create file list for concat
        filelist_path = output_path + ".filelist.txt"
        with open(filelist_path, "w") as f:
            for path in video_paths:
                # FFmpeg needs escaped paths
                escaped = path.replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")

        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            filelist_path,
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            output_path,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Clean up filelist
        if os.path.exists(filelist_path):
            os.remove(filelist_path)

        if result.returncode == 0 and os.path.exists(output_path):
            logger.info("✅ Concat: %d scenes → %s", len(video_paths), output_path)
            return True
        else:
            logger.warning("❌ Concat failed: %s", result.stderr[:200])
            return False

    except Exception as e:
        logger.error("Concat error: %s", e)
        return False


async def assemble_final_video(
    scene_video_paths: list[str],
    scene_audio_paths: list[str],
    output_dir: str,
    job_id: str,
) -> Optional[str]:
    """
    Full assembly pipeline:
    1. Mux audio into each scene video
    2. Concatenate all muxed scenes
    3. Return path to final output

    Args:
        scene_video_paths: Ordered list of rendered scene .mp4 files
        scene_audio_paths: Ordered list of TTS .wav files (same order)
        output_dir: Directory for output files
        job_id: Job ID for naming

    Returns:
        Path to final assembled video, or None on failure
    """
    os.makedirs(output_dir, exist_ok=True)

    # ── Step 1: Mux audio into each scene ────────────────────
    muxed_paths = []
    for i, (video, audio) in enumerate(zip(scene_video_paths, scene_audio_paths)):
        muxed = os.path.join(output_dir, f"scene_{i:02d}_muxed.mp4")

        if await mux_audio_video(video, audio, muxed):
            muxed_paths.append(muxed)
        else:
            # Fallback: use video without audio
            logger.warning("Using video without audio for scene %d", i)
            muxed_paths.append(video)

    # ── Step 2: Concatenate ──────────────────────────────────
    final_path = os.path.join(output_dir, f"{job_id}_final.mp4")

    if await concat_videos(muxed_paths, final_path):
        logger.info("✅ Final video assembled: %s", final_path)
        return final_path
    else:
        logger.error("❌ Final assembly failed")
        return None


async def generate_hls_playlist(
    video_path: str,
    output_dir: str,
) -> Optional[str]:
    """
    Generate HLS playlist for streaming.
    (Future enhancement — direct MP4 delivery for now)
    """
    try:
        playlist_path = os.path.join(output_dir, "output.m3u8")

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-codec:",
            "copy",
            "-start_number",
            "0",
            "-hls_time",
            "10",
            "-hls_list_size",
            "0",
            "-f",
            "hls",
            playlist_path,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            logger.info("HLS playlist generated: %s", playlist_path)
            return playlist_path
        else:
            logger.warning("HLS generation failed: %s", result.stderr[:200])
            return None

    except Exception as e:
        logger.error("HLS error: %s", e)
        return None
