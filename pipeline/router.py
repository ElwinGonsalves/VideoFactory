"""Universal Style Router: maps a requested style to an engine and composition."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Route:
    engine: str  # remotion | explainroo | handanim | manim | clipper | openmontage
    composition: str | None  # Remotion composition id, when engine == "remotion"
    caption_style: str
    theme: str | None = None


ROUTES: dict[str, Route] = {
    "concept_explainer": Route("remotion", "ConceptExplainer", "word_highlight"),
    "case_study": Route("remotion", "ConceptExplainer", "word_highlight"),
    "kinetic_type": Route("remotion", "ConceptExplainer", "word_highlight"),
    "ui_demo": Route("remotion", "UniversalCustom", "phrase_box", "minimal"),
    "vox_documentary": Route("remotion", "VoxEditorial", "minimal_editorial"),
    "editorial_map": Route("remotion", "VoxEditorial", "minimal_editorial"),
    "news_breakdown": Route("remotion", "VoxEditorial", "minimal_editorial"),
    "whiteboard": Route("remotion", "WhiteboardDraw", "phrase_box"),
    "hand_drawn": Route("remotion", "WhiteboardDraw", "phrase_box"),
    "sketch": Route("remotion", "WhiteboardDraw", "phrase_box"),
    "explainroo": Route("explainroo", None, "phrase_box"),
    "handanim": Route("handanim", None, "phrase_box"),
    "math_science": Route("manim", None, "phrase_box"),
    "algorithm": Route("manim", None, "phrase_box"),
    "clip_repurpose": Route("clipper", None, "word_highlight"),
    "hybrid_or_custom": Route("remotion", "UniversalCustom", "word_highlight", "concept"),
    "openmontage": Route("openmontage", None, "minimal_editorial"),
}

BLUEPRINT_ENGINE_TO_STYLE = {
    "remotion": "concept_explainer",
    "vox_remotion": "vox_documentary",
    "explainroo": "explainroo",
    "handanim": "handanim",
    "manim": "math_science",
    "openmontage": "openmontage",
}


def route(style: str) -> Route:
    try:
        return ROUTES[style]
    except KeyError as exc:
        known = ", ".join(sorted(ROUTES))
        raise ValueError(f"Unknown style '{style}'. Known styles: {known}") from exc
