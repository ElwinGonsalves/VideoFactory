"""Produce one video end to end from a project's script.json.

Steps (audio first, because audio duration is the master clock):
  1. Voice + word captions     audio_pipeline/make_voice_and_subs.py
  2. Ducked music, -14 LUFS    audio_pipeline/mix_music_and_sfx.py
  3. Route style -> engine     pipeline/router.py
  4. QA stills (4 frames)      projects/<slug>/qa/*.png
  5. Final render              output/<slug>.mp4 (H.264 yuv420p + AAC, faststart)
  6. Metadata                  output/<slug>.meta.json

Usage:
    python make_video.py projects/demo
    python make_video.py projects/demo --aspect 16:9 --style vox_documentary --mood dramatic
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audio_pipeline import make_voice_and_subs, mix_music_and_sfx  # noqa: E402
from common import OUTPUT, read_json, write_json  # noqa: E402
from pipeline import render  # noqa: E402
from pipeline.router import route  # noqa: E402

ASPECTS = ("9:16", "16:9", "1:1")


def build_meta(script: dict[str, Any], slug: str, mp4: Path, attribution: dict[str, Any]) -> dict[str, Any]:
    music = attribution.get("music", {})
    credit = f"Music: {music.get('title', '?')} by {music.get('artist', '?')} ({music.get('license', '?')})"
    media_credits = [
        f"{m.get('title', '')} - {m.get('author', '')} ({m.get('license', '')})" for m in attribution.get("media", [])
    ]
    description = script.get("description", script.get("title", ""))
    if media_credits:
        description += "\n\nMedia:\n" + "\n".join(media_credits)
    return {
        "slug": slug,
        "file": str(mp4),
        "title": script.get("title", slug)[:100],
        "description": description,
        "tags": script.get("tags", []),
        "platform_targets": script.get("platforms", ["youtube"]),
        "visibility": script.get("visibility", "unlisted"),
        "music_attribution": credit,
    }


def produce(
    project: Path,
    *,
    style: str | None = None,
    aspect: str | None = None,
    mood: str | None = None,
    skip_qa: bool = False,
    show_safe_zones: bool = False,
    whisper_model: str = "auto",
    device: str = "auto",
    concurrency: str | None = None,
    music_volume: float = 0.22,
) -> dict[str, Any]:
    project = project.resolve()
    script_path = project / "script.json"
    script = read_json(script_path)
    slug = script.get("slug") or project.name
    style = style or script.get("style", "concept_explainer")
    aspect = aspect or script.get("aspect_ratio", "9:16")
    mood = mood or script.get("music_mood", "documentary")
    if aspect not in ASPECTS:
        raise ValueError(f"aspect must be one of {ASPECTS}")

    if script.get("blueprint") and script.get("approval") != "approved":
        raise PermissionError(
            f"{script_path} comes from a reference blueprint but is not approved. "
            "Run `python analyzer/analyze_reference.py approve ...` after the user picks ideas."
        )
    r = route(style)
    run_dir = project / "assets"

    print(f"[1/6] voice + captions ({style}, {aspect})")
    timing = make_voice_and_subs.run_pipeline(script_path, run_dir, whisper_model=whisper_model, device=device)

    print(f"[2/6] music bed ({mood}) with ducking")
    track = mix_music_and_sfx.choose_track(mood, slug)
    sfx = script.get("sfx", [])
    mix_music_and_sfx.mix(
        run_dir / "narration.wav",
        mix_music_and_sfx.MUSIC_LIBRARY / track["file"],
        run_dir / "mixed_master.wav",
        sfx,
        music_volume,
    )
    media_attr = (
        read_json(run_dir / "media" / "attribution.json") if (run_dir / "media" / "attribution.json").exists() else []
    )
    attribution = {"music": track, "sfx": sfx, "media": media_attr}
    write_json(run_dir / "attribution.json", attribution)

    out_mp4 = OUTPUT / f"{slug}.mp4"
    if r.engine != "remotion":
        print(f"[3/6] engine {r.engine}")
        from engines import dispatch

        dispatch(r.engine, script=script, run_dir=run_dir, out_mp4=out_mp4, aspect=aspect)
    else:
        print(f"[3/6] composition {r.composition}")
        prefix = render.stage_assets(run_dir, slug)
        props = render.build_props(
            script,
            timing,
            read_json(run_dir / "captions.json"),
            aspect_ratio=aspect,
            caption_style=script.get("caption_style", r.caption_style),
            theme=r.theme,
            asset_prefix=prefix,
            show_safe_zones=show_safe_zones,
        )
        props_file = render.write_props(props, project / "props.json")
        if skip_qa:
            print("[4/6] QA stills skipped")
        else:
            stills = render.render_stills(r.composition, props_file, props["durationSec"], project / "qa")
            print(f"[4/6] QA stills -> {stills[0].parent} (inspect for clipping / safe-zone issues)")
        print(f"[5/6] rendering {out_mp4}")
        render.render_video(r.composition, props_file, out_mp4, concurrency)

    report = render.validate_mp4(out_mp4)
    meta = build_meta(script, slug, out_mp4, attribution)
    write_json(OUTPUT / f"{slug}.meta.json", meta)
    print(f"[6/6] {report['video']} | {report['audio']} | {report['duration_sec']}s -> {out_mp4}")
    return {"mp4": str(out_mp4), "meta": meta, "report": report}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("project", type=Path, help="Folder containing script.json, e.g. projects/demo")
    p.add_argument("--style", help="Overrides script.json style (see pipeline/router.py)")
    p.add_argument("--aspect", choices=ASPECTS)
    p.add_argument("--mood", choices=mix_music_and_sfx.MOODS)
    p.add_argument("--skip-qa", action="store_true", help="Skip the 4 QA still frames")
    p.add_argument("--safe-zones", action="store_true", help="Draw red safe-zone overlay (debug)")
    p.add_argument("--whisper-model", default="auto", help="auto = small.en on GPU, base.en on CPU")
    p.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    p.add_argument("--concurrency", help="Remotion render concurrency, e.g. 2 or 50%%")
    p.add_argument("--music-volume", type=float, default=0.22, help="Music bed level vs voice (0.22 = about -13 dB)")
    a = p.parse_args(argv)
    produce(
        a.project,
        style=a.style,
        aspect=a.aspect,
        mood=a.mood,
        skip_qa=a.skip_qa,
        show_safe_zones=a.safe_zones,
        whisper_model=a.whisper_model,
        device=a.device,
        concurrency=a.concurrency,
        music_volume=a.music_volume,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
