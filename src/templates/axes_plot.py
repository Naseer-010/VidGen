"""
DIME Template — Axes Plot.
Graph on coordinate axes (position-time, velocity-time, energy diagrams).
"""

from __future__ import annotations
from typing import Any

from src.models import DirectorBlueprint, Scene, TTSResult, VisualType
from src.pipeline.template_matcher import register_template
from src.templates.base import ManimTemplate


@register_template(VisualType.AXES_PLOT)
class AxesPlotTemplate(ManimTemplate):
    def can_handle(self, params: dict[str, Any]) -> bool:
        return "functions" in params and "x_range" in params

    def render(
        self, scene: Scene, blueprint: DirectorBlueprint, tts_result: TTSResult
    ) -> str:
        p = scene.visual_params
        x_range = p.get("x_range", [-5, 5])
        y_range = p.get("y_range", [-5, 5])
        x_label = p.get("x_label", "x")
        y_label = p.get("y_label", "y")
        functions = p.get("functions", [])
        bg = self._get_bg_color(blueprint)
        cls = self._class_name(scene.scene_id)
        waits = self._build_wait_calls(tts_result, len(functions) + 1)

        colors = ["BLUE", "RED", "GREEN", "YELLOW", "ORANGE", "PURPLE", "TEAL"]

        code = self.HEADER
        code += f'''class {cls}(Scene):
    def construct(self):
        self.camera.background_color = "{bg}"

        # Create axes
        axes = Axes(
            x_range=[{x_range[0]}, {x_range[1]}, 1],
            y_range=[{y_range[0]}, {y_range[1]}, 1],
            x_length=10,
            y_length=6,
            axis_config={{"include_numbers": True, "font_size": 24}},
        )
        labels = axes.get_axis_labels(
            x_label=MathTex(r"{x_label}"),
            y_label=MathTex(r"{y_label}"),
        )

        self.play(Create(axes), Write(labels))
        {waits[0]}
'''

        for i, func in enumerate(functions):
            expr = func.get("expr", "x")
            color = func.get("color", colors[i % len(colors)])
            label = func.get("label", "")
            code += f'''
        # Function {i + 1}: {expr}
        graph_{i} = axes.plot(lambda x: {expr}, color={color}, x_range=[{x_range[0]}, {x_range[1]}])
        graph_{i}_label = axes.get_graph_label(graph_{i}, label=MathTex(r"{label or expr}"), x_val={x_range[1] * 0.7}, direction=UP)
        self.play(Create(graph_{i}), Write(graph_{i}_label))
        {waits[min(i + 1, len(waits) - 1)]}
'''

        code += """
        self.wait(2)
"""
        return code
