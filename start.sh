#!/usr/bin/env bash
# Start the Video Factory studio. First run sets up the minimum (Python venv, Remotion, the UI);
# later runs just start the server. Arguments go to ui/server.py, e.g.:
#   ./start.sh --port 8766 --no-browser
#   VF_FULL=1 ./start.sh      # first run: also GPU libs, engines, publisher, music, skills
set -euo pipefail
cd "$(dirname "$0")"

for tool in python3 node npm ffmpeg; do
  command -v "$tool" >/dev/null 2>&1 || { echo "Missing '$tool' on PATH. See docs/FIRST_VIDEO_GUIDE.md for installs." >&2; exit 1; }
done

PY=.venv/bin/python
if [ ! -x "$PY" ]; then
  echo "First run: setting up (a few minutes)..."
  if [ "${VF_FULL:-}" = "1" ]; then python3 scripts/bootstrap.py
  else python3 scripts/bootstrap.py --python --studio --frontend --assets; fi
elif [ ! -f frontend/dist/index.html ]; then
  echo "Building the studio UI..."
  "$PY" scripts/bootstrap.py --frontend
fi

exec "$PY" ui/server.py "$@"
