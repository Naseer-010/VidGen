"""
DIME — ManimTemplate Base Class.

All 12 templates inherit from this base class.
Templates produce complete, runnable Manim Scene Python code
from structured parameters — zero LLM involvement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.models import DirectorBlueprint, Scene, TTSResult


class ManimTemplate(ABC):
    """Abstract base class for all Manim animation templates."""

    # Header included in every generated scene file
    HEADER = """from manim import *
import numpy as np

"""

    @abstractmethod
    def can_handle(self, params: dict[str, Any]) -> bool:
        """Return True if this template can handle the given parameters."""
        ...

    @abstractmethod
    def render(
        self,
        scene: Scene,
        blueprint: DirectorBlueprint,
        tts_result: TTSResult,
    ) -> str:
        """Generate complete Manim Scene Python code."""
        ...

    def _class_name(self, scene_id: str) -> str:
        """Convert scene_id to a valid Python class name."""
        parts = scene_id.split("_")
        return "".join(p.capitalize() for p in parts)

    def _build_wait_calls(self, tts_result: TTSResult, num_segments: int) -> list[str]:
        """Build self.wait() calls distributed across the audio duration."""
        if not tts_result.duration_sec or num_segments <= 0:
            return ["self.wait(2)"]

        segment_duration = tts_result.duration_sec / num_segments
        return [f"self.wait({segment_duration:.1f})" for _ in range(num_segments)]

    def _get_bg_color(self, blueprint: DirectorBlueprint) -> str:
        """Get background color from blueprint."""
        return blueprint.background_color or "#1e1e2e"

    def _safe_latex(self, expr: str) -> str:
        """Sanitize LaTeX expression for MathTex."""
        # Escape common issues
        expr = expr.replace("\\\\", "\\")
        return expr
