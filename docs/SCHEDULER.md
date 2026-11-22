# Scheduler

`scheduler/schedule.yaml` says what should happen. `scheduler/state.sqlite` records what has happened. The daemon checks both every 60 seconds, so stopping and restarting it never loses or repeats work.

## Add jobs

The easiest way is the UI **Schedule** tab (below). Each queue card has **Pause / Resume** (`enabled` in the YAML), **Run Now**, **Retry** and **Remove**.

You can also edit `schedule.yaml` directly, or use the CLI (it appends to the YAML):

```powershell
.venv\Scripts\python scheduler\run_scheduler.py add --id netflix-dvd `
  --script projects/concept-001/script.json `
  --generate-at 2026-11-24T08:00:00+05:30 --upload-at 2026-11-24T18:00:00+05:30 `
  --platforms youtube,instagram
```

## The Schedule tab
**Pre-Flight bar**
- **Scheduler Daemon** ON/OFF. The daemon runs while the UI is open; for always-on use a startup task below.
- **Keep PC Awake**: while any render or upload is pending or running, the daemon asks Windows not to sleep (`SetThreadExecutionState(0x80000001)` from one long-lived thread) and releases it (`0x80000000`) when the queue is empty. No effect on macOS/Linux.
- **Safe-Publish Gate**: a video with unverified facts (see `claims` in `script.json`) is still rendered, but its upload is held as `needs_review`. Check the facts in the Library, then press **Approve upload** on its queue card. Switch the gate off to upload everything.
- **Auth badges** for YouTube / Instagram / TikTok (checked / not checked). **Check** runs a session check now.

**Session check before each upload.** 5 to 10 minutes before an upload is due (`scheduler.pre_check_minutes`, default 7) the cookie session or API credentials are checked. If they have expired, that platform's queue is paused once (a single `platform_paused` event, no retry loop) and its uploads wait. Reconnect in Settings or press **Check** in the Pre-Flight bar; a successful check resumes the queue.

**Schedule Builder.** Pick videos by title, the first upload (*Now*, *Tonight 11:00 PM*, or a picker) and the spacing (30 min, 45 min, 1 hr, 2 hr, 4 hr, custom such as `90m`). A live preview shows the times in words ("Today 11:45 PM"). Rendering is either *auto-generate N min before each upload* or *generate all now, upload staggered*. Videos that are already rendered become `upload_only` jobs.

**Queue cards** show the times in words and the steps Queued, Rendering, Uploading, Published (with a link when one is known).

Alerts to Telegram or Discord (Settings) are sent when a generation or upload fails, a platform is paused, a video is held, or a batch finishes.

Job types:

| type | What runs |
| --- | --- |
| `generate_only` | Render at `generate_at`, no upload |
| `upload_only` | Upload an existing `meta:` file at `upload_at` |
| `generate_and_upload` | Render at `generate_at`, then upload at `upload_at` |

Leave `generate_at` or `upload_at` out to mean "as soon as possible".

### Batches

Add one job per video. A week of daily Shorts:

```yaml
jobs:
  - { id: "w48-mon", script_or_prompt: "projects/w48-mon/script.json", generate_at: "2026-11-23T06:00:00", upload_at: "2026-11-23T18:00:00", platforms: ["youtube"] }
  - { id: "w48-tue", script_or_prompt: "projects/w48-tue/script.json", generate_at: "2026-11-24T06:00:00", upload_at: "2026-11-24T18:00:00", platforms: ["youtube", "instagram"] }
