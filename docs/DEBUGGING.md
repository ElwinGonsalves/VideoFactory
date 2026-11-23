# Debugging

Start with the two scripts:

```powershell
.venv\Scripts\python scripts\doctor.py       # what is installed / missing
.venv\Scripts\python scripts\smoke_test.py   # 5 s real render, checks codec, loudness, ducking
```

## Where things are written

| Artifact | Path |
| --- | --- |
| Narration, captions, timing, mix | `projects/<slug>/assets/` |
| Remotion props for the run | `projects/<slug>/props.json` |
| QA stills (hook/early/mid/outro) | `projects/<slug>/qa/*.png` |
| Final video, thumbnail, metadata | `output/<project_id>/<project_id>.mp4`, `.thumb.jpg`, `.meta.json` |
| Library index, idea history, analytics, Gemini token log | `data/projects.db` |
| Assets Remotion reads | `studio/public/assets/<slug>/` |
| Scheduler log (JSON lines) | `scheduler/logs/scheduler.log` |
| Scheduler state | `scheduler/state.sqlite` |
| TTS / music / media caches | `audio_pipeline/cache/`, `media_pipeline/cache/` |

Delete a cache folder to force regeneration. Nothing in the caches is needed for correctness.

## Keep the project outside OneDrive
Renders write thousands of files and SQLite (`scheduler/state.sqlite`, `data/projects.db`) needs reliable file locks. OneDrive syncs and locks files while they are written, which shows up as `PermissionError` on rename, `database is locked`, or a render that stalls. Move the whole folder to a non-synced path such as `C:\dev\video-factory` (copy it, run `python scripts\doctor.py`, delete the old one). `doctor.py` lists this as an optional check. If you must stay, `common.safe_replace` retries renames, but expect occasional slowness.

## UI errors
| Message in the UI | Meaning and fix |
| --- | --- |
| **Server not reachable.** Is `python ui/server.py` running? | The page cannot connect. Start the server again and reload the tab. |
| **The server did not answer within 30 s.** | Calls time out after 30 s (uploads 120 s). The server is probably busy; heavy work runs as background jobs, so retry and watch the log panel. |
| A message plus a grey hint (HTTP 4xx/5xx) | The API always answers `{detail, hint}`. 401 means the page is from an old server run: reload. 500 means a bug: the full traceback is in the console running `ui/server.py`. |
| Library video does not play | The player uses `GET /api/projects/<id>/stream` (HTTP 206). Check `Accept-Ranges: bytes` in the browser's network tab. One `<video>` exists at a time, so the browser's 6-connections-per-host limit is no longer exhausted. |

Cross-origin calls are accepted only from `http://127.0.0.1:<port>` and `http://localhost:<port>`, and every call still needs the per-launch token.

## Gemini grounding, tokens and spend
- **Google Search grounding is not on the free tier.** The script is written without it and every numeric claim is `verified: false`; the Safe-Publish Gate then holds the upload until you approve it.
- Each Gemini call is logged to `llm_usage` in `data/projects.db` (input and output tokens; thinking tokens count as output). Settings shows this month's estimate in rupees. Choose *Paid* and a stop limit (default Rs 100) to make batches pause cleanly when it is reached; the free tier costs Rs 0 and is not limited here. Prices per model and the USD to INR rate are editable. `sqlite3 data\projects.db "SELECT model, SUM(input_tokens), SUM(output_tokens) FROM llm_usage GROUP BY model"`.
- Token field names on the `interactions` endpoint are not documented; they are parsed defensively and count as 0 when absent.

## FFmpeg and codec errors

| Symptom | Fix |
| --- | --- |
| `ffmpeg not found on PATH` | `winget install Gyan.FFmpeg`, then open a new terminal |
| ffprobe reports `yuvj420p` | The render must pass `--color-space=bt709` (`pipeline/render.py` does). Old renders: `ffmpeg -i in.mp4 -c:v libx264 -pix_fmt yuv420p -c:a copy out.mp4` |
| `Unknown encoder 'libx264'` | Use a "full" FFmpeg build (gyan.dev full or BtbN GPL) |
| `No such filter: 'sidechaincompress'` | Same: use a full build. `doctor.py` checks this |
| Upload preview stalls at start | The moov atom is at the end. `faststart()` in `pipeline/render.py` fixes it; for other files run `ffmpeg -i in.mp4 -c copy -movflags +faststart out.mp4` |
| `subtitles` filter fails on Windows paths (clipper) | Paths need escaped colons. `clipper_engine.write_ass` handles it; keep the project path free of `'` quotes |

## Text-to-speech

