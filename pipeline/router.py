"""Universal Style Router: maps a requested style to an engine, composition, captions, transition and look."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Route:
    engine: str  # remotion | explainroo | handanim | manim | clipper | openmontage
    composition: str | None  # Remotion composition id, when engine == "remotion"
    caption_style: str
    theme: str | None = None  # UniversalCustom theme override
    transition: str = "fade"  # hard_cut | fade | whip_pan | paper_slide | pen_draw
    look: str = "concept"  # theme family; also picks the default SFX set


ROUTES: dict[str, Route] = {
    "concept_explainer": Route("remotion", "ConceptExplainer", "word_highlight", transition="fade"),
    "case_study": Route("remotion", "ConceptExplainer", "word_highlight", transition="whip_pan"),
    "kinetic_type": Route("remotion", "ConceptExplainer", "word_highlight", transition="hard_cut"),
    "ui_demo": Route("remotion", "UniversalCustom", "phrase_box", "minimal", "fade", "minimal"),
    "vox_documentary": Route("remotion", "VoxEditorial", "minimal_editorial", transition="paper_slide", look="vox"),
    "editorial_map": Route("remotion", "VoxEditorial", "minimal_editorial", transition="paper_slide", look="vox"),
    "news_breakdown": Route("remotion", "VoxEditorial", "minimal_editorial", transition="hard_cut", look="vox"),
    "whiteboard": Route("remotion", "WhiteboardDraw", "phrase_box", transition="pen_draw", look="whiteboard"),
    "hand_drawn": Route("remotion", "WhiteboardDraw", "phrase_box", transition="pen_draw", look="whiteboard"),
    "sketch": Route("remotion", "WhiteboardDraw", "phrase_box", transition="pen_draw", look="whiteboard"),
    "explainroo": Route("explainroo", None, "phrase_box", look="whiteboard"),
    "handanim": Route("handanim", None, "phrase_box", look="whiteboard"),
    "math_science": Route("manim", None, "phrase_box"),
    "algorithm": Route("manim", None, "phrase_box"),
    "clip_repurpose": Route("clipper", None, "word_highlight"),
    "hybrid_or_custom": Route("remotion", "UniversalCustom", "word_highlight", "concept"),
    "openmontage": Route("openmontage", None, "minimal_editorial", "vox", "paper_slide", "vox"),
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
