"""
DIME Template — Orbital Diagram.
Atomic orbital filling, hybridization diagrams.
"""

from __future__ import annotations
from typing import Any

from src.models import DirectorBlueprint, Scene, TTSResult, VisualType
from src.pipeline.template_matcher import register_template
from src.templates.base import ManimTemplate


@register_template(VisualType.ORBITAL_DIAGRAM)
class OrbitalDiagramTemplate(ManimTemplate):
    def can_handle(self, params: dict[str, Any]) -> bool:
        return "element" in params and "electrons" in params

    def render(
        self, scene: Scene, blueprint: DirectorBlueprint, tts_result: TTSResult
    ) -> str:
        p = scene.visual_params
        element = p.get("element", "C")
        electrons = p.get("electrons", 6)
        show_hybridization = p.get("show_hybridization", False)
        bg = self._get_bg_color(blueprint)
        cls = self._class_name(scene.scene_id)
        waits = self._build_wait_calls(tts_result, 4)

        code = self.HEADER
        code += f'''class {cls}(Scene):
    def construct(self):
        self.camera.background_color = "{bg}"

        title = MathTex(r"\\text{{{element}}} \\quad (Z = {electrons})").scale(0.9)
        title.to_edge(UP).set_color(GOLD)
        self.play(Write(title))
        {waits[0]}

        # Orbital boxes — filling order: 1s, 2s, 2p, 3s, 3p, ...
        orbitals = [
            ("1s", 2, 1), ("2s", 2, 1), ("2p", 6, 3),
            ("3s", 2, 1), ("3p", 6, 3), ("4s", 2, 1), ("3d", 10, 5),
        ]

        all_orbitals = VGroup()
        labels = VGroup()
        electrons_remaining = {electrons}
        y_pos = 2.0

        for orbital_name, max_e, num_boxes in orbitals:
            if electrons_remaining <= 0:
                break

            row = VGroup()
            row_label = Tex(orbital_name).scale(0.5).set_color(TEAL)

            for b in range(num_boxes):
                box = Square(side_length=0.5, color=WHITE, stroke_width=2)
                box.set_fill(BLACK, opacity=0.3)
                row.add(box)

            row.arrange(RIGHT, buff=0.1)
            row.move_to(RIGHT * 1 + UP * y_pos)
            row_label.next_to(row, LEFT, buff=0.3)

            all_orbitals.add(row)
            labels.add(row_label)

            y_pos -= 0.8

        self.play(Create(all_orbitals), Write(labels), run_time=1.5)
        {waits[1]}

        # Fill electrons (arrows up ↑ and down ↓)
        electrons_remaining = {electrons}
        electron_arrows = VGroup()

        for orbital_group in all_orbitals:
            if electrons_remaining <= 0:
                break
            # First pass: one electron per box (Hund's rule)
            for box in orbital_group:
                if electrons_remaining <= 0:
                    break
                up_arrow = MathTex(r"\\uparrow").scale(0.5).set_color(YELLOW)
                up_arrow.move_to(box.get_center() + LEFT * 0.08)
                electron_arrows.add(up_arrow)
                electrons_remaining -= 1

            # Second pass: pair up
            for box in orbital_group:
                if electrons_remaining <= 0:
                    break
                down_arrow = MathTex(r"\\downarrow").scale(0.5).set_color(ORANGE)
                down_arrow.move_to(box.get_center() + RIGHT * 0.08)
                electron_arrows.add(down_arrow)
                electrons_remaining -= 1

        self.play(Write(electron_arrows), run_time=2)
        {waits[2]}
'''

        if show_hybridization:
            code += f"""
        # Hybridization
        hybrid_text = Tex("Hybridization: sp$^3$").scale(0.7).set_color(PINK)
        hybrid_text.to_edge(DOWN, buff=1)
        self.play(Write(hybrid_text))
        {waits[3]}
"""

        code += f"""
        # Electronic configuration text
        config_text = Tex(r"Electronic Configuration of {element}").scale(0.6)
        config_text.to_edge(DOWN, buff=0.5).set_color(WHITE)
        self.play(Write(config_text))

        self.wait(2)
"""
        return code