```

Times without an offset are read in `defaults.timezone`.

## Inspect and control

```powershell
.venv\Scripts\python scheduler\run_scheduler.py list                 # every job + per-platform upload state
.venv\Scripts\python scheduler\run_scheduler.py status               # caps used today, recent events, last errors
.venv\Scripts\python scheduler\run_scheduler.py run-now netflix-dvd  # ignore the clock (still respects caps)
.venv\Scripts\python scheduler\run_scheduler.py run-now netflix-dvd --generate-only
.venv\Scripts\python scheduler\run_scheduler.py retry netflix-dvd    # re-queue failed parts
.venv\Scripts\python scheduler\run_scheduler.py daemon               # run continuously
```

`python scheduler\run_scheduler.py check-auth youtube` checks one platform from the terminal and resumes its queue when it passes.
Weekly analytics (Settings > Analytics) run from the same daemon on Mondays at 09:00.

## Rules

- **Retries:** a failed generation or upload is retried after 5, 10, 20 and 40 minutes. After the 5th failure it is marked `failed` and waits for `retry`.
- **Daily caps:** successful uploads are counted per platform per local day in the `posts` table, which the UI Upload button, `publisher/publish.py` and the scheduler all share. At the cap, a scheduled upload moves to the same time tomorrow and a manual one is refused. Defaults: Instagram 2 (keep it at 1-2), YouTube 5, TikTok 3.
- **Paused jobs:** `enabled: false` keeps a job in the YAML without running it. The shipped `concept-001` example is paused.
- **Visibility:** YouTube uploads use `defaults.youtube_visibility` (`unlisted`) unless a job sets `visibility`. Switch to `public` after you have reviewed a few unlisted uploads.
- **Sync never resets progress:** editing a job in the YAML updates it only while it is still `pending`. Finished jobs stay finished.

## Run the daemon on startup

### Windows Task Scheduler

```powershell
$root = "C:\Users\ELWIN G\OneDrive\Documents\UltiimateVideoGen_Boi\video-factory"
$action = New-ScheduledTaskAction -Execute "$root\.venv\Scripts\python.exe" -Argument "scheduler\run_scheduler.py daemon" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5) -ExecutionTimeLimit 0
Register-ScheduledTask -TaskName "video-factory-scheduler" -Action $action -Trigger $trigger -Settings $settings
```

Remove it with `Unregister-ScheduledTask -TaskName video-factory-scheduler`. Run at log-on (not "whether user is logged on or not"), because uploads drive a browser session.

### macOS launchd (`~/Library/LaunchAgents/com.videofactory.scheduler.plist`)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.videofactory.scheduler</string>
  <key>WorkingDirectory</key><string>/path/to/video-factory</string>
  <key>ProgramArguments</key><array>
    <string>/path/to/video-factory/.venv/bin/python</string>
    <string>scheduler/run_scheduler.py</string><string>daemon</string>
  </array>
  <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/path/to/video-factory/scheduler/logs/launchd.log</string>
  <key>StandardErrorPath</key><string>/path/to/video-factory/scheduler/logs/launchd.log</string>
</dict></plist>
```

Load it with `launchctl load ~/Library/LaunchAgents/com.videofactory.scheduler.plist`.

### Linux cron

Start the daemon at boot:

```cron
@reboot cd /path/to/video-factory && .venv/bin/python scheduler/run_scheduler.py daemon >> scheduler/logs/cron.log 2>&1
```

## Inspect `state.sqlite`

```powershell
sqlite3 scheduler\state.sqlite "SELECT id, gen_status, gen_attempts, gen_next_at FROM jobs;"
sqlite3 scheduler\state.sqlite "SELECT job_id, platform, status, attempts, local_day FROM uploads;"
sqlite3 scheduler\state.sqlite "SELECT at, job_id, kind, detail FROM events ORDER BY at DESC LIMIT 20;"
sqlite3 scheduler\state.sqlite "SELECT at, local_day, platform, method, slug, visibility FROM posts ORDER BY at DESC;"
```

Without the sqlite3 CLI: `.venv\Scripts\python -c "import sqlite3;print(sqlite3.connect('scheduler/state.sqlite').execute('select * from events').fetchall())"`.

`scheduler/logs/scheduler.log` holds the same events as JSON lines. Both files are gitignored.

## Optional: Postiz

For a multi-channel calendar UI, self-host [postiz-app](https://github.com/gitroomhq/postiz-app) and point an `upload_only` step at it instead of `publisher/publish.py`. This is not wired in by default.
