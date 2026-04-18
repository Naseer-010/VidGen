"""
DIME Template — Reaction Mechanism.
Chemical reaction arrow-pushing, electron movement.
"""

from __future__ import annotations
from typing import Any

from src.models import DirectorBlueprint, Scene, TTSResult, VisualType
from src.pipeline.template_matcher import register_template
from src.templates.base import ManimTemplate


@register_template(VisualType.REACTION_MECHANISM)
class ReactionMechanismTemplate(ManimTemplate):
    def can_handle(self, params: dict[str, Any]) -> bool:
        return "reactants" in params and "products" in params

    def render(
        self, scene: Scene, blueprint: DirectorBlueprint, tts_result: TTSResult
    ) -> str:
        p = scene.visual_params
        reactants = p.get("reactants", [])
        products = p.get("products", [])
        steps = p.get("mechanism_steps", [])
        bg = self._get_bg_color(blueprint)
        cls = self._class_name(scene.scene_id)
        waits = self._build_wait_calls(tts_result, len(steps) + 3)

        code = self.HEADER
        code += f'''class {cls}(Scene):
    def construct(self):
        self.camera.background_color = "{bg}"

        title = Tex("Reaction Mechanism").scale(0.8).to_edge(UP).set_color(GOLD)
        self.play(Write(title))
        {waits[0]}

        # Reactants
        reactant_group = VGroup()
'''
        for i, r in enumerate(reactants):
            code += f'''        r_{i} = MathTex(r"{self._safe_latex(str(r))}").scale(0.8).set_color(BLUE)
        reactant_group.add(r_{i})
'''
        code += f"""        reactant_group.arrange(RIGHT, buff=0.3)
        plus_signs_r = VGroup()
        for i in range(len(reactant_group) - 1):
            plus = MathTex("+").scale(0.8)
            plus.move_to((reactant_group[i].get_right() + reactant_group[i+1].get_left()) / 2)
            plus_signs_r.add(plus)

        all_reactants = VGroup(reactant_group, plus_signs_r).move_to(LEFT * 3 + UP * 1)
        self.play(Write(all_reactants))
        {waits[1]}

        # Reaction arrow
        arrow = Arrow(LEFT * 0.8, RIGHT * 0.8, color=YELLOW, stroke_width=3)
        arrow.move_to(UP * 1)
        self.play(Create(arrow))

        # Products
        product_group = VGroup()
"""
        for i, pr in enumerate(products):
            code += f'''        p_{i} = MathTex(r"{self._safe_latex(str(pr))}").scale(0.8).set_color(GREEN)
        product_group.add(p_{i})
'''
        code += f"""        product_group.arrange(RIGHT, buff=0.3)
        plus_signs_p = VGroup()
        for i in range(len(product_group) - 1):
            plus = MathTex("+").scale(0.8)
            plus.move_to((product_group[i].get_right() + product_group[i+1].get_left()) / 2)
            plus_signs_p.add(plus)

        all_products = VGroup(product_group, plus_signs_p).move_to(RIGHT * 3 + UP * 1)
        self.play(Write(all_products))
        {waits[2]}
"""

        # Mechanism steps
        for i, step in enumerate(steps):
            code += f'''
        # Step {i + 1}: {step}
        step_{i} = Tex(r"{step}").scale(0.6).set_color(WHITE)
        step_{i}.move_to(DOWN * (0.5 + {i} * 0.8))
        step_num_{i} = Tex(f"Step {i + 1}:").scale(0.5).set_color(YELLOW)
        step_num_{i}.next_to(step_{i}, LEFT, buff=0.3)
        self.play(Write(step_num_{i}), Write(step_{i}))
        {waits[min(i + 3, len(waits) - 1)]}
'''

        code += """
        self.wait(2)
"""
        return code
