"""Narrators and languages: the voice catalog, Hindi/Hinglish captions from the script, and the API edges."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from audio_pipeline.make_voice_and_subs import language_from_voice, script_captions
from common import voices
from ui import server

H = {"X-VF-Token": server.TOKEN}


@pytest.fixture
def client() -> TestClient:
    return TestClient(server.app, base_url="http://127.0.0.1:8765", raise_server_exceptions=False)


def test_each_language_has_voices_and_a_default() -> None:
    for key, lang in voices.LANGUAGES.items():
        assert lang["default_voice"] in voices.VOICE_IDS
        assert any(v["lang"] == key for v in voices.VOICES)


def test_styles_get_their_own_narrator_and_line() -> None:
    a, b = voices.voice_for("vox_documentary", "english"), voices.voice_for("stickman", "english")
    assert a["voice"] != b["voice"]
    assert voices.sample_line("vox_documentary", "english") != voices.sample_line("stickman", "english")
    assert voices.voice_for("vox_documentary", "hindi")["voice"].startswith("hi-IN")
    assert voices.voice_for("stickman", "english", "hi-IN-SwaraNeural")["voice"] == "hi-IN-SwaraNeural"
    assert voices.voice_for("stickman", "english", "not-a-voice")["voice"] == voices.STYLE_NARRATOR["stickman"]["voice"]
    assert "Roman" in voices.LANGUAGES["hinglish"]["prompt"] and "Devanagari" in voices.LANGUAGES["hindi"]["prompt"]


def test_script_captions_follow_the_scene_spans() -> None:
    texts = ["सोचिए, एक रुपया कम।", "Isko left-digit effect kehte hain."]
    scenes = [{"start": 0.0, "end": 3.0}, {"start": 3.0, "end": 6.5}]
    caps = script_captions(texts, scenes)
    assert [c["word"] for c in caps] == [*texts[0].split(), *texts[1].split()]
    assert all(a["end"] <= b["start"] + 1e-9 for a, b in zip(caps, caps[1:], strict=False))
    assert caps[0]["start"] >= 0 and caps[3]["end"] <= 3.0 and caps[-1]["end"] <= 6.5


def test_whisper_language_from_indian_voices() -> None:
    assert language_from_voice("hi-IN-MadhurNeural") == "hi"
    assert language_from_voice("en-IN-NeerjaNeural") == "en"
    assert language_from_voice("hf_alpha") == "hi"


def test_options_publish_the_catalog(client: TestClient) -> None:
    body = client.get("/api/options", headers=H).json()
    assert {lang["id"] for lang in body["languages"]} == {"english", "hinglish", "hindi"}
    assert len(body["voices"]) >= 10 and "concept_explainer" in body["style_narrators"]


@pytest.mark.parametrize(("field", "value"), [("language", "klingon"), ("voice", "../../x")])
def test_write_rejects_unknown_language_or_voice(
    client: TestClient, field: str, value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(server.jobs, "submit", lambda *a, **k: pytest.fail("must not start a job"))
    res = client.post(
        "/api/projects/write", headers=H, json={"mode": "idea", "prompt": "why prices end in 99", field: value}
    )
    assert res.status_code == 400


def test_write_passes_language_and_voice(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict = {}

    class J:
        def public(self) -> dict:
            return {"id": "x"}

    monkeypatch.setattr(server.jobs, "submit", lambda kind, label, args, *a, **k: seen.update(args=args) or J())
    body = {"mode": "idea", "prompt": "why prices end in 99", "language": "hinglish", "voice": "en-IN-PrabhatNeural"}
    assert client.post("/api/projects/write", headers=H, json=body).status_code == 200
    args = seen["args"]
    assert args[args.index("--language") + 1] == "hinglish" and args[args.index("--voice") + 1] == "en-IN-PrabhatNeural"


def test_projects_report_their_stage(client: TestClient) -> None:
    rows = client.get("/api/projects", headers=H).json()
    for r in rows:
        assert r["stage"] in ("script", "rendered", "published")
        assert (r["stage"] == "script") == (not r["rendered"] and not r["published"])
        assert {"language", "voice", "duration_sec", "mtime"} <= set(r)


def test_voice_preview_defaults_to_the_style_line(
    client: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hashlib

    monkeypatch.setattr(server, "VOICE_CACHE", tmp_path)
    style, voice = "stickman", voices.STYLE_NARRATOR["stickman"]["voice"]
    text = voices.sample_line(style, "english")
    (tmp_path / f"{hashlib.sha1(f'{voice}|{text}'.encode()).hexdigest()[:20]}.mp3").write_bytes(b"ID3")
    res = client.get("/api/voice/preview", params={"style": style}, headers=H)
    assert res.status_code == 200 and res.content == b"ID3"
