"""Groq / OpenRouter providers, the fallback chain, and tolerant script parsing. No network: HTTP is faked."""

from __future__ import annotations

import json
from typing import Any

import pytest

from llm import providers, tasks
from llm.providers import ChainProvider, LLMError, OpenAICompatProvider


class Res:
    def __init__(self, status: int, body: Any = None, text: str = "") -> None:
        self.status_code, self._body, self.ok = status, body, 200 <= status < 300
        self.text = text or json.dumps(body or {})
        self.headers: dict[str, str] = {}

    def json(self) -> Any:
        return self._body


def chat(content: str) -> Res:
    return Res(200, {"choices": [{"message": {"content": content}}]})


def test_groq_uses_json_mode_and_puts_schema_in_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(providers.settings, "env", lambda k, d="": "k-123" if k == "GROQ_API_KEY" else d)
    seen: dict[str, Any] = {}

    def post(url: str, payload: dict, headers: dict, attempts: int = 4) -> Res:
        seen.update(url=url, payload=payload, headers=headers)
        return chat('{"ok": true}')

    monkeypatch.setattr(providers, "_post", post)
    p = providers.single_provider("groq")
    assert p.generate_json("hi", {"type": "object", "properties": {"ok": {"type": "boolean"}}}) == {"ok": True}
    assert seen["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert seen["payload"]["response_format"] == {"type": "json_object"}
    assert "JSON Schema" in seen["payload"]["messages"][-1]["content"]
    assert seen["headers"]["Authorization"] == "Bearer k-123"


def test_openrouter_retries_without_json_mode_and_sends_attribution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(providers.settings, "env", lambda k, d="": "k" if k == "OPENROUTER_API_KEY" else d)
    calls: list[dict] = []

    def post(url: str, payload: dict, headers: dict, attempts: int = 4) -> Res:
        calls.append(dict(payload))
        if "response_format" in payload:
            return Res(400, text='{"error": "response_format is not supported"}')
        assert headers["X-Title"] == "video-factory"
        return chat('Sure! {"ok": true}')

    monkeypatch.setattr(providers, "_post", post)
    p = providers.single_provider("openrouter")
    assert p.model.endswith(":free")
    assert p.generate_json("hi", {"type": "object"}) == {"ok": True}
    assert len(calls) == 2 and "response_format" not in calls[1]


@pytest.mark.parametrize(("status", "words"), [(401, "rejected the API key"), (429, "rate limit")])
def test_clear_errors(monkeypatch: pytest.MonkeyPatch, status: int, words: str) -> None:
    monkeypatch.setattr(providers, "_post", lambda *a, **k: Res(status, {}))
    p = OpenAICompatProvider("groq", "m", api_key="k", label="Groq", key_name="GROQ_API_KEY")
    with pytest.raises(LLMError, match=words):
        p.generate_text("hi")


def test_missing_key_names_the_right_variable() -> None:
    p = OpenAICompatProvider("groq", "m", api_key="", key_name="GROQ_API_KEY")
    with pytest.raises(LLMError, match="GROQ_API_KEY"):
        p.generate_text("hi")


class Fake(providers.Provider):
    def __init__(self, name: str, answer: Any = None, fail: str = "") -> None:
        super().__init__(name, f"{name}-model")
        self.answer, self.fail, self.calls = answer, fail, 0

    def generate_json(self, prompt: str, schema: dict, system: str = "") -> Any:
        self.calls += 1
        if self.fail:
            raise LLMError(self.fail)
        return self.answer


def test_chain_falls_through_to_the_next_brain() -> None:
    bad, good = Fake("gemini", fail="Gemini rejected the API key (403)"), Fake("groq", {"ok": 1})
    chain = ChainProvider("gemini", "x", chain=[bad, good])
    assert chain.generate_json("p", {}) == {"ok": 1}
    assert bad.calls == good.calls == 1


def test_chain_reports_every_failure() -> None:
    chain = ChainProvider("gemini", "x", chain=[Fake("gemini", fail="quota"), Fake("groq", fail="429")])
    with pytest.raises(LLMError, match=r"gemini failed \(quota\).*groq failed \(429\)"):
        chain.generate_json("p", {})


def test_get_provider_only_chains_providers_with_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = {"llm": {"provider": "gemini", "gemini_model": "g", "fallback_providers": ["groq", "openrouter"]}}
    monkeypatch.setattr(providers.settings, "load", lambda: cfg)
    monkeypatch.setattr(
        providers.settings, "env", lambda k, d="": "k" if k in ("GEMINI_API_KEY", "GROQ_API_KEY") else d
    )
    p = providers.get_provider()
    assert isinstance(p, ChainProvider) and [x.name for x in p.chain] == ["gemini", "groq"]
    assert providers.get_provider("groq").name == "groq"  # an explicit name is never chained


def test_gemini_timeout_moves_on_to_the_next_endpoint_and_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """The reported failure: /interactions read-timed out and the whole job died instead of trying on."""
    from llm import usage

    monkeypatch.setattr(usage, "check_limit", lambda: None)
    monkeypatch.setattr(usage, "record", lambda *a: None)
    tried: list[str] = []

    def post(url: str, payload: dict, headers: dict, attempts: int = 4, timeout: Any = None) -> Res:
        tried.append(url.rsplit("/", 1)[-1])
        if "slow-model" in url or url.endswith("/interactions"):
            raise LLMError("cannot reach ...: Read timed out. (read timeout=60)")
        return Res(200, {"candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}]})

    monkeypatch.setattr(providers, "_post", post)
    p = providers.GeminiProvider("gemini", "slow-model", api_key="k", fallbacks=["good-model"])
    assert p.generate_json("hi", {"type": "object"}) == {"ok": True}
    assert tried == ["slow-model:generateContent", "interactions", "good-model:generateContent"]
    assert p.model == "good-model"


# ------------------------------------------------------------------ tolerant script parsing
OPTS = {"style": "concept_explainer", "aspect": "9:16", "mood": "documentary", "voice": {}}


@pytest.mark.parametrize(
    "raw",
    [
        [{"narration": "One."}, {"narration": "Two."}],
        {"script": {"title": "T", "scenes": [{"narration": "One."}, {"narration": "Two."}]}},
        {"Scenes": ["One.", "Two."]},
    ],
)
def test_normalize_accepts_drifted_shapes(raw: Any) -> None:
    script = tasks.normalize_script(raw, **OPTS)
    assert [s["narration"] for s in script["scenes"]] == ["One.", "Two."]
