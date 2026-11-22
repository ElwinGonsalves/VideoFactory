"""Create page: script mode keeps words verbatim, style templates, grounding with fallback."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from llm import providers as P
from llm import tasks as T
from prompts.script_templates import REGISTRY, default_aspect_for
from tests.test_llm import FakeProvider, FakeResponse
from ui import server

SCRIPT = (
    "What if nobody could ever lie? Honesty sounds great. In 2019 a survey found 60 percent of people lie daily.\n\n"
    "Now picture a world where every sentence is true. Deals close faster, but feelings get hurt. "
    "Politicians would stop talking altogether. Would you want that world, or would you miss the small kindnesses?"
)
VOICE = {"engine": "edge-tts", "voice": "v", "rate": "+0%"}


def norm(s: str) -> str:
    return " ".join(s.split())


def test_split_keeps_every_word_in_order() -> None:
    pieces = T.split_narration(SCRIPT)
    assert norm(" ".join(pieces)) == norm(SCRIPT)
    assert len(pieces) >= 3
    assert pieces[0].startswith("What if nobody")
    # the blank line is a hard scene boundary
    assert any(p.startswith("Now picture") for p in pieces)


def test_script_mode_never_uses_model_narration() -> None:
    reply = {
        "title": "Lies",
        "cover_text": "No more lies",
        "scenes": [
            {
                "index": 0,
                "beat": "hook",
                "narration": "REWRITTEN BY MODEL",
                "visual": {"type": "headline", "heading": "H"},
            }
        ],
    }
    s = T.script_from_text(SCRIPT, style="concept_explainer", aspect="9:16", mood="chill", voice=VOICE,
                           provider=FakeProvider(reply), grounding=False)  # fmt: skip
    assert norm(" ".join(sc["narration"] for sc in s["scenes"])) == norm(SCRIPT)
    assert "REWRITTEN" not in str(s["scenes"])
    assert s["title"] == "Lies" and s["input_mode"] == "script"
    assert s["scenes"][0]["visual"]["heading"] == "H"


def test_script_mode_survives_model_failure_and_keeps_user_title() -> None:
    class Down(FakeProvider):
        def generate_json(self, *a: Any, **k: Any) -> Any:
            raise P.LLMError("quota")

    msgs: list[str] = []
    s = T.script_from_text(SCRIPT, title="My title", style="whiteboard", aspect="9:16", mood="chill", voice=VOICE,
                           provider=Down({}), grounding=False, on_status=msgs.append)  # fmt: skip
    assert s["title"] == "My title" and len(s["scenes"]) >= 3
    assert any("failed" in m for m in msgs)


def test_numeric_claims_unverified_without_grounding() -> None:
    s = T.script_from_text(SCRIPT, title="t", style="concept_explainer", aspect="9:16", mood="chill", voice=VOICE,
                           provider=FakeProvider({"title": "t", "scenes": []}), grounding=True)  # fmt: skip
    assert s["grounded"] is False and s["sources"] == []
    assert s["claims"] and all(c["verified"] is False for c in s["claims"])
    assert any("60 percent" in c["text"] for c in s["claims"])
    assert s["facts_to_verify"]


class GroundedProvider(FakeProvider):
    def grounded_research(self, query: str, system: str = "") -> dict[str, Any]:
        return {
            "notes": "Netflix launched streaming in 2007.",
            "sources": [{"title": "Netflix", "url": "https://example.com/n"}],
        }


def test_write_script_with_grounding_marks_supported_claims_verified() -> None:
    reply = {
        "title": "T",
        "cover_text": "c",
        "scenes": [
            {"narration": "Netflix launched streaming in 2007.", "visual": {"type": "headline", "heading": "2007"}},
            {"narration": "It changed everything.", "visual": {"type": "headline", "heading": "x"}},
        ],
        "facts": [{"claim": "Netflix launched streaming in 2007", "supported_by_research": True}],
        "facts_to_verify": [],
    }
    s = T.write_script(brief="b", style="concept_explainer", aspect="9:16", mood="chill", duration_sec=40, voice=VOICE,
                       provider=GroundedProvider(reply))  # fmt: skip
    assert s["grounded"] is True and s["sources"][0]["url"] == "https://example.com/n"
    claim = next(c for c in s["claims"] if "2007" in c["text"])
    assert claim["verified"] is True and claim["sources"] == ["https://example.com/n"]
    assert s["facts_to_verify"] == []


def test_write_script_falls_back_when_grounding_refused() -> None:
    class Free(FakeProvider):
        def grounded_research(self, query: str, system: str = "") -> dict[str, Any]:
            raise P.GroundingUnavailable("free tier")

    reply = {
        "title": "T",
        "cover_text": "c",
        "scenes": [
            {"narration": "Sales hit 5 million units.", "visual": {"type": "headline", "heading": "5M"}},
            {"narration": "Then they fell.", "visual": {"type": "headline", "heading": "x"}},
        ],
        "facts": [{"claim": "Sales hit 5 million units", "supported_by_research": True}],
    }
    status: list[str] = []
    s = T.write_script(brief="b", style="concept_explainer", aspect="9:16", mood="chill", duration_sec=40, voice=VOICE,
                       provider=Free(reply), on_status=status.append)  # fmt: skip
    assert s["grounded"] is False
    assert all(c["verified"] is False for c in s["claims"])  # the model's own "supported" claim is not trusted
    assert "ungrounded" in status[0]


def test_gemini_grounding_parsing_and_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    g = P.GeminiProvider("gemini", "m", api_key="k")
    body = {
        "candidates": [
            {
                "content": {"parts": [{"text": "notes"}]},
                "groundingMetadata": {
                    "groundingChunks": [
                        {"web": {"uri": "https://a.test/1", "title": "A"}},
                        {"web": {"uri": "https://a.test/1"}},
                    ],
                    "webSearchQueries": ["q"],
                },
            }
        ]
    }
    seen: dict[str, Any] = {}

    def ok(url: str, payload: dict, headers: dict, attempts: int = 4) -> FakeResponse:
        seen["tools"] = payload["tools"]
        return FakeResponse(200, body)

    monkeypatch.setattr(P, "_post", ok)
    r = g.grounded_research("q")
    assert seen["tools"] == [{"google_search": {}}]
    assert r["sources"] == [{"title": "A", "url": "https://a.test/1"}] and r["notes"] == "notes"
    monkeypatch.setattr(P, "_post", lambda *a, **k: FakeResponse(403, text="grounding not available on free tier"))
    with pytest.raises(P.GroundingUnavailable):
        g.grounded_research("q")
    with pytest.raises(P.GroundingUnavailable):
        FakeProvider({}).grounded_research("q")


def test_templates_have_native_beats() -> None:
    assert REGISTRY.for_style("case_study").beat_ids == ["hook", "mechanism", "case_study", "takeaway"]
    assert REGISTRY.for_style("vox_documentary").beat_ids == ["cold_open", "context", "turning_point", "synthesis"]
    assert REGISTRY.for_style("hand_drawn").beat_ids == ["problem", "draw_steps", "recap"]
    assert REGISTRY.for_style("stickman").beat_ids == ["setup", "escalation", "punchline"]
    assert REGISTRY.for_style("long_form").beat_ids[0:3] == ["hook", "intro", "chapter_1"]
    assert default_aspect_for("long_form") == "16:9" and default_aspect_for("stickman") is None
    block = REGISTRY.for_style("vox_documentary").prompt_block(60)
    assert "Cold Open" in block and 'beat "turning_point"' in block


def test_reference_blueprint_inherits_beats() -> None:
    bp = {
        "style_name": "my_ref",
        "aspect_ratio": "16:9",
        "beat_template": [
            {"beat": "teaser", "pct_duration": 0.2, "visual_role": "face close-up"},
            {"beat": "payoff", "pct_duration": 0.8, "visual_role": "chart"},
        ],
    }
    t = REGISTRY.for_style("reference_blueprint", bp)
    assert t.beat_ids == ["teaser", "payoff"] and t.default_aspect == "16:9" and t.inherited_from == "my_ref"
    assert "face close-up" in t.prompt_block(50)


def test_write_endpoint_validates_script_mode() -> None:
    c = TestClient(server.app, base_url="http://127.0.0.1:8765")
    h = {"X-VF-Token": server.TOKEN}
    assert c.post("/api/projects/write", headers=h, json={"mode": "script", "script": "too short"}).status_code == 400
    assert c.post("/api/projects/write", headers=h, json={"mode": "idea", "prompt": " "}).status_code == 400
    assert c.post("/api/projects/write", headers=h, json={"mode": "bogus"}).status_code == 400
    opts = c.get("/api/options", headers=h).json()
    assert "stickman" in opts["styles"] and opts["templates"]["long_form"]["default_aspect"] == "16:9"
