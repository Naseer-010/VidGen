"""
DIME Template — Geometry Construction.
Coordinate geometry — circles, parabolas, lines with labels.
"""

from __future__ import annotations
from typing import Any

from src.models import DirectorBlueprint, Scene, TTSResult, VisualType
from src.pipeline.template_matcher import register_template
from src.templates.base import ManimTemplate


@register_template(VisualType.GEOMETRY_CONSTRUCTION)
class GeometryConstructionTemplate(ManimTemplate):
    def can_handle(self, params: dict[str, Any]) -> bool:
        return "shapes" in params or "points" in params

    def render(
        self, scene: Scene, blueprint: DirectorBlueprint, tts_result: TTSResult
    ) -> str:
        p = scene.visual_params
        shapes = p.get("shapes", [])
        points = p.get("points", [])
        bg = self._get_bg_color(blueprint)
        cls = self._class_name(scene.scene_id)
        waits = self._build_wait_calls(tts_result, len(shapes) + len(points) + 1)

        colors_map = {
            "RED": "RED",
            "BLUE": "BLUE",
            "GREEN": "GREEN",
            "YELLOW": "YELLOW",
            "ORANGE": "ORANGE",
            "PURPLE": "PURPLE",
            "TEAL": "TEAL",
            "WHITE": "WHITE",
        }

        code = self.HEADER
        code += f'''class {cls}(Scene):
    def construct(self):
        self.camera.background_color = "{bg}"

        # Coordinate axes
        axes = Axes(
            x_range=[-6, 6, 1],
            y_range=[-4, 4, 1],
            x_length=10,
            y_length=6,
            axis_config={{"include_numbers": True, "font_size": 20}},
        )
        self.play(Create(axes))
        {waits[0]}
'''

        for i, shape in enumerate(shapes):
            shape_type = shape.get("type", "line")
            equation = shape.get("equation", "")
            color = shape.get("color", "BLUE")
            color_val = colors_map.get(color.upper(), "BLUE")

            if shape_type == "circle":
                # Parse circle: x^2 + y^2 = r^2 or (x-h)^2 + (y-k)^2 = r^2
                code += f'''
        # Circle: {equation}
        circle_{i} = Circle(radius=2, color={color_val}, stroke_width=3)
        circle_{i}.move_to(axes.c2p(0, 0))
        circle_label_{i} = MathTex(r"{self._safe_latex(equation)}").scale(0.5).set_color({color_val})
        circle_label_{i}.next_to(circle_{i}, UR, buff=0.2)
        self.play(Create(circle_{i}), Write(circle_label_{i}))
'''
            elif shape_type == "parabola":
                code += f'''
        # Parabola: {equation}
        parabola_{i} = axes.plot(lambda x: x**2, color={color_val}, x_range=[-3, 3])
        parabola_label_{i} = MathTex(r"{self._safe_latex(equation)}").scale(0.5).set_color({color_val})
        parabola_label_{i}.next_to(parabola_{i}, UP, buff=0.2)
        self.play(Create(parabola_{i}), Write(parabola_label_{i}))
'''
            elif shape_type == "ellipse":
                code += f'''
        # Ellipse: {equation}
        ellipse_{i} = Ellipse(width=4, height=2, color={color_val}, stroke_width=3)
        ellipse_{i}.move_to(axes.c2p(0, 0))
        ellipse_label_{i} = MathTex(r"{self._safe_latex(equation)}").scale(0.5).set_color({color_val})
        ellipse_label_{i}.next_to(ellipse_{i}, UR, buff=0.2)
        self.play(Create(ellipse_{i}), Write(ellipse_label_{i}))
'''
            else:  # line
                code += f'''
        # Line: {equation}
        line_{i} = axes.plot(lambda x: x, color={color_val}, x_range=[-5, 5])
        line_label_{i} = MathTex(r"{self._safe_latex(equation)}").scale(0.5).set_color({color_val})
        line_label_{i}.next_to(line_{i}.get_end(), UR, buff=0.2)
        self.play(Create(line_{i}), Write(line_label_{i}))
'''
            code += f"""        {waits[min(i + 1, len(waits) - 1)]}
"""

        for i, point in enumerate(points):
            x = point.get("x", 0)
            y = point.get("y", 0)
            label = point.get("label", f"P{i}")
            code += f'''
        # Point: {label}({x}, {y})
        pt_{i} = Dot(axes.c2p({x}, {y}), color=YELLOW, radius=0.08)
        pt_label_{i} = MathTex(r"{label}({x}, {y})").scale(0.4).next_to(pt_{i}, UR, buff=0.1)
        self.play(Create(pt_{i}), Write(pt_label_{i}))
        {waits[min(len(shapes) + i + 1, len(waits) - 1)]}
'''

        code += """
        self.wait(2)
"""
        return code
