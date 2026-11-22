"""CLI for LLM tasks (the UI runs these as logged jobs).

python -m llm.cli write-script --slug my-video --prompt "Why prices rise" [--style ... --aspect 9:16 --mood ... --duration 50]
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
from llm.tasks import write_metadata, write_script  # noqa: E402


def cmd_write_script(a: argparse.Namespace) -> int:
    prefs = settings.load()["defaults"]
    explicit = re.sub(r"[^a-z0-9_-]+", "-", a.slug.lower()).strip("-") if a.slug else ""
    if explicit and (PROJECTS / explicit / "script.json").exists() and not a.overwrite:
        print(f"{PROJECTS / explicit / 'script.json'} exists; pass --overwrite to replace it", file=sys.stderr)
        return 2
    print(f"writing script with {settings.load()['llm']['provider']} ...", flush=True)
    script = write_script(
        brief=a.prompt,
        style=a.style or prefs["style"],
        aspect=a.aspect or prefs["aspect_ratio"],
        mood=a.mood or prefs["music_mood"],
        duration_sec=a.duration or int(prefs["target_duration_sec"]),
        voice={"engine": prefs["voice_engine"], "voice": prefs["voice"], "rate": prefs["rate"]},
        language=prefs["language"],
    )
    script["platforms"] = a.platforms.split(",") if a.platforms else ["youtube"]
    slug = explicit or title_slug(script["title"])  # the slug comes from the Title only, never the prompt
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
    w.add_argument("--prompt", required=True)
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
