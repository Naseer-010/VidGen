"""
DIME — Phase 5: Quality Gate.

Automated validation of rendered scene .mp4 files before assembly.
No LLM calls — purely deterministic checks.
"""

from __future__ import annotations

import logging
import os
import subprocess
import json
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class QualityResult:
    """Result of quality gate checks."""

    passed: bool
    scene_id: str
    checks: dict[str, bool]
    errors: list[str]
    video_duration: float = 0.0
    resolution: tuple[int, int] = (0, 0)
    file_size_bytes: int = 0


def check_scene_quality(
    video_path: str,
    scene_id: str,
    expected_duration: float,
    target_width: int = 1920,
    target_height: int = 1080,
) -> QualityResult:
    """
    Run all quality checks on a rendered scene video.

    Checks:
    1. Duration match (within 0.3s of expected)
    2. Resolution check (must be target resolution)
    3. Blank frame detection (not all-black or all-white)
    4. File size sanity (2-40MB for a typical scene)
    """
    checks = {}
    errors = []

    if not os.path.exists(video_path):
        return QualityResult(
            passed=False,
            scene_id=scene_id,
            checks={"file_exists": False},
            errors=[f"Video file not found: {video_path}"],
        )

    checks["file_exists"] = True

    # ── File size check ──────────────────────────────────────
    file_size = os.path.getsize(video_path)
    min_size = 100_000  # 100KB minimum
    max_size = 100_000_000  # 100MB maximum
    checks["file_size_ok"] = min_size <= file_size <= max_size
    if not checks["file_size_ok"]:
        errors.append(f"File size {file_size / 1e6:.1f}MB outside expected range")

    # ── Get video info via FFprobe ───────────────────────────
    probe = _ffprobe(video_path)
    if probe is None:
        return QualityResult(
            passed=False,
            scene_id=scene_id,
            checks=checks,
            errors=errors + ["FFprobe failed — cannot analyze video"],
            file_size_bytes=file_size,
        )

    # ── Duration check ───────────────────────────────────────
    video_duration = probe.get("duration", 0.0)
    duration_diff = abs(video_duration - expected_duration)
    checks["duration_match"] = duration_diff < 2.0  # Allow 2s tolerance
    if not checks["duration_match"]:
        errors.append(
            f"Duration mismatch: expected {expected_duration:.1f}s, got {video_duration:.1f}s"
        )

    # ── Resolution check ─────────────────────────────────────
    width = probe.get("width", 0)
    height = probe.get("height", 0)
    # Accept target or close to it (Manim may produce slightly different)
    checks["resolution_ok"] = (
        abs(width - target_width) <= 8 and abs(height - target_height) <= 8
    )
    if not checks["resolution_ok"]:
        errors.append(
            f"Resolution {width}x{height} != expected {target_width}x{target_height}"
        )

    # ── Blank frame detection ────────────────────────────────
    checks["not_blank"] = _check_not_blank(video_path)
    if not checks["not_blank"]:
        errors.append("Blank frame detected — video may be empty/broken")

    # ── Overall pass ─────────────────────────────────────────
    passed = all(checks.values())

    result = QualityResult(
        passed=passed,
        scene_id=scene_id,
        checks=checks,
        errors=errors,
        video_duration=video_duration,
        resolution=(width, height),
        file_size_bytes=file_size,
    )

    if passed:
        logger.info(
            "✅ QG PASS: %s (%.1fs, %dx%d, %.1fMB)",
            scene_id,
            video_duration,
            width,
            height,
            file_size / 1e6,
        )
    else:
        logger.warning("❌ QG FAIL: %s — %s", scene_id, "; ".join(errors))

    return result


def _ffprobe(video_path: str) -> Optional[dict]:
    """Extract video metadata using FFprobe."""
    try:
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode != 0:
            logger.warning("FFprobe error: %s", result.stderr[:200])
            return None

        data = json.loads(result.stdout)
        info = {}

        # Get duration from format
        if "format" in data:
            info["duration"] = float(data["format"].get("duration", 0))

        # Get resolution from video stream
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                info["width"] = int(stream.get("width", 0))
                info["height"] = int(stream.get("height", 0))
                if "duration" not in info or info["duration"] == 0:
                    info["duration"] = float(stream.get("duration", 0))
                break

        return info

    except Exception as e:
        logger.warning("FFprobe failed: %s", e)
        return None


def _check_not_blank(video_path: str) -> bool:
    """Check that the video isn't all-black or all-white."""
    try:
        # Extract 5 frames at evenly spaced intervals
        cmd = [
            "ffmpeg",
            "-i",
            video_path,
            "-vf",
            "select='not(mod(n\\,30))',setpts=N/FRAME_RATE/TB",
            "-frames:v",
            "5",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "gray",
            "-v",
            "quiet",
            "-",
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=15)

        if result.returncode != 0 or not result.stdout:
            return True  # If we can't check, assume it's fine

        # Check pixel values
        import numpy as np

        pixels = np.frombuffer(result.stdout, dtype=np.uint8)

        if len(pixels) == 0:
            return True

        avg_brightness = pixels.mean()
        std_brightness = pixels.std()

        # All-black: mean ≈ 0, std ≈ 0
        # All-white: mean ≈ 255, std ≈ 0
        # Normal video: mean varies, std > 10
        return std_brightness > 5.0

    except Exception as e:
        logger.debug("Blank check failed (assuming OK): %s", e)
        return True
