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
| Final video + metadata | `output/<slug>.mp4`, `output/<slug>.meta.json` |
| Assets Remotion reads | `studio/public/assets/<slug>/` |
| Scheduler log (JSON lines) | `scheduler/logs/scheduler.log` |
| Scheduler state | `scheduler/state.sqlite` |
| TTS / music / media caches | `audio_pipeline/cache/`, `media_pipeline/cache/` |

Delete a cache folder to force regeneration. Nothing in the caches is needed for correctness.

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

Never commit `publisher/**/cookies/`. `.gitignore` excludes them; check with `git status` before pushing.

## Scheduler

- `python scheduler/run_scheduler.py status` shows daily cap usage, the 15 latest events and the last error of every job.
- A job is stuck as `running` after a crash: `sqlite3 scheduler/state.sqlite "UPDATE jobs SET gen_status='pending' WHERE id='x'"`, or delete `state.sqlite` to start over (history is lost; `schedule.yaml` is the source of jobs).
- A job needs `projects/<slug>/script.json`. If `script_or_prompt` is a plain prompt, the scheduler writes `prompt.txt` and retries until the agent has written the script.

## Windows and OneDrive

- `PermissionError: [WinError 32] ... being used by another process` comes from OneDrive or antivirus scanning a new file. `common.safe_replace` retries renames. If it persists, pause OneDrive sync or keep the project outside OneDrive.
- Hugging Face symlink warnings are silenced; the model cache still works without Developer Mode.