| Symptom | Fix |
| --- | --- |
| `edge_tts.exceptions.NoAudioReceived` | The Edge endpoint drops some requests. `synth_edge` retries 5 times with backoff. If every attempt fails, check the voice name (`edge-tts --list-voices`) and your network or VPN |
| Kokoro: `No module named kokoro` | `pip install -r requirements-optional.txt` |
| Kokoro non-English voices mispronounce or fail | Kokoro's dependency `espeakng-loader` bundles espeak-ng (verified with Spanish `ef_dora`). If it is missing, `pip install espeakng-loader`, or install system espeak-ng (`winget install eSpeak-NG.eSpeak-NG`, needs admin) |
| Wrong-language captions with Kokoro | The voice id's first letter sets the Whisper language (`a`/`b` English, `e` Spanish, `f` French, `h` Hindi, `i` Italian, `j` Japanese, `p` Portuguese, `z` Chinese); non-English uses the multilingual model |
| Want a different voice | Set `voice` in `script.json`. Edge examples: `en-US-AndrewNeural`, `en-US-AvaNeural`, `en-GB-RyanNeural`. Kokoro: `af_heart`, `am_michael` |

## GPU (NVIDIA) for faster-whisper and Kokoro

This machine (RTX 4050 Laptop, driver 580.97) runs both on the GPU. Nothing needs a system CUDA Toolkit; only the NVIDIA driver plus pip packages inside `.venv`:

| Component | What provides CUDA | Install |
| --- | --- | --- |
| faster-whisper (ctranslate2 4.x) | `nvidia-cublas-cu12`, `nvidia-cudnn-cu12` (CUDA 12 cuBLAS + cuDNN 9 DLLs) | `pip install -r requirements-gpu.txt` |
| Kokoro (torch) | CUDA build of torch, `torch==2.15.0+cu132` | `python scripts/bootstrap.py --gpu` |

- `common/__init__.py::register_cuda_dlls()` adds `.venv/Lib/site-packages/nvidia/*/bin` to PATH and the DLL search path on import, so ctranslate2 finds `cublas64_12.dll` and `cudnn64_9.dll`. Import `common` before loading Whisper in any new script.
- `device=auto` tries CUDA and falls back to CPU int8 with a one-line notice. `--device cpu` skips the GPU.
- Model choice: `--whisper-model auto` (default) uses `small.en` on GPU for better accuracy and `base.en` on CPU. `medium.en` fits in 6 GB VRAM if you want even better captions.
- `doctor.py` loads a real model on CUDA and runs a torch op, so its two `GPU:` lines are reliable.
- `torch.cuda.is_available()` is False after a `pip install` that pulled in a CPU torch: re-run `python scripts/bootstrap.py --gpu`. It swaps in the CUDA wheel of the same version with `--no-deps`.
- cu132 wheels need driver 580 or newer. On an older driver, use `--index-url https://download.pytorch.org/whl/cu128` with a torch version that index has (for example 2.9.1).
- Out of GPU memory (6 GB): Remotion renders in Chrome, not CUDA, so they do not compete, but avoid running two `make_video.py` at once with `medium` models.
- `TypeError: open() got an unexpected keyword argument 'metadata_errors'` comes from a PyAV/faster-whisper mismatch. The pipeline decodes audio with FFmpeg and passes NumPy arrays, so it does not depend on PyAV.
- Captions mishear a word ("Cost" for "Costs"). This only affects the on-screen text; fix the narration spelling or switch to `small.en`.

## Remotion memory, speed and concurrency

- First render downloads Chrome Headless Shell (about 100 MB). If that fails behind a proxy, run `npx remotion browser ensure` inside `studio/`.
- Out of memory or a frozen machine: `python make_video.py projects/x --concurrency 2`. Lower it further on 8 GB machines.
- Faster iteration: `--skip-qa` skips the 4 stills; preview interactively with `cd studio; npx remotion studio src/index.ts`, then paste `projects/<slug>/props.json` into the props panel.
- Type errors: `cd studio; npx tsc --noEmit`.
- Text clipping or safe-zone overlap: re-run with `--safe-zones` to draw the red unsafe regions into the QA stills, then shorten headings (aim for 6 words or fewer at 9:16) or split a scene.
- `Unexpected token '\ufeff'` in `package.json`: a file was saved with a UTF-8 BOM (Windows PowerShell 5 `Set-Content -Encoding utf8` does this). Re-save it as UTF-8 without BOM.

## Audio ducking balance

