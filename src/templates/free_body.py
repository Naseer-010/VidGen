"""
DIME Template — Free Body Diagram.
Force vectors on an object with labels.
"""

from __future__ import annotations
from typing import Any

from src.models import DirectorBlueprint, Scene, TTSResult, VisualType
from src.pipeline.template_matcher import register_template
from src.templates.base import ManimTemplate


@register_template(VisualType.FREE_BODY)
class FreeBodyTemplate(ManimTemplate):
    def can_handle(self, params: dict[str, Any]) -> bool:
        return "forces" in params

    def render(
        self, scene: Scene, blueprint: DirectorBlueprint, tts_result: TTSResult
    ) -> str:
        p = scene.visual_params
        forces = p.get("forces", [])
        obj_shape = p.get("object_shape", "circle")
        bg = self._get_bg_color(blueprint)
        cls = self._class_name(scene.scene_id)
        waits = self._build_wait_calls(tts_result, len(forces) + 1)

        code = self.HEADER
        code += f'''class {cls}(Scene):
    def construct(self):
        self.camera.background_color = "{bg}"

        # Object
'''
        if obj_shape == "rectangle":
            code += """        obj = Rectangle(width=1.5, height=1.0, color=WHITE, fill_opacity=0.3)
"""
        else:
            code += """        obj = Circle(radius=0.5, color=WHITE, fill_opacity=0.3)
"""

        code += f"""        obj.move_to(ORIGIN)
        obj_label = Tex("Object").scale(0.5).move_to(obj)
        self.play(Create(obj), Write(obj_label))
        {waits[0]}

        # Force vectors
"""
        for i, force in enumerate(forces):
            name = force.get("name", f"F_{i}")
            mag = force.get("magnitude", 1)
            angle = force.get("angle", 0)
            color = force.get("color", "YELLOW")
            # Scale force length relative to magnitude
            length = min(mag / 5, 3)  # Scale and cap

            code += f'''
        # Force: {name}
        angle_{i} = {angle} * DEGREES
        direction_{i} = np.array([np.cos(angle_{i}), np.sin(angle_{i}), 0])
        arrow_{i} = Arrow(
            start=obj.get_center(),
            end=obj.get_center() + direction_{i} * {length:.2f},
            color={color},
            buff=0.5,
            stroke_width=4,
        )
        label_{i} = MathTex(r"{name} = {mag}\\text{{ N}}").scale(0.6).set_color({color})
        label_{i}.next_to(arrow_{i}.get_end(), direction_{i}, buff=0.2)
        self.play(Create(arrow_{i}), Write(label_{i}))
        {waits[min(i + 1, len(waits) - 1)]}
'''

        code += """
        self.wait(2)
"""
        return code
