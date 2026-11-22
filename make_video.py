"""Produce one video end to end from a project's script.json.

Steps (audio first, because audio duration is the master clock):
  1. Voice + word captions     audio_pipeline/make_voice_and_subs.py
  2. Ducked music + SFX        audio_pipeline/mix_music_and_sfx.py, audio_pipeline/sfx.py (-14 LUFS)
  3. Route style -> engine     pipeline/router.py (composition, transition, look)
  4. Visual QA                 cover + hook/early/mid/outro stills, automated pixel checks -> qa/report.json
  5. Final render              output/<slug>.mp4 (H.264 yuv420p + AAC, faststart)
  6. Thumbnail + metadata      output/<slug>.thumb.jpg, output/<slug>.meta.json (LLM titles/hashtags if set up)

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

from audio_pipeline import make_voice_and_subs, mix_music_and_sfx, sfx  # noqa: E402
from common import OUTPUT, ROOT, read_json, settings, write_json  # noqa: E402
from pipeline import render  # noqa: E402
from pipeline.router import route  # noqa: E402
from pipeline.visuals import validate_script as validate_visuals  # noqa: E402

ASPECTS = ("9:16", "16:9", "1:1")


def _rel(p: Path) -> str:
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


def llm_metadata(script: dict[str, Any], platforms: list[str]) -> dict[str, Any] | None:
    """Titles/hashtags/tags from the configured LLM. Never fails a render: returns None on any error."""
    provider_name = settings.load()["llm"]["provider"]
    key = {"gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY"}.get(provider_name)
    if key and not settings.env(key):
        print(f"      metadata: {key} not set, using script fields (add it in Settings for LLM titles/hashtags)")
        return None
    try:
        from llm.tasks import write_metadata

        return write_metadata(script, platforms)
    except Exception as exc:  # noqa: BLE001
        print(f"      metadata: LLM unavailable ({str(exc)[:160]}); using script fields")
        return None


def build_meta(
    script: dict[str, Any],
    slug: str,
    mp4: Path,
    attribution: dict[str, Any],
    *,
    aspect: str,
    generated: dict[str, Any] | None = None,
    thumbnail: Path | None = None,
    qa_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    music = attribution.get("music", {})
    credit = f"Music: {music.get('title', '?')} by {music.get('artist', '?')} ({music.get('license', '?')})"
    media_credits = [
        f"{m.get('title', '')} - {m.get('author', '')} ({m.get('license', '')})" for m in attribution.get("media", [])
    ]
    g = generated or {}
    user = script.get("metadata") or {}  # edits from the Library tab always win
    description = user.get("description") or g.get("description") or script.get("description", script.get("title", ""))
    if media_credits:
        description += "\n\nMedia:\n" + "\n".join(media_credits)
    platforms = script.get("platforms", ["youtube"])
    hashtags = (
        user.get("hashtags") or g.get("hashtags") or [f"#{t.replace(' ', '')}" for t in script.get("tags", [])[:5]]
    )
    titles = g.get("titles") or [script.get("title", slug)]
    return {
        "slug": slug,
        "file": _rel(mp4),
        "aspect_ratio": aspect,
        "title": (user.get("title") or titles[0])[:100],
        "title_variants": titles,
        "hook_variants": g.get("hook_variants", []),
        "description": description,
        "hashtags": hashtags,
        "tags": user.get("tags") or g.get("tags") or script.get("tags", []),
        "pinned_comment": g.get("pinned_comment", ""),
        "thumbnail_text": g.get("thumbnail_text") or render.cover_text_for(script),
        "thumbnail": _rel(thumbnail) if thumbnail else "",
        "platform_targets": platforms,
        "visibility": script.get("visibility", settings.load()["publish"]["youtube"]["visibility"]),
        "music_attribution": credit,
        "facts_to_verify": script.get("facts_to_verify", []),
        "qa_ok": None if qa_report is None else qa_report.get("ok"),
        "metadata_source": "user" if user else ("llm" if g else "script"),
    }


def produce(
    project: Path,
    *,
    style: str | None = None,
    aspect: str | None = None,
    mood: str | None = None,
    skip_qa: bool = False,
    strict_qa: bool = False,
    show_safe_zones: bool = False,
    whisper_model: str = "auto",
    device: str = "auto",
    concurrency: str | None = None,
    music_volume: float = 0.22,
    use_llm: bool = True,
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
            f"{script_path} comes from a reference blueprint but is not approved. Approve its idea in the Ideas tab "
            "(or `python analyzer/analyze_reference.py approve ...`) first."
        )
    blueprint = (
        read_json(ROOT / script["blueprint"])
        if script.get("blueprint") and (ROOT / script["blueprint"]).exists()
        else {}
    )
    r = route(style)
    run_dir = project / "assets"
    for note in validate_visuals(script, r.look):  # text-only scenes become illustrated ones
        print(f"      visuals: {note}", flush=True)

    print(f"[1/6] voice + captions ({style}, {aspect})", flush=True)
    timing = make_voice_and_subs.run_pipeline(script_path, run_dir, whisper_model=whisper_model, device=device)

    print(f"[2/6] music bed ({mood}) with ducking + sfx", flush=True)
    track = mix_music_and_sfx.choose_track(mood, slug)
    sfx_spec = script.get("sfx", "auto")
    if sfx_spec == "auto":
        cues = sfx.auto_cues(
            timing,
            script.get("scenes", []),
            r.look,
            blueprint.get("audio_profile", {}).get("sfx_cues"),
            voice_peak_db=sfx.peak_db(run_dir / "narration.wav"),
        )
    else:
        cues = sfx_spec if isinstance(sfx_spec, list) else []
    mix_music_and_sfx.mix(
        run_dir / "narration.wav",
        mix_music_and_sfx.MUSIC_LIBRARY / track["file"],
        run_dir / "mixed_master.wav",
        cues,
        music_volume,
    )
    media_attr = (
        read_json(run_dir / "media" / "attribution.json") if (run_dir / "media" / "attribution.json").exists() else []
    )
    attribution = {"music": track, "sfx": [Path(c["file"]).stem for c in cues], "media": media_attr}
    write_json(run_dir / "attribution.json", attribution)

    out_mp4 = OUTPUT / f"{slug}.mp4"
    qa_report: dict[str, Any] | None = None
    if r.engine != "remotion":
        print(f"[3/6] engine {r.engine}", flush=True)
        from engines import dispatch

        dispatch(r.engine, script=script, run_dir=run_dir, out_mp4=out_mp4, aspect=aspect)
        print("[4/6] visual QA: n/a for this engine (inspect the video)", flush=True)
    else:
        from media_pipeline.fetch_free_media import ensure_textures

        ensure_textures()
        print(f"[3/6] composition {r.composition}", flush=True)
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
            transition=blueprint.get("pacing", {}).get("transition_style", r.transition),
        )
        props_file = render.write_props(props, project / "props.json")
        if skip_qa:
            print("[4/6] visual QA skipped", flush=True)
        else:
            qa_report = render.render_qa(r.composition, props_file, props["durationSec"], project / "qa")
            status = "PASS" if qa_report["ok"] else "ISSUES"
            print(f"[4/6] visual QA {status} -> {project / 'qa' / 'report.json'}", flush=True)
            for f in qa_report["frames"]:
                for issue in f["issues"]:
                    print(f"      {f['frame']}: {issue}", flush=True)
            if strict_qa and not qa_report["ok"]:
                raise RuntimeError("visual QA failed (--strict-qa); fix the scenes above and re-run")
        print(f"[5/6] rendering {out_mp4}", flush=True)
        render.render_video(r.composition, props_file, out_mp4, concurrency)

    report = render.validate_mp4(out_mp4)
    print("[6/6] thumbnail + metadata", flush=True)
    platforms = script.get("platforms", ["youtube"])
    generated = (
        None if (script.get("metadata") or not use_llm) else llm_metadata({**script, "aspect_ratio": aspect}, platforms)
    )
    thumb_text = (
        (script.get("metadata") or {}).get("thumbnail_text")
        or (generated or {}).get("thumbnail_text")
        or render.cover_text_for(script)
    )
    thumbnail = None
    try:
        from pipeline.thumbnail import make_thumbnail

        thumbnail = make_thumbnail(
            slug=slug, text=thumb_text, aspect=aspect, script=script, run_dir=run_dir, theme=r.theme or r.look
        )
    except Exception as exc:  # noqa: BLE001 - a missing thumbnail must not lose a finished render
        print(f"      thumbnail failed: {str(exc)[:200]}", flush=True)
    meta = build_meta(
        script, slug, out_mp4, attribution, aspect=aspect, generated=generated, thumbnail=thumbnail, qa_report=qa_report
    )
    write_json(OUTPUT / f"{slug}.meta.json", meta)
    print(f"DONE {report['video']} | {report['audio']} | {report['duration_sec']}s -> {out_mp4}", flush=True)
    return {"mp4": str(out_mp4), "meta": meta, "report": report, "qa": qa_report}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("project", type=Path, help="Folder containing script.json, e.g. projects/demo")
    p.add_argument("--style", help="Overrides script.json style (see pipeline/router.py)")
    p.add_argument("--aspect", choices=ASPECTS)
    p.add_argument("--mood", choices=mix_music_and_sfx.MOODS)
    p.add_argument("--skip-qa", action="store_true", help="Skip the visual QA stills")
    p.add_argument("--strict-qa", action="store_true", help="Stop before the final render if QA finds issues")
    p.add_argument("--safe-zones", action="store_true", help="Draw red safe-zone overlay (debug)")
    p.add_argument("--whisper-model", default="auto", help="auto = small.en on GPU, base.en on CPU")
    p.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    p.add_argument("--concurrency", help="Remotion render concurrency, e.g. 2 or 50%%")
    p.add_argument("--music-volume", type=float, default=0.22, help="Music bed level vs voice (0.22 = about -13 dB)")
    p.add_argument("--no-llm", action="store_true", help="Do not call the LLM for titles/hashtags")
    a = p.parse_args(argv)
    produce(
        a.project,
        style=a.style,
        aspect=a.aspect,
        mood=a.mood,
        skip_qa=a.skip_qa,
        strict_qa=a.strict_qa,
        show_safe_zones=a.safe_zones,
        whisper_model=a.whisper_model,
        device=a.device,
        concurrency=a.concurrency,
        music_volume=a.music_volume,
        use_llm=not a.no_llm,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
