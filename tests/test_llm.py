"""LLM layer with a fake HTTP transport and a fake provider: no network, no key needed."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from llm import providers as P
from llm import tasks as T


class FakeResponse:
    def __init__(self, status: int, body: Any = None, text: str = "") -> None:
        self.status_code, self._body, self.text, self.headers = status, body, text or str(body), {}

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> Any:
        return self._body


class FakeProvider(P.Provider):
    def __init__(self, reply: Any) -> None:
        super().__init__("fake", "fake-1")
        self.reply, self.prompts = reply, []

    def generate_json(self, prompt: str, schema: dict[str, Any], system: str = "") -> Any:
        self.prompts.append(prompt)
        return self.reply

    def vision_json(self, prompt: str, schema: dict[str, Any], images: list[Path], system: str = "") -> Any:
        self.prompts.append(prompt)
        return self.reply


def test_extract_json_variants() -> None:
    assert P.extract_json('{"a": 1}') == {"a": 1}
    assert P.extract_json('```json\n{"a": 2}\n```') == {"a": 2}
    assert P.extract_json('Sure! Here it is: {"a": 3} hope that helps') == {"a": 3}
    with pytest.raises(P.LLMError):
        P.extract_json("no json here")


def test_find_text_skips_thoughts_and_input() -> None:
    body = {
        "input": "echo",
        "outputs": [{"type": "thought", "text": "thinking..."}, {"type": "text", "text": '{"ok": true}'}],
    }
    assert P._find_text(body) == '{"ok": true}'
    legacy = {"candidates": [{"content": {"parts": [{"thought": True, "text": "x"}, {"text": "answer"}]}}]}
    assert P._find_text(legacy) == "answer"


def test_gemini_falls_back_to_next_model_and_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_post(url: str, payload: dict, headers: dict, attempts: int = 4) -> FakeResponse:
        calls.append(url.rsplit("/", 1)[-1])
        if "old-model" in url or payload.get("model") == "old-model":
            return FakeResponse(404, text="model not found")
        if url.endswith("/interactions"):
            return FakeResponse(400, text="bad request")
        return FakeResponse(200, {"candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}]})

    monkeypatch.setattr(P, "_post", fake_post)
    g = P.GeminiProvider("gemini", "old-model", api_key="k", fallbacks=["new-model"])
    assert g.generate_json("hi", {"type": "object"}) == {"ok": True}
    assert g.model == "new-model"
    assert calls == ["interactions", "old-model:generateContent", "interactions", "new-model:generateContent"]


def test_gemini_bad_key_is_clear(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(P, "_post", lambda *a, **k: FakeResponse(403, text="denied"))
    with pytest.raises(P.LLMError, match="GEMINI_API_KEY"):
        P.GeminiProvider("gemini", "m", api_key="k").generate_text("hi")
    with pytest.raises(P.LLMError, match="not set"):
        P.GeminiProvider("gemini", "m", api_key="").generate_text("hi")


def test_ollama_missing_model_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(P, "_post", lambda *a, **k: FakeResponse(404, text="not found"))
    with pytest.raises(P.LLMError, match="ollama pull qwen2.5:7b"):
        P.OllamaProvider("ollama", "qwen2.5:7b").generate_text("hi")


def test_write_script_normalizes_sloppy_output() -> None:
    reply = {
        "title": "  A  very long title " + "x" * 200,
        "cover_text": "Big hook",
        "scenes": [
            {"narration": "Hook line.", "visual": {"type": "nonsense", "heading": "H"}},
            {
                "narration": "Stats.",
                "visual": {"type": "chart", "data": [{"label": "a", "value": "3"}, {"label": "b", "value": 5}]},
            },
            {"narration": "Bad chart.", "visual": {"type": "chart", "data": [{"label": "a"}]}},
            {"narration": "", "visual": {"type": "headline"}},
            {"narration": "Map.", "visual": {"type": "map", "countries": ["usa", "IN", "BRA"]}},
        ],
        "facts_to_verify": ["X grew 3x"],
    }
    script = T.write_script(
        brief="b",
        style="concept_explainer",
        aspect="9:16",
        mood="chill",
        duration_sec=45,
        voice={},
        provider=FakeProvider(reply),
    )
    assert len(script["title"]) <= 100
    kinds = [s["visual"]["type"] for s in script["scenes"]]
    assert kinds == ["headline", "chart", "headline", "map"]  # empty narration dropped, bad chart -> headline
    assert script["scenes"][1]["visual"]["data"][0]["value"] == 3.0
    assert script["scenes"][3]["visual"]["countries"] == ["USA", "BRA"]
    assert script["facts_to_verify"] == ["X grew 3x"]


def test_write_script_rejects_empty() -> None:
    with pytest.raises(P.LLMError):
        T.write_script(
            brief="b",
            style="s",
            aspect="9:16",
            mood="chill",
            duration_sec=30,
            voice={},
            provider=FakeProvider({"scenes": []}),
        )


def test_metadata_hashtags_and_tag_limits() -> None:
    reply = {
        "titles": ["One", "Two", "Three", "Four"],
        "hook_variants": ["h1"],
        "thumbnail_text": "Big",
        "description": "d",
        "hashtags": ["money", "#Money", "finance tips", "#a", "#b", "#c", "#d", "#e", "#f", "#g"],
        "tags": ["t" * 29] * 30,
    }
    meta = T.write_metadata({"title": "T", "scenes": []}, ["youtube"], provider=FakeProvider(reply))
    assert meta["titles"] == ["One", "Two", "Three"]
    assert meta["hashtags"][0] == "#shorts" and len(meta["hashtags"]) <= 8
    assert "#financetips" in meta["hashtags"]
    assert sum(len(t) + 2 for t in meta["tags"]) <= 480


def test_ideas_validation() -> None:
    idea = {
        "title": "T",
        "hook": "H",
        "angle": "A",
        "case_study": "C",
        "style": "not_a_style",
        "music_mood": "loud",
        "why_it_works": "W",
    }
    ideas = T.generate_ideas(blueprint=None, provider=FakeProvider({"ideas": [idea] * 6}))
    assert len(ideas) == 5 and ideas[0]["style"] == "concept_explainer" and ideas[0]["music_mood"] == "documentary"
    assert [i["n"] for i in ideas] == [1, 2, 3, 4, 5]


def test_reference_frames_fills_blueprint() -> None:
    bp = {"hook_first_3s": {"visual_pattern": "TODO", "verbal_pattern": "said"}, "pacing": {"caption_style": "none"}}
    reply = {
        "visual_pattern": "Close-up face",
        "visual_vs_verbal_contrast": "C",
        "on_screen_text": ["WOW"],
        "visual_style_notes": "n",
        "caption_style": "word_highlight",
    }
    out = T.read_reference_frames(bp, [Path("x.jpg")], "said", provider=FakeProvider(reply))
    assert (
        out["hook_first_3s"]["visual_pattern"] == "Close-up face" and out["hook_first_3s"]["verbal_pattern"] == "said"
    )
    assert out["pacing"]["caption_style"] == "word_highlight" and out["on_screen_text"] == ["WOW"]
