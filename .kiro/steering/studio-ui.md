---
inclusion: fileMatch
fileMatchPattern: "frontend/**"
---

# Studio UI (frontend/) rules

- Stack: Vite + React 19 + TypeScript + Tailwind v4 (`@theme` tokens in `frontend/src/index.css`) + lucide-react + framer-motion. FastAPI serves `frontend/dist` at `/`; the old vanilla UI stays at `/classic` (owner decision, do not delete).
- Design system: read `DESIGN.md` before changing visuals. Use the existing tokens and the primitives in `frontend/src/components/ui.tsx` (Button, LinkButton, Field, Panel, Badge, SpecimenTag, Notice...). No new colors, fonts or one-off shadows.
- Signal colors mean one thing each: volt = live/healthy, ghost violet = scheduled, candle = needs attention, blood = failure. One pumpkin primary button per view.
- Job status lives in the header Studio Status Pill and the Activity Drawer. Never add a persistent bottom jobs bar.
- Every API call goes through `src/lib/api.ts` (it adds the `X-VF-Token` header). New backend data for the pill/drawer belongs in `ui/studio.py` and `GET /api/studio`.
- Accessibility floor: visible pumpkin focus ring, labelled controls, 44px touch targets on coarse pointers, `prefers-reduced-motion` stops the seam animation, overlays use `components/Overlay.tsx` (focus trap, Escape, return focus).
- Never stop or test on port 8765 (the owner's server). Test on 8766:
  1. `cd frontend; npm run build` (runs `tsc --noEmit` first)
  2. `.venv\Scripts\python.exe ui\server.py --port 8766 --no-browser`
  3. `.venv\Scripts\python.exe scripts\ui_audit.py` must report every view clean at 375, 768, 1280 and 1440 px, then look at the screenshots in `ui/logs/ui_audit/`.
- Style Picker images are real Remotion frames. Regenerate with `scripts/render_style_cards.py`; never use stock or illustrated mockups.
