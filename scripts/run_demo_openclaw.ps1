# Real OpenClaw demo: gateway + HTTP proxy + smoke test + realtime picks
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\run_demo_openclaw.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\run_demo_openclaw.ps1 -SkipRealtime
#   powershell -ExecutionPolicy Bypass -File .\scripts\run_demo_openclaw.ps1 -WithUI

param(
    [string]$Date = (Get-Date -Format "yyyy-MM-dd"),
    [int]$GatewayPort = 18789,
    [int]$ProxyPort = 18790,
    [int]$Iterations = 1,
    [int]$IntervalSeconds = 1,
    [int]$TopN = 3,
    [switch]$SkipDaily,
    [switch]$SkipRealtime,
    [switch]$WithUI
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error "Missing .venv. Run: python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt"
}

$OpenClawCmd = (Get-Command openclaw.cmd -ErrorAction SilentlyContinue).Source
if (-not $OpenClawCmd) { $OpenClawCmd = (Get-Command openclaw -ErrorAction SilentlyContinue).Source }
if (-not $OpenClawCmd) { Write-Error "openclaw not found in PATH. Install: npm i -g openclaw" }

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

function Read-OpenClawConfig() {
    $paths = @(
        (Join-Path $env:USERPROFILE ".openclaw\openclaw.json"),
        (Join-Path $env:USERPROFILE ".openclaw\openclaw.json.bak")
    )
    foreach ($p in $paths) {
        if (Test-Path $p) {
            return (Get-Content $p -Raw | ConvertFrom-Json)
        }
    }
    return $null
}

$cfg = Read-OpenClawConfig
if ($null -eq $cfg) {
    Write-Error "OpenClaw config not found under %USERPROFILE%\.openclaw\"
}

$token = $cfg.gateway.auth.token
$model = $cfg.agents.defaults.model
if ($null -ne $model -and $model.PSObject.Properties.Name -contains 'primary') {
    $model = $model.primary
}
if (-not $model) { $model = "deepseek/deepseek-v4-flash" }
if ($cfg.gateway.port) { $GatewayPort = [int]$cfg.gateway.port }

$GatewayProc = $null
if (-not (Test-PortOpen $GatewayPort)) {
    Write-Host "Starting OpenClaw gateway on port $GatewayPort (first start may take ~30s) ..."
    $GatewayProc = Start-Process -FilePath $OpenClawCmd `
        -ArgumentList "gateway", "run", "--port", "$GatewayPort", "--force" `
        -PassThru -WindowStyle Hidden
    $deadline = (Get-Date).AddSeconds(90)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortOpen $GatewayPort) { break }
        Start-Sleep -Seconds 2
    }
    if (-not (Test-PortOpen $GatewayPort)) {
        Write-Error "Gateway did not open on port $GatewayPort. Try: openclaw gateway run --port $GatewayPort"
    }
} else {
    Write-Host "Gateway already listening on $GatewayPort"
}

$ProxyProc = $null
if (-not (Test-PortOpen $ProxyPort)) {
    Write-Host "Starting HTTP proxy on http://127.0.0.1:$ProxyPort (model=$model) ..."
    $env:WS_GATEWAY_URL = "ws://127.0.0.1:$GatewayPort"
    $env:WS_GATEWAY_TOKEN = $token
    $env:WS_GATEWAY_MODEL = $model
    $env:WS_GATEWAY_RESPONSE_TIMEOUT = "90"
    $ProxyProc = Start-Process -FilePath $Python `
        -ArgumentList "-m", "uvicorn", "openclaw_ws_proxy:app", "--host", "127.0.0.1", "--port", "$ProxyPort" `
        -PassThru -WindowStyle Hidden `
        -WorkingDirectory $Root
    Start-Sleep -Seconds 3
    if (-not (Test-PortOpen $ProxyPort)) {
        Write-Error "Proxy failed to bind port $ProxyPort"
    }
} else {
    Write-Host "Proxy already listening on $ProxyPort"
}

$env:WS_GATEWAY_URL = "ws://127.0.0.1:$GatewayPort"
$env:WS_GATEWAY_TOKEN = $token
$env:WS_GATEWAY_MODEL = $model
$env:WS_GATEWAY_RESPONSE_TIMEOUT = "90"
$env:OPENCLAW_URL = "http://127.0.0.1:$ProxyPort"
$env:OPENCLAW_TIMEOUT = "90"
$env:OPENCLAW_SKIP_ROW_SCORE = "1"
Remove-Item Env:OPENCLAW_TOKEN -ErrorAction SilentlyContinue

Write-Host "`nTip: For row-level OpenClaw scores use scripts/run_daily_openclaw.ps1 (two-phase crawl + rescore)"

Write-Host "`n=== OpenClaw smoke test (2 sample texts) ==="
& $Python -c @"
import requests, time
texts = ['茅台业绩超预期，强烈看好买入', '股价暴跌，风险很大建议卖出']
t = time.time()
r = requests.post('$($env:OPENCLAW_URL)/api/v1/sentiment', json={'texts': texts}, timeout=190)
print('status', r.status_code)
print('elapsed', round(time.time()-t, 1), 's')
print(r.text)
if r.status_code != 200:
    raise SystemExit(1)
"@

if (-not $SkipDaily) {
    Write-Host "`n=== Daily ($Date) with real OpenClaw ==="
    Write-Host "(18 platform x symbol calls; ~5-10 min with DeepSeek API)"
    & $Python run_pipeline.py --mode daily --date $Date
}

if (-not $SkipRealtime) {
    Write-Host "`n=== Realtime picks (real OpenClaw) ==="
    Write-Host "(1 cycle ~5-10 min on DeepSeek; scores will differ from stub)"
    & $Python run_pipeline.py --mode realtime `
        --iterations $Iterations `
        --interval-seconds $IntervalSeconds `
        --top-n $TopN
}

Write-Host "`n=== Done ==="
Write-Host "  OPENCLAW_URL = $($env:OPENCLAW_URL)"
Write-Host "  Model        = $model"
Write-Host "  Reports      = data/reports/realtime_picks_*.md"

if ($WithUI) {
    Write-Host "`nUI: http://localhost:8501"
    & $Python -m streamlit run src/opinion_trading/ui_dashboard.py --server.port 8501
}

if ($GatewayProc) {
    Write-Host "`nGateway PID $($GatewayProc.Id) (Stop-Process -Id $($GatewayProc.Id))"
}
if ($ProxyProc) {
    Write-Host "Proxy PID $($ProxyProc.Id) (Stop-Process -Id $($ProxyProc.Id))"
}
