"""
DIME Template — Integration Area.
Shaded area under/between curves for definite integrals.
"""

from __future__ import annotations
from typing import Any

from src.models import DirectorBlueprint, Scene, TTSResult, VisualType
from src.pipeline.template_matcher import register_template
from src.templates.base import ManimTemplate


@register_template(VisualType.INTEGRATION_AREA)
class IntegrationAreaTemplate(ManimTemplate):
    def can_handle(self, params: dict[str, Any]) -> bool:
        return "functions" in params and "x_range" in params

    def render(
        self, scene: Scene, blueprint: DirectorBlueprint, tts_result: TTSResult
    ) -> str:
        p = scene.visual_params
        functions = p.get("functions", [{"expr": "x**2"}])
        x_range = p.get("x_range", [0, 2])
        shade_between = p.get("shade_between", False)
        bg = self._get_bg_color(blueprint)
        cls = self._class_name(scene.scene_id)
        waits = self._build_wait_calls(tts_result, 4)

        code = self.HEADER
        code += f'''class {cls}(Scene):
    def construct(self):
        self.camera.background_color = "{bg}"

        # Axes
        axes = Axes(
            x_range=[-1, {max(x_range[1] + 1, 5)}, 1],
            y_range=[-1, 6, 1],
            x_length=8,
            y_length=5,
            axis_config={{"include_numbers": True, "font_size": 20}},
        ).shift(DOWN * 0.3)
        labels = axes.get_axis_labels(x_label="x", y_label="y")
        self.play(Create(axes), Write(labels))
        {waits[0]}
'''

        colors = ["BLUE", "RED", "GREEN", "ORANGE"]
        for i, func in enumerate(functions):
            expr = func.get("expr", "x**2")
            color = colors[i % len(colors)]
            code += f"""
        # Function {i + 1}
        func_{i} = axes.plot(lambda x: {expr}, color={color}, x_range=[-1, {x_range[1] + 1}])
        func_label_{i} = MathTex(r"f(x) = {expr}").scale(0.5).set_color({color})
        func_label_{i}.to_corner(UR).shift(DOWN * {i * 0.5})
        self.play(Create(func_{i}), Write(func_label_{i}))
"""

        code += f"""        {waits[1]}

        # Shaded area
"""
        if shade_between and len(functions) >= 2:
            code += f"""        area = axes.get_area(
            func_0,
            bounded_graph=func_1,
            x_range=[{x_range[0]}, {x_range[1]}],
            color=[BLUE, GREEN],
            opacity=0.4,
        )
"""
        else:
            code += f"""        area = axes.get_area(
            func_0,
            x_range=[{x_range[0]}, {x_range[1]}],
            color=[BLUE, PURPLE],
            opacity=0.4,
        )
"""

        code += f"""        self.play(FadeIn(area), run_time=1.5)
        {waits[2]}

        # Bounds markers
        x_min_line = axes.get_vertical_line(axes.c2p({x_range[0]}, 0), color=YELLOW, line_config={{"stroke_width": 2}})
        x_max_line = axes.get_vertical_line(axes.c2p({x_range[1]}, 0), color=YELLOW, line_config={{"stroke_width": 2}})
        a_label = MathTex("a = {x_range[0]}").scale(0.5).next_to(x_min_line, DOWN)
        b_label = MathTex("b = {x_range[1]}").scale(0.5).next_to(x_max_line, DOWN)
        self.play(Create(x_min_line), Create(x_max_line), Write(a_label), Write(b_label))

        # Integral notation
        integral = MathTex(
            r"\\int_{{{x_range[0]}}}^{{{x_range[1]}}} f(x) \\, dx"
        ).scale(0.8).set_color(GOLD)
        integral.to_edge(DOWN, buff=0.5)
        self.play(Write(integral))
        {waits[3]}

        self.wait(2)
"""
        return code
