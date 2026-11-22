# Clone the gitignored third-party repos (engines + uploader) and install their dependencies.
# Usage (from the repo root):  powershell -ExecutionPolicy Bypass -File scripts\setup_repos.ps1
# Full setup of everything else: python scripts\bootstrap.py
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
& $py scripts\bootstrap.py --engines --publisher
if ($LASTEXITCODE -ne 0) { throw "setup_repos failed (exit $LASTEXITCODE)" }
Write-Host "Repos ready: engines\openmontage, engines\explainroo, engines\clipper, publisher\social-auto-upload"
