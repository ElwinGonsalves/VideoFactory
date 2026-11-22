"""CLI for LLM tasks (the UI runs these as logged jobs).

python -m llm.cli write-script --prompt "Why prices rise" [--title ... --style ... --aspect 9:16 --mood ... --duration 50]
python -m llm.cli write-script --mode script --text-file my_script.txt --title "My title"   # keeps your words verbatim
python -m llm.cli metadata --slug my-video          # (re)write titles/hashtags/tags into output/<slug>.meta.json
python -m llm.cli ping                              # test the configured provider
python -m llm.cli models                            # list Gemini models available to your key
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import OUTPUT, PROJECTS, read_json, settings, write_json  # noqa: E402
from common.slugs import title_slug  # noqa: E402
from llm.providers import GeminiProvider, get_provider  # noqa: E402
from llm.tasks import script_from_text, write_metadata, write_script  # noqa: E402
from prompts.script_templates import default_aspect_for  # noqa: E402


def cmd_write_script(a: argparse.Namespace) -> int:
    cfg = settings.load()
    prefs = cfg["defaults"]
    explicit = re.sub(r"[^a-z0-9_-]+", "-", a.slug.lower()).strip("-") if a.slug else ""
    if explicit and (PROJECTS / explicit / "script.json").exists() and not a.overwrite:
        print(f"{PROJECTS / explicit / 'script.json'} exists; pass --overwrite to replace it", file=sys.stderr)
        return 2
    if a.mode == "idea" and not (a.prompt or "").strip():
        print("idea mode needs --prompt", file=sys.stderr)
        return 2
    if a.mode == "script" and not (a.text_file or (a.prompt or "").strip()):
        print("script mode needs --text-file", file=sys.stderr)
        return 2
    style = a.style or prefs["style"]
    aspect = a.aspect or default_aspect_for(style) or prefs["aspect_ratio"]
    mood = a.mood or prefs["music_mood"]
    voice = {"engine": prefs["voice_engine"], "voice": prefs["voice"], "rate": prefs["rate"]}
    ground = cfg["llm"].get("grounding", True) if a.ground is None else a.ground
    say = lambda msg: print(f"  {msg}", flush=True)  # noqa: E731
    print(
        f"{'keeping your script' if a.mode == 'script' else 'writing script'} with {cfg['llm']['provider']} ...",
        flush=True,
    )
    if a.mode == "script":
        text = Path(a.text_file).read_text(encoding="utf-8") if a.text_file else (a.prompt or "")
        script = script_from_text(
            text,
            title=a.title or "",
            style=style,
            aspect=aspect,
            mood=mood,
            voice=voice,
            grounding=ground,
            on_status=say,
        )
    else:
        script = write_script(
            brief=a.prompt or "",
            style=style,
            aspect=aspect,
            mood=mood,
            duration_sec=a.duration or int(prefs["target_duration_sec"]),
            voice=voice,
            language=prefs["language"],
            grounding=ground,
            on_status=say,
        )
        if a.title:
            script["title"] = a.title[:100]
    script["platforms"] = a.platforms.split(",") if a.platforms else ["youtube"]
    slug = explicit or title_slug(script["title"])  # the slug comes from the Title only, never prompt or script text
    proj = PROJECTS / slug
    proj.mkdir(parents=True, exist_ok=True)
    write_json(proj / "script.json", script)
    print(f"SCRIPT {proj / 'script.json'} ({len(script['scenes'])} scenes)", flush=True)
    for f in script.get("facts_to_verify", []):
        print(f"  verify: {f}", flush=True)
    return 0


def cmd_metadata(a: argparse.Namespace) -> int:
    meta_path = OUTPUT / f"{a.slug}.meta.json"
    script = read_json(PROJECTS / a.slug / "script.json")
    meta = read_json(meta_path) if meta_path.exists() else {}
    gen = write_metadata(
        {**script, "aspect_ratio": meta.get("aspect_ratio", script.get("aspect_ratio"))},
        meta.get("platform_targets", ["youtube"]),
    )
    meta.update(
        {
            "title": gen["titles"][0],
            "title_variants": gen["titles"],
            "hook_variants": gen["hook_variants"],
            "description": gen["description"],
            "hashtags": gen["hashtags"],
            "tags": gen["tags"],
            "pinned_comment": gen["pinned_comment"],
            "thumbnail_text": gen["thumbnail_text"],
            "metadata_source": "llm",
        }
    )
    write_json(meta_path, meta)
    print(f"METADATA {meta_path}: {gen['titles'][0]} | {' '.join(gen['hashtags'])}", flush=True)
    return 0


def cmd_ping(_: argparse.Namespace) -> int:
    print(get_provider().ping(), flush=True)
    return 0


def cmd_models(_: argparse.Namespace) -> int:
    p = get_provider("gemini")
    assert isinstance(p, GeminiProvider)
    for m in p.list_models():
        print(m)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write-script")
    w.add_argument(
        "--mode", choices=["idea", "script"], default="idea", help="idea: AI writes it; script: keep your text"
    )
    w.add_argument("--prompt", help="the idea (idea mode)")
    w.add_argument("--text-file", help="file holding your script (script mode)")
    w.add_argument("--title", help="video title; the project slug is built from it")
    w.add_argument("--ground", dest="ground", action="store_true", default=None, help="use Google Search grounding")
    w.add_argument("--no-ground", dest="ground", action="store_false")
    w.add_argument("--slug")
    w.add_argument("--style")
    w.add_argument("--aspect", choices=["9:16", "16:9", "1:1"])
    w.add_argument("--mood", choices=["chill", "documentary", "upbeat", "dramatic"])
    w.add_argument("--duration", type=int)
    w.add_argument("--platforms", help="comma list, e.g. youtube,instagram")
    w.add_argument("--overwrite", action="store_true")
    w.set_defaults(func=cmd_write_script)
    m = sub.add_parser("metadata")
    m.add_argument("--slug", required=True)
    m.set_defaults(func=cmd_metadata)
    sub.add_parser("ping").set_defaults(func=cmd_ping)
    sub.add_parser("models").set_defaults(func=cmd_models)
    a = p.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
