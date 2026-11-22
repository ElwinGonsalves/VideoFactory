"""OpenMontage engine: production planning + open-archive montage, rendered with Remotion.

OpenMontage (engines/openmontage) is an agent-driven planner with pipeline definitions
(documentary montage, animation, hybrid, clip factory, ...) and keyless archive retrieval.
This wrapper:
  1. Lists the available pipeline definitions (`pipelines()`), so the agent can pick one.
  2. Pulls keyless archive images for each scene's `media_query` with media_pipeline.
  3. Renders the resulting plan with the `UniversalCustom` Remotion composition.

script.json:
    "style": "hybrid_or_custom",
    "openmontage": {"pipeline": "documentary-montage", "theme": "vox"},
    "scenes": [{"narration": "...", "media_query": "apollo 11 launch"}]
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import ROOT, read_json, write_json
from media_pipeline.fetch_free_media import fetch
from pipeline import render as remotion

OM = ROOT / "engines" / "openmontage"


def pipelines() -> list[str]:
    defs = OM / "pipeline_defs"
    return sorted(p.stem for p in defs.glob("*")) if defs.exists() else []


def render(script: dict[str, Any], run_dir: Path, out_mp4: Path, aspect: str) -> Path:
    cfg = script.get("openmontage") or {}
    slug = out_mp4.stem
    media_dir = run_dir / "media"
    credits: list[dict[str, Any]] = []
    scenes = []
    for spec in script.get("scenes", []):
        spec = dict(spec)
        query = spec.get("media_query")
        if query and not spec.get("visual"):
            got = fetch(query, media_dir, count=1, media_type="image")
            if got:
                item = got[0]
                credits.append(item)
                spec["visual"] = {
                    "type": "image",
                    "src": f"assets/{slug}/media/{Path(item['file']).name}",
                    "heading": spec.get("heading", ""),
                    "credit": f"{item.get('author', '')} / {item.get('license', '')}",
                }
        scenes.append(spec)
    plan = {**script, "scenes": scenes, "openmontage_pipeline": cfg.get("pipeline", "hybrid")}
    write_json(run_dir / "production_plan.json", plan)

    prefix = remotion.stage_assets(run_dir, slug)
    props = remotion.build_props(
        plan,
        read_json(run_dir / "timing.json"),
        read_json(run_dir / "captions.json"),
        aspect_ratio=aspect,
        caption_style=script.get("caption_style", "minimal_editorial"),
        theme=cfg.get("theme", "vox"),
        asset_prefix=prefix,
    )
    props_file = remotion.write_props(props, run_dir.parent / "props.json")
    return remotion.render_video("UniversalCustom", props_file, out_mp4)
