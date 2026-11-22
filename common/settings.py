"""Local settings: secrets in `.env`, preferences in `config/settings.json`. Both are gitignored.

Every module reads settings through `load()` so the UI, CLI and scheduler agree. Secrets are
never returned unmasked by `public_view()`, which is what the UI's GET endpoint uses.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from common import ROOT

ENV_FILE = ROOT / ".env"
SETTINGS_FILE = ROOT / "config" / "settings.json"
SECRETS_DIR = ROOT / "config" / "secrets"  # OAuth tokens, client_secret.json

# Secret keys live in .env. Anything matching these names is masked in the UI.
SECRET_KEYS = (
    "GEMINI_API_KEY",
    "OPENAI_API_KEY",
    "INSTAGRAM_ACCESS_TOKEN",
    "TIKTOK_ACCESS_TOKEN",
)
ENV_KEYS = (
    *SECRET_KEYS,
    "OLLAMA_HOST",
    "OPENAI_BASE_URL",
    "INSTAGRAM_USER_ID",
)

DEFAULTS: dict[str, Any] = {
    "llm": {
        "provider": "gemini",  # gemini | ollama | openai
        "gemini_model": "gemini-4-hydrogen",
        # Tried in order when the chosen model is retired (404) or rate limited.
        "gemini_fallback_models": ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"],
        "ollama_model": "qwen2.5:7b",
        "openai_model": "gpt-4o-mini",
        "temperature": 0.8,
        # Google Search grounding for case studies/stats. Free-tier Gemini refuses it; scripts then fall back
        # to ungrounded writing and every numeric claim is marked unverified.
        "grounding": True,
    },
    "defaults": {
        "aspect_ratio": "9:16",
        "style": "concept_explainer",
        "music_mood": "documentary",
        "voice_engine": "edge-tts",
        "voice": "en-US-AndrewNeural",
        "rate": "+5%",
        "target_duration_sec": 50,
        "language": "English",
        "niche": "",
        "brand": "default",
    },
    "publish": {
        # cookie = social-auto-upload browser session (works today); api = official platform API
        "youtube": {"method": "cookie", "account": "main", "visibility": "unlisted"},
        "instagram": {"method": "cookie", "account": "main"},
        "tiktok": {"method": "cookie", "account": "main", "privacy_level": "SELF_ONLY"},
        "graph_api_version": "v23.0",
    },
    "clipper": {"speaker_tracking": False},
    # weekly: the scheduler daemon syncs views/likes every Monday 09:00 (yt-dlp). channel_url matches videos by title.
    "analytics": {"weekly": False, "channel_url": ""},
}


def _deep_merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in over.items():
        out[k] = _deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def read_env_file(path: Path | None = None) -> dict[str, str]:
    path = path or ENV_FILE  # resolved at call time, so tests/tools can relocate ENV_FILE
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        m = re.match(r"^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$", line)
        if m and not line.lstrip().startswith("#"):
            values[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return values


def env(name: str, default: str = "") -> str:
    """Process environment wins over .env, so CI or a shell export can override."""
    return os.environ.get(name) or read_env_file().get(name, default)


def load() -> dict[str, Any]:
    prefs = json.loads(SETTINGS_FILE.read_text(encoding="utf-8")) if SETTINGS_FILE.exists() else {}
    return _deep_merge(DEFAULTS, prefs)


def save_prefs(update: dict[str, Any]) -> dict[str, Any]:
    merged = _deep_merge(load(), update)
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    return merged


def save_env(update: dict[str, str]) -> None:
    """Write only known keys. Empty string deletes a key. Never logs values."""
    unknown = set(update) - set(ENV_KEYS)
    if unknown:
        raise ValueError(f"unknown setting(s): {', '.join(sorted(unknown))}")
    for value in update.values():
        if "\n" in value or "\r" in value:
            raise ValueError("values must be a single line")
    current = read_env_file()
    for k, v in update.items():
        if v == "":
            current.pop(k, None)
        else:
            current[k] = v.strip()
    lines = ["# video-factory local secrets. Gitignored. Edit here or in the UI Settings tab."]
    lines += [f"{k}={v}" for k, v in sorted(current.items())]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if os.name != "nt":
        ENV_FILE.chmod(0o600)


def mask(value: str) -> str:
    if not value:
        return ""
    return "•" * 8 + value[-4:] if len(value) > 8 else "•" * len(value)


def public_view() -> dict[str, Any]:
    """Settings safe to send to the browser: secrets masked, plus which ones are set."""
    file_env = read_env_file()
    env_view = {}
    for k in ENV_KEYS:
        v = os.environ.get(k) or file_env.get(k, "")
        env_view[k] = {"set": bool(v), "value": mask(v) if k in SECRET_KEYS else v}
    return {"prefs": load(), "env": env_view}
