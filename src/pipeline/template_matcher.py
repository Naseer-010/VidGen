"""
DIME — Phase 3: Template Matcher.

Maps visual_type → pre-built Manim template.
Templates handle ~70% of scenes without any LLM call.
"""

from __future__ import annotations

import logging
from typing import Optional

from src.models import DirectorBlueprint, Scene, TTSResult, VisualType

logger = logging.getLogger(__name__)

# ── Template registry (populated at import time) ─────────────
_TEMPLATE_REGISTRY: dict[VisualType, type] = {}


def register_template(visual_type: VisualType):
    """Decorator to register a template class for a visual type."""

    def wrapper(cls):
        _TEMPLATE_REGISTRY[visual_type] = cls
        return cls

    return wrapper


def match_template(
    scene: Scene,
    blueprint: DirectorBlueprint,
    tts_result: TTSResult,
) -> Optional[str]:
    """
    Try to match a scene to a pre-built template.

    Returns:
        Manim Python code string if template matches, None otherwise.
    """
    template_cls = _TEMPLATE_REGISTRY.get(scene.visual_type)

    if template_cls is None:
        logger.info("No template for visual_type=%s", scene.visual_type.value)
        return None

    template = template_cls()

    if not template.can_handle(scene.visual_params):
        logger.info(
            "Template %s cannot handle params for %s",
            template_cls.__name__,
            scene.scene_id,
        )
        return None

    try:
        code = template.render(
            scene=scene,
            blueprint=blueprint,
            tts_result=tts_result,
        )
        logger.info(
            "✅ Template HIT: %s → %s (%d chars)",
            scene.scene_id,
            template_cls.__name__,
            len(code),
        )
        return code
    except Exception as e:
        logger.warning(
            "Template %s render failed for %s: %s",
            template_cls.__name__,
            scene.scene_id,
            e,
        )
        return None


def get_registered_templates() -> dict[str, str]:
    """Return a dict of visual_type → template class name."""
    return {vt.value: cls.__name__ for vt, cls in _TEMPLATE_REGISTRY.items()}


# ── Import all template modules to trigger registration ──────
def _register_all():
    """Import all template modules."""
    from src.templates import (  # noqa: F401
        equation_transform,
        axes_plot,
        free_body,
        projectile,
        circuit,
        ray_diagram,
        reaction_mechanism,
        orbital_diagram,
        number_line,
        geometry_construction,
        integration_area,
        text_reveal,
    )


# Auto-register on import
_register_all()
