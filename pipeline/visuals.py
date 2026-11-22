"""Visual validator: no scene may be plain text on an empty background.

`CONCRETE` types draw something (a diagram, counter, sketch, paper cutout, timeline, stick figure,
chart, map or photo). `headline`, `bullets` and `quote` are text-first, so `ensure_concrete` upgrades
them to a concrete type that suits the look (vox -> cutout, whiteboard -> sketch, others -> diagram/sketch)
and picks an icon from the narration. The Remotion templates apply the same rule at render time.
"""

from __future__ import annotations

import re
from typing import Any

CONCRETE = {"stat", "counter", "chart", "flow", "diagram", "sketch", "cutout", "timeline", "stickman", "image", "map"}
TEXT_FIRST = {"headline", "bullets", "quote"}
STICK_POSES = ("idle", "point", "shrug", "run", "celebrate", "panic", "think")

# Must match the keys of studio/src/components/visuals/icons.tsx (tests/test_visuals.py checks).
ICON_NAMES = [
    "book-open",
    "brain",
    "building",
    "clock",
    "coins",
    "factory",
    "flame",
    "globe",
    "handshake",
    "heart",
    "lightbulb",
    "lock",
    "megaphone",
    "rocket",
    "scale",
    "search",
    "shield",
    "sparkles",
    "target",
    "trending-down",
    "trending-up",
    "users",
    "wallet",
    "zap",
]

ICON_KEYWORDS: dict[str, tuple[str, ...]] = {
    "coins": ("money", "price", "cost", "cash", "dollar", "pay", "profit", "revenue", "cheap", "afford"),
    "wallet": ("budget", "spend", "save", "saving", "bank", "loan", "debt"),
    "trending-up": ("grow", "rise", "increase", "surge", "boom", "double", "climb"),
    "trending-down": ("fall", "drop", "decline", "crash", "collapse", "shrink", "loss"),
    "brain": ("brain", "mind", "think", "psycholog", "bias", "memory", "lie", "lied", "truth"),
    "users": ("people", "customer", "audience", "crowd", "society", "everyone", "viewer"),
    "globe": ("world", "global", "country", "countries", "nation", "international"),
    "clock": ("time", "year", "years", "day", "hour", "minute", "history", "decade"),
    "rocket": ("launch", "startup", "fast", "space", "scale", "rocket"),
    "shield": ("safe", "protect", "security", "risk", "defend"),
    "lightbulb": ("idea", "invent", "discover", "learn", "secret", "insight"),
    "scale": ("law", "court", "fair", "justice", "trade-off", "balance", "choice"),
    "search": ("find", "search", "investigate", "research", "why", "how"),
    "lock": ("private", "lock", "hidden", "locked", "password"),
    "flame": ("hot", "fire", "viral", "trend", "burn"),
    "book-open": ("book", "story", "read", "school", "teach"),
    "factory": ("factory", "produce", "manufactur", "supply", "industry"),
    "handshake": ("deal", "partner", "agree", "trust", "negotiat"),
    "megaphone": ("announce", "say", "said", "ad", "advert", "market", "tell"),
    "target": ("goal", "target", "aim", "focus", "win"),
    "heart": ("love", "feel", "kind", "care", "emotion"),
    "building": ("company", "business", "firm", "brand", "corporation", "store"),
    "zap": ("power", "energy", "electric", "instant", "shock"),
}


def pick_icon(*texts: str) -> str:
    """Icon for the first keyword hit in the given texts (heading before narration), else sparkles."""
    for text in texts:
        low = (text or "").lower()
        for icon, words in ICON_KEYWORDS.items():
            if any(re.search(rf"\b{re.escape(w)}", low) for w in words):
                return icon
    return "sparkles"


def _look_type(look: str) -> str:
    return {"vox": "cutout", "whiteboard": "sketch"}.get(look, "sketch")


def ensure_concrete(visual: dict[str, Any], narration: str, look: str = "concept") -> dict[str, Any]:
    """Return a visual that draws something. Concrete visuals pass through (an icon is added where useful)."""
    v = dict(visual)
    kind = v.get("type", "headline")
    heading = v.get("heading") or v.get("text") or ""
    if kind in CONCRETE:
        if kind in ("sketch", "cutout", "diagram") and v.get("icon") not in ICON_NAMES:
            v["icon"] = pick_icon(heading, narration)
        return v
    icon = v.get("icon") if v.get("icon") in ICON_NAMES else pick_icon(heading, narration)
    if kind == "bullets" and len(v.get("items") or []) >= 2:
        return {**v, "type": "diagram", "icon": icon}
    if kind == "quote":
        quote = v.get("text") or heading or narration
        return {"type": "cutout", "heading": quote[:90], "label": v.get("label", ""), "icon": icon or "megaphone"}
    out: dict[str, Any] = {"type": _look_type(look), "heading": heading[:60] or narration[:60], "icon": icon}
    if v.get("items"):
        out["draw_cues"] = [str(i)[:32] for i in v["items"][:4]]
    if v.get("text") and v.get("heading"):
        out["label"] = str(v["text"])[:60]
    return out


def validate_script(script: dict[str, Any], look: str = "concept") -> list[str]:
    """Upgrade every text-first scene in place. Returns a note per scene that was changed."""
    notes = []
    for i, scene in enumerate(script.get("scenes", [])):
        before = (scene.get("visual") or {}).get("type", "headline")
        scene["visual"] = ensure_concrete(scene.get("visual") or {}, scene.get("narration", ""), look)
        after = scene["visual"]["type"]
        if after != before:
            notes.append(f"scene {i + 1}: {before} -> {after} (text-only scenes are not allowed)")
    return notes
