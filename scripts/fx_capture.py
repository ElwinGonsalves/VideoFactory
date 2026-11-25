"""Screenshot the haunted effects mid-animation (bats, It's alive!, click ghost, scroll ghost, boo, emblems)
and once with prefers-reduced-motion, into ui/logs/fx/. Test server only (default port 8766).

    .venv\\Scripts\\python.exe scripts\\fx_capture.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from playwright.sync_api import Error as PwError  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402
from ui_audit import browser_path  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8766")
    ap.add_argument("--out", default="ui/logs/fx")
    a = ap.parse_args()
    if ":8765" in a.url:
        print("refusing port 8765")
        return 2
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except PwError:
            browser = p.chromium.launch(executable_path=browser_path())
        for motion in ("no-preference", "reduce"):
            tag = "" if motion == "no-preference" else "_reduced"
            ctx = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion=motion)
            page = ctx.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)[:200]))
            page.on("console", lambda m: errors.append(m.text[:200]) if m.type == "error" else None)

            # finish the setup guide -> bats
            page.goto(f"{a.url}/#/create", wait_until="networkidle")
            page.evaluate("localStorage.clear()")
            page.reload(wait_until="networkidle")
            page.wait_for_selector("[role=dialog]")
            for _ in range(2):  # step 1 -> 2 -> 3 ("Next", then "Next" or "Continue without a key")
                page.locator("[role=dialog] [data-autofocus]").click()
                page.wait_for_timeout(250)
            page.get_by_role("button", name="Enter the lab").click()
            done = 0
            for ms in (700, 1300, 2100):
                page.wait_for_timeout(ms - done)
                done = ms
                page.screenshot(path=str(out / f"bats_{ms}{tag}.png"))
            page.wait_for_timeout(1500)

            # It's alive (Settings preview button)
            page.goto(f"{a.url}/#/settings", wait_until="networkidle")
            page.wait_for_timeout(600)
            page.get_by_role("button", name="Strike lightning").or_(page.get_by_text("Haunted effects")).first.wait_for(
                timeout=8000
            )
            strike = page.get_by_role("button", name="Strike lightning")
            if strike.count():
                strike.scroll_into_view_if_needed()
                strike.click()
                page.wait_for_timeout(180)
                page.screenshot(path=str(out / f"alive_180{tag}.png"))
                page.wait_for_timeout(450)
                page.screenshot(path=str(out / f"alive_630{tag}.png"))
            else:
                page.evaluate("window.dispatchEvent(new CustomEvent('vf:haunt', {detail: 'alive'}))")
                page.wait_for_timeout(500)
                page.screenshot(path=str(out / f"alive_500{tag}.png"))
            page.wait_for_timeout(1800)

            # click ghost on the primary button of Create
            page.goto(f"{a.url}/#/create", wait_until="networkidle")
            page.wait_for_timeout(700)
            btn = page.locator("main [data-variant=primary]").first
            btn.scroll_into_view_if_needed()
            box = btn.bounding_box()
            page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.wait_for_timeout(200)
            page.screenshot(
                path=str(out / f"click_200{tag}.png"),
                clip={"x": max(0, box["x"] - 120), "y": max(0, box["y"] - 140), "width": 360, "height": 240},
            )
            page.wait_for_timeout(250)
            page.screenshot(
                path=str(out / f"click_450{tag}.png"),
                clip={"x": max(0, box["x"] - 120), "y": max(0, box["y"] - 140), "width": 360, "height": 240},
            )

            # scroll ghost, then the boo at the bottom
            page.goto(f"{a.url}/#/settings", wait_until="networkidle")
            page.wait_for_timeout(600)
            page.mouse.wheel(0, 900)
            page.wait_for_timeout(350)
            page.screenshot(path=str(out / f"scroll{tag}.png"))
            page.mouse.wheel(0, 20000)
            page.wait_for_timeout(500)
            page.screenshot(path=str(out / f"boo{tag}.png"))
            # emblems + atmosphere, idle
            page.goto(f"{a.url}/#/schedule", wait_until="networkidle")
            page.mouse.move(700, 300)
            page.wait_for_timeout(900)
            page.screenshot(path=str(out / f"idle{tag}.png"))
            ctx.close()
        browser.close()
    for e in dict.fromkeys(errors):
        print("error:", e)
    print("captured", len(list(out.glob("*.png"))), "frames in", out)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