- Music level: `music_volume` (default 0.22) is relative to a loudness-matched track (-14 LUFS), so the bed sits about 13 dB under the voice before ducking. Use `--music-volume 0.15` for quieter, 0.3 for louder.
- Ducking depth and speed: edit `sidechaincompress=threshold=0.02:ratio=6:attack=30:release=350` in `audio_pipeline/mix_music_and_sfx.py`. A higher `ratio` ducks harder; a longer `release` makes the music swell back more slowly between sentences.
- Loudness: the master is normalized with measured gain and a -1.5 dBTP limiter, iterated to within 0.5 LU of -14. Check a file with `ffmpeg -i projects/x/assets/mixed_master.wav -af loudnorm=print_format=summary -f null -`.
- "Music is silent": some library tracks start quietly. The loudness match fixes most of them; otherwise pick another track by changing `--seed`, or remove the track from `manifest.json`.

## Publishing (Playwright cookies)

| Symptom | Fix |
| --- | --- |
| `cookie is missing or expired` / `check` prints `invalid` | `python publisher/publish.py login youtube --account main` opens a browser. Sign in, then close it. Cookies are saved to `publisher/social-auto-upload/cookies/youtube_main.json` |
| Cookies expire every few weeks | Re-run `login`. The scheduler retries uploads 5 times with backoff, then marks them `failed`; `run_scheduler.py retry <job>` re-queues them after you log in again |
| Instagram asks for a challenge or blocks posting | Keep `instagram_daily_cap` at 1-2, post with the browser visible (`--headed`), and log in again by hand |
| `Publisher venv missing` | `python scripts/bootstrap.py --publisher` |
| `No module named tinycss2` (or similar) in social-auto-upload | Upstream `requirements.txt` lags `pyproject.toml`; `bootstrap.py --publisher` installs both |
| Garbled Chinese text in upstream logs | Harmless. `publish.py` sets `PYTHONUTF8=1`; the upstream messages are in Chinese |
| `instagram daily cap reached (2/2 today)` (CLI exit code 3) | Caps count every post from UI, CLI and scheduler (`posts` table). Wait for tomorrow, raise the cap in Schedule → Defaults, or `publish.py upload ... --force` for one exception |
| `YouTube API not connected` | Settings → Publishing → Official API credentials: upload the Desktop-app OAuth JSON, then **Connect YouTube API** (a consent page opens). Or switch the method back to *cookie* |
| API upload succeeded but the video is private | Expected for unverified Google Cloud projects until Google's API audit passes. Use the cookie method meanwhile |
| `Instagram container failed: 400` | The token needs `instagram_content_publish` and the account must be Business/Creator; check `graph_api_version` in `config/settings.json` |
| TikTok API post is "SELF_ONLY" / private | Unaudited TikTok apps can only post privately. The TikTok adapter follows the documented Direct Post flow but has not been tested against a live account |

Never commit `publisher/**/cookies/`. `.gitignore` excludes them; check with `git status` before pushing.

## Scheduler

- `python scheduler/run_scheduler.py status` shows daily cap usage, the 15 latest events and the last error of every job.
- A job is stuck as `running` after a crash: `sqlite3 scheduler/state.sqlite "UPDATE jobs SET gen_status='pending' WHERE id='x'"`, or delete `state.sqlite` to start over (history is lost; `schedule.yaml` is the source of jobs).
- A job needs `projects/<slug>/script.json`. If `script_or_prompt` is a plain prompt, the scheduler writes `prompt.txt` and retries until the agent has written the script.

## Web UI

| Symptom | Fix |
| --- | --- |
| `missing or wrong session token; reload the page` | The server restarted and issued a new token. Reload the tab |
| `bad host` | You opened it via a hostname other than `127.0.0.1`/`localhost`. Use `http://127.0.0.1:8765`, or start with `--host 0.0.0.0` for LAN access |
| Phone cannot connect | Start with `--host 0.0.0.0`, open the printed link (it carries the token), and allow Python through Windows Firewall for private networks |
| Port in use | `python ui/server.py --port 8770` |
| A job seems stuck | Open the Status Pill → Activity Drawer → **Show log** for its live output; **Cancel** kills the whole process tree (Chrome + FFmpeg). Logs persist in `ui/logs/<job>.log` |
| Renders wait in "queued" | By design: renders, analyses and approvals run one at a time to protect GPU, RAM and Chrome |

## Language model (Gemini / Ollama / OpenAI-compatible)

