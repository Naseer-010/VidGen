"""
DIME Template — Ray Diagram.
Lens or mirror with incident and refracted/reflected rays.
"""

from __future__ import annotations
from typing import Any

from src.models import DirectorBlueprint, Scene, TTSResult, VisualType
from src.pipeline.template_matcher import register_template
from src.templates.base import ManimTemplate


@register_template(VisualType.RAY_DIAGRAM)
class RayDiagramTemplate(ManimTemplate):
    def can_handle(self, params: dict[str, Any]) -> bool:
        return "element" in params and "focal_length" in params

    def render(
        self, scene: Scene, blueprint: DirectorBlueprint, tts_result: TTSResult
    ) -> str:
        p = scene.visual_params
        element = p.get("element", "convex_lens")
        f = p.get("focal_length", 2)
        u = p.get("object_distance", 4)
        bg = self._get_bg_color(blueprint)
        cls = self._class_name(scene.scene_id)
        waits = self._build_wait_calls(tts_result, 4)

        is_lens = "lens" in element
        is_convex = "convex" in element

        code = self.HEADER
        code += f'''class {cls}(Scene):
    def construct(self):
        self.camera.background_color = "{bg}"

        f = {f}  # focal length
        u = {u}  # object distance

        # Mirror formula: 1/v = 1/f - 1/u (lens) or 1/v + 1/u = 1/f (mirror)
'''
        if is_lens:
            code += """        v = (f * u) / (u - f) if u != f else float('inf')
"""
        else:
            code += """        v = (f * u) / (u - f) if u != f else float('inf')
"""

        code += f"""        magnification = -v / u if u != 0 else 0

        # Scale for screen
        scale = 1.0

        # Principal axis
        axis = Line(LEFT * 6, RIGHT * 6, color=GREY, stroke_width=1)
        self.play(Create(axis))
        {waits[0]}

        # Optical element
"""
        if is_lens:
            code += f'''        lens = DoubleArrow(UP * 2.5, DOWN * 2.5, color=BLUE, buff=0, stroke_width=3)
        lens.move_to(ORIGIN)
        lens_label = Tex("{"Convex" if is_convex else "Concave"} Lens").scale(0.5).next_to(lens, UP, buff=0.3)
'''
        else:
            code += f'''        mirror_arc = Arc(radius=6, angle=PI/3, color=BLUE, stroke_width=3)
        mirror_arc.move_to(ORIGIN)
        mirror_arc.rotate({"PI/2" if is_convex else "-PI/2"})
        lens = mirror_arc
        lens_label = Tex("{"Convex" if is_convex else "Concave"} Mirror").scale(0.5).next_to(lens, UP, buff=0.3)
'''

        code += f"""
        self.play(Create(lens), Write(lens_label))

        # Focal points
        f_left = Dot(LEFT * f, color=YELLOW)
        f_right = Dot(RIGHT * f, color=YELLOW)
        f_label_l = MathTex("F").scale(0.5).next_to(f_left, DOWN)
        f_label_r = MathTex("F'").scale(0.5).next_to(f_right, DOWN)
        self.play(Create(f_left), Create(f_right), Write(f_label_l), Write(f_label_r))
        {waits[1]}

        # Object (arrow on left)
        obj_height = 1.0
        obj_arrow = Arrow(
            start=LEFT * u + DOWN * 0,
            end=LEFT * u + UP * obj_height,
            color=GREEN, buff=0, stroke_width=4,
        )
        obj_label = Tex("Object").scale(0.4).next_to(obj_arrow, UP, buff=0.1)
        self.play(Create(obj_arrow), Write(obj_label))
        {waits[2]}

        # Rays
        # Ray 1: Parallel to axis, then through F'
        ray1_in = Line(LEFT * u + UP * obj_height, UP * obj_height, color=YELLOW, stroke_width=2)
        img_height = obj_height * magnification if abs(magnification) < 5 else obj_height
        v_clamped = min(max(v, -5), 5) if abs(v) < float('inf') else 5

        ray1_out = Line(UP * obj_height, RIGHT * v_clamped + UP * img_height, color=YELLOW, stroke_width=2)

        # Ray 2: Through center
        ray2 = Line(LEFT * u + UP * obj_height, RIGHT * v_clamped + UP * img_height, color=RED, stroke_width=2)

        self.play(Create(ray1_in), run_time=0.5)
        self.play(Create(ray1_out), Create(ray2), run_time=1)

        # Image (if real)
        if abs(v_clamped) < 6:
            img_arrow = Arrow(
                start=RIGHT * v_clamped,
                end=RIGHT * v_clamped + UP * img_height,
                color=ORANGE, buff=0, stroke_width=4,
            )
            img_label = Tex("Image").scale(0.4).next_to(img_arrow, DOWN, buff=0.1)
            self.play(Create(img_arrow), Write(img_label))
        {waits[3]}

        # Formula
        formula = MathTex(r"\\frac{{1}}{{v}} - \\frac{{1}}{{u}} = \\frac{{1}}{{f}}").scale(0.7)
        formula.to_corner(DR).set_color(GOLD)
        self.play(Write(formula))

        self.wait(2)
"""
        return code
