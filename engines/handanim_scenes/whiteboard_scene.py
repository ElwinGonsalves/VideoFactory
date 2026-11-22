"""Default handanim whiteboard: sketches each scene's heading and text in sync with narration."""

from __future__ import annotations

from typing import Any

from handanim import FadeOutAnimation, Scene, SketchAnimation, StrokeStyle, Text

INK = (0.12, 0.16, 0.22)


def build(script: dict[str, Any], timing: dict[str, Any], width: int, height: int) -> Scene:
    scene = Scene(width=width, height=height, fps=30, background_color=(1, 1, 1))
    scale = min(width, height) / 1080
    for spec, t in zip(script.get("scenes", []), timing["scenes"], strict=False):
        visual = spec.get("visual", {})
        lines = [visual.get("heading") or spec.get("narration", ""), visual.get("text", "")]
        dur = max(0.5, t["end"] - t["start"])
        for i, line in enumerate(x for x in lines if x):
            size = int((120 if i == 0 else 72) * scale)
            stroke = StrokeStyle(color=INK, width=(6 if i == 0 else 4) * scale)
            pos = (width * 0.08, height * 0.38 + i * size * 1.6)
            drawable = Text(line, position=pos, font_size=size, stroke_style=stroke)
            scene.add(SketchAnimation(start_time=t["start"] + i * 0.3, duration=min(1.5, dur * 0.5)), drawable)
            scene.add(FadeOutAnimation(start_time=t["end"] - 0.3, duration=0.3), drawable)
    return scene
