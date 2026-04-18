"""
DIME Template — Projectile Motion.
Parabolic arc with velocity component animation.
"""

from __future__ import annotations
from typing import Any

from src.models import DirectorBlueprint, Scene, TTSResult, VisualType
from src.pipeline.template_matcher import register_template
from src.templates.base import ManimTemplate


@register_template(VisualType.PROJECTILE)
class ProjectileTemplate(ManimTemplate):
    def can_handle(self, params: dict[str, Any]) -> bool:
        return all(k in params for k in ["u", "theta", "g"])

    def render(
        self, scene: Scene, blueprint: DirectorBlueprint, tts_result: TTSResult
    ) -> str:
        p = scene.visual_params
        u = p["u"]
        theta = p["theta"]
        g = p["g"]
        show_components = p.get("show_components", True)
        bg = self._get_bg_color(blueprint)
        cls = self._class_name(scene.scene_id)
        waits = self._build_wait_calls(tts_result, 4)

        code = self.HEADER
        code += f'''class {cls}(Scene):
    def construct(self):
        self.camera.background_color = "{bg}"

        u = {u}  # initial velocity (m/s)
        theta = {theta}  # launch angle (degrees)
        g = {g}  # gravity (m/s^2)
        theta_rad = theta * np.pi / 180

        # Calculate trajectory parameters
        ux = u * np.cos(theta_rad)
        uy = u * np.sin(theta_rad)
        t_flight = 2 * uy / g
        x_range_val = ux * t_flight
        y_max = uy**2 / (2 * g)

        # Scale to fit screen
        scale_x = 8 / max(x_range_val, 1)
        scale_y = 5 / max(y_max * 1.3, 1)
        scale = min(scale_x, scale_y)

        # Ground line
        ground = Line(LEFT * 5, RIGHT * 5, color=GREY).shift(DOWN * 2.5)
        self.play(Create(ground))

        # Title
        title = MathTex(
            r"u = {u}\\text{{ m/s}},\\quad \\theta = {theta}^\\circ,\\quad g = {g}\\text{{ m/s}}^2"
        ).scale(0.7).to_edge(UP)
        self.play(Write(title))
        {waits[0]}

        # Trajectory path
        def trajectory(t):
            x = ux * t * scale + LEFT * 4.5 + ground.get_start()
            y = (uy * t - 0.5 * g * t**2) * scale
            return np.array([ux * t * scale - 4.5, y - 2.5, 0])

        path = ParametricFunction(
            trajectory,
            t_range=[0, t_flight, 0.01],
            color=YELLOW,
            stroke_width=3,
        )
        self.play(Create(path), run_time=2)
        {waits[1]}
'''
        if show_components:
            code += f"""
        # Velocity components at launch
        origin = np.array([-4.5, -2.5, 0])
        vx_arrow = Arrow(origin, origin + RIGHT * ux * scale * 0.3, color=BLUE, buff=0)
        vy_arrow = Arrow(origin, origin + UP * uy * scale * 0.3, color=RED, buff=0)
        v_arrow = Arrow(origin, origin + np.array([ux, uy, 0]) * scale * 0.3, color=GREEN, buff=0)

        vx_label = MathTex(r"u_x = {u}\\cos {theta}^\\circ").scale(0.5).set_color(BLUE)
        vx_label.next_to(vx_arrow, DOWN, buff=0.1)
        vy_label = MathTex(r"u_y = {u}\\sin {theta}^\\circ").scale(0.5).set_color(RED)
        vy_label.next_to(vy_arrow, LEFT, buff=0.1)

        self.play(Create(v_arrow), Create(vx_arrow), Create(vy_arrow))
        self.play(Write(vx_label), Write(vy_label))
        {waits[2]}
"""

        code += f"""
        # Key results
        results = VGroup(
            MathTex(r"R = " + f"{{ux * t_flight:.1f}}" + r"\\text{{ m}}").scale(0.6),
            MathTex(r"H = " + f"{{y_max:.1f}}" + r"\\text{{ m}}").scale(0.6),
            MathTex(r"T = " + f"{{t_flight:.1f}}" + r"\\text{{ s}}").scale(0.6),
        ).arrange(DOWN, aligned_edge=LEFT).to_corner(DR).set_color(GOLD)

        self.play(Write(results))
        {waits[3]}

        self.wait(2)
"""
        return code
