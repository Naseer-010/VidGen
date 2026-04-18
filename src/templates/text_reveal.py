"""
DIME Template — Text Reveal.
Simple step-by-step text appearing — for derivation steps.
"""

from __future__ import annotations
from typing import Any

from src.models import DirectorBlueprint, Scene, TTSResult, VisualType
from src.pipeline.template_matcher import register_template
from src.templates.base import ManimTemplate


@register_template(VisualType.TEXT_REVEAL)
class TextRevealTemplate(ManimTemplate):
    def can_handle(self, params: dict[str, Any]) -> bool:
        return "steps" in params

    def render(
        self, scene: Scene, blueprint: DirectorBlueprint, tts_result: TTSResult
    ) -> str:
        p = scene.visual_params
        steps = p.get("steps", [])
        highlight_color = p.get("highlight_color", "YELLOW")
        bg = self._get_bg_color(blueprint)
        cls = self._class_name(scene.scene_id)
        waits = self._build_wait_calls(tts_result, len(steps) + 1)

        code = self.HEADER
        code += f'''class {cls}(Scene):
    def construct(self):
        self.camera.background_color = "{bg}"

        steps_group = VGroup()
'''
        for i, step in enumerate(steps):
            # Determine if step looks like math (contains =, x, ^, etc.)
            is_math = any(c in step for c in "=^_{}\\")

            if is_math:
                code += f'''
        # Step {i + 1} (math)
        step_{i} = MathTex(r"{self._safe_latex(step)}").scale(0.7)
'''
            else:
                code += f'''
        # Step {i + 1} (text)
        step_{i} = Tex(r"{step}").scale(0.7)
'''
            code += f"""        steps_group.add(step_{i})
"""

        code += f"""
        # Arrange all steps vertically
        steps_group.arrange(DOWN, aligned_edge=LEFT, buff=0.4)
        steps_group.move_to(ORIGIN)

        # Ensure everything fits on screen
        if steps_group.height > 6:
            steps_group.scale_to_fit_height(6)

        # Reveal one by one
        for i, step in enumerate(steps_group):
            if i == len(steps_group) - 1:
                step.set_color({highlight_color})
            self.play(Write(step), run_time=0.8)
            {waits[0]}

        # Highlight the final step
        final_box = SurroundingRectangle(steps_group[-1], color=GOLD, buff=0.15)
        self.play(Create(final_box))

        self.wait(2)
"""
        return code
