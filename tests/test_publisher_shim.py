"""The social-auto-upload shim: headless Chromium contexts get a normal Chrome user agent.

Regression for "YouTube login does not stay": YouTube Studio ignores a valid saved session when the
browser says HeadlessChrome, so every check read "expired" and uploads stopped at the first step.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

from publisher import publish

SHIM = Path(publish.__file__).resolve().parent / "sau_shim" / "sitecustomize.py"


def _load_shim(fake_module: types.ModuleType):  # type: ignore[no-untyped-def]
    sys.modules["patchright.async_api"] = fake_module
    try:
        spec = importlib.util.spec_from_file_location("vf_sitecustomize_test", SHIM)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod
    finally:
        sys.modules.pop("patchright.async_api", None)


def test_headless_chromium_gets_a_real_chrome_user_agent() -> None:
    seen: dict = {}

    class Browser:
        version = "141.0.7390.55"
        browser_type = types.SimpleNamespace(name="chromium")

        async def new_context(self, *a, **kw):  # type: ignore[no-untyped-def]
            seen.update(kw)
            return "ctx"

    fake = types.ModuleType("patchright.async_api")
    fake.Browser = Browser
    _load_shim(fake)
    assert asyncio.run(Browser().new_context(storage_state="x.json")) == "ctx"
    ua = seen["user_agent"]
    assert "Headless" not in ua and "Chrome/141.0.0.0" in ua and seen["storage_state"] == "x.json"


def test_explicit_user_agent_and_firefox_are_left_alone() -> None:
    seen: list[dict] = []

    class Browser:
        version = "141.0"
        browser_type = types.SimpleNamespace(name="chromium")

        async def new_context(self, *a, **kw):  # type: ignore[no-untyped-def]
            seen.append(kw)

    fake = types.ModuleType("patchright.async_api")
    fake.Browser = Browser
    _load_shim(fake)
    asyncio.run(Browser().new_context(user_agent="mine"))
    ff = Browser()
    ff.browser_type = types.SimpleNamespace(name="firefox")
    asyncio.run(ff.new_context())
    assert seen[0]["user_agent"] == "mine" and "user_agent" not in seen[1]


def test_uploader_processes_load_the_shim() -> None:
    env = publish._sau_env()
    assert str(SHIM.parent) == env["PYTHONPATH"].split(";" if sys.platform == "win32" else ":")[0]
    assert env["PYTHONUTF8"] == "1"
