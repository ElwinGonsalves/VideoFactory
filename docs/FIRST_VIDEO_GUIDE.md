# First video guide

**Push this repo to GitHub.** The GitHub CLI is installed but not logged in (login needs your browser). In a **new** terminal, from this folder:

```powershell
gh auth login --web
gh repo create video-factory --private --source . --remote origin --push
```

Without the CLI: create an empty private repo named `video-factory` at https://github.com/new, then `git remote add origin https://github.com/ElwinGonsalves/video-factory.git` and `git push -u origin main`.

---

All commands run from the `video-factory` folder in PowerShell.

## 1. Check the machine (30 seconds)

```powershell
.venv\Scripts\python scripts\doctor.py
```

Every `REQUIRED` line should say `PASS`. `skip` lines are optional (upload cookies, an LLM key you haven't added yet, gh). On a fresh clone, run `python scripts\bootstrap.py` first. It creates `.venv`, installs Node packages, clones the engines and uploader (`scripts\setup_repos.ps1` does only that part), seeds the music library, installs the skill packs, swaps in GPU builds when an NVIDIA driver is present, and writes the handanim MCP config.

## 2. Open the UI

```powershell
.venv\Scripts\python ui\server.py
```

Your browser opens `http://127.0.0.1:8765`. The UI only listens on this computer. To preview on your phone over the same Wi-Fi, use `--host 0.0.0.0` and open the link the console prints (it contains the access token).

Five tabs:

| Tab | What you do there |
| --- | --- |
| **Create** | Type a topic → **Write script** (the LLM writes hook / concept / case study / takeaway) → edit narration and headings → **Render** |
| **Ideas** | Paste reference links → the analyzer learns their style → 5 ideas → tick the ones you want → **Approve selected** (renders them if "render after approval" is on) |
| **Library** | Watch the result, check the 5 QA frames (cover + hook/early/mid/outro, red border = an automated check failed), edit or AI-regenerate title, description, hashtags, then **Upload** |
| **Schedule** | Queue renders and uploads for later, see daily caps, start the scheduler daemon |
| **Settings** | Gemini key, video defaults, publishing logins, **System health** button |

The panel at the bottom shows the live log of whatever is running.

## 3. Add your Gemini key (one time)

Get a free key at https://aistudio.google.com/api-keys. In **Settings → Language model**, paste it into *Gemini API key*, click **Save**, then **Test connection**. The key is stored in the local `.env` file (gitignored) and shown masked afterwards.

Without a key everything still renders; only script writing, ideas and AI titles/hashtags are unavailable. Free-tier note: Google may use free-tier prompts to improve its products.

## 4. Render the example (about 3 minutes)

A ready-made 9:16 concept + case-study Short ships in `projects/concept-001` (Netflix's DVD years, 8 scenes including a world map and a chart, about 47 s). In **Create**, click **Open** on it, then **Render**. Or from the terminal:

```powershell
.venv\Scripts\python make_video.py projects\concept-001
```

What happens:

1. Edge-TTS voices each scene; faster-whisper (on your GPU) times every word. The audio sets the length of everything.
2. A documentary track from the local library is laid under the voice, ducked while the narrator speaks, with whoosh/pop sound effects at scene changes; the master is normalized to -14 LUFS.
3. Five QA stills are rendered and checked automatically: frame 0 must be a high-contrast cover, nothing may sit in the Shorts UI zones (bottom 22%, right 15%), nothing may run off the frame edge.
4. Remotion renders `output\concept-001.mp4` (H.264 yuv420p + AAC, faststart).
5. A thumbnail (`output\concept-001.thumb.jpg`) and upload metadata (`output\concept-001.meta.json`) are written. With a Gemini key, the metadata includes 3 title variants, alternative hooks, hashtags and tags.

The Library tab shows a yellow **Verify before posting** box listing the facts the script states with numbers. Check them before you publish.

## 5. Make your own

In **Create**, type a topic, for example *"Why Costco sells hot dogs for $1.50"*, pick a style (`concept_explainer`, `vox_documentary`, `whiteboard`, ...), aspect and mood, click **Write script**, edit the scenes, then **Render**.

From a reference video instead: in **Ideas**, paste one or more YouTube/Shorts/Reels/TikTok links and click **Analyze + propose ideas**. The analyzer downloads them, tiles frames into contact sheets, transcribes, measures shot pacing, lets Gemini read the frames, and saves a style blueprint. You get 5 ideas in that style; nothing renders until you approve.

Terminal equivalents: `python -m llm.cli write-script --prompt "..."` and `python analyzer\analyze_reference.py analyze <url> --style my_style`.

## 6. One-time login for uploads

In **Settings → Publishing**, click **Login** next to YouTube (and Instagram/TikTok if you use them). A browser opens; sign in, then close it. Cookies are saved under `publisher\social-auto-upload\cookies\` (gitignored). **Check** confirms they are valid.

Official APIs (optional, under *Official API credentials*) need app approval: YouTube API uploads stay private until Google audits your project, Instagram needs a Business/Creator account and a Meta app, TikTok posts are private until your app is audited. Keep the method on **cookie** until then.

## 7. Test upload (unlisted)

In **Library**, pick `youtube`, leave visibility on *default (unlisted)*, tick **show browser** for the first try, and click **Upload**. Check the video in YouTube Studio. When you trust the pipeline, switch the default in **Schedule → Defaults** or pick *public* per upload.

Daily caps (Instagram 2, YouTube 5, TikTok 3) apply to every upload, whether from the UI, the scheduler or the CLI.

## 8. Schedule it

In **Schedule**, choose a project, a generate time and an upload time, tick platforms, **Add to schedule**, then switch **daemon running** on. See `docs/SCHEDULER.md` to start the daemon automatically at log-on.

## If something breaks

**Settings → System health** runs `doctor.py`; **Run smoke test** does a full 5-second render with checks. Then read `docs/DEBUGGING.md`.
