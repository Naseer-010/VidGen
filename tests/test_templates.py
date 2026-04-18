"""
DIME — Template Render Tests.

Verifies that each of the 12 templates can:
1. Instantiate with sample JEE parameters
2. Produce syntactically valid Python code (ast.parse)
3. Contain essential Manim imports and class structure
"""

import ast
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import (
    DirectorBlueprint,
    ObjectPlacement,
    Scene,
    TTSResult,
    VisualType,
    WordTimestamp,
)


# ── Helper factories ─────────────────────────────────────────


def make_scene(visual_type: VisualType, params: dict) -> Scene:
    return Scene(
        scene_id="scene_01",
        duration_estimate_sec=8.0,
        narration="This is a test narration for the scene animation.",
        visual_type=visual_type,
        visual_params=params,
    )


def make_blueprint() -> DirectorBlueprint:
    return DirectorBlueprint(
        scene_id="scene_01",
        placements=[
            ObjectPlacement(
                object_id="main", position="ORIGIN", color="WHITE", scale=1.0
            ),
        ],
        background_color="#1e1e2e",
    )


def make_tts() -> TTSResult:
    return TTSResult(
        scene_id="scene_01",
        audio_path="/tmp/test.wav",
        duration_sec=8.0,
        word_timestamps=[
            WordTimestamp(word="Hello", start=0.0, end=0.5),
            WordTimestamp(word="World", start=0.5, end=1.0),
        ],
    )


def validate_manim_code(code: str) -> None:
    """Validate that code is syntactically valid Python with Manim structure."""
    # Must parse as valid Python
    ast.parse(code)

    # Must contain essential elements
    assert "from manim import" in code, "Missing manim import"
    assert "class " in code, "Missing class definition"
    assert "def construct" in code, "Missing construct method"
    assert "(Scene)" in code, "Must inherit from Scene"


# ═════════════════════════════════════════════════════════════
# Template Tests
# ═════════════════════════════════════════════════════════════


class TestEquationTransform:
    def test_basic(self):
        from src.templates.equation_transform import EquationTransformTemplate

        t = EquationTransformTemplate()
        assert t.can_handle({"from_expr": "x^2", "to_expr": "2x"})
        code = t.render(
            make_scene(
                VisualType.EQUATION_TRANSFORM,
                {
                    "from_expr": "x^2",
                    "to_expr": "2x",
                    "intermediate_steps": ["x \\cdot x"],
                },
            ),
            make_blueprint(),
            make_tts(),
        )
        validate_manim_code(code)


class TestAxesPlot:
    def test_basic(self):
        from src.templates.axes_plot import AxesPlotTemplate

        t = AxesPlotTemplate()
        params = {
            "functions": [{"expr": "x**2", "color": "BLUE"}],
            "x_range": [-5, 5],
            "y_range": [0, 25],
        }
        assert t.can_handle(params)
        code = t.render(
            make_scene(VisualType.AXES_PLOT, params), make_blueprint(), make_tts()
        )
        validate_manim_code(code)


class TestFreeBody:
    def test_basic(self):
        from src.templates.free_body import FreeBodyTemplate

        t = FreeBodyTemplate()
        params = {
            "forces": [{"name": "F", "magnitude": 10, "angle": 45, "color": "YELLOW"}]
        }
        assert t.can_handle(params)
        code = t.render(
            make_scene(VisualType.FREE_BODY, params), make_blueprint(), make_tts()
        )
        validate_manim_code(code)


class TestProjectile:
    def test_basic(self):
        from src.templates.projectile import ProjectileTemplate

        t = ProjectileTemplate()
        params = {"u": 20, "theta": 60, "g": 10, "show_components": True}
        assert t.can_handle(params)
        code = t.render(
            make_scene(VisualType.PROJECTILE, params), make_blueprint(), make_tts()
        )
        validate_manim_code(code)


class TestCircuit:
    def test_basic(self):
        from src.templates.circuit import CircuitTemplate

        t = CircuitTemplate()
        params = {"components": [{"type": "resistor", "value": "10Ω", "label": "R1"}]}
        assert t.can_handle(params)
        code = t.render(
            make_scene(VisualType.CIRCUIT, params), make_blueprint(), make_tts()
        )
        validate_manim_code(code)


class TestRayDiagram:
    def test_basic(self):
        from src.templates.ray_diagram import RayDiagramTemplate

        t = RayDiagramTemplate()
        params = {"element": "convex_lens", "focal_length": 2, "object_distance": 4}
        assert t.can_handle(params)
        code = t.render(
            make_scene(VisualType.RAY_DIAGRAM, params), make_blueprint(), make_tts()
        )
        validate_manim_code(code)


class TestReactionMechanism:
    def test_basic(self):
        from src.templates.reaction_mechanism import ReactionMechanismTemplate

        t = ReactionMechanismTemplate()
        params = {
            "reactants": ["H_2", "O_2"],
            "products": ["H_2O"],
            "mechanism_steps": ["Bond breaking"],
        }
        assert t.can_handle(params)
        code = t.render(
            make_scene(VisualType.REACTION_MECHANISM, params),
            make_blueprint(),
            make_tts(),
        )
        validate_manim_code(code)


class TestOrbitalDiagram:
    def test_basic(self):
        from src.templates.orbital_diagram import OrbitalDiagramTemplate

        t = OrbitalDiagramTemplate()
        params = {"element": "Carbon", "electrons": 6, "show_hybridization": True}
        assert t.can_handle(params)
        code = t.render(
            make_scene(VisualType.ORBITAL_DIAGRAM, params), make_blueprint(), make_tts()
        )
        validate_manim_code(code)


class TestNumberLine:
    def test_basic(self):
        from src.templates.number_line import NumberLineTemplate

        t = NumberLineTemplate()
        params = {
            "range": [-5, 5],
            "points": [{"value": 2, "label": "a"}],
            "intervals": [{"start": -1, "end": 3, "type": "closed"}],
        }
        assert t.can_handle(params)
        code = t.render(
            make_scene(VisualType.NUMBER_LINE, params), make_blueprint(), make_tts()
        )
        validate_manim_code(code)


class TestGeometryConstruction:
    def test_basic(self):
        from src.templates.geometry_construction import GeometryConstructionTemplate

        t = GeometryConstructionTemplate()
        params = {
            "shapes": [{"type": "circle", "equation": "x^2+y^2=4", "color": "BLUE"}],
            "points": [{"x": 1, "y": 1, "label": "P"}],
        }
        assert t.can_handle(params)
        code = t.render(
            make_scene(VisualType.GEOMETRY_CONSTRUCTION, params),
            make_blueprint(),
            make_tts(),
        )
        validate_manim_code(code)


class TestIntegrationArea:
    def test_basic(self):
        from src.templates.integration_area import IntegrationAreaTemplate

        t = IntegrationAreaTemplate()
        params = {"functions": [{"expr": "x**2"}], "x_range": [0, 2]}
        assert t.can_handle(params)
        code = t.render(
            make_scene(VisualType.INTEGRATION_AREA, params),
            make_blueprint(),
            make_tts(),
        )
        validate_manim_code(code)


class TestTextReveal:
    def test_basic(self):
        from src.templates.text_reveal import TextRevealTemplate

        t = TextRevealTemplate()
        params = {
            "steps": [
                "Step 1: Given data",
                "Step 2: Apply formula",
                "Step 3: Calculate",
            ]
        }
        assert t.can_handle(params)
        code = t.render(
            make_scene(VisualType.TEXT_REVEAL, params), make_blueprint(), make_tts()
        )
        validate_manim_code(code)
