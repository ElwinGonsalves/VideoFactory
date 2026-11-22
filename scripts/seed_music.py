"""Seed the local mood music library from gyoridavid/short-video-maker (YouTube Audio Library tracks).

Usage: python scripts/seed_music.py

Downloads only ``static/music`` via a sparse clone, copies the MP3s into
``audio_pipeline/music_library/<mood>/`` and writes ``manifest.json``.
Tracks are free to use, including monetised videos, with no attribution required.
"""

from __future__ import annotations

import contextlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "audio_pipeline" / "music_library"
REPO = "https://github.com/gyoridavid/short-video-maker.git"
SOURCE = "gyoridavid/short-video-maker (YouTube Audio Library)"
LICENSE = "YouTube Audio Library License (free, no attribution required)"

# Upstream mood -> our four moods.
MOOD_MAP = {
    "chill": "chill",
    "hopeful": "chill",
    "melancholic": "documentary",
    "sad": "documentary",
    "contemplative": "documentary",
    "happy": "upbeat",
    "euphoric": "upbeat",
    "excited": "upbeat",
    "funny": "upbeat",
    "dark": "dramatic",
    "uneasy": "dramatic",
    "angry": "dramatic",
}

# file -> upstream mood (from upstream src/short-creator/music.ts)
TRACKS = {
    "Sly Sky - Telecasted.mp3": "melancholic",
    "No.2 Remembering Her - Esther Abrami.mp3": "melancholic",
    "Champion - Telecasted.mp3": "chill",
    "Oh Please - Telecasted.mp3": "chill",
    "Jetski - Telecasted.mp3": "uneasy",
    "Phantom - Density & Time.mp3": "uneasy",
    "On The Hunt - Andrew Langdon.mp3": "uneasy",
    "Name The Time And Place - Telecasted.mp3": "excited",
    "Delayed Baggage - Ryan Stasik.mp3": "euphoric",
    "Like It Loud - Dyalla.mp3": "euphoric",
    "Organic Guitar House - Dyalla.mp3": "euphoric",
    "Honey, I Dismembered The Kids - Ezra Lipp.mp3": "dark",
    "Night Hunt - Jimena Contreras.mp3": "dark",
    "Curse of the Witches - Jimena Contreras.mp3": "dark",
    "Restless Heart - Jimena Contreras.mp3": "sad",
    "Heartbeat Of The Wind - Asher Fulero.mp3": "sad",
    "Hopeless - Jimena Contreras.mp3": "sad",
    "Touch - Anno Domini Beats.mp3": "happy",
    "Cafecito por la Manana - Cumbia Deli.mp3": "happy",
    "Aurora on the Boulevard - National Sweetheart.mp3": "happy",
    "Buckle Up - Jeremy Korpas.mp3": "angry",
    "Twin Engines - Jeremy Korpas.mp3": "angry",
    "Hopeful - Nat Keefe.mp3": "hopeful",
    "Hopeful Freedom - Asher Fulero.mp3": "hopeful",
    "Crystaline - Quincas Moreira.mp3": "contemplative",
    "Final Soliloquy - Asher Fulero.mp3": "contemplative",
    "Seagull - Telecasted.mp3": "funny",
    "Banjo Doops - Joel Cummins.mp3": "funny",
    "Baby Animals Playing - Joel Cummins.mp3": "funny",
    "Sinister - Anno Domini Beats.mp3": "dark",
    "Traversing - Godmode.mp3": "dark",
}


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


def main() -> int:
    with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
        clone = Path(tmp) / "svm"
        _run(["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse", REPO, str(clone)])
        _run(["git", "sparse-checkout", "set", "static/music"], cwd=clone)
        src = clone / "static" / "music"
        tracks = []
        for name, upstream in sorted(TRACKS.items()):
            mood = MOOD_MAP[upstream]
            dest_dir = LIB / mood
            dest_dir.mkdir(parents=True, exist_ok=True)
            if not (src / name).exists():
                print(f"missing upstream file: {name}", file=sys.stderr)
                continue
            shutil.copy2(src / name, dest_dir / name)
            tracks.append(
                {
                    "file": f"{mood}/{name}",
                    "mood": mood,
                    "upstream_mood": upstream,
                    "bpm": None,
                    "license": LICENSE,
                    "source": SOURCE,
                    "title": name.rsplit(" - ", 1)[0],
                    "artist": name.rsplit(" - ", 1)[-1].removesuffix(".mp3"),
                }
            )
        # Remove read-only git objects so TemporaryDirectory can clean up on Windows.
        for p in clone.rglob("*"):
            with contextlib.suppress(OSError):
                p.chmod(0o700)
    (LIB / "manifest.json").write_text(json.dumps({"tracks": tracks}, indent=2), encoding="utf-8")
    print(f"seeded {len(tracks)} tracks into {LIB}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
