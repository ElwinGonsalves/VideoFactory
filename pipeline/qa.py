"""Automated visual QA on rendered stills.

Each QA frame is rendered twice: normally, and with `qaHideContent` (background only).
The pixel difference is exactly the scene content + captions, so we can measure:

  - safe-zone violations: content inside the 9:16 unsafe bands (bottom 22%, right 15%)
  - edge clipping: content touching the outer frame (text running off screen)
  - emptiness: a frame with almost no content (a scene failed to render)
  - cover contrast: frame 0 must be a high-contrast cover (luma std-dev)

Writes qa/<frame>.overlay.png with problems painted magenta for the UI, and returns a report.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

DIFF_THRESHOLD = 40  # per-channel difference that counts as "content"
ZONE_TOLERANCE = 0.002  # 0.2% of a band may differ (anti-aliasing, glow, drop shadows)
EDGE_PX = 3
MIN_CONTENT = 0.004
MIN_COVER_STD = 45.0


def unsafe_mask(h: int, w: int, aspect: str) -> np.ndarray:
    mask = np.zeros((h, w), dtype=bool)
    if aspect == "9:16":
        mask[int(h * 0.78) :, :] = True
        mask[:, int(w * 0.85) :] = True
    return mask


def _load(p: Path) -> np.ndarray:
    return np.asarray(Image.open(p).convert("RGB"), dtype=np.int16)


def check_frame(full: Path, bg: Path, aspect: str, name: str) -> dict[str, Any]:
    a, b = _load(full), _load(bg)
    content = np.abs(a - b).max(axis=2) > DIFF_THRESHOLD
    h, w = content.shape
    issues: list[str] = []
    bad = np.zeros_like(content)

    unsafe = unsafe_mask(h, w, aspect)
    if unsafe.any():
        frac = content[unsafe].mean()
        if frac > ZONE_TOLERANCE:
            issues.append(f"content in 9:16 unsafe zone ({frac:.1%} of band)")
            bad |= content & unsafe

    edges = np.zeros_like(content)
    edges[:EDGE_PX, :] = edges[-EDGE_PX:, :] = True
    edges[:, :EDGE_PX] = edges[:, -EDGE_PX:] = True
    if content[edges].mean() > ZONE_TOLERANCE * 5:
        issues.append("content touches the frame edge (possible clipping)")
        bad |= content & edges

    coverage = float(content.mean())
    if name != "cover" and coverage < MIN_CONTENT:
        issues.append("frame is almost empty")

    if name == "cover":
        luma = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2])[: int(h * 0.78)]
        if luma.std() < MIN_COVER_STD:
            issues.append(f"cover contrast is low (luma std {luma.std():.0f} < {MIN_COVER_STD:.0f})")

    overlay = a.astype(np.uint8).copy()
    overlay[unsafe] = (overlay[unsafe] * 0.6 + np.array([120, 0, 0]) * 0.4).astype(np.uint8)
    overlay[bad] = (255, 0, 255)
    out = full.with_name(f"{full.stem}.overlay.png")
    Image.fromarray(overlay).resize((w // 2, h // 2)).save(out)
    return {"frame": name, "ok": not issues, "issues": issues, "coverage": round(coverage, 4), "overlay": out.name}


def check_frames(out_dir: Path, frames: dict[str, int], aspect: str) -> dict[str, Any]:
    results = []
    for name, frame in frames.items():
        full, bg = out_dir / f"{name}.png", out_dir / f"_{name}.bg.png"
        res = check_frame(full, bg, aspect, name)
        res["index"] = frame
        results.append(res)
        bg.unlink(missing_ok=True)
    return {"ok": all(r["ok"] for r in results), "aspect": aspect, "frames": results}
