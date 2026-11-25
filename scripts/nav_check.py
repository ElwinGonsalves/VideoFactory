"""Click through every sidebar page in one tab, in every order that starts from each page, and report
any click that does not show the target page. Run against a test server (default port 8766).

    .venv\\Scripts\\python.exe scripts\\nav_check.py [--url http://127.0.0.1:8766]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from playwright.sync_api import Error as PwError  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402
from ui_audit import browser_path  # noqa: E402

PAGES = ["create", "render", "ideas", "batch", "library", "schedule", "settings"]
LABEL = {p: p.title() for p in PAGES}
# a heading only that page renders, so a stuck page (old content under the new h1) is caught
MARK = {"create": "Stitch a new video", "render": "The slab", "ideas": "Find the next video", "batch": "Feed the lab a spreadsheet",
        "library": "The vault", "schedule": "Pre-Flight", "settings": "Brain & spend"}  # fmt: skip


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8766")
    a = ap.parse_args()
    if ":8765" in a.url:
        print("refusing port 8765 (the owner's server)")
        return 2
    bad: list[str] = []
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except PwError:
            browser = p.chromium.launch(executable_path=browser_path())
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)[:200]))
        page.goto(f"{a.url}/#/create", wait_until="networkidle")
        page.evaluate("localStorage.setItem('vf-onboarded','1')")
        for start in PAGES:
            page.goto(f"{a.url}/#/{start}", wait_until="networkidle")
            page.reload(wait_until="networkidle")
            page.wait_for_timeout(800)
            for target in PAGES:
                if target == start:
                    continue
                nav = page.locator("aside nav[aria-label=Main]")
                try:
                    nav.locator(f'a[href="#/{target}"]').click(timeout=4000)
                    page.locator("main#main").get_by_text(MARK[target], exact=True).first.wait_for(timeout=4000)
                    # back to the start page the same way, so every pair starts from the start page
                    nav.locator(f'a[href="#/{start}"]').click(timeout=4000)
                    page.locator("main#main").get_by_text(MARK[start], exact=True).first.wait_for(timeout=4000)
                except PwError as exc:
                    h1 = page.evaluate("document.querySelector('h1')?.textContent")
                    inert = page.evaluate("document.getElementById('root')?.inert")
                    shown = [k for k, v in MARK.items() if page.locator("main#main").get_by_text(v, exact=True).count()]
                    why = str(exc).splitlines()[0][:90]
                    bad.append(f"{start} -> {target}: h1={h1!r} showing={shown} inert={inert} ({why})")
                    page.reload(wait_until="networkidle")
                    page.wait_for_timeout(800)
        browser.close()
    for line in bad:
        print("FAIL", line)
    for e in dict.fromkeys(errors):
        print("pageerror", e)
    n = len(PAGES) * (len(PAGES) - 1)
    print(f"{n - len(bad)}/{n} transitions ok")
    return 1 if bad or errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
