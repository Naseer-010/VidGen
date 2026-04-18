"""
DIME Template — Equation Transform.
Shows one equation morphing into another using TransformMatchingTex.
"""

from __future__ import annotations
from typing import Any

from src.models import DirectorBlueprint, Scene, TTSResult, VisualType
from src.pipeline.template_matcher import register_template
from src.templates.base import ManimTemplate


@register_template(VisualType.EQUATION_TRANSFORM)
class EquationTransformTemplate(ManimTemplate):
    def can_handle(self, params: dict[str, Any]) -> bool:
        return "from_expr" in params and "to_expr" in params

    def render(
        self, scene: Scene, blueprint: DirectorBlueprint, tts_result: TTSResult
    ) -> str:
        p = scene.visual_params
        from_expr = self._safe_latex(p["from_expr"])
        to_expr = self._safe_latex(p["to_expr"])
        steps = p.get("intermediate_steps", [])
        bg = self._get_bg_color(blueprint)
        cls = self._class_name(scene.scene_id)
        waits = self._build_wait_calls(tts_result, len(steps) + 2)

        code = self.HEADER
        code += f'''class {cls}(Scene):
    def construct(self):
        self.camera.background_color = "{bg}"

        # Initial equation
        eq1 = MathTex(r"{from_expr}").scale(1.2)
        eq1.move_to(ORIGIN)
        self.play(Write(eq1))
        {waits[0]}
'''
        # Intermediate steps
        for i, step in enumerate(steps):
            step_safe = self._safe_latex(step)
            code += f'''
        # Step {i + 1}
        eq_step_{i} = MathTex(r"{step_safe}").scale(1.2)
        eq_step_{i}.move_to(ORIGIN)
        self.play(TransformMatchingTex({"eq1" if i == 0 else f"eq_step_{i - 1}"}, eq_step_{i}))
        {waits[min(i + 1, len(waits) - 1)]}
'''

        prev = f"eq_step_{len(steps) - 1}" if steps else "eq1"
        code += f'''
        # Final equation
        eq_final = MathTex(r"{to_expr}").scale(1.2).set_color(YELLOW)
        eq_final.move_to(ORIGIN)
        self.play(TransformMatchingTex({prev}, eq_final))
        {waits[-1]}

        # Highlight final result
        box = SurroundingRectangle(eq_final, color=GOLD, buff=0.2)
        self.play(Create(box))
        self.wait(2)
'''
        return code
