"""Render the Style Picker card images with the real Remotion compositions (no stock art, no mockups).

    python scripts/render_style_cards.py

Writes frontend/public/styles/<family>.webp (portrait 270x480, long_form 480x270). Each image is one
frame of the actual composition for that style, so the picker shows what the engine really draws.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import ROOT, STUDIO, read_json, run, which, write_json  # noqa: E402
from pipeline.render import render_stills_batch  # noqa: E402

OUT = ROOT / "frontend" / "public" / "styles"
BRAND = read_json(STUDIO / "brands" / "default" / "brand.json")

# family -> (composition, aspect, visual, frame)
# card image -> (composition, aspect, visual, frame, variant). The variant is the style id whose own look
# (palette, background, type) the card shows; frames are real renders of that look.
CARDS = {
    "concept": ("ConceptExplainer", "9:16", {"type": "counter", "value": "7.5M+", "label": "subscribers by 2007",
                                              "data": [{"label": "2007", "value": 7}, {"label": "2012", "value": 33}, {"label": "2017", "value": 118}]}, 60, "concept_explainer"),
    "case_study": ("ConceptExplainer", "9:16", {"type": "timeline", "heading": "Netflix timeline",
                                                 "items": ["1998: DVD by mail", "2007: Streaming", "2016: 190 countries"]}, 75, "case_study"),
    "kinetic": ("ConceptExplainer", "9:16", {"type": "headline", "heading": "Fast. Cheap. Everywhere."}, 60, "kinetic_type"),
    "vox": ("VoxEditorial", "9:16", {"type": "cutout", "heading": "The turning point", "icon": "scale", "label": "1998"}, 60, "vox_documentary"),
    "map": ("VoxEditorial", "9:16", {"type": "map", "heading": "Where it launched", "countries": ["USA", "CAN", "GBR"], "label": "2010-2012"}, 75, "editorial_map"),
    "news": ("VoxEditorial", "9:16", {"type": "counter", "value": "4.25%", "label": "repo rate, cut today",
                                       "data": [{"label": "Jan", "value": 65}, {"label": "Apr", "value": 60}, {"label": "Jun", "value": 42}]}, 60, "news_breakdown"),
    "whiteboard": ("WhiteboardDraw", "9:16", {"type": "sketch", "heading": "How a loan works", "icon": "coins",
                                              "draw_cues": ["Bank lends", "You repay", "Interest grows"]}, 75, "whiteboard"),
    "hand_drawn": ("WhiteboardDraw", "9:16", {"type": "sketch", "heading": "Why we put things off", "icon": "clock",
                                              "draw_cues": ["Fear", "Delay", "Relief", "Regret"]}, 75, "hand_drawn"),
    "sketch": ("WhiteboardDraw", "9:16", {"type": "flow", "heading": "How rain forms", "items": ["Heat", "Vapour", "Cloud", "Rain"]}, 75, "sketch"),
    "stickman": ("WhiteboardDraw", "9:16", {"type": "stickman", "pose": "panic", "bubble": "The price doubled again?!"}, 60, "stickman"),
    "long_form": ("ConceptExplainer", "16:9", {"type": "diagram", "heading": "", "icon": "lightbulb",
                                               "items": ["Hook", "Mechanism", "Case study", "Takeaway"]}, 90, "long_form"),
}  # fmt: skip


def props_for(aspect: str, visual: dict, variant: str | None = None) -> dict:
    return {
        **({"variant": variant} if variant else {}),
        "aspectRatio": aspect,
        "title": "style card",
        "durationSec": 4,
        "captionStyle": "none",
        "showSafeZones": False,
        "brand": BRAND,
        "scenes": [{"start": 0, "end": 4, "visual": visual}],
        "captions": [],
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="vf-style-"))
    try:
        jobs = []
        for family, (comp, aspect, visual, frame, variant) in CARDS.items():
            props = work / f"{family}.json"
            write_json(props, props_for(aspect, visual, variant))
            jobs.append({"composition": comp, "props": props, "frame": frame, "output": work / f"{family}.png"})
        render_stills_batch(jobs, work)
        for family, (_c, aspect, _v, _f, _s) in CARDS.items():
            size = "270:480" if aspect == "9:16" else "480:270"
            dest = OUT / f"{family}.webp"
            run([which("ffmpeg"), "-y", "-v", "error", "-i", str(work / f"{family}.png"), "-vf", f"scale={size}:flags=lanczos",
                 "-quality", "82", str(dest)])  # fmt: skip
            print(f"{dest.relative_to(ROOT)} ({dest.stat().st_size // 1024} KB)")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
