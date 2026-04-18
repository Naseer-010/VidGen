"""
DIME — Phase 2B: Director (Layout Coordinator).

Uses the same Qwen2.5-VL-7B model (via vLLM prefix caching) to
convert abstract scene descriptions into concrete Manim coordinates.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from src.backend import get_brain_client
from src.config import settings
from src.models import BrainOutput, DirectorBlueprint, ObjectPlacement, Scene

logger = logging.getLogger(__name__)

DIRECTOR_SYSTEM_PROMPT = """You are a Manim animation layout director. Given a scene description for a JEE educational video, output precise Manim positioning coordinates.

Your job is to decide WHERE each visual element should appear on screen, what COLOR it should be, and how LARGE.

Manim coordinate system:
- Screen is roughly -7 to +7 horizontally, -4 to +4 vertically
- CENTER = ORIGIN = (0, 0, 0)
- UP, DOWN, LEFT, RIGHT are unit vectors
- Combine like: UP*2 + LEFT*3

OUTPUT FORMAT: Respond with ONLY a valid JSON object:
{
  "scene_id": "<same as input>",
  "placements": [
    {
      "object_id": "<descriptive name>",
      "position": "UP*2 + LEFT*3",
      "color": "BLUE",
      "scale": 1.0
    }
  ],
  "camera_frame_width": 14.0,
  "background_color": "#1e1e2e"
}

Common Manim colors: WHITE, YELLOW, BLUE, GREEN, RED, ORANGE, PURPLE, TEAL, GOLD, PINK

Layout rules:
1. Title/equations go at UP*3 or UP*2.5
2. Main diagram goes at CENTER or slightly DOWN
3. Labels go near their parent objects
4. Keep 1.0 unit minimum spacing between elements
5. Never place text below DOWN*3.5 (gets cut off)
6. Use scale 0.7-0.9 for secondary text, 1.0-1.2 for primary
"""


async def run_director(
    brain_output: BrainOutput,
    max_retries: int = 2,
) -> list[DirectorBlueprint]:
    """
    Generate layout blueprints for all scenes.

    Uses the same vLLM model as Brain (prefix caching benefit).
    """
    client = get_brain_client()
    blueprints = []

    for scene in brain_output.scenes:
        try:
            blueprint = await _direct_single_scene(client, scene)
            blueprints.append(blueprint)
            logger.info(
                "Director: %s → %d placements",
                scene.scene_id,
                len(blueprint.placements),
            )
        except Exception as e:
            logger.warning(
                "Director failed for %s, using defaults: %s",
                scene.scene_id,
                e,
            )
            blueprints.append(_default_blueprint(scene))

    return blueprints


async def _direct_single_scene(client, scene: Scene) -> DirectorBlueprint:
    """Generate layout for a single scene."""
    scene_desc = json.dumps(
        {
            "scene_id": scene.scene_id,
            "visual_type": scene.visual_type.value,
            "visual_params": scene.visual_params,
            "narration": scene.narration,
            "duration": scene.duration_estimate_sec,
        }
    )

    messages = [
        {"role": "system", "content": DIRECTOR_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Create the layout blueprint for this scene:\n{scene_desc}",
        },
    ]

    response = await client.chat.completions.create(
        model=settings.brain_model_name,
        messages=messages,
        temperature=0.2,
        max_tokens=1024,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content.strip()
    data = json.loads(raw)
    return DirectorBlueprint.model_validate(data)


def _default_blueprint(scene: Scene) -> DirectorBlueprint:
    """Generate a sensible default layout when Director fails."""
    placements = [
        ObjectPlacement(
            object_id="title",
            position="UP*3",
            color="WHITE",
            scale=0.8,
        ),
        ObjectPlacement(
            object_id="main_content",
            position="ORIGIN",
            color="YELLOW",
            scale=1.0,
        ),
    ]

    return DirectorBlueprint(
        scene_id=scene.scene_id,
        placements=placements,
        camera_frame_width=14.0,
        background_color="#1e1e2e",
    )
