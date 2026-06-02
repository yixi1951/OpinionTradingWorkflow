# One-click Streamlit dashboard for sentiment / stock-pick analysis
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\run_ui.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\run_ui.ps1 -WithDemo
#   powershell -ExecutionPolicy Bypass -File .\scripts\run_ui.ps1 -Port 8502

param(
    [int]$Port = 8501,
    [switch]$WithDemo,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error "Virtual env not found. Run: python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt"
}

function Test-PortOpen([int]$P) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $client.Connect("127.0.0.1", $P)
        $client.Close()
        return $true
    } catch {
        return $false
    }
}

$hasPicks = @(Get-ChildItem -Path (Join-Path $Root "data\reports") -Filter "realtime_picks_*.md" -ErrorAction SilentlyContinue).Count -gt 0

if ($WithDemo -or -not $hasPicks) {
    if (-not $hasPicks) {
        Write-Host "No realtime picks found — running stub demo first (~2 min) ..."
    } else {
        Write-Host "WithDemo: refreshing data via stub demo ..."
    }
    & powershell -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\run_demo.ps1") -SkipDaily:$false -Iterations 1 -IntervalSeconds 1
}

if (Test-PortOpen $Port) {
    Write-Warning "Port $Port already in use. Stop the existing Streamlit process or use -Port 8502"
}

$url = "http://localhost:$Port"
Write-Host ""
Write-Host "=== Opinion Trading Dashboard ==="
Write-Host "  URL: $url"
Write-Host "  Tabs: 实时选股 | 舆情分析 | 评论依据 | 回测评估"
Write-Host ""

if (-not $NoBrowser) {
    Start-Process $url
}

& $Python -m streamlit run src/opinion_trading/ui_dashboard.py --server.port $Port --server.headless true
