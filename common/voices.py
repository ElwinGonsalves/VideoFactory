"""Narrators: the voice catalog, script languages, and each style's default narrator.

Edge-TTS voices are free and online; Kokoro voices are local (GPU). Hindi is written in Devanagari and
spoken by the hi-IN voices. Hinglish is conversational Hindi-English written in Latin script, which the
Indian English (en-IN) voices read naturally; the hi-IN voices can read it too.
"""

from __future__ import annotations

from typing import Any

LANGUAGES: dict[str, dict[str, str]] = {
    "english": {
        "label": "English",
        "prompt": "English",
        "default_voice": "en-US-AndrewNeural",
    },
    "hinglish": {
        "label": "Hinglish",
        "prompt": (
            "Hinglish: casual Hindi-English mix the way Indian YouTube creators talk, written ONLY in Latin "
            "(Roman) script, e.g. 'Socho, agar ek rupee kam ho toh price itna sasta kyun lagta hai?'. "
            "Never use Devanagari."
        ),
        "default_voice": "en-IN-NeerjaNeural",
    },
    "hindi": {
        "label": "हिन्दी (Hindi)",
        "prompt": (
            "Hindi written in Devanagari script. Keep brand names, numbers and common English terms "
            "(like 'startup', 'GDP') as they are; write numbers as digits."
        ),
        "default_voice": "hi-IN-MadhurNeural",
    },
}

# id, display name, engine, language key, description
VOICES: list[dict[str, str]] = [
    {"id": "en-US-AndrewNeural", "name": "Andrew", "engine": "edge-tts", "lang": "english", "about": "warm US male, explainer"},
    {"id": "en-US-AvaNeural", "name": "Ava", "engine": "edge-tts", "lang": "english", "about": "bright US female"},
    {"id": "en-US-BrianNeural", "name": "Brian", "engine": "edge-tts", "lang": "english", "about": "casual US male"},
    {"id": "en-US-EmmaNeural", "name": "Emma", "engine": "edge-tts", "lang": "english", "about": "friendly US female"},
    {"id": "en-US-ChristopherNeural", "name": "Christopher", "engine": "edge-tts", "lang": "english", "about": "deep US male, documentary"},
    {"id": "en-GB-RyanNeural", "name": "Ryan", "engine": "edge-tts", "lang": "english", "about": "British male, editorial"},
    {"id": "en-GB-SoniaNeural", "name": "Sonia", "engine": "edge-tts", "lang": "english", "about": "British female"},
    {"id": "en-AU-NatashaNeural", "name": "Natasha", "engine": "edge-tts", "lang": "english", "about": "Australian female"},
    {"id": "en-IN-PrabhatNeural", "name": "Prabhat", "engine": "edge-tts", "lang": "hinglish", "about": "Indian English male"},
    {"id": "en-IN-NeerjaNeural", "name": "Neerja", "engine": "edge-tts", "lang": "hinglish", "about": "Indian English female"},
    {"id": "hi-IN-MadhurNeural", "name": "Madhur", "engine": "edge-tts", "lang": "hindi", "about": "Hindi male"},
    {"id": "hi-IN-SwaraNeural", "name": "Swara", "engine": "edge-tts", "lang": "hindi", "about": "Hindi female"},
    {"id": "af_heart", "name": "Heart (Kokoro)", "engine": "kokoro", "lang": "english", "about": "local US female"},
    {"id": "am_michael", "name": "Michael (Kokoro)", "engine": "kokoro", "lang": "english", "about": "local US male"},
    {"id": "hf_alpha", "name": "Alpha (Kokoro)", "engine": "kokoro", "lang": "hindi", "about": "local Hindi female"},
    {"id": "hm_omega", "name": "Omega (Kokoro)", "engine": "kokoro", "lang": "hindi", "about": "local Hindi male"},
]  # fmt: skip
VOICE_IDS = {v["id"] for v in VOICES}

# Each style's own narrator and the line the Style Picker's ghost reads before you type anything.
STYLE_NARRATOR: dict[str, dict[str, str]] = {
    "concept_explainer": {"voice": "en-US-AndrewNeural", "line": "One number explains this whole business. Let me show you why."},
    "case_study": {"voice": "en-US-ChristopherNeural", "line": "In 1997, a tiny DVD-by-mail company made a bet that changed television."},
    "vox_documentary": {"voice": "en-GB-RyanNeural", "line": "On a cold morning in 1971, one decision quietly redrew the map."},
    "whiteboard": {"voice": "en-US-EmmaNeural", "line": "Grab a marker. Here is how a loan really works, step by step."},
    "stickman": {"voice": "en-US-BrianNeural", "line": "So the price doubled. Again. And Steve is not okay about it."},
    "long_form": {"voice": "en-US-ChristopherNeural", "line": "Chapter one. Before the empire, there was a garage and a terrible idea."},
    "kinetic_type": {"voice": "en-US-AvaNeural", "line": "Fast. Cheap. Everywhere. That is the whole playbook."},
    "editorial_map": {"voice": "en-GB-SoniaNeural", "line": "Watch these three countries light up as the money starts to move."},
    "news_breakdown": {"voice": "en-GB-RyanNeural", "line": "Here is what happened, what it means, and what nobody is telling you."},
    "hand_drawn": {"voice": "en-US-EmmaNeural", "line": "Let me sketch this out, because the picture makes it obvious."},
    "sketch": {"voice": "en-US-EmmaNeural", "line": "Three quick diagrams, and this will finally click."},
    "math_science": {"voice": "en-GB-SoniaNeural", "line": "Take a circle. Now ask a simple question that breaks it."},
    "algorithm": {"voice": "en-US-AndrewNeural", "line": "Step one: compare. Step two: swap. Watch the list sort itself."},
}  # fmt: skip
DEFAULT_LINE = "Ever wondered why Costco still sells a hot dog for a dollar fifty?"
HINDI_LINES = {
    "hinglish": "Socho, agar ek rupee kam ho, toh price itna sasta kyun lagta hai?",
    "hindi": "सोचिए, सिर्फ़ एक रुपया कम होने से कीमत इतनी सस्ती क्यों लगती है?",
}


def language_key(value: str | None) -> str:
    v = (value or "english").strip().lower()
    if v in LANGUAGES:
        return v
    return {"en": "english", "hi": "hindi", "हिन्दी": "hindi"}.get(v, "english")


def voice_for(style: str, language: str, chosen: str | None = None) -> dict[str, str]:
    """{engine, voice} for a new script: the user's pick, else the style's narrator (English) or the language's."""
    lang = language_key(language)
    if chosen and chosen in VOICE_IDS:
        v = next(x for x in VOICES if x["id"] == chosen)
        return {"engine": v["engine"], "voice": v["id"]}
    if lang == "english" and style in STYLE_NARRATOR:
        return {"engine": "edge-tts", "voice": STYLE_NARRATOR[style]["voice"]}
    return {"engine": "edge-tts", "voice": LANGUAGES[lang]["default_voice"]}


def sample_line(style: str, language: str) -> str:
    lang = language_key(language)
    if lang in HINDI_LINES:
        return HINDI_LINES[lang]
    return STYLE_NARRATOR.get(style, {}).get("line", DEFAULT_LINE)


def public() -> dict[str, Any]:
    return {
        "languages": [
            {"id": k, "label": v["label"], "default_voice": v["default_voice"]} for k, v in LANGUAGES.items()
        ],
        "voices": VOICES,
        "style_narrators": STYLE_NARRATOR,
        "default_line": DEFAULT_LINE,
        "language_lines": HINDI_LINES,
    }
