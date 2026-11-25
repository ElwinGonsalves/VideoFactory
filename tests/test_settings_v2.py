"""Settings v2: token logging, spend stop-limit, notifications, masked platform secrets, clipper checkbox gone."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import requests
from fastapi.testclient import TestClient

from batch import run as batch_run
from common import ROOT, db, notify, settings, write_json
from llm import providers as P
from llm import usage
from tests.test_llm import FakeResponse
from ui import server

H = {"X-VF-Token": server.TOKEN}


@pytest.fixture
def cfg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    """Paid-tier config with a Rs 100 limit, isolated from the owner's config/settings.json."""
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings, "ENV_FILE", tmp_path / ".env")
    settings.save_prefs({"llm": {"gemini_tier": "paid", "spend_limit_inr": 100, "usd_inr": 85.0}})
    return settings.load()["llm"]


def test_extract_usage_handles_both_api_shapes() -> None:
    legacy = {
        "candidates": [],
        "usageMetadata": {"promptTokenCount": 120, "candidatesTokenCount": 80, "thoughtsTokenCount": 40},
    }
    assert usage.extract_usage(legacy) == (120, 120)  # thinking tokens bill as output
    interactions = {"outputs": [], "usage": {"input_tokens": 10, "output_tokens": 5}}
    assert usage.extract_usage(interactions) == (10, 5)
    nested = {"interaction": {"usage_metadata": {"prompt_token_count": 7, "candidates_token_count": 3}}}
    assert usage.extract_usage(nested) == (7, 3)
    assert usage.extract_usage({"text": "no usage here"}) == (0, 0)
    assert usage.extract_usage("garbage") == (0, 0)


def test_cost_uses_per_model_prices_and_free_tier_is_zero(cfg: dict[str, Any]) -> None:
    assert usage.cost_usd("gemini-4-hydrogen", 1_000_000, 1_000_000, cfg) == pytest.approx(9.0)  # $1.50 + $7.50
    custom = {**cfg, "prices": {"my-model": {"input": 2.0, "output": 4.0}}}
    assert usage.cost_usd("my-model-v2", 500_000, 250_000, custom) == pytest.approx(2.0)
    assert usage.cost_usd("unknown", 1000, 1000, cfg) == 0.0
    assert usage.cost_usd("gemini-4-hydrogen", 10**6, 10**6, {**cfg, "gemini_tier": "free"}) == 0.0


