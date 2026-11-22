"""Token accounting and the spend stop-limit.

Every Gemini call is logged to data/projects.db (llm_usage) with its input and output tokens. Cost is
estimated from per-model prices (USD per 1M tokens) and an editable USD to INR rate. The free tier costs
nothing; on a paid tier the monthly total is compared with `llm.spend_limit_inr` before each call, and
batches stop cleanly when it is reached.
"""

from __future__ import annotations

import contextvars
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
from typing import Any

from common import db, settings
from llm.providers import LLMError

_task: contextvars.ContextVar[str] = contextvars.ContextVar("llm_task", default="llm")

# USD per 1M tokens (thinking tokens bill as output). Editable in Settings: llm.prices.
DEFAULT_PRICES: dict[str, dict[str, float]] = {"gemini-4-hydrogen": {"input": 1.50, "output": 7.50}}

_INPUT_KEYS = (
    "promptTokenCount",
    "prompt_token_count",
    "input_tokens",
    "inputTokens",
    "prompt_tokens",
    "total_input_tokens",
)
_OUTPUT_KEYS = (
    "candidatesTokenCount",
    "candidates_token_count",
    "output_tokens",
    "outputTokens",
    "completion_tokens",
    "total_output_tokens",
)
_EXTRA_OUTPUT_KEYS = (
    "thoughtsTokenCount",
    "thoughts_token_count",
    "reasoning_tokens",
    "total_thought_tokens",
    "thought_tokens",
)
_USAGE_BLOCKS = ("usageMetadata", "usage_metadata", "usage")


class SpendLimitReached(LLMError):
    """The monthly spend limit was reached; batches stop and wait for you."""


@contextmanager
def task(name: str):  # type: ignore[no-untyped-def]
    token = _task.set(name)
    try:
        yield
    finally:
        _task.reset(token)


def tracked(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Label every model call made inside the decorated task function."""

    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def inner(*a: Any, **k: Any) -> Any:
            with task(name):
                return fn(*a, **k)

        return inner

    return deco


def _num(block: dict[str, Any], keys: tuple[str, ...]) -> int:
    for k in keys:
        v = block.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return int(v)
    return 0


def extract_usage(body: Any) -> tuple[int, int]:
    """(input_tokens, output_tokens) from a response, tolerant of both API shapes.

    generateContent reports usageMetadata; the interactions endpoint's field names are not documented, so
    any dict under a usage-like key is searched with several spellings. Missing data counts as 0.
    """
    block: dict[str, Any] | None = None

    def find(obj: Any) -> None:
        nonlocal block
        if block is not None:
            return
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in _USAGE_BLOCKS and isinstance(v, dict):
                    block = v
                    return
            for v in obj.values():
                find(v)
        elif isinstance(obj, list):
            for v in obj:
                find(v)

    find(body)
    if not block:
        return 0, 0
    return _num(block, _INPUT_KEYS), _num(block, _OUTPUT_KEYS) + _num(block, _EXTRA_OUTPUT_KEYS)


def prices_for(model: str, cfg: dict[str, Any]) -> dict[str, float]:
    table = {**DEFAULT_PRICES, **(cfg.get("prices") or {})}
    best = ""
    for name in table:
        if model.startswith(name) and len(name) > len(best):
            best = name
    return table.get(best, {"input": 0.0, "output": 0.0})


def cost_usd(model: str, input_tokens: int, output_tokens: int, cfg: dict[str, Any] | None = None) -> float:
    cfg = cfg or settings.load()["llm"]
    if cfg.get("gemini_tier", "free") == "free":
        return 0.0
    p = prices_for(model, cfg)
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000


def record(provider: str, model: str, body: Any) -> None:
    """Log one call. Never raises: accounting must not break a render."""
    try:
        tin, tout = extract_usage(body)
        cfg = settings.load()["llm"]
        db.log_usage(provider, model, _task.get(), tin, tout, cost_usd(model, tin, tout, cfg))
    except Exception:  # noqa: BLE001
        pass


def month_start() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-01")


def summary() -> dict[str, Any]:
    cfg = settings.load()["llm"]
    s = db.usage_summary(month_start())
    rate = float(cfg.get("usd_inr", 85))
    return {
        **s,
        "month": month_start()[:7],
        "spend_inr": round(s["cost_usd"] * rate, 2),
        "limit_inr": float(cfg.get("spend_limit_inr", 100)),
        "usd_inr": rate,
        "tier": cfg.get("gemini_tier", "free"),
        "prices": {**DEFAULT_PRICES, **(cfg.get("prices") or {})},
    }


def check_limit() -> None:
    """Raise SpendLimitReached when this month's estimated spend is at or over the limit (paid tier only)."""
    s = summary()
    if s["tier"] != "free" and s["limit_inr"] > 0 and s["spend_inr"] >= s["limit_inr"]:
        raise SpendLimitReached(
            f"Spend limit reached: about Rs {s['spend_inr']:.2f} used this month (limit Rs {s['limit_inr']:.0f}). "
            "Raise the limit in Settings or wait until next month."
        )
