# Design: Studio UI v3

Visual system: `DESIGN.md` ("Film lab after midnight"). Surface brief: `.impeccable/surfaces/frontend-index-html.md`.

## Architecture

```
frontend/ (Vite + React + TS + Tailwind v4)        ui/server.py (FastAPI, localhost, X-VF-Token)
  src/lib/api.ts ── fetch + token ──────────────▶  existing /api/* (create, ideas, batch, library, schedule, settings)
  src/lib/studio.tsx  StudioProvider ── 2 s poll ─▶  GET /api/studio      ui/studio.py job_view + parse_progress
  components/Activity.tsx  pill + drawer            GET /api/engines     ui/studio.py engines() (60 s cache)
  components/Engines.tsx   badge + modal            GET /api/onboarding  key status + demo_assets()
  components/Onboarding.tsx 3 steps + Judge Demo    GET /api/demo/batch  sample.xlsx validated like an upload
  dist/ ◀── npm run build ── served at / ; ui/static served at /classic
```

## Progress model
`make_video.py` prints `[N/6]` step markers and Remotion prints `Rendered n/m`. `ui/studio.py:parse_progress` maps them onto 5 nodes:

| make_video step | node | percent |
|---|---|---|
| LLM job | Script | — |
| 1 voice + captions | Voice | 5–20 |
| 2 music + SFX | Music+SFX | 20–30 |
| 3 route, 4 QA stills, 5 final render | Render | 30–92 (frame counter inside step 5) |
| 6 validate, thumbnail, metadata | QA | 92–99 |

## Key decisions
- Hash router (`#/page?x`) with no router dependency; FastAPI keeps one HTML route.
- Panels are CSS containers, so layouts respond to panel width (the drawer and the rail change the available width).
- Style cards are real Remotion frames from `scripts/render_style_cards.py`.
- Judge Demo Mode only shows files that exist (`demo_assets()`); sample idea cards are labelled "Sample".
- OneDrive: Remotion's bundler fails on cloud-file reparse points, so `pipeline/render.py:public_dir()` mirrors `studio/public` to `~/.video-factory/remotion-public` and renders with `--public-dir`.

## Testing
- `tests/test_studio_ui.py`: progress parsing, engines, studio/onboarding/demo endpoints, `/classic`, path traversal on `/styles` and `/assets`, the OneDrive mirror.
- `scripts/ui_audit.py`: Playwright, 4 viewports, 45 views, including a mocked mid-render drawer.
