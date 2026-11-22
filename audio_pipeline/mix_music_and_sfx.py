"""Mix a mood-matched royalty-free music bed under the narration with auto-ducking.

Music source order:
  1. Local library (audio_pipeline/music_library/manifest.json), picked by mood.
  2. Archive.org public-domain / CC0 audio, downloaded and cached (keyless).
  3. Optional local ACE-Step generation: drop a WAV/MP3 into the mood folder and
     add it to manifest.json. See docs/ADDING_STYLES.md.

FFmpeg `sidechaincompress` lowers the music whenever the narrator speaks, then
`loudnorm` (two pass) normalizes the master to -14 LUFS.

Usage:
    python audio_pipeline/mix_music_and_sfx.py --narration studio/public/assets/narration.wav \
        --mood documentary --out studio/public/assets
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

from common import (  # noqa: E402
    MUSIC_LIBRARY,
    media_duration,
    read_json,
    run,
    safe_replace,
    sha256_file,
    sha256_text,
    which,
    write_json,
)

MOODS = ("chill", "documentary", "upbeat", "dramatic")
TARGET_LUFS = -14.0
TAIL_SEC = 0.5
CACHE_DIR = MUSIC_LIBRARY.parent / "cache"
USER_AGENT = "video-factory/1.0 (https://github.com/ElwinGonsalves/video-factory; local zero-API video tool)"


def load_manifest() -> list[dict[str, Any]]:
    path = MUSIC_LIBRARY / "manifest.json"
    if not path.exists():
        return []
    return read_json(path).get("tracks", [])


def pick_local_track(mood: str, seed: str) -> dict[str, Any] | None:
    candidates = [t for t in load_manifest() if t.get("mood") == mood and (MUSIC_LIBRARY / t["file"]).exists()]
    if not candidates:
        return None
    index = int(sha256_text(seed, mood)[:8], 16) % len(candidates)
    return candidates[index]


def fetch_archive_track(mood: str) -> dict[str, Any] | None:
    """Download one public-domain/CC0 instrumental from Archive.org and register it in the manifest."""
    query = f"mediatype:audio AND (licenseurl:*publicdomain* OR licenseurl:*zero*) AND subject:({mood} instrumental)"
    try:
        res = requests.get(
            "https://archive.org/advancedsearch.php",
            params={"q": query, "fl[]": ["identifier", "title", "creator", "licenseurl"], "rows": 5, "output": "json"},
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        docs = res.json()["response"]["docs"]
        for doc in docs:
            meta = requests.get(f"https://archive.org/metadata/{doc['identifier']}", timeout=30).json()
            mp3s = [f for f in meta.get("files", []) if f.get("name", "").lower().endswith(".mp3")]
            if not mp3s:
                continue
            name = mp3s[0]["name"]
            safe = re.sub(r"[^A-Za-z0-9._-]+", "_", f"{doc['identifier']}_{Path(name).name}")
            dest = MUSIC_LIBRARY / mood / safe
            dest.parent.mkdir(parents=True, exist_ok=True)
            with requests.get(f"https://archive.org/download/{doc['identifier']}/{name}", stream=True, timeout=60) as r:
                r.raise_for_status()
                with dest.open("wb") as fh:
                    for chunk in r.iter_content(1 << 16):
                        fh.write(chunk)
            track = {
                "file": f"{mood}/{safe}",
                "mood": mood,
                "bpm": None,
                "license": str(doc.get("licenseurl", "public domain / CC0")),
                "source": f"https://archive.org/details/{doc['identifier']}",
                "title": str(doc.get("title", doc["identifier"])),
                "artist": str(doc.get("creator", "unknown")),
            }
            manifest = {"tracks": [*load_manifest(), track]}
            write_json(MUSIC_LIBRARY / "manifest.json", manifest)
            return track
    except (requests.RequestException, KeyError, ValueError):
        return None
    return None


WIKIMEDIA_OK_LICENSES = ("public domain", "cc0", "cc by", "cc-by")  # no NC/ND, no share-alike surprises in SA


def fetch_wikimedia_track(mood: str) -> dict[str, Any] | None:
    """Public-domain / CC0 / CC-BY instrumental from Wikimedia Commons (keyless), saved as MP3."""
    try:
        res = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "format": "json",
                "generator": "search",
                "gsrnamespace": 6,
                "gsrsearch": f"{mood} instrumental music filetype:audio",
                "gsrlimit": 10,
                "prop": "imageinfo",
                "iiprop": "url|extmetadata|mime|size",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        pages = (res.json().get("query", {}) or {}).get("pages", {}).values()
        for page in pages:
            info = (page.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata", {})
            lic = str(meta.get("LicenseShortName", {}).get("value", "")).lower()
            if not any(ok in lic for ok in WIKIMEDIA_OK_LICENSES) or "nc" in lic.split("-") or "nd" in lic.split("-"):
                continue
            if not info.get("url") or int(info.get("size", 0)) > 40_000_000:
                continue
            stem = re.sub(r"[^A-Za-z0-9._-]+", "_", page["title"].removeprefix("File:"))[:80]
            raw = CACHE_DIR / f"wm_{stem}"
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with requests.get(info["url"], headers={"User-Agent": USER_AGENT}, stream=True, timeout=120) as r:
                r.raise_for_status()
                with raw.open("wb") as fh:
                    for chunk in r.iter_content(1 << 16):
                        fh.write(chunk)
            dest = MUSIC_LIBRARY / mood / (Path(stem).stem + ".mp3")
            dest.parent.mkdir(parents=True, exist_ok=True)
            run([which("ffmpeg"), "-y", "-v", "error", "-i", str(raw), "-vn", "-ac", "2", "-b:a", "192k", str(dest)])
            raw.unlink(missing_ok=True)
            artist = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "unknown")).strip()
            track = {
                "file": f"{mood}/{dest.name}",
                "mood": mood,
                "bpm": None,
                "license": meta.get("LicenseShortName", {}).get("value", "see source"),
                "source": info.get("descriptionurl", ""),
                "title": page["title"].removeprefix("File:"),
                "artist": artist or "unknown",
            }
            write_json(MUSIC_LIBRARY / "manifest.json", {"tracks": [*load_manifest(), track]})
            return track
    except (requests.RequestException, KeyError, ValueError, RuntimeError):
        return None
    return None


def choose_track(mood: str, seed: str) -> dict[str, Any]:
    """Local library first, then Archive.org, then Wikimedia Commons, then any local mood."""
    track = pick_local_track(mood, seed) or fetch_archive_track(mood) or fetch_wikimedia_track(mood)
    if track is None:
        # Last resort: any local track, so a render never fails on a missing mood.
        for other in MOODS:
            track = pick_local_track(other, seed)
            if track:
                break
    if track is None:
        raise RuntimeError("No music available. Run `python scripts/seed_music.py`.")
    return track


def build_filter(duration: float, sfx: list[dict[str, Any]], music_volume: float) -> str:
    """Ducked music + narration (+ optional SFX) mix graph, ending in [out]."""
    fade_out_start = max(0.0, duration - 1.2)
    parts = [
        f"[0:a]apad=pad_dur={TAIL_SEC:.3f},asplit=2[vo][vo_sc]",
        f"[1:a]atrim=0:{duration:.3f},asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.6,"
        f"afade=t=out:st={fade_out_start:.3f}:d=1.2,volume={music_volume}[music_base]",
        "[music_base][vo_sc]sidechaincompress=threshold=0.02:ratio=6:attack=30:release=350[music_ducked]",
    ]
    mix_inputs = ["[vo]", "[music_ducked]"]
    for i, cue in enumerate(sfx):
        delay_ms = int(float(cue.get("at", 0)) * 1000)
        vol = float(cue.get("volume", 0.6))
        parts.append(f"[{i + 2}:a]adelay={delay_ms}|{delay_ms},volume={vol}[sfx{i}]")
        mix_inputs.append(f"[sfx{i}]")
    n = len(mix_inputs)
    parts.append(f"{''.join(mix_inputs)}amix=inputs={n}:duration=first:dropout_transition=0:normalize=0[out]")
    return ";".join(parts)


def measure_lufs(path: Path) -> float:
    """Integrated loudness (LUFS) via FFmpeg loudnorm's JSON report."""
    res = run(
        [which("ffmpeg"), "-hide_banner", "-i", str(path), "-af", "loudnorm=print_format=json", "-f", "null", "-"]
    )
    blob = res.stderr[res.stderr.rfind("{") : res.stderr.rfind("}") + 1]
    return float(json.loads(blob)["input_i"])


