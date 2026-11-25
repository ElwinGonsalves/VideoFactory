"""Playwright multi-viewport audit of the studio UI.

    python scripts/ui_audit.py [--url http://127.0.0.1:8766] [--out ui/logs/ui_audit]

Opens every page (Create, Ideas, Batch, Library, Schedule, Settings) and the Onboarding modal, Studio
Activity drawer, Stitched Engines modal and mobile More sheet at 375x812, 768x1024, 1280x800 and
1440x900. For each view it writes a screenshot and measures:

  overflow     page wider than the viewport, or elements poking past its right edge
  clipped      text cut off by overflow without an ellipsis, or ellipsis-truncated with no title
  wrapped      buttons, badges and tabs whose label wrapped onto 2+ lines
  targets      interactive controls smaller than 24x24 CSS px (WCAG 2.5.8)
  unnamed      controls with no accessible name
  contrast     text below 4.5:1 (3:1 for large text) against its resolved background
  console      console errors and page errors
  network      failed requests and HTTP >= 400 (media aborts excluded)

Exit code 1 when any view has a finding, so it can gate a commit. Never point it at port 8765.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import Error as PwError
from playwright.sync_api import sync_playwright

VIEWS = {"mobile": (375, 812), "tablet": (768, 1024), "laptop": (1280, 800), "desktop": (1440, 900)}
PAGES = ["create", "render", "ideas", "batch", "library", "schedule", "settings"]

MEASURE = r"""
() => {
  const vw = document.documentElement.clientWidth;
  const out = {scrollW: document.documentElement.scrollWidth, vw, overflow: [], clipped: [], wrapped: [], targets: [], unnamed: [], contrast: []};
  const visible = (el) => {
    // decorative effects (coffin lids, ghosts, bolts) are aria-hidden and animate through clipping on purpose
    if (el.closest('[aria-hidden="true"]')) return false;
    // checkVisibility also covers closed <details> content (content-visibility: hidden in Chromium).
    if (el.checkVisibility && !el.checkVisibility({checkOpacity: true, checkVisibilityCSS: true, contentVisibilityAuto: true})) return false;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || Number(cs.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return false;
    if (el.closest('.sr-only') || cs.clip === 'rect(0px, 0px, 0px, 0px)' || (cs.position === 'absolute' && r.width <= 1)) return false;
    return true;
  };
  const desc = (el) => {
    const id = el.id ? '#' + el.id : '';
    const cls = (el.className && typeof el.className === 'string') ? '.' + el.className.split(/\s+/).filter(c => !c.includes(':') && !c.includes('[')).slice(0, 2).join('.') : '';
    const txt = (el.innerText || el.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ').slice(0, 50);
    return `${el.tagName.toLowerCase()}${id}${cls}${txt ? ` "${txt}"` : ''}`;
  };
  const inScroller = (el) => {
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const o = getComputedStyle(p).overflowX;
      if (o === 'auto' || o === 'scroll' || o === 'hidden') return true;
    }
    return false;
  };
  const scope = document.querySelector('[role=dialog]') || document.body;
  const all = [...scope.querySelectorAll('*')].filter(visible);
  for (const el of all) {
    const r = el.getBoundingClientRect();
    if (r.right > vw + 1 && !inScroller(el) && getComputedStyle(el).position !== 'fixed') out.overflow.push(`${desc(el)} right=${Math.round(r.right)}`);
  }
  // clipped / truncated text
  for (const el of all) {
    if (!el.childNodes.length || ![...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) continue;
    const cs = getComputedStyle(el);
    const hiddenX = cs.overflowX !== 'visible' || cs.textOverflow === 'ellipsis';
    const clampY = cs.webkitLineClamp && cs.webkitLineClamp !== 'none';
    const cutX = el.scrollWidth > el.clientWidth + 1 && hiddenX;
    const cutY = clampY && el.scrollHeight > el.clientHeight + 1;
    if (!cutX && !cutY) continue;
    const named = el.closest('[title]') || el.closest('[aria-label]');
    if (cs.textOverflow === 'ellipsis' || cutY) { if (!named) out.clipped.push(`truncated, no title: ${desc(el)}`); }
    else out.clipped.push(`clipped: ${desc(el)}`);
  }
  // text cut by an ancestor that clips (overflow hidden/clip), e.g. a card name running past its card
  const clipAncestor = (el) => {
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const cs = getComputedStyle(p);
      // A scroll container met first means the text is reachable by scrolling, not cut.
      if (['auto', 'scroll'].includes(cs.overflowX) || ['auto', 'scroll'].includes(cs.overflowY)) return null;
      if (['hidden', 'clip'].includes(cs.overflowX) || ['hidden', 'clip'].includes(cs.overflowY)) return p;
    }
    return null;
  };
  for (const el of all) {
    if (getComputedStyle(el).textOverflow === 'ellipsis' || (getComputedStyle(el).webkitLineClamp || 'none') !== 'none') continue;
    const anc = clipAncestor(el);
    if (!anc) continue;
    const box = anc.getBoundingClientRect();
    for (const n of el.childNodes) {
      if (n.nodeType !== 3 || !n.textContent.trim()) continue;
      const rg = document.createRange(); rg.selectNodeContents(n);
      const r = rg.getBoundingClientRect();
      if (r.width && (r.right > box.right + 1 || r.bottom > box.bottom + 1)) { out.clipped.push(`cut by ancestor: ${desc(el)}`); break; }
    }
  }
  // wrapped labels in compact controls: count rendered lines of each text node (Range rects)
  const lines = (node) => {
    const rg = document.createRange(); rg.selectNodeContents(node);
    const tops = [...rg.getClientRects()].filter(r => r.width > 0).map(r => Math.round(r.top));
    return new Set(tops).size;
  };
  for (const el of scope.querySelectorAll('button, [role=radio], [role=switch], a[class*="h-10"], a[class*="h-8"], span[class*="rounded-full"], nav a')) {
    if (!visible(el)) continue;
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      if (n.textContent.trim() && n.parentElement && visible(n.parentElement) && lines(n) > 1) { out.wrapped.push(desc(el)); break; }
    }
  }
  // targets + names
  const controls = scope.querySelectorAll('a[href], button, input:not([type=hidden]), select, textarea, [role=switch], [role=radio], summary, [tabindex="0"]');
  for (const el of controls) {
    // A checkbox or radio inside (or bound to) a label is hit through the whole label.
    const box = el.tagName === 'INPUT' && ['checkbox', 'radio'].includes(el.type);
    const bound = box ? (el.closest('label') || (el.id && document.querySelector(`label[for="${CSS.escape(el.id)}"]`))) : null;
    const target = bound || el;
    if (!target || !visible(target)) continue;
    const r = target.getBoundingClientRect();
    const inline = el.tagName === 'A' && el.closest('p, li, dd, dt') && getComputedStyle(el).display === 'inline';
    if (!inline && (r.width < 24 || r.height < 24)) out.targets.push(`${desc(target)} ${Math.round(r.width)}x${Math.round(r.height)}`);
    let name = el.getAttribute('aria-label') || '';
    const lb = el.getAttribute('aria-labelledby');
    if (!name && lb) name = lb.split(' ').map(i => document.getElementById(i)?.innerText || '').join(' ');
    if (!name && el.id) name = document.querySelector(`label[for="${CSS.escape(el.id)}"]`)?.innerText || '';
    if (!name) name = el.closest('label')?.innerText || '';
    if (!name) name = el.getAttribute('title') || '';
    if (!name && !['INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName)) name = el.innerText || el.querySelector('img[alt]')?.getAttribute('alt') || '';
    if (!name.trim()) out.unnamed.push(desc(el));
  }
  // contrast
  const parse = (c) => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1}; };
  const lum = ({r, g, b}) => { const f = (v) => { v /= 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const blend = (top, under) => ({r: top.r * top.a + under.r * (1 - top.a), g: top.g * top.a + under.g * (1 - top.a), b: top.b * top.a + under.b * (1 - top.a), a: 1});
  const bgOf = (el) => {
    const stack = [];
    for (let p = el; p; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if (cs.backgroundImage && cs.backgroundImage !== 'none' && !cs.backgroundImage.startsWith('linear-gradient(rgba(0, 0, 0, 0)')) return null;
      const c = parse(cs.backgroundColor);
      if (c && c.a > 0) { stack.push(c); if (c.a >= 1) break; }
    }
    let base = {r: 10, g: 15, b: 12, a: 1};
    for (let i = stack.length - 1; i >= 0; i--) base = blend(stack[i], base);
    return base;
  };
  for (const el of all) {
    if (![...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) continue;
    if (el.closest('[disabled], [aria-disabled=true], video, img')) continue;
    const cs = getComputedStyle(el);
    const fg = parse(cs.color); const bg = bgOf(el);
    if (!fg || !bg) continue;
    let opacity = 1; for (let p = el; p; p = p.parentElement) opacity *= Number(getComputedStyle(p).opacity);
    const fgb = blend({...fg, a: fg.a * opacity}, bg);
    const L1 = lum(fgb), L2 = lum(bg);
    const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const size = parseFloat(cs.fontSize); const bold = Number(cs.fontWeight) >= 600;
    const need = size >= 24 || (bold && size >= 18.66) ? 3 : 4.5;
    if (ratio < need - 0.05) out.contrast.push(`${desc(el)} ${ratio.toFixed(2)}:1 (needs ${need})`);
  }
  for (const k of ['overflow', 'clipped', 'wrapped', 'targets', 'unnamed', 'contrast']) out[k] = [...new Set(out[k])].slice(0, 12);
  return out;
}
"""


def live_studio(real: dict) -> dict:
    """The real /api/studio payload with one synthetic render job at the Render node (audit only)."""
    now = time.time()
    job = {"id": "audit-live", "kind": "render", "title": "Why Netflix Mailed DVDs for 10 Years", "status": "running",
           "created": now - 300, "started": now - 287, "ended": None, "returncode": None, "meta": {"slug": "audit-live"},
           "node": "render", "node_index": 3, "percent": 27, "done_nodes": ["script", "voice", "music"], "slug": "audit-live",
           "style": "concept_explainer", "aspect_ratio": "9:16", "elapsed_sec": 287, "pipeline": True}  # fmt: skip
    return {**real, "now": job, "running": [job]}


def browser_path() -> str | None:
    root = Path.home() / "AppData" / "Local" / "ms-playwright"
    for pattern in (
        "chromium_headless_shell-*/chrome-headless-shell-win64/chrome-headless-shell.exe",
        "chromium-*/chrome-win64/chrome.exe",
    ):
        found = sorted(root.glob(pattern))
        if found:
            return str(found[-1])
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://127.0.0.1:8766")
    ap.add_argument("--out", default="ui/logs/ui_audit")
    ap.add_argument("--only", help="comma list of views, e.g. mobile,laptop")
    a = ap.parse_args()
    if ":8765" in a.url:
        print("refusing to audit port 8765 (the owner's server)")
        return 2
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    report: dict[str, dict] = {}
    views = {k: v for k, v in VIEWS.items() if not a.only or k in a.only.split(",")}
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except PwError:
            browser = p.chromium.launch(executable_path=browser_path())
        for vname, (w, h) in views.items():
            ctx = browser.new_context(
                viewport={"width": w, "height": h},
                device_scale_factor=1,
                has_touch=vname == "mobile",
                is_mobile=vname == "mobile",
            )
            page = ctx.new_page()
            errors: list[str] = []
            failed: list[str] = []
            page.on("console", lambda m, e=errors: e.append(m.text[:200]) if m.type == "error" else None)
            page.on("pageerror", lambda exc, e=errors: e.append(f"pageerror: {str(exc)[:200]}"))
            page.on(
                "requestfailed",
                lambda r, f=failed: (
                    None
                    if re.search(r"/stream|\.mp4|/files/", r.url) or "ERR_ABORTED" in str(r.failure)
                    else f.append(f"{r.url[:120]} {r.failure}")
                ),
            )
            page.on(
                "response", lambda r, f=failed: f.append(f"HTTP {r.status} {r.url[:120]}") if r.status >= 400 else None
            )

            def snap(  # loop values bound as defaults (called within this iteration only)
                name: str, scope_full: bool = True, page=page, vname=vname, errors=errors, failed=failed
            ) -> None:
                page.wait_for_timeout(700)
                page.screenshot(path=str(out / f"{name}_{vname}.png"), full_page=scope_full)
                m = page.evaluate(MEASURE)
                m["console"], m["network"] = list(dict.fromkeys(errors)), list(dict.fromkeys(failed))
                errors.clear()
                failed.clear()
                report[f"{name}@{vname}"] = m

            # first run: onboarding modal shows itself
            page.goto(f"{a.url}/#/create", wait_until="networkidle")
            page.evaluate("localStorage.clear()")
            page.reload(wait_until="networkidle")
            page.wait_for_selector("[role=dialog]", timeout=8000)
            snap("onboarding", scope_full=False)
            page.get_by_role("button", name="Next", exact=True).click()
            snap("onboarding-step2", scope_full=False)
            page.evaluate("localStorage.setItem('vf-onboarded','1')")
            for name in PAGES:
                page.goto(f"{a.url}/#/{name}", wait_until="networkidle")
                page.reload(wait_until="networkidle")
                page.wait_for_selector("main#main", timeout=8000)
                page.wait_for_timeout(500)
                snap(name)
            # overlays
            page.goto(f"{a.url}/#/create", wait_until="networkidle")
            page.get_by_role("button", name=re.compile("^Studio activity")).click()
            page.wait_for_selector("[role=dialog]")
            snap("drawer", scope_full=False)
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
            # the same drawer mid-render: a mocked job proves the 5-node stepper lays out at this width
            page.route("**/api/studio*", lambda route: route.fulfill(json=live_studio(route.fetch().json())))
            page.route(
                "**/api/jobs/audit-live/log*",
                lambda route: route.fulfill(json={"text": "[4/6] Rendering video\nRendered 412/1500\n", "offset": 40}),
            )
            page.reload(wait_until="networkidle")
            page.get_by_role("button", name=re.compile("^Studio activity")).click()
            page.wait_for_selector("[role=dialog]")
            snap("drawer-live", scope_full=False)
            page.keyboard.press("Escape")
            page.unroute("**/api/studio*")
            page.reload(wait_until="networkidle")
            page.wait_for_timeout(300)
            if vname == "mobile":
                page.get_by_role("button", name="More", exact=True).click()
                page.wait_for_selector("[role=dialog]")
                snap("more-sheet", scope_full=False)
                page.get_by_role("dialog").get_by_role("button", name="Stitched Engines").click()
            else:
                page.get_by_role("button", name=re.compile("^Stitched Engines")).click()
            page.wait_for_selector("[role=dialog]")
            snap("engines", scope_full=False)
            ctx.close()
        browser.close()

    keys = ["overflow", "clipped", "wrapped", "targets", "unnamed", "contrast", "console", "network"]
    bad = 0
    lines = []
    for view, m in report.items():
        found = {k: m[k] for k in keys if m.get(k)}
        if m["scrollW"] > m["vw"]:
            found["overflow"] = [f"page {m['scrollW']}px > {m['vw']}px", *found.get("overflow", [])]
        if found:
            bad += 1
            lines.append(f"FAIL {view}")
            for k, v in found.items():
                lines.append(f"  {k}: " + " | ".join(v[:6]))
        else:
            lines.append(f"pass {view}")
    (out / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("\n".join(lines))
    print(f"\n{len(report) - bad}/{len(report)} views clean · screenshots in {out}")
    return 1 if bad else 0


if __name__ == "__main__":
    t0 = time.time()
    code = main()
    print(f"({time.time() - t0:.0f}s)")
    sys.exit(code)
