"""Optional Telegram / Discord messages when an overnight batch finishes or a job fails.

Credentials live in .env (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DISCORD_WEBHOOK_URL). Sending never raises:
a notification problem must not fail a render or an upload.
"""

from __future__ import annotations

import os

import requests

from common import settings

UI_URL = "http://127.0.0.1:8765"
TIMEOUT = 15


def configured() -> dict[str, bool]:
    return {
        "telegram": bool(settings.env("TELEGRAM_BOT_TOKEN") and settings.env("TELEGRAM_CHAT_ID")),
        "discord": bool(settings.env("DISCORD_WEBHOOK_URL")),
    }


def compose(title: str, lines: list[str] | None = None, links: dict[str, str] | None = None) -> str:
    parts = [title, *(lines or [])]
    parts += [f"{label}: {url}" for label, url in (links or {}).items()]
    return "\n".join(parts)[:1900]


def send(title: str, lines: list[str] | None = None, links: dict[str, str] | None = None) -> dict[str, str]:
    """Returns {"telegram": "sent"|error text, "discord": ...} for the channels that are set up."""
    text = compose(title, lines, links)
    result: dict[str, str] = {}
    if os.environ.get("PYTEST_CURRENT_TEST") and not os.environ.get("VF_NOTIFY_IN_TESTS"):
        return {"skipped": "running under pytest"}
    if configured()["telegram"]:
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{settings.env('TELEGRAM_BOT_TOKEN')}/sendMessage",
                json={"chat_id": settings.env("TELEGRAM_CHAT_ID"), "text": text, "disable_web_page_preview": True},
                timeout=TIMEOUT,
            )
            result["telegram"] = "sent" if r.ok else f"HTTP {r.status_code}"
        except requests.RequestException as exc:
            result["telegram"] = type(exc).__name__  # the URL holds the bot token: never echo exception text
    if configured()["discord"]:
        try:
            r = requests.post(settings.env("DISCORD_WEBHOOK_URL"), json={"content": text}, timeout=TIMEOUT)
            result["discord"] = "sent" if r.ok else f"HTTP {r.status_code}"
        except requests.RequestException as exc:
            result["discord"] = type(exc).__name__
    return result
