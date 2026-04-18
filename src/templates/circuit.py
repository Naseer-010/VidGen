"""
DIME Template — Circuit Diagram.
Resistor/capacitor/inductor circuit with current flow animation.
"""

from __future__ import annotations
from typing import Any

from src.models import DirectorBlueprint, Scene, TTSResult, VisualType
from src.pipeline.template_matcher import register_template
from src.templates.base import ManimTemplate


@register_template(VisualType.CIRCUIT)
class CircuitTemplate(ManimTemplate):
    def can_handle(self, params: dict[str, Any]) -> bool:
        return "components" in params

    def render(
        self, scene: Scene, blueprint: DirectorBlueprint, tts_result: TTSResult
    ) -> str:
        p = scene.visual_params
        components = p.get("components", [])
        bg = self._get_bg_color(blueprint)
        cls = self._class_name(scene.scene_id)
        waits = self._build_wait_calls(tts_result, len(components) + 2)

        code = self.HEADER
        code += f'''class {cls}(Scene):
    def construct(self):
        self.camera.background_color = "{bg}"

        title = Tex("Circuit Diagram").scale(0.8).to_edge(UP).set_color(GOLD)
        self.play(Write(title))
        {waits[0]}

        # Build circuit as connected segments
        circuit_group = VGroup()
        labels_group = VGroup()

        # Circuit path: rectangular loop
        corners = [
            np.array([-3, 1.5, 0]),
            np.array([3, 1.5, 0]),
            np.array([3, -1.5, 0]),
            np.array([-3, -1.5, 0]),
        ]
'''
        # Place components along circuit edges
        for i, comp in enumerate(components):
            comp_type = comp.get("type", "resistor")
            value = comp.get("value", "")
            label = comp.get("label", f"C{i}")
            edge = i % 4  # Distribute along 4 edges

            if comp_type == "battery":
                code += f'''
        # Battery: {label}
        batt_line_long = Line(UP * 0.4, DOWN * 0.4, color=RED).move_to(
            (corners[{edge}] + corners[{(edge + 1) % 4}]) / 2
        )
        batt_line_short = Line(UP * 0.25, DOWN * 0.25, color=BLUE).next_to(batt_line_long, RIGHT, buff=0.15)
        batt_label = MathTex(r"{label} = {value}").scale(0.5)
        batt_label.next_to(batt_line_long, UP, buff=0.3)
        circuit_group.add(batt_line_long, batt_line_short)
        labels_group.add(batt_label)
'''
            elif comp_type == "capacitor":
                code += f'''
        # Capacitor: {label}
        cap_left = Line(UP * 0.4, DOWN * 0.4, color=TEAL).move_to(
            (corners[{edge}] + corners[{(edge + 1) % 4}]) / 2 + LEFT * 0.1
        )
        cap_right = Line(UP * 0.4, DOWN * 0.4, color=TEAL).move_to(
            (corners[{edge}] + corners[{(edge + 1) % 4}]) / 2 + RIGHT * 0.1
        )
        cap_label = MathTex(r"{label} = {value}").scale(0.5)
        cap_label.next_to(cap_left, UP, buff=0.3)
        circuit_group.add(cap_left, cap_right)
        labels_group.add(cap_label)
'''
            else:  # resistor (default)
                code += f'''
        # Resistor: {label}
        zigzag_points = []
        mid_{i} = (corners[{edge}] + corners[{(edge + 1) % 4}]) / 2
        for j in range(7):
            offset = UP * 0.2 * ((-1) ** j)
            zigzag_points.append(mid_{i} + LEFT * 0.6 + RIGHT * 0.2 * j + offset)
        resistor_{i} = VMobject(color=ORANGE)
        resistor_{i}.set_points_as_corners(zigzag_points)
        res_label_{i} = MathTex(r"{label} = {value}").scale(0.5)
        res_label_{i}.next_to(resistor_{i}, UP, buff=0.3)
        circuit_group.add(resistor_{i})
        labels_group.add(res_label_{i})
'''

        code += f"""
        # Wire connections
        for i in range(4):
            wire = Line(corners[i], corners[(i + 1) % 4], color=GREY_B, stroke_width=2)
            circuit_group.add(wire)

        self.play(Create(circuit_group), run_time=2)
        {waits[1]}
        self.play(Write(labels_group))
        {waits[min(2, len(waits) - 1)]}

        # Current flow indicator
        current_arrow = Arrow(LEFT * 0.5, RIGHT * 0.5, color=YELLOW, stroke_width=3)
        current_arrow.move_to(corners[0] + RIGHT * 1)
        current_label = MathTex(r"I").scale(0.6).set_color(YELLOW)
        current_label.next_to(current_arrow, UP, buff=0.1)
        self.play(Create(current_arrow), Write(current_label))

        self.wait(2)
"""
        return code
