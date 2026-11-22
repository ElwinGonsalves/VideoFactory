"""Project ids: short kebab-case slugs built from the video Title only.

Never feed prompt or script text in here. A title like "How would the world be if a person never
lied?" becomes `how-world-person-never-lied`. Clashes get `-2`, `-3`, ...
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from common import OUTPUT, PROJECTS

MAX_WORDS = 5
MIN_WORDS = 3
MAX_LEN = 48
STOPWORDS = frozenset(
    [
        "a",
        "an",
        "the",
        "of",
        "to",
        "in",
        "on",
        "at",
        "is",
        "are",
        "be",
        "was",
        "were",
        "am",
        "if",
        "and",
        "or",
        "for",
        "with",
        "would",
        "will",
        "can",
        "could",
        "do",
        "does",
        "did",
        "you",
        "your",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "by",
        "as",
        "from",
        "into",
        "than",
        "then",
        "so",
        "but",
    ]
)


def _words(text: str) -> list[str]:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.findall(r"[a-z0-9]+", ascii_text.lower())


def base_slug(title: str) -> str:
    """3-5 meaningful words of the title in order, kebab-case. Falls back to `video`."""
    words = _words(title)
    if not words:
        return "video"
    meaningful = [w for w in words if w not in STOPWORDS]
    if len(meaningful) < MIN_WORDS:
        meaningful = words  # e.g. "To be or not to be": too few content words, keep the title as written
    picked = meaningful[:MAX_WORDS]
    slug = "-".join(picked)
    while len(slug) > MAX_LEN and len(picked) > 1:
        picked.pop()
        slug = "-".join(picked)
    return slug[:MAX_LEN].strip("-") or "video"


def unique_slug(base: str, existing: Iterable[str]) -> str:
    taken = set(existing)
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


def existing_slugs() -> set[str]:
    """Every id already used by a project folder or an output (flat legacy files or per-project folders)."""
    names: set[str] = set()
    if PROJECTS.exists():
        names |= {p.name for p in PROJECTS.iterdir() if p.is_dir()}
    if OUTPUT.exists():
        for p in OUTPUT.iterdir():
            if p.is_dir():
                names.add(p.name)
            elif p.name.endswith(".meta.json"):
                names.add(p.name.removesuffix(".meta.json"))
    return names


def title_slug(title: str, existing: Iterable[str] | None = None) -> str:
    return unique_slug(base_slug(title), existing_slugs() if existing is None else existing)
