# Two-phase OpenClaw daily: fast crawl + incremental AI rescore
#
# Phase 1  daily crawl with keyword scores (~5 min)
# Phase 2  OpenClaw rescore in small batches (~1 min/batch of 4)
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\run_daily_openclaw.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\run_daily_openclaw.ps1 -Date 2026-06-03 -SkipRescore
#   powershell -ExecutionPolicy Bypass -File .\scripts\run_daily_openclaw.ps1 -BatchSize 4 -MaxRescoreRows 40

param(
    [string]$Date = (Get-Date -Format "yyyy-MM-dd"),
    [int]$GatewayPort = 18789,
    [int]$ProxyPort = 18790,
    [int]$BatchSize = 4,
    [int]$MaxRescoreRows = 0,
    [switch]$SkipRescore,
    [switch]$SkipRealtime,
    [switch]$KeepServices
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error "Missing .venv. Run: python -m venv .venv; pip install -r requirements.txt"
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

function Read-OpenClawConfig() {
    foreach ($p in @(
        (Join-Path $env:USERPROFILE ".openclaw\openclaw.json"),
        (Join-Path $env:USERPROFILE ".openclaw\openclaw.json.bak")
    )) {
        if (Test-Path $p) { return (Get-Content $p -Raw | ConvertFrom-Json) }
    }
    return $null
}

$OpenClawCmd = (Get-Command openclaw.cmd -ErrorAction SilentlyContinue).Source
if (-not $OpenClawCmd) { $OpenClawCmd = (Get-Command openclaw -ErrorAction SilentlyContinue).Source }
if (-not $OpenClawCmd) { Write-Error "openclaw not found. Install: npm i -g openclaw" }

$cfg = Read-OpenClawConfig
if ($null -eq $cfg) { Write-Error "OpenClaw config not found under %USERPROFILE%\.openclaw\" }

$token = $cfg.gateway.auth.token
$model = $cfg.agents.defaults.model
if ($null -ne $model -and $model.PSObject.Properties.Name -contains 'primary') {
    $model = $model.primary
}
if (-not $model) { $model = "deepseek/deepseek-v4-flash" }
if ($cfg.gateway.port) { $GatewayPort = [int]$cfg.gateway.port }

$GatewayProc = $null
$ProxyProc = $null

if (-not (Test-PortOpen $GatewayPort)) {
    Write-Host "[1/4] Starting OpenClaw gateway on port $GatewayPort ..."
    $GatewayProc = Start-Process -FilePath $OpenClawCmd `
        -ArgumentList "gateway", "run", "--port", "$GatewayPort", "--force" `
        -PassThru -WindowStyle Hidden
    $deadline = (Get-Date).AddSeconds(120)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortOpen $GatewayPort) { break }
        Start-Sleep -Seconds 2
    }
    if (-not (Test-PortOpen $GatewayPort)) {
        Write-Error "Gateway did not start on port $GatewayPort"
    }
} else {
    Write-Host "[1/4] Gateway already on port $GatewayPort"
}

if (-not (Test-PortOpen $ProxyPort)) {
    Write-Host "[2/4] Starting HTTP proxy on http://127.0.0.1:$ProxyPort (model=$model) ..."
    $env:WS_GATEWAY_URL = "ws://127.0.0.1:$GatewayPort"
    $env:WS_GATEWAY_TOKEN = $token
    $env:WS_GATEWAY_MODEL = $model
    $env:WS_GATEWAY_RESPONSE_TIMEOUT = "180"
    $ProxyProc = Start-Process -FilePath $Python `
        -ArgumentList "-m", "uvicorn", "openclaw_ws_proxy:app", "--host", "127.0.0.1", "--port", "$ProxyPort" `
        -PassThru -WindowStyle Hidden -WorkingDirectory $Root
    Start-Sleep -Seconds 4
    if (-not (Test-PortOpen $ProxyPort)) { Write-Error "Proxy failed on port $ProxyPort" }
} else {
    Write-Host "[2/4] Proxy already on port $ProxyPort"
}

$env:WS_GATEWAY_URL = "ws://127.0.0.1:$GatewayPort"
$env:WS_GATEWAY_TOKEN = $token
$env:WS_GATEWAY_MODEL = $model
$env:WS_GATEWAY_RESPONSE_TIMEOUT = "180"
$env:OPENCLAW_URL = "http://127.0.0.1:$ProxyPort"
$env:OPENCLAW_TIMEOUT = "600"
$env:OPENCLAW_BATCH_SIZE = "$BatchSize"
$env:OPENCLAW_SKIP_ROW_SCORE = "1"
Remove-Item Env:OPENCLAW_TOKEN -ErrorAction SilentlyContinue

Write-Host "[3/4] Daily crawl ($Date) — keyword scores only, ~5 min ..."
& $Python run_pipeline.py --mode daily --date $Date
if ($LASTEXITCODE -ne 0) { Write-Error "daily failed with exit $LASTEXITCODE" }

$RawCsv = Join-Path $Root "data\raw\raw_posts_$Date.csv"
if (-not (Test-Path $RawCsv)) { Write-Error "Missing $RawCsv after daily" }

if (-not $SkipRescore) {
    Write-Host "[4/4] OpenClaw rescore (batch=$BatchSize, incremental save) ..."
    $rescoreArgs = @(
        "scripts\rescore_raw_openclaw.py",
        "--csv", $RawCsv,
        "--batch-size", "$BatchSize"
    )
    if ($MaxRescoreRows -gt 0) {
        $rescoreArgs += @("--max-rows", "$MaxRescoreRows")
    }
    & $Python @rescoreArgs
    if ($LASTEXITCODE -ne 0) { Write-Error "rescore failed with exit $LASTEXITCODE" }
} else {
    Write-Host "[4/4] Skipped rescore (-SkipRescore)"
}

if (-not $SkipRealtime) {
    Write-Host "Realtime picks (aggregate OpenClaw, 1 cycle) ..."
    & $Python run_pipeline.py --mode realtime --iterations 1 --interval-seconds 1 --top-n 3
}

Write-Host "`n=== Done ==="
Write-Host "  Raw CSV   = $RawCsv"
Write-Host "  Log hint  = data\reports\rescore_openclaw.log (if tee used)"
Write-Host "  UI        = streamlit run src/opinion_trading/ui_dashboard.py --server.port 8501"

if (-not $KeepServices) {
    if ($ProxyProc) { Stop-Process -Id $ProxyProc.Id -Force -ErrorAction SilentlyContinue }
    if ($GatewayProc) { Stop-Process -Id $GatewayProc.Id -Force -ErrorAction SilentlyContinue }
    Write-Host "  Gateway/proxy stopped (use -KeepServices to leave running)"
}
