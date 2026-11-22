# Batch sheets

Queue many videos from a spreadsheet in the **Batch** tab. Videos render strictly **one at a time** (a 6 GB GPU cannot do two), and rows with `auto_publish` are added to the Schedule.

## Get started
1. Batch tab > **Download Sample Excel** (or `GET /api/batch/sample`).
2. Fill one row per video. Save as `.xlsx` or `.csv`.
3. Upload the file, or paste a Google Sheets link (share it as *Anyone with the link can view*; the page reads `.../export?format=csv`, add `#gid=<tab>` for another tab).
4. Read the **preview**: each row is validated, errors are listed in red and **Start batch** stays disabled until every row is valid.
5. Choose the **Relative upload interval** (30 min, 45 min, 1 hour, 2 hours, 4 hours or custom such as `90m` / `1.5h`) and optionally the first upload time, then **Start batch**.

## Columns
| Column | Values |
| --- | --- |
| `input_mode` | `idea` (the AI writes the script from `content`) or `script` (`content` is kept word for word) |
| `title` | Video title; the project folder is made from it (empty: the AI suggests one) |
| `content` | The idea or the full script (min 8 words in script mode) |
| `style` | Any style in Create, e.g. `concept_explainer`, `case_study`, `vox_documentary`, `whiteboard`, `hand_drawn`, `stickman`, `long_form` |
| `aspect_ratio` | `9:16`, `16:9`, `1:1` (`long_form` is always 16:9) |
| `music_mood` | `chill`, `documentary`, `upbeat`, `dramatic` |
| `voice` | Empty = Settings default, e.g. `en-US-AndrewNeural` |
| `auto_publish` | `yes`/`no`: add an upload job after rendering |
| `platforms` | `youtube,instagram,tiktok` (comma separated; default `youtube`) |
| `schedule_at` | Optional local time, e.g. `2026-12-01 20:00`. Empty: the row gets `start + k x interval`, counting only rows that auto-publish |

At most 100 rows. Empty `style`, `aspect_ratio` and `music_mood` fall back to your Settings defaults.

## What happens to a row
Write or split the script (with Google Search grounding when available) > render > register in `data/projects.db` > if `auto_publish`, add an `upload_only` job at its upload time. Uploads still pass through the daily caps, the session check and the Safe-Publish Gate (rows with unverified facts are held as `needs_review`).

A failing row is logged and skipped; the batch continues. If you use the paid Gemini tier and the monthly stop limit is reached, the batch stops cleanly after the current row ("batch paused"), finished rows stay finished, and you get a Telegram/Discord message if configured. Raise the limit in Settings and start the remaining rows again.

`python batch/run.py <batch.json>` runs a prepared batch from the terminal (the UI writes this file under `ui/logs/inputs/`).
