"""
DIME Template — Number Line.
Points and intervals for inequalities.
"""

from __future__ import annotations
from typing import Any

from src.models import DirectorBlueprint, Scene, TTSResult, VisualType
from src.pipeline.template_matcher import register_template
from src.templates.base import ManimTemplate


@register_template(VisualType.NUMBER_LINE)
class NumberLineTemplate(ManimTemplate):
    def can_handle(self, params: dict[str, Any]) -> bool:
        return "range" in params

    def render(
        self, scene: Scene, blueprint: DirectorBlueprint, tts_result: TTSResult
    ) -> str:
        p = scene.visual_params
        nl_range = p.get("range", [-5, 5])
        points = p.get("points", [])
        intervals = p.get("intervals", [])
        bg = self._get_bg_color(blueprint)
        cls = self._class_name(scene.scene_id)
        waits = self._build_wait_calls(tts_result, len(points) + len(intervals) + 1)

        code = self.HEADER
        code += f'''class {cls}(Scene):
    def construct(self):
        self.camera.background_color = "{bg}"

        # Number line
        nl = NumberLine(
            x_range=[{nl_range[0]}, {nl_range[1]}, 1],
            length=10,
            include_numbers=True,
            font_size=24,
            color=WHITE,
        )
        self.play(Create(nl))
        {waits[0]}
'''

        for i, point in enumerate(points):
            val = point.get("value", 0)
            label = point.get("label", str(val))
            code += f'''
        # Point: {label} at {val}
        dot_{i} = Dot(nl.n2p({val}), color=YELLOW, radius=0.12)
        dot_label_{i} = MathTex(r"{label}").scale(0.6).next_to(dot_{i}, UP, buff=0.2)
        self.play(Create(dot_{i}), Write(dot_label_{i}))
        {waits[min(i + 1, len(waits) - 1)]}
'''

        for i, interval in enumerate(intervals):
            start = interval.get("start", 0)
            end = interval.get("end", 1)
            int_type = interval.get("type", "closed")
            color = "GREEN" if int_type == "closed" else "BLUE"

            code += f"""
        # Interval: [{start}, {end}] ({int_type})
        line_{i} = Line(nl.n2p({start}), nl.n2p({end}), color={color}, stroke_width=6)
        self.play(Create(line_{i}))
"""
            if int_type == "closed":
                code += f"""        end_dot_l_{i} = Dot(nl.n2p({start}), color={color}, radius=0.1)
        end_dot_r_{i} = Dot(nl.n2p({end}), color={color}, radius=0.1)
        self.play(Create(end_dot_l_{i}), Create(end_dot_r_{i}))
"""
            else:
                code += f"""        end_dot_l_{i} = Circle(radius=0.1, color={color}).move_to(nl.n2p({start}))
        end_dot_r_{i} = Circle(radius=0.1, color={color}).move_to(nl.n2p({end}))
        self.play(Create(end_dot_l_{i}), Create(end_dot_r_{i}))
"""
            code += f"""        {waits[min(len(points) + i + 1, len(waits) - 1)]}
"""

        code += """
        self.wait(2)
"""
        return code
