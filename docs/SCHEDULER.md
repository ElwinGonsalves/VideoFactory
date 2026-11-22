# Scheduler

`scheduler/schedule.yaml` says what should happen. `scheduler/state.sqlite` records what has happened. The daemon checks both every 60 seconds, so stopping and restarting it never loses or repeats work.

## Add jobs

Edit `schedule.yaml` directly, or use the CLI (it appends to the YAML):

```powershell
.venv\Scripts\python scheduler\run_scheduler.py add --id netflix-dvd `
  --script projects/concept-001/script.json `
  --generate-at 2026-11-24T08:00:00+05:30 --upload-at 2026-11-24T18:00:00+05:30 `
  --platforms youtube,instagram
```

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

## Rules

- **Retries:** a failed generation or upload is retried after 5, 10, 20 and 40 minutes. After the 5th failure it is marked `failed` and waits for `retry`.
- **Daily caps:** successful uploads are counted per platform per local day. At the cap, the upload moves to the same time tomorrow. Defaults: Instagram 2 (keep it at 1-2), YouTube 5, TikTok 3.
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
```

Without the sqlite3 CLI: `.venv\Scripts\python -c "import sqlite3;print(sqlite3.connect('scheduler/state.sqlite').execute('select * from events').fetchall())"`.

`scheduler/logs/scheduler.log` holds the same events as JSON lines. Both files are gitignored.

## Optional: Postiz

For a multi-channel calendar UI, self-host [postiz-app](https://github.com/gitroomhq/postiz-app) and point an `upload_only` step at it instead of `publisher/publish.py`. This is not wired in by default.
