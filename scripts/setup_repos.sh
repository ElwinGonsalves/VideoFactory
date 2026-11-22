#!/usr/bin/env sh
# Clone the gitignored third-party repos (engines + uploader) and install their dependencies.
# Usage (from the repo root): sh scripts/setup_repos.sh      Full setup: python3 scripts/bootstrap.py
set -eu
cd "$(dirname "$0")/.."
PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"
"$PY" scripts/bootstrap.py --engines --publisher
echo "Repos ready: engines/openmontage, engines/explainroo, engines/clipper, publisher/social-auto-upload"
