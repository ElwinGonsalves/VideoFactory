"""Loaded automatically by Python when publisher/publish.py starts social-auto-upload (PYTHONPATH points here).

Why: headless Chrome announces itself as "HeadlessChrome" in its user agent. YouTube Studio then never
leaves its landing page, so a perfectly valid saved login reads as "expired" and uploads stop at the
first step. Giving every Chromium context a normal Chrome user agent fixes the session check and the
uploads alike. The vendored package stays untouched (it is re-cloned by scripts/bootstrap.py).
"""

from __future__ import annotations

import importlib
import platform

_OS = {
    "Windows": "Windows NT 10.0; Win64; x64",
    "Darwin": "Macintosh; Intel Mac OS X 10_15_7",
}.get(platform.system(), "X11; Linux x86_64")


def _real_ua(version: str) -> str:
    # Chrome ships a reduced UA: only the major version, the rest zeros
    major = (version or "130").split(".")[0]
    return f"Mozilla/5.0 ({_OS}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36"


def _patch(module: str) -> None:
    try:
        mod = importlib.import_module(module)
    except Exception:  # noqa: BLE001 - the library is optional in this interpreter
        return
    browser_cls = getattr(mod, "Browser", None)
    if browser_cls is None or getattr(browser_cls.new_context, "_vf_real_ua", False):
        return
    original = browser_cls.new_context

    async def new_context(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        if "user_agent" not in kwargs and self.browser_type.name == "chromium":
            kwargs["user_agent"] = _real_ua(self.version)
        return await original(self, *args, **kwargs)

    new_context._vf_real_ua = True  # type: ignore[attr-defined]
    browser_cls.new_context = new_context


for _name in ("patchright.async_api", "playwright.async_api"):
    _patch(_name)