| Symptom | Fix |
| --- | --- |
| `GEMINI_API_KEY is not set` | Settings → Language model → paste the key → Save. Renders still work without it (titles/hashtags fall back to script fields) |
| `Gemini rejected the API key (403)` | Regenerate the key at https://aistudio.google.com/api-keys |
| `HTTP 404 ... model not found` | Google retired the model. Settings → **List Gemini models**, put a current one in *Gemini model*. The adapter already tries `gemini_fallback_models` in `config/settings.json` |
| `HTTP 429` | Free-tier rate limit. The adapter retries with backoff and moves to the next fallback model; wait a minute or space out jobs |
| `Ollama model 'qwen2.5:7b' not found` | `ollama pull qwen2.5:7b` (~4.7 GB disk). Vision (reading reference frames) needs a vision model, e.g. `qwen2.5vl:7b` |
| Script facts look wrong | The model is told to list every number in `facts_to_verify`; the Library shows them. Edit the scene text and re-render |
| `blueprint: vision step skipped` | The provider can't read images; ideas still work from transcript + pacing. Fill `hook_first_3s.visual_pattern` by hand if you want |

## Reference analysis (yt-dlp)

| Symptom | Fix |
| --- | --- |
| `HTTP Error 429` on subtitles | Captions are best-effort now (original English only); the video still downloads. If the video itself 429s, wait and retry |
| `HTTP Error 403` / "Sign in to confirm you're not a bot" | `.venv\Scripts\python -m pip install -U yt-dlp`; for age-gated public videos add `--cookies-from-browser chrome` in `analyzer/analyze_reference.py::download` |
| Old yt-dlp is used | `common.which()` prefers `.venv\Scripts`; check with `.venv\Scripts\yt-dlp --version` |
| `exceeds the 15-sheet gate` | Use mode `hook` (first 20 s) or `condensed`, or tick "allow long videos" |

## Engines

| Symptom | Fix |
| --- | --- |
| explainroo `Error: write EOF` | Too many parallel FFmpeg pipes for free RAM. The engine uses `--workers 2`; lower with `"explainroo": {"workers": 1}` |
| explainroo first render is slow | It downloads its voice runtime/model once (~100 MB, `~/.cache/explainroo`) |
| `Timed out after 30000ms while setting up the headless browser` | Remotion Chrome start-up under memory pressure. `render_video` retries once with `--concurrency=2`; close heavy apps or pass `--concurrency 2` |
| Clipper crops off the speaker | Turn on speaker tracking (Settings → Video defaults, or `"clip": {"speaker_tracking": true}`). It follows the largest face per shot; `speaker_tracking.json` in assets shows the positions |
| Manim/handanim video has no captions | Captions are burned in from `assets/captions.json` by `engines.mux_audio`; check that file exists |
| Map scene shows no countries | Codes must be ISO A3 (`USA`, `IND`, `GBR`). `studio/public/geo/countries.geojson` must exist (`python scripts/fetch_geo.py`) |

## Node / npm

| Symptom | Fix |
| --- | --- |
| `npm error Invalid Version:` | A lockfile with empty entries. Move `studio/package-lock.json` aside and run `npm install` again (this regenerated it cleanly during the build) |
| `You can only pass the quality option if imageFormat is 'jpeg'` | Fixed in `studio/scripts/stills.mjs`; pull the latest version |

## Windows and OneDrive

- Remotion `EPERM: operation not permitted, symlink` while bundling: OneDrive turns files in `studio/public` into cloud-file reparse points, which the bundler copies as symlinks. `pipeline/render.py` now mirrors `studio/public` to `~/.video-factory/remotion-public` when the project is inside OneDrive and renders with `--public-dir`. If a file is still downloading from OneDrive the render says so; retry in a moment.
- The studio shows the old UI at `/`: `frontend/dist` is missing. Run `.\start.ps1` or `python scripts/bootstrap.py --frontend`.
- `PermissionError: [WinError 32] ... being used by another process` comes from OneDrive or antivirus scanning a new file. `common.safe_replace` retries renames. If it persists, pause OneDrive sync or keep the project outside OneDrive.
- `UnicodeEncodeError: 'charmap' codec can't encode character` came from Remotion's progress glyphs on a cp1252 console. `common` reconfigures stdout/stderr to replace unencodable characters.
- Wikimedia `HTTP 429` on every download: Wikimedia requires a descriptive User-Agent with contact info; both fetchers send `video-factory/1.0 (https://github.com/ElwinGonsalves/video-factory; ...)`. Change it if you fork the project.
- Disk space: renders need ~1 GB of temporary space. The pip cache (`%LOCALAPPDATA%\pip\cache`) and npm cache (`%LOCALAPPDATA%\npm-cache`) can be cleared safely with `pip cache purge` and `npm cache clean --force`.
- Hugging Face symlink warnings are silenced; the model cache still works without Developer Mode.
