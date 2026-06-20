# Wait for rescore PID then run realtime picks
param(
    [int]$RescorePid,
    [string]$Date = "2026-06-03"
)
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Log = Join-Path $Root "data\reports\run_daily_openclaw.log"

while (Get-Process -Id $RescorePid -ErrorAction SilentlyContinue) {
    Start-Sleep 60
}
Add-Content $Log "`n[5/5] Realtime picks after rescore ..."
$env:OPENCLAW_URL = "http://127.0.0.1:18790"
$env:OPENCLAW_TIMEOUT = "600"
$env:OPENCLAW_SKIP_ROW_SCORE = "1"
& $Python run_pipeline.py --mode realtime --iterations 1 --interval-seconds 1 --top-n 3
Add-Content $Log "`n=== Full run complete ==="
