"""Content tasks on top of any provider: ideas, scripts, upload metadata.

Every output is validated and normalized into the exact JSON contracts in docs/ARCHITECTURE.md,
so a sloppy model reply can never break a render. Numbers a model states as facts are listed
in `facts_to_verify` so the UI can ask you to check them before publishing.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from llm.providers import LLMError, Provider, get_provider
from pipeline.router import ROUTES

VISUAL_TYPES = ["headline", "stat", "bullets", "chart", "image", "quote", "flow", "map"]
MOODS = ["chill", "documentary", "upbeat", "dramatic"]
CAPTION_STYLES = ["word_highlight", "phrase_box", "minimal_editorial", "none"]
REMOTION_STYLES = sorted(k for k, r in ROUTES.items() if r.engine in ("remotion", "openmontage"))

SYSTEM = (
    "You are a senior short-form video producer and scriptwriter. You write tight, spoken-style "
    "narration (short sentences, no stage directions, no emojis in narration), strong 0-3 second hooks, "
    "and accurate case studies. Never invent statistics: if unsure of a number, phrase it qualitatively "
    "and list every factual claim with a number in facts_to_verify."
)

IDEAS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "ideas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "hook": {"type": "string", "description": "first 3 seconds, spoken"},
                    "angle": {"type": "string", "description": "core concept / angle"},
                    "case_study": {"type": "string"},
                    "style": {"type": "string", "enum": REMOTION_STYLES},
                    "music_mood": {"type": "string", "enum": MOODS},
                    "why_it_works": {"type": "string"},
                },
                "required": ["title", "hook", "angle", "case_study", "style", "music_mood", "why_it_works"],
            },
        }
    },
    "required": ["ideas"],
}

SCRIPT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "cover_text": {"type": "string", "description": "2-5 word on-screen hook for frame 0"},
        "description": {"type": "string"},
        "music_mood": {"type": "string", "enum": MOODS},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "beat": {"type": "string", "enum": ["hook", "concept", "case_study", "takeaway", "other"]},
                    "narration": {"type": "string"},
                    "visual": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": VISUAL_TYPES},
                            "heading": {"type": "string"},
                            "text": {"type": "string"},
                            "value": {"type": "string"},
                            "label": {"type": "string"},
                            "items": {"type": "array", "items": {"type": "string"}},
                            "data": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {"label": {"type": "string"}, "value": {"type": "number"}},
                                    "required": ["label", "value"],
                                },
                            },
                            "countries": {"type": "array", "items": {"type": "string"}, "description": "ISO A3 codes"},
                        },
                        "required": ["type"],
                    },
                    "media_query": {"type": "string", "description": "optional archive photo search"},
                },
                "required": ["narration", "visual"],
            },
        },
        "facts_to_verify": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "cover_text", "scenes", "facts_to_verify"],
}

META_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "titles": {"type": "array", "items": {"type": "string"}, "description": "3 variants, <=70 chars"},
        "hook_variants": {"type": "array", "items": {"type": "string"}},
        "thumbnail_text": {"type": "string", "description": "2-4 words"},
        "description": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}},
        "pinned_comment": {"type": "string"},
    },
    "required": ["titles", "hook_variants", "thumbnail_text", "description", "hashtags", "tags"],
}


# --------------------------------------------------------------------------- normalizers
def _clip(s: Any, n: int) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def normalize_visual(v: dict[str, Any], narration: str) -> dict[str, Any]:
    t = v.get("type") if v.get("type") in VISUAL_TYPES else "headline"
    out: dict[str, Any] = {"type": t}
    if v.get("heading"):
        out["heading"] = _clip(v["heading"], 48)
    if v.get("text"):
        out["text"] = _clip(v["text"], 90)
    if t == "stat":
        out["value"] = _clip(v.get("value") or "?", 8)
        out["label"] = _clip(v.get("label") or "", 40)
    if t in ("bullets", "flow"):
        items = [_clip(i, 32 if t == "bullets" else 14) for i in (v.get("items") or []) if str(i).strip()]
        out["items"] = items[: (4 if t == "bullets" else 4)] or [_clip(narration, 32)]
    if t == "chart":
        data = []
        for d in v.get("data") or []:
            try:
                data.append({"label": _clip(d["label"], 10), "value": float(d["value"])})
            except (KeyError, TypeError, ValueError):
                continue
        if len(data) < 2:
            return {"type": "headline", "heading": out.get("heading") or _clip(narration, 48)}
        out["data"] = data[:6]
    if t == "quote":
        out["text"] = _clip(v.get("text") or narration, 120)
        if v.get("label"):
            out["label"] = _clip(v["label"], 40)
    if t == "map":
        codes = [str(c).upper()[:3] for c in (v.get("countries") or []) if re.fullmatch(r"[A-Za-z]{3}", str(c))]
        out["countries"] = codes[:8]
        out["label"] = _clip(v.get("label") or "", 40)
    if t == "headline" and "heading" not in out:
        out["heading"] = _clip(narration, 48)
    return out


def normalize_script(
    raw: dict[str, Any], *, style: str, aspect: str, mood: str, voice: dict[str, Any]
) -> dict[str, Any]:
    scenes = []
    for s in raw.get("scenes") or []:
        narration = _clip(s.get("narration"), 400)
        if not narration:
            continue
        scene: dict[str, Any] = {"narration": narration, "visual": normalize_visual(s.get("visual") or {}, narration)}
        if s.get("beat"):
            scene["beat"] = s["beat"]
        if s.get("media_query"):
            scene["media_query"] = _clip(s["media_query"], 60)
        scenes.append(scene)
    if len(scenes) < 2:
        raise LLMError("model returned fewer than 2 usable scenes; try again or shorten the prompt")
    return {
        "title": _clip(raw.get("title") or "Untitled", 100),
        "cover_text": _clip(raw.get("cover_text") or raw.get("title") or "", 40),
        "description": _clip(raw.get("description") or "", 4500),
        "style": style,
        "aspect_ratio": aspect,
        "music_mood": raw.get("music_mood") if raw.get("music_mood") in MOODS else mood,
        "voice": voice,
        "scenes": scenes[:12],
        "facts_to_verify": [_clip(f, 200) for f in raw.get("facts_to_verify") or []][:12],
    }


def normalize_hashtag(tag: str) -> str:
    tag = re.sub(r"[^\w]", "", str(tag).lstrip("#"))
    return f"#{tag}" if tag else ""


def normalize_meta(raw: dict[str, Any], fallback_title: str, platform_targets: list[str]) -> dict[str, Any]:
    titles = [_clip(t, 100) for t in raw.get("titles") or [] if str(t).strip()] or [fallback_title]
    hashtags = list(dict.fromkeys(h for h in (normalize_hashtag(t) for t in raw.get("hashtags") or []) if h))
    if "youtube" in platform_targets and "#shorts" not in (h.lower() for h in hashtags):
        hashtags.insert(0, "#shorts")
    # YouTube ignores all hashtags when a video has more than 15; keep a focused set.
    hashtags = hashtags[:8]
    tags, total = [], 0
    for t in raw.get("tags") or []:
        t = _clip(str(t).lstrip("#"), 30)
        if t and total + len(t) + 2 <= 480:  # YouTube tag field limit is 500 chars
            tags.append(t)
            total += len(t) + 2
    return {
        "titles": titles[:3],
        "hook_variants": [_clip(h, 120) for h in raw.get("hook_variants") or []][:3],
        "thumbnail_text": _clip(raw.get("thumbnail_text") or titles[0], 32),
        "description": _clip(raw.get("description") or "", 4500),
        "hashtags": hashtags,
        "tags": tags,
        "pinned_comment": _clip(raw.get("pinned_comment") or "", 500),
    }


VISUAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "visual_pattern": {"type": "string", "description": "what the first 3 seconds SHOW"},
        "visual_vs_verbal_contrast": {"type": "string"},
        "on_screen_text": {"type": "array", "items": {"type": "string"}, "description": "verbatim"},
        "visual_style_notes": {"type": "string", "description": "palette, typography, framing, b-roll vs graphics"},
        "recommended_engine": {
            "type": "string",
            "enum": ["remotion", "vox_remotion", "explainroo", "handanim", "manim", "openmontage"],
        },
        "caption_style": {"type": "string", "enum": CAPTION_STYLES},
        "transition_style": {"type": "string", "enum": ["hard_cut", "fade", "whip_pan", "paper_slide", "pen_draw"]},
    },
    "required": ["visual_pattern", "visual_vs_verbal_contrast", "on_screen_text", "visual_style_notes"],
}


# --------------------------------------------------------------------------- tasks
def read_reference_frames(
    blueprint: dict[str, Any], sheets: list[Path], said_first_3s: str, provider: Provider | None = None
) -> dict[str, Any]:
    """Vision pass over contact sheets: fills the blueprint's TODO visual fields (watchvideo's 'vision' step)."""
    provider = provider or get_provider()
    prompt = (
        "These are contact sheets from a reference video (frames tiled left-to-right, top-to-bottom). "
        "If present, the sheet named first-3s shows only the first 3 seconds.\n"
        f"What the video SAYS in its first 3 seconds: {said_first_3s!r}\n"
        "Describe what it SHOWS in the first 3 seconds, how that contrasts with what is said, quote on-screen "
        "text verbatim, and summarize the visual style. Then pick the closest engine, caption style and transition."
    )
    raw = provider.vision_json(prompt, VISUAL_SCHEMA, sheets[:6], SYSTEM)
    bp = dict(blueprint)
    hook = dict(bp.get("hook_first_3s", {}))
    hook["visual_pattern"] = _clip(raw.get("visual_pattern"), 300)
    hook["visual_vs_verbal_contrast"] = _clip(raw.get("visual_vs_verbal_contrast"), 300)
    bp["hook_first_3s"] = hook
    bp["on_screen_text"] = [_clip(t, 120) for t in raw.get("on_screen_text") or []][:12]
    bp["visual_style_notes"] = _clip(raw.get("visual_style_notes"), 500)
    pacing = dict(bp.get("pacing", {}))
    if raw.get("caption_style") in CAPTION_STYLES:
        pacing["caption_style"] = raw["caption_style"]
    if raw.get("transition_style") in ("hard_cut", "fade", "whip_pan", "paper_slide", "pen_draw"):
        pacing["transition_style"] = raw["transition_style"]
    bp["pacing"] = pacing
    if raw.get("recommended_engine"):
        bp["recommended_engine"] = raw["recommended_engine"]
    return bp


def _blueprint_brief(blueprint: dict[str, Any] | None) -> str:
    if not blueprint:
        return "No reference blueprint: use the default Concept + Case Study structure."
    keep = {
        k: blueprint.get(k)
        for k in (
            "style_name",
            "aspect_ratio",
            "target_duration_sec",
            "hook_first_3s",
            "pacing",
            "audio_profile",
            "beat_template",
        )
    }
    return "Reference style blueprint (copy the STYLE, never the content):\n" + repr(keep)


def generate_ideas(
    *,
    blueprint: dict[str, Any] | None,
    topic_hint: str = "",
    niche: str = "",
    reference_notes: str = "",
    provider: Provider | None = None,
) -> list[dict[str, Any]]:
    provider = provider or get_provider()
    prompt = (
        "Propose exactly 5 distinct short-video ideas.\n"
        f"Channel niche: {niche or 'general explainers'}\n"
        f"Topic hint from the user: {topic_hint or 'none, choose strong evergreen topics'}\n"
        f"{_blueprint_brief(blueprint)}\n"
        f"Notes from the reference videos (transcript hooks, pacing):\n{reference_notes[:4000] or 'none'}\n"
        "Each idea needs a pattern-interrupt hook, a clear concept, and one concrete real-world case study."
    )
    raw = provider.generate_json(prompt, IDEAS_SCHEMA, SYSTEM)
    ideas = []
    for i, idea in enumerate((raw.get("ideas") or [])[:5], 1):
        ideas.append(
            {
                "n": i,
                "title": _clip(idea.get("title"), 100),
                "hook": _clip(idea.get("hook"), 160),
                "angle": _clip(idea.get("angle"), 300),
                "case_study": _clip(idea.get("case_study"), 300),
                "style": idea.get("style") if idea.get("style") in ROUTES else "concept_explainer",
                "music_mood": idea.get("music_mood") if idea.get("music_mood") in MOODS else "documentary",
                "why_it_works": _clip(idea.get("why_it_works"), 300),
            }
        )
    if len(ideas) < 3:
        raise LLMError("model returned fewer than 3 ideas; try again")
    return ideas


def write_script(
    *,
    brief: str,
    style: str,
    aspect: str,
    mood: str,
    duration_sec: int,
    voice: dict[str, Any],
    language: str = "English",
    blueprint: dict[str, Any] | None = None,
    provider: Provider | None = None,
) -> dict[str, Any]:
    provider = provider or get_provider()
    words = int(duration_sec * 2.6)  # ~155 wpm spoken
    prompt = (
        f"Write a {duration_sec}-second {aspect} video script in {language} (about {words} spoken words total).\n"
        f"Brief: {brief}\n{_blueprint_brief(blueprint)}\n"
        "Structure: hook (0-3 s), concept (to ~20 s), concrete case study with real figures (to ~45 s), "
        "one-line takeaway that loops back to the hook.\n"
        "Use 6-9 scenes, one idea per scene, 1-3 sentences each. Pick the visual that best shows each scene: "
        "headline (<=6 words), stat (value + label), bullets (<=4 short items), chart (2-6 numeric points), "
        "flow (3-4 one-word steps), quote, map (ISO A3 country codes), image (add media_query for an archive photo).\n"
        "cover_text is the frame-0 cover: 2-5 punchy words, no hashtags."
    )
    raw = provider.generate_json(prompt, SCRIPT_SCHEMA, SYSTEM)
    return normalize_script(raw, style=style, aspect=aspect, mood=mood, voice=voice)


def write_metadata(
    script: dict[str, Any], platform_targets: list[str], provider: Provider | None = None
) -> dict[str, Any]:
    provider = provider or get_provider()
    narration = " ".join(s.get("narration", "") for s in script.get("scenes", []))
    prompt = (
        f"Write upload metadata for this {script.get('aspect_ratio', '9:16')} video for {', '.join(platform_targets)}.\n"
        f"Working title: {script.get('title')}\nNarration: {narration[:3000]}\n"
        "Give 3 title variants (curiosity + clarity, <=70 chars, no clickbait lies), 3 alternative spoken hooks, "
        "thumbnail_text (2-4 words), a description whose first line works as a hook, 3-6 specific hashtags "
        "(mix broad and niche), up to 15 search tags, and a pinned comment that invites replies."
    )
    raw = provider.generate_json(prompt, META_SCHEMA, SYSTEM)
    return normalize_meta(raw, script.get("title", ""), platform_targets)
