# First video guide

**Push this repo to GitHub** (no remote was configured and `gh` was not installed during the build). Create an empty **private** repo named `video-factory` at https://github.com/new, then run:

```powershell
git remote add origin https://github.com/ElwinGonsalves/video-factory.git
git push -u origin main
```

---

All commands run from the `video-factory` folder in PowerShell.

## 1. Check the machine (30 seconds)

```powershell
.venv\Scripts\python scripts\doctor.py
```

Every `REQUIRED` line should say `PASS`. `skip` lines are optional (espeak-ng, GPU, gh, upload cookies). On a fresh clone, run `python scripts\bootstrap.py` first; it creates `.venv`, installs Node packages, clones the engines and uploader, seeds the music library and installs the skill packs.

## 2. Generate your first video (about 3-5 minutes)

A ready-made 9:16 concept + case-study Short ships in `projects/concept-001/script.json` (Netflix's DVD years, six scenes, about 35 seconds):

```powershell
.venv\Scripts\python make_video.py projects\concept-001
```

What happens:

1. Edge-TTS voices each scene and faster-whisper times every word. The audio sets the length of everything.
2. A documentary-mood track from the local library is laid under the voice, ducked while the narrator speaks, and the master is normalized to -14 LUFS.
3. Four QA stills (hook, early, mid, outro) are written to `projects\concept-001\qa\`.
4. Remotion renders `output\concept-001.mp4` (H.264 yuv420p + AAC, faststart) and writes `output\concept-001.meta.json`.

## 3. Preview it

```powershell
start output\concept-001.mp4
start projects\concept-001\qa
```

Look at the four stills for clipped text or anything in the Shorts UI area. Re-run with `--safe-zones` to draw the unsafe regions in red:

```powershell
.venv\Scripts\python make_video.py projects\concept-001 --safe-zones --skip-qa
```

For live tweaking, run `cd studio; npx remotion studio src/index.ts` and paste `projects\concept-001\props.json` into the props panel.

## 4. Make your own

Copy the example and edit the narration and visuals:

```powershell
Copy-Item -Recurse projects\concept-001 projects\my-first
notepad projects\my-first\script.json
.venv\Scripts\python make_video.py projects\my-first
```

Useful switches: `--aspect 16:9` or `--aspect 1:1`, `--style vox_documentary` or `--style whiteboard`, `--mood upbeat|chill|dramatic|documentary`. Scene types: `headline`, `stat`, `bullets`, `chart`, `image`, `quote`, `flow` (schema in `docs/ARCHITECTURE.md`).

Or ask Kiro: "Make a 50-second Short about X." The steering file `.kiro/steering/video-factory.md` tells it to write the script, run the pipeline, and inspect the QA stills.

Need real photos? Fetch keyless archive images and reference them as `image` visuals:

```powershell
.venv\Scripts\python media_pipeline\fetch_free_media.py "apollo 11 launch" --out projects\my-first\assets\media
```

## 5. One-time login for uploads

Each platform needs one manual sign-in. A browser opens; log in, then close it. Cookies are saved under `publisher\social-auto-upload\cookies\`, which is gitignored.

```powershell
.venv\Scripts\python publisher\publish.py login youtube --account main
.venv\Scripts\python publisher\publish.py check youtube --account main     # prints "valid"
.venv\Scripts\python publisher\publish.py login instagram --account main   # optional
```

## 6. Test upload (unlisted)

```powershell
.venv\Scripts\python publisher\publish.py upload output\concept-001.meta.json --platform youtube --account main --headed
```

YouTube uploads default to **unlisted**. Check the video in YouTube Studio. When you are happy, pass `--visibility public` or set `youtube_visibility: "public"` in `scheduler/schedule.yaml`.

## 7. Schedule it

```powershell
.venv\Scripts\python scheduler\run_scheduler.py list
.venv\Scripts\python scheduler\run_scheduler.py daemon
```

See `docs/SCHEDULER.md` for batches, daily caps and starting the daemon at log-on.

## If something breaks

Run `scripts\smoke_test.py` (a full 5-second render with checks) and read `docs/DEBUGGING.md`.
