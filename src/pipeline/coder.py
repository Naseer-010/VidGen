"""
DIME — Phase 4: Coder LLM (Qwen2.5-Coder-7B).

Generates Manim Scene code for scenes that templates cannot handle.
Includes RAG context injection from ChromaDB.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from src.backend import get_coder_client
from src.config import settings
from src.models import DirectorBlueprint, Scene, TTSResult

logger = logging.getLogger(__name__)

CODER_SYSTEM_PROMPT = """You are an expert Manim Community Edition (ManimCE v0.18+) programmer specializing in JEE (Joint Entrance Examination) educational animations.

Given a scene description, director blueprint, and audio timestamps, generate a COMPLETE, RUNNABLE Manim Scene Python file.

CRITICAL RULES:
1. Output ONLY Python code — no markdown fences, no explanations
2. Always start with: from manim import *
3. Create exactly ONE Scene class inheriting from Scene
4. Use self.play() for animations, self.wait() for pauses
5. Match animation timing to audio timestamps using self.wait()
6. Use the colors specified in the director blueprint
7. Place objects at the coordinates from the director blueprint
8. NEVER use deprecated APIs:
   - Use Create() not ShowCreation()
   - Use FadeIn() not FadeInFrom()
   - Use GrowFromPoint() not GrowFromCenter()
9. For LaTeX: use MathTex() for math, Tex() for text
10. End the construct() method with self.wait(2)
11. Set background color in construct(): self.camera.background_color = "#1e1e2e"

IMPORTANT MANIM PATTERNS:
- Transform equations: self.play(TransformMatchingTex(eq1, eq2))
- Fade in: self.play(FadeIn(obj))
- Write text: self.play(Write(text))
- Draw line: self.play(Create(line))
- Move object: self.play(obj.animate.move_to(UP*2))
- Scale: self.play(obj.animate.scale(1.5))
- Color change: self.play(obj.animate.set_color(YELLOW))
- Multiple animations: self.play(FadeIn(a), Write(b))
- Wait for narration: self.wait(3.5)
"""


async def generate_scene_code(
    scene: Scene,
    blueprint: DirectorBlueprint,
    tts_result: TTSResult,
    rag_context: Optional[str] = None,
    error_context: Optional[str] = None,
) -> str:
    """
    Generate Manim Scene code using the Coder LLM.

    Args:
        scene: Scene definition from Brain
        blueprint: Coordinate layout from Director
        tts_result: Audio timestamps from TTS
        rag_context: Retrieved Manim documentation chunks
        error_context: Previous error traceback (for retry)

    Returns:
        Complete Python source code for a Manim Scene
    """
    client = get_coder_client()

    # ── Build the prompt ─────────────────────────────────────
    prompt_parts = []

    # Scene description
    prompt_parts.append(f"SCENE: {scene.scene_id}")
    prompt_parts.append(f"Visual Type: {scene.visual_type.value}")
    prompt_parts.append(f"Narration: {scene.narration}")
    prompt_parts.append(f"Duration: {scene.duration_estimate_sec}s")
    prompt_parts.append(f"Visual Params: {json.dumps(scene.visual_params, indent=2)}")

    # Director blueprint
    prompt_parts.append(f"\nDIRECTOR BLUEPRINT:")
    prompt_parts.append(f"Background: {blueprint.background_color}")
    for p in blueprint.placements:
        prompt_parts.append(
            f"  {p.object_id}: position={p.position}, color={p.color}, scale={p.scale}"
        )

    # Audio timestamps
    if tts_result.word_timestamps:
        prompt_parts.append(f"\nAUDIO TIMESTAMPS (total={tts_result.duration_sec}s):")
        # Show key timestamp markers
        timestamps = tts_result.word_timestamps
        markers = timestamps[:: max(1, len(timestamps) // 8)]  # Show ~8 markers
        for wt in markers:
            prompt_parts.append(f'  [{wt.start:.1f}s] "{wt.word}"')

    # RAG context
    if rag_context:
        prompt_parts.append(f"\nRELEVANT MANIM DOCUMENTATION:\n{rag_context}")

    # Error context (for retry)
    if error_context:
        prompt_parts.append(
            f"\nPREVIOUS ATTEMPT FAILED with this error:\n{error_context}\n"
            f"Fix the error and generate corrected code."
        )

    prompt_parts.append(
        f"\nGenerate a complete, runnable Manim Scene class called '{_scene_class_name(scene.scene_id)}'. "
        f"Output ONLY Python code, no markdown."
    )

    user_prompt = "\n".join(prompt_parts)

    # ── Call vLLM ────────────────────────────────────────────
    response = await client.chat.completions.create(
        model=settings.coder_model_name,
        messages=[
            {"role": "system", "content": CODER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=4096,
    )

    raw_code = response.choices[0].message.content.strip()

    # Clean up — remove markdown fences if present
    code = _clean_code_output(raw_code)

    logger.info(
        "Coder generated %d chars for %s",
        len(code),
        scene.scene_id,
    )

    return code


def _scene_class_name(scene_id: str) -> str:
    """Convert scene_id to a valid Python class name."""
    # scene_01 → Scene01
    parts = scene_id.split("_")
    return "".join(p.capitalize() for p in parts)


def _clean_code_output(code: str) -> str:
    """Remove markdown fences and other non-code artifacts."""
    # Remove ```python ... ``` fences
    if code.startswith("```"):
        lines = code.split("\n")
        # Find opening fence
        start = 0
        for i, line in enumerate(lines):
            if line.strip().startswith("```"):
                start = i + 1
                break
        # Find closing fence
        end = len(lines)
        for i in range(len(lines) - 1, start, -1):
            if lines[i].strip() == "```":
                end = i
                break
        code = "\n".join(lines[start:end])

    # Ensure it starts with 'from manim import'
    if "from manim import" not in code:
        code = "from manim import *\n\n" + code

    return code
