# One-shot stock-picking demo (OpenClaw stub + daily + realtime + optional UI)
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\run_demo.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\run_demo.ps1 -WithUI
#   powershell -ExecutionPolicy Bypass -File .\scripts\run_demo.ps1 -OpenClawUrl "http://127.0.0.1:18790"

param(
    [string]$Date = (Get-Date -Format "yyyy-MM-dd"),
    [string]$OpenClawUrl = "http://127.0.0.1:18080",
    [int]$Iterations = 2,
    [int]$IntervalSeconds = 1,
    [int]$TopN = 3,
    [switch]$WithUI,
    [switch]$SkipDaily
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error "Virtual env not found. Run: python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt"
}

function Test-PortOpen([int]$Port) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $client.Connect("127.0.0.1", $Port)
        $client.Close()
        return $true
    } catch {
        return $false
    }
}

$StubPort = 18080
if ($OpenClawUrl -match ":(\d+)$") {
    $StubPort = [int]$Matches[1]
}

$StubProc = $null
if (-not (Test-PortOpen $StubPort)) {
    if ($OpenClawUrl -match ":18080$") {
        Write-Host "Starting OpenClaw stub on $OpenClawUrl ..."
        $StubProc = Start-Process -FilePath $Python `
            -ArgumentList "-m", "uvicorn", "openclaw_stub:app", "--host", "127.0.0.1", "--port", "$StubPort" `
            -PassThru -WindowStyle Hidden
        Start-Sleep -Seconds 3
    } else {
        Write-Warning "OpenClaw not reachable at $OpenClawUrl. Start your gateway/proxy first."
    }
} else {
    Write-Host "OpenClaw endpoint already listening on port $StubPort"
}

$env:OPENCLAW_URL = $OpenClawUrl
Remove-Item Env:OPENCLAW_TOKEN -ErrorAction SilentlyContinue

if (-not $SkipDaily) {
    Write-Host "`n=== Daily ($Date) ==="
    & $Python run_pipeline.py --mode daily --date $Date
}

Write-Host "`n=== Realtime picks ==="
& $Python run_pipeline.py --mode realtime `
    --iterations $Iterations `
    --interval-seconds $IntervalSeconds `
    --top-n $TopN

Write-Host "`n=== Demo outputs ==="
Write-Host "  Daily report : data/reports/$Date.md"
Write-Host "  Quality      : data/reports/quality_$Date.md"
Write-Host "  Latest picks : data/reports/realtime_picks_*.csv (newest file)"
Write-Host "  Raw evidence : data/raw/raw_posts_$Date.csv"

if ($WithUI) {
    Write-Host "`nStarting Streamlit UI on http://localhost:8501 ..."
    & $Python -m streamlit run src/opinion_trading/ui_dashboard.py --server.port 8501
}

if ($StubProc) {
    Write-Host "`nStub PID $($StubProc.Id) still running. Stop with: Stop-Process -Id $($StubProc.Id)"
}
