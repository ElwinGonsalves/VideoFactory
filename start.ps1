# Start the Video Factory studio. First run sets up the minimum (Python venv, Remotion, the UI);
# later runs just start the server. Extra arguments go to ui/server.py, e.g.:
#   .\start.ps1 -Port 8766 -NoBrowser
#   .\start.ps1 -Full          # first run: also GPU libs, engines, publisher, music, skills
param(
    [int]$Port = 8765,
    [switch]$NoBrowser,
    [switch]$Full,
    [string]$BindHost = "127.0.0.1"
)
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

foreach ($tool in "python", "node", "npm", "ffmpeg") {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Host "Missing '$tool' on PATH. See docs/FIRST_VIDEO_GUIDE.md for installs." -ForegroundColor Red
        exit 1
    }
}

$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $py)) {
    Write-Host "First run: setting up (a few minutes)..." -ForegroundColor Yellow
    if ($Full) { python scripts/bootstrap.py } else { python scripts/bootstrap.py --python --studio --frontend --assets }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
elseif (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot "frontend\dist\index.html"))) {
    Write-Host "Building the studio UI..." -ForegroundColor Yellow
    & $py scripts/bootstrap.py --frontend
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$serverArgs = @("ui/server.py", "--port", $Port, "--host", $BindHost)
if ($NoBrowser) { $serverArgs += "--no-browser" }
& $py @serverArgs
exit $LASTEXITCODE
