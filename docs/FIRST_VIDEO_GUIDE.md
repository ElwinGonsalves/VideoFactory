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
.\start.ps1                                   # or: .\.venv\Scripts\python.exe ui\server.py
```

Your browser opens `http://127.0.0.1:8765`. On the first visit a 3-step guide checks the engines and your key; **Judge Demo Mode** there shows a sample Short, Blueprint and Batch without any key. The UI only listens on this computer. To preview on your phone over the same Wi-Fi, use `--host 0.0.0.0` and open the link the console prints (it contains the access token).

Six tabs:

| Tab | What you do there |
| --- | --- |
| **Create** | Pick **From Idea** (the AI writes the script) or **From Script** (your exact words are kept for the voice-over), choose a style, edit the scenes (type, move, add, delete), **Render** |
| **Ideas** | **Brainstorm from Topic / Niche**, or **Learn from Reference Video(s)**. Editable pitch cards with **Approve & Generate**, **Edit Script**, **Add to Schedule**, **Dismiss** |
| **Batch** | Upload an Excel/CSV or a public Google Sheet, check the validated preview, render everything one video at a time (see [BATCH_SHEETS.md](BATCH_SHEETS.md)) |
| **Library** | Search the list on the left; the Inspector on the right plays the video, shows the QA strip and fact-check banner, edits title/description/hashtags, downloads the MP4, re-renders 16:9 or 9:16, publishes or schedules |
| **Schedule** | Pre-Flight bar, Schedule Builder and queue cards (see [SCHEDULER.md](SCHEDULER.md)) |
| **Settings** | Gemini key and spend limit, video defaults, one card per publishing platform, Telegram/Discord alerts, **System health** |

The **Studio Status Pill** in the header (`● Ready · 2 Scheduled · Next upload in 45m`) opens the Activity Drawer: what is rendering now with a 5-step stepper (Script → Voice → Music+SFX → Render → QA), its live log and Cancel, what is scheduled next, and recent results. The **Stitched Engines** badge in the sidebar shows the health of every engine. The old UI is at `/classic`.

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
4. Remotion renders `output\concept-001\concept-001.mp4` (H.264 yuv420p + AAC, faststart).
5. A thumbnail (`output\concept-001\concept-001.thumb.jpg`) and upload metadata (`output\concept-001\concept-001.meta.json`) are written. With a Gemini key, the metadata includes 3 title variants, alternative hooks, hashtags and tags.

The Library tab shows a yellow **Verify before posting** box listing the facts the script states with numbers. Check them before you publish.

## 5. Make your own
**From an idea.** In **Create**, keep *From Idea*, type a topic such as *"Why Costco sells hot dogs for $1.50"*, pick a style, aspect and mood, click **Write script**. Each style writes with its own beats (for example Vox documentary: Cold Open, Archival/Map Context, Turning Point, Editorial Synthesis; stickman: Character Setup, Escalation, Punchline; `long_form` is 16:9 with 3-5 chapters). With **check facts with Google Search** on, case studies and statistics are researched on the web and the sources are saved in `script.json`. Gemini's free tier does not offer that search: the script is then written without it and every numeric claim is marked unverified.

**From your own script.** Switch to *From Script*, paste your text and click **Split into scenes**. Your sentences are used word for word for the voice; they are only cut into scenes (a blank line always starts a new scene). The AI may choose visuals and suggest a title, never rewrite narration.

The folder name of a project is made from the video **title** (3 to 5 words, for example `how-world-person-never-lied`; a clash becomes `-2`, `-3`).

Every scene shows something concrete in the middle of the frame: a diagram, counter, hand-drawn sketch, paper cutout, timeline, stick figure, chart, map or a photo with a slow zoom. Text-only scenes are upgraded automatically, and the visual QA flags a frame whose centre is mostly empty.

**From a reference video.** In **Ideas**, choose *Learn from Reference Video(s)*, paste links, set **Analysis depth** (Fast = the first 20 seconds, Detailed = the whole video) and click **Analyze + propose ideas**. Saved Style Blueprints are listed on the same page and can be reused in *Brainstorm*. Ideas that repeat a video you already made are filtered out.

Terminal equivalents: `python -m llm.cli write-script --prompt "..."`, `python -m llm.cli write-script --mode script --text-file my.txt --title "..."`, `python analyzer\analyze_reference.py analyze <url> --style my_style`.

## 6. One-time login for uploads

In **Settings → Publishing accounts**, pick *Cookie Login* on the platform card and click **Connect / Refresh Login** for YouTube (and Instagram/TikTok if you use them). A browser opens; sign in, then close it. Cookies are saved under `publisher\social-auto-upload\cookies\` (gitignored). **Check Session** confirms they are valid.

Official APIs (optional: switch the card to *Official API*; Client ID/Secret, tokens and `client_secret.json` are stored only in your local `.env` / `config/`, shown masked, with a **Test Connection** button) need app approval: YouTube API uploads stay private until Google audits your project, Instagram needs a Business/Creator account and a Meta app, TikTok posts are private until your app is audited. Keep the method on **cookie** until then.

## 7. Test upload (unlisted)

In **Library**, select the video, pick `youtube`, leave visibility on *default (unlisted)*, tick **show browser** for the first try, and click **Publish Now**. Check the video in YouTube Studio. When you trust the pipeline, switch the default in **Schedule → Defaults** or pick *public* per upload.

Daily caps (Instagram 2, YouTube 5, TikTok 3) apply to every upload, whether from the UI, the scheduler or the CLI.

## 8. Schedule it
In **Schedule**, tick the videos (by title), choose the first upload (*Now*, *Tonight 11:00 PM* or a time) and the spacing (30 min to 4 hr, or custom), choose whether each video renders shortly before its upload or all now, and check the live time preview. **Add to schedule**, then switch **Scheduler Daemon** on and leave **Keep PC Awake** on. The Pre-Flight bar also shows the Safe-Publish Gate and whether each platform login is valid. See [SCHEDULER.md](SCHEDULER.md) to start the daemon at log-on.

## Unattended notes
- Keep the project **outside OneDrive** (for example `C:\dev\video-factory`). OneDrive locks files during renders and SQLite writes.
- Upgrading from v1: back up, then `python scripts\migrate_output.py --dry-run` and `python scripts\migrate_output.py` to move `output\<slug>.*` into `output\<slug>\`.

## If something breaks

**Settings → System health** runs `doctor.py`; **Run smoke test** does a full 5-second render with checks. Then read `docs/DEBUGGING.md`.