def normalize(src: Path, dest: Path, target: float = TARGET_LUFS) -> float:
    """Gain to target LUFS with a -1.5 dBTP true-peak limiter, iterating to within 0.5 LU.

    Two-pass `loudnorm` falls back to dynamic mode on short clips whose peaks would clip
    under linear gain, and then undershoots. Measured gain plus a limiter converges instead.
    """
    current = src
    level = measure_lufs(current)
    for i in range(4):
        gain = target - level
        if abs(gain) <= 0.5 and current != src:
            break
        nxt = dest.with_name(f"{dest.stem}.pass{i}.wav")
        run(
            [
                which("ffmpeg"), "-y", "-hide_banner", "-i", str(current),
                "-af", f"volume={gain:.2f}dB,alimiter=limit=0.84:level=false:attack=5:release=50",
                "-ar", "48000", "-ac", "2", str(nxt),
            ]
        )  # fmt: skip
        if current != src:
            current.unlink(missing_ok=True)
        current = nxt
        level = measure_lufs(current)
    safe_replace(current, dest)
    return level


def music_gain(music: Path) -> float:
    """Linear gain that brings a track to TARGET_LUFS (library tracks vary by 30 dB).

    Measured on the first 60 s once per file and cached by content hash.
    """
    cache_file = CACHE_DIR / "music_lufs.json"
    cache = read_json(cache_file) if cache_file.exists() else {}
    key = sha256_file(music)
    if key not in cache:
        clip = CACHE_DIR / f"{key[:16]}.{os.getpid()}.probe.wav"  # pid: concurrent runs never share it
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        run([which("ffmpeg"), "-y", "-hide_banner", "-t", "60", "-i", str(music), "-ac", "2", str(clip)])
        cache[key] = measure_lufs(clip)
        clip.unlink(missing_ok=True)
        write_json(cache_file, cache)
    lufs = float(cache[key])
    if lufs < -70:  # silent file; leave it alone
        return 1.0
    return 10 ** ((TARGET_LUFS - lufs) / 20)


