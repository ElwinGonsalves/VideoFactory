"""Example Manim scene used by engines/manim_engine.py. Copy it to start a new one."""

import os

from manim import BLUE, UP, WHITE, Axes, Create, FadeIn, Scene, Text, Write, config

config.background_color = "#0f172a"


class ConceptGraph(Scene):
    def construct(self) -> None:
        total = float(os.environ.get("VF_DURATION", "6"))
        title = Text(os.environ.get("VF_TITLE", "Growth"), color=WHITE).scale(0.9).to_edge(UP)
        axes = Axes(x_range=[0, 10, 2], y_range=[0, 100, 20], x_length=6, y_length=5)
        curve = axes.plot(lambda x: x**2, x_range=[0, 10], color=BLUE)
        self.play(Write(title), run_time=min(1.5, total * 0.2))
        self.play(FadeIn(axes), run_time=min(1.0, total * 0.15))
        self.play(Create(curve), run_time=max(1.0, total * 0.5))
        self.wait(max(0.1, total * 0.15))
