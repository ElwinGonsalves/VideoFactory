"""Per-style script structures.

Each style family has its own native beats (what the story does) and, per beat, the visuals that
suit it. `ScriptTemplateRegistry.for_style()` hands the LLM prompt a block that describes that
structure, so a Vox documentary is not written like a whiteboard explainer.

    template = REGISTRY.for_style("vox_documentary")
    template.prompt_block(duration_sec=60)

`reference_blueprint` has no fixed beats: they are inherited from analyzer/blueprints/<style>.json
(`beat_template`), so the structure of a studied reference video drives the new script.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Beat:
    id: str  # stored as scene["beat"]
    label: str  # shown to the user
    goal: str  # what the narration does here
    visuals: tuple[str, ...]  # visual types that suit this beat, best first
    visual_fields: str  # what the visual must contain (fed to the model)
    share: float  # fraction of the total duration


@dataclass(frozen=True)
class ScriptTemplate:
    family: str
    label: str
    beats: tuple[Beat, ...]
    default_aspect: str = "9:16"
    notes: str = ""
    inherited_from: str = ""

    @property
    def beat_ids(self) -> list[str]:
        return [b.id for b in self.beats]

    def prompt_block(self, duration_sec: int) -> str:
        total = sum(b.share for b in self.beats) or 1.0
        lines = [f"Script structure for the '{self.label}' style (follow these beats in order):"]
        for i, b in enumerate(self.beats, 1):
            secs = max(2, round(duration_sec * b.share / total))
            lines.append(
                f'{i}. beat "{b.id}" ({b.label}, about {secs} s): {b.goal} '
                f"Preferred visuals: {', '.join(b.visuals)}. {b.visual_fields}"
            )
        if self.notes:
            lines.append(self.notes)
        lines.append('Set each scene\'s "beat" to the beat id it belongs to. Every beat needs at least one scene.')
        return "\n".join(lines)

    def public(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "label": self.label,
            "default_aspect": self.default_aspect,
            "beats": [{"id": b.id, "label": b.label, "visuals": list(b.visuals), "share": b.share} for b in self.beats],
        }


def _beat(id_: str, label: str, goal: str, visuals: tuple[str, ...], fields: str, share: float) -> Beat:
    return Beat(id_, label, goal, visuals, fields, share)


CONCEPT = ScriptTemplate(
    "concept",
    "Concept / Case Study",
    (
        _beat("hook", "Hook", "A counter-intuitive question or claim in under 8 words.", ("counter", "diagram"),
              "Show the surprising number or a diagram with the key terms.", 0.08),
        _beat("mechanism", "Mechanism", "Explain how the thing works, one idea per scene.", ("diagram", "flow"),
              "Boxes and arrows with 3-4 one-word steps.", 0.30),
        _beat("case_study", "Case Study", "A real company or event with dates and figures.", ("timeline", "chart", "counter", "image"),
              "Give real data points (label + number) or dated milestones.", 0.40),
        _beat("takeaway", "Takeaway Loop", "One line takeaway that loops back to the hook.", ("sketch", "counter"),
              "An icon or the number from the hook returning.", 0.22),
    ),
    notes="Never invent statistics. If unsure of a figure, say it qualitatively and flag it in facts.",
)  # fmt: skip

VOX = ScriptTemplate(
    "vox",
    "Vox Documentary",
    (
        _beat("cold_open", "Cold Open", "Start mid-story with a vivid scene or striking fact, no intro.", ("cutout", "image"),
              "A paper-cutout card or archive photo with a one-line caption.", 0.14),
        _beat("context", "Archival / Map Context", "Place it in time and space.", ("map", "image", "timeline"),
              "Highlight the countries involved or show a dated archive photo.", 0.30),
        _beat("turning_point", "Turning Point", "The event or decision that changed things.", ("cutout", "counter", "image"),
              "One dominant image or figure, big caption.", 0.30),
        _beat("synthesis", "Editorial Synthesis", "What it means. A point of view, not a summary.", ("cutout", "quote"),
              "A pull quote on a paper card or a closing archive image.", 0.26),
    ),
    notes="Editorial voice: measured, specific, a little dry. Prefer archive images and maps over graphics.",
)  # fmt: skip

WHITEBOARD = ScriptTemplate(
    "whiteboard",
    "Whiteboard / Hand-drawn",
    (
        _beat("problem", "Problem Sketch", "Pose the problem as something that can be drawn.", ("sketch", "diagram"),
              "Name an icon to draw (e.g. 'lightbulb', 'coins') and 2-4 labels.", 0.22),
        _beat("draw_steps", "Step-by-Step Draw Cues", "Solve it in steps; each scene draws one new thing.", ("sketch", "flow", "diagram"),
              "Each scene lists the shapes/icons to draw in order (draw_cues).", 0.56),
        _beat("recap", "Recap", "Re-trace the finished drawing in one sentence.", ("sketch", "flow"),
              "The final icon with a one-word label per step.", 0.22),
    ),
    notes="Narration describes what is being drawn as it appears.",
)  # fmt: skip

STICKMAN = ScriptTemplate(
    "stickman",
    "Stickman",
    (
        _beat("setup", "Character Setup", "Introduce one stick character and their problem.", ("stickman",),
              "Pose (idle, point, shrug, run, celebrate, panic) and a speech bubble line.", 0.22),
        _beat("escalation", "Escalation & Reaction Beats", "Things get worse or sillier; the character reacts each time.", ("stickman",),
              "Change the pose every scene; short speech bubbles.", 0.55),
        _beat("punchline", "Punchline", "Land the joke or lesson in the final beat.", ("stickman",),
              "A strong closing pose and a one-line bubble.", 0.23),
    ),
    notes="Comedic timing: short lines, a reaction after every statement.",
)  # fmt: skip

LONG_FORM = ScriptTemplate(
    "long_form",
    "Long-form (16:9)",
    (
        _beat("hook", "Hook", "Promise what the viewer will learn in the first 20 seconds.", ("counter", "image"),
              "A striking figure or image.", 0.05),
        _beat("intro", "Intro", "Frame the question and why it matters now.", ("diagram", "map"), "Context graphic.", 0.07),
        _beat("chapter_1", "Chapter 1", "First main idea with an example.", ("diagram", "chart", "image"), "Chapter title card then evidence.", 0.20),
        _beat("chapter_2", "Chapter 2", "Second main idea with an example.", ("timeline", "chart", "image"), "Chapter title card then evidence.", 0.20),
        _beat("chapter_3", "Chapter 3", "Third main idea with an example.", ("flow", "chart", "map"), "Chapter title card then evidence.", 0.20),
        _beat("chapters_more", "Chapters 4-5 (optional)", "One or two further chapters if the topic needs them.", ("diagram", "image"),
              "Only if there is real material; otherwise skip this beat.", 0.12),
        _beat("summary_cta", "Summary & CTA", "Recap in three points and a single call to action.", ("sketch", "diagram"), "Three icons, one per point.", 0.16),
    ),
    default_aspect="16:9",
    notes="3-5 chapters. Give each chapter its own scene group; chapter titles are short.",
)  # fmt: skip


class ScriptTemplateRegistry:
    """Style id -> template. Unknown styles fall back to the concept structure."""

    def __init__(self) -> None:
        self._by_style: dict[str, ScriptTemplate] = {}
        self._families: dict[str, ScriptTemplate] = {}

    def register(self, template: ScriptTemplate, *styles: str) -> None:
        self._families[template.family] = template
        for s in styles:
            self._by_style[s] = template

    def families(self) -> list[ScriptTemplate]:
        return list(self._families.values())

    def for_style(self, style: str, blueprint: dict[str, Any] | None = None) -> ScriptTemplate:
        if style == "reference_blueprint" or (
            blueprint and blueprint.get("beat_template") and style not in self._by_style
        ):
            return self.from_blueprint(blueprint or {})
        return self._by_style.get(style, CONCEPT)

    def from_blueprint(self, blueprint: dict[str, Any]) -> ScriptTemplate:
        """Beats inherited from a saved Style Blueprint (`beat_template`)."""
        raw = blueprint.get("beat_template") or []
        if not raw:
            return CONCEPT
        beats = tuple(
            _beat(
                str(b.get("beat", f"beat_{i}")),
                str(b.get("beat", f"beat {i}")).replace("_", " ").title(),
                f"Match the reference video: {b.get('visual_role', 'visual beat')}.",
                ("diagram", "counter", "image"),
                str(b.get("visual_role", "")),
                float(b.get("pct_duration", 1 / len(raw))),
            )
            for i, b in enumerate(raw, 1)
        )
        name = str(blueprint.get("style_name", "reference"))
        return ScriptTemplate(
            "reference_blueprint", f"Reference blueprint ({name})", beats,
            default_aspect=str(blueprint.get("aspect_ratio", "9:16")), inherited_from=name,
        )  # fmt: skip


REGISTRY = ScriptTemplateRegistry()
REGISTRY.register(CONCEPT, "concept_explainer", "case_study", "kinetic_type", "ui_demo", "hybrid_or_custom")
REGISTRY.register(VOX, "vox_documentary", "editorial_map", "news_breakdown", "openmontage")
REGISTRY.register(WHITEBOARD, "whiteboard", "hand_drawn", "sketch", "explainroo", "handanim")
REGISTRY.register(STICKMAN, "stickman")
REGISTRY.register(LONG_FORM, "long_form")


def default_aspect_for(style: str) -> str | None:
    """Aspect that a style forces (long_form is 16:9); None when the user's choice stands."""
    t = REGISTRY.for_style(style)
    return t.default_aspect if t.family == "long_form" else None