def test_gemini_calls_are_logged_with_tokens(cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    body = {
        "candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}],
        "usageMetadata": {"promptTokenCount": 1000, "candidatesTokenCount": 500},
    }
    monkeypatch.setattr(P, "_post", lambda *a, **k: FakeResponse(200, body))
    with usage.task("script"):
        assert P.GeminiProvider("gemini", "gemini-4-hydrogen", api_key="k").generate_json("hi", {"type": "object"}) == {
            "ok": True
        }
    s = db.usage_summary()
    assert (s["input_tokens"], s["output_tokens"], s["calls"]) == (1000, 500, 1)
    assert s["cost_usd"] == pytest.approx((1000 * 1.5 + 500 * 7.5) / 1e6)
    with db.connect() as conn:
        assert conn.execute("SELECT task FROM llm_usage").fetchone()[0] == "script"


def test_limit_blocks_calls_at_the_cap_and_ignores_free_tier(cfg: dict[str, Any]) -> None:
    usage.check_limit()  # nothing spent yet
    db.log_usage("gemini", "gemini-4-hydrogen", "x", 0, 0, 100 / 85.0)  # exactly Rs 100 this month
    with pytest.raises(usage.SpendLimitReached, match="Spend limit reached"):
        usage.check_limit()
    with pytest.raises(usage.SpendLimitReached):
        P.GeminiProvider("gemini", "m", api_key="k").generate_text("hi")  # blocked before any request is made
    settings.save_prefs({"llm": {"gemini_tier": "free"}})
    usage.check_limit()
    settings.save_prefs({"llm": {"gemini_tier": "paid", "spend_limit_inr": 500}})
    usage.check_limit()  # raising the limit resumes work


def test_batch_pauses_cleanly_at_the_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:

    sent: list[str] = []
    calls: list[str] = []

    rendered: list[str] = []

    def fake(d: dict[str, Any]) -> str:
        calls.append(d["content"])
        if d["content"] == "second":
            raise usage.SpendLimitReached("Spend limit reached: Rs 100")
        return d["content"]

    monkeypatch.setattr(batch_run, "write_row", fake)
    monkeypatch.setattr(batch_run, "render_row", lambda slug, *a: rendered.append(slug))
    monkeypatch.setattr(notify, "send", lambda title, *a, **k: sent.append(title) or {})
    row = lambda c: {"data": {"content": c, "title": c}, "upload_at": None}  # noqa: E731
    write_json(tmp_path / "b.json", {"rows": [row("first"), row("second"), row("third")]})
    assert batch_run.main([str(tmp_path / "b.json")]) == 3
    assert calls == ["first", "second"]  # the third row was never written
    assert rendered == ["first"]  # what was written before the limit still renders
    assert sent == ["video-factory: batch paused (spend limit)"]


def test_notifications_reach_both_channels_without_leaking_the_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(settings, "ENV_FILE", tmp_path / ".env")
    monkeypatch.setenv("VF_NOTIFY_IN_TESTS", "1")
    for k, v in (
        ("TELEGRAM_BOT_TOKEN", "123:SECRET"),
        ("TELEGRAM_CHAT_ID", "42"),
        ("DISCORD_WEBHOOK_URL", "https://discord.test/hook"),
    ):
        monkeypatch.setenv(k, v)
    posted: list[tuple[str, dict]] = []

    class R:
        ok = True
        status_code = 200

    def fake_post(url: str, json: dict, timeout: int) -> R:
        posted.append((url, json))
        if "discord" in url:
            raise requests.ConnectionError(f"cannot reach {url}")
        return R()

    monkeypatch.setattr(notify.requests, "post", fake_post)
    res = notify.send("Batch finished", ["3 rendered"], {"Library": "http://127.0.0.1:8765/#library"})
    assert res == {"telegram": "sent", "discord": "ConnectionError"}
    tg = next(p for p in posted if "telegram" in p[0])
    assert tg[1]["chat_id"] == "42" and "Library: http://127.0.0.1:8765/#library" in tg[1]["text"]
    monkeypatch.delenv("VF_NOTIFY_IN_TESTS")
    assert notify.send("x") == {"skipped": "running under pytest"}


def test_platform_secrets_are_masked_and_clipper_checkbox_is_gone(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    c = TestClient(server.app, base_url="http://127.0.0.1:8765")
    secret = {
        "YOUTUBE_CLIENT_ID": "1234567890-abc.apps.googleusercontent.com",
        "YOUTUBE_CLIENT_SECRET": "GOCSPX-supersecret",
        "TELEGRAM_BOT_TOKEN": "999:tok",
    }
    assert c.put("/api/settings/secrets", headers=H, json=secret).status_code == 200
    view = c.get("/api/settings", headers=H).json()
    for k, v in secret.items():
        assert view["env"][k]["set"] is True and v not in str(view) and view["env"][k]["value"].startswith("•")
    assert (
        c.put("/api/settings/prefs", headers=H, json={"clipper": {"speaker_tracking": True}}).json()["clipper"][
            "speaker_tracking"
        ]
        is False
    )
    assert "Clipper speaker tracking" not in (ROOT / "ui/static/index.html").read_text(encoding="utf-8")
    assert "d-tracking" not in (ROOT / "ui/static/app.js").read_text(encoding="utf-8")
    assert c.get("/api/usage", headers=H).json()["tier"] == "paid"
