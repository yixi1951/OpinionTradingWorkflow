# One-click web research desk. Builds the Vite frontend, starts the same-origin
# FastAPI gateway, and opens the browser at http://localhost:8000.
param([int]$Port = 8000, [switch]$WithDemo, [switch]$NoBrowser)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { Write-Error "Virtual env not found. Run: python -m venv .venv" }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Write-Error "Node.js/npm is required to build the web frontend." }
if ($WithDemo) { & powershell -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\run_demo.ps1") -SkipDaily:$false -Iterations 1 -IntervalSeconds 1 }
Push-Location (Join-Path $Root "web")
npm install --no-audit --no-fund
npm run build
Pop-Location
$env:PYTHONPATH = "src"
$env:PORT = "$Port"
$url = "http://localhost:$Port"
Write-Host "=== OpenClaw Research Desk ==="
Write-Host "  URL: $url"
if (-not $NoBrowser) { Start-Process $url }
& $Python -m opinion_trading.services.api_app