def mix(
    narration: Path,
    music: Path,
    out_wav: Path,
    sfx: list[dict[str, Any]] | None = None,
    music_volume: float = 0.22,
) -> float:
    """Create mixed_master.wav. Returns its duration in seconds.

    `music_volume` is relative to a loudness-matched track (-14 LUFS), so 0.22 puts the
    bed about 13 dB under the voice before ducking.
    """
    sfx = sfx or []
    ffmpeg = which("ffmpeg")
    duration = media_duration(narration) + TAIL_SEC
    music_volume = round(music_volume * music_gain(music), 5)
    inputs = ["-i", str(narration), "-stream_loop", "-1", "-i", str(music)]
    for cue in sfx:
        inputs += ["-i", str(cue["file"])]
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    raw = out_wav.with_name(f"{out_wav.stem}.raw.wav")
    graph = build_filter(duration, sfx, music_volume)
    run([ffmpeg, "-y", "-hide_banner", *inputs, "-filter_complex", graph, "-map", "[out]",
         "-ar", "48000", "-ac", "2", str(raw)])  # fmt: skip
    normalize(raw, out_wav)
    raw.unlink(missing_ok=True)
    return media_duration(out_wav)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--narration", type=Path, required=True)
    p.add_argument("--mood", default="documentary", choices=MOODS)
    p.add_argument("--out", type=Path, required=True, help="Directory for mixed_master.wav and attribution.json")
    p.add_argument("--seed", default="", help="Changes which track is picked for a mood")
    p.add_argument("--music-volume", type=float, default=0.22)
    p.add_argument("--sfx-json", type=Path, help='JSON list: [{"file": "...", "at": 1.2, "volume": 0.6}]')
    args = p.parse_args(argv)

    track = choose_track(args.mood, args.seed or args.narration.stem)
    sfx = read_json(args.sfx_json) if args.sfx_json else []
    out_wav = args.out / "mixed_master.wav"
    dur = mix(args.narration, MUSIC_LIBRARY / track["file"], out_wav, sfx, args.music_volume)
    write_json(args.out / "attribution.json", {"music": track, "sfx": sfx})
    print(f"mixed {track['file']} -> {out_wav} ({dur:.2f}s, target {TARGET_LUFS} LUFS)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
