# Restart OpenClaw gateway + proxy using DeepSeek from openclaw.json
param(
    [int]$GatewayPort = 0,
    [int]$ProxyPort = 18790
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$OpenClawCmd = (Get-Command openclaw.cmd -ErrorAction SilentlyContinue).Source
if (-not $OpenClawCmd) { $OpenClawCmd = (Get-Command openclaw -ErrorAction SilentlyContinue).Source }
if (-not $OpenClawCmd) { Write-Error "openclaw not in PATH" }

$cfgPath = Join-Path $env:USERPROFILE ".openclaw\openclaw.json"
$cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
$token = $cfg.gateway.auth.token
$model = $cfg.agents.defaults.model.primary
if (-not $model) { $model = "deepseek/deepseek-v4-flash" }
if ($GatewayPort -le 0) { $GatewayPort = [int]$cfg.gateway.port }

Write-Host "Model: $model | Gateway port: $GatewayPort"

Get-Process python, node -ErrorAction SilentlyContinue | ForEach-Object {
    $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine
    if ($cmd -match 'uvicorn openclaw_ws_proxy|openclaw.*gateway|rescore_raw|run_pipeline') {
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
}
Start-Sleep -Seconds 2

$Python = Join-Path $Root ".venv\Scripts\python.exe"
Write-Host "Starting gateway ..."
Start-Process -FilePath $OpenClawCmd `
    -ArgumentList "gateway", "run", "--port", "$GatewayPort", "--force" `
    -WindowStyle Hidden | Out-Null
$deadline = (Get-Date).AddSeconds(120)
$gatewayReady = $false
while ((Get-Date) -lt $deadline) {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $c.Connect("127.0.0.1", $GatewayPort)
        $c.Close()
        $gatewayReady = $true
        break
    } catch { Start-Sleep -Seconds 2 }
}
if (-not $gatewayReady) {
    Write-Warning "Gateway port $GatewayPort not ready; proxy may fail"
}

Start-Sleep -Seconds 5
$env:WS_GATEWAY_URL = "ws://127.0.0.1:$GatewayPort"
$env:WS_GATEWAY_TOKEN = $token
$env:WS_GATEWAY_MODEL = $model
$env:WS_GATEWAY_RESPONSE_TIMEOUT = "120"
$env:OPENCLAW_URL = "http://127.0.0.1:$ProxyPort"
$env:OPENCLAW_TIMEOUT = "120"
$env:OPENCLAW_BATCH_SIZE = "4"

Write-Host "Starting proxy on $ProxyPort ..."
Start-Process -FilePath $Python `
    -ArgumentList "-m", "uvicorn", "openclaw_ws_proxy:app", "--host", "127.0.0.1", "--port", "$ProxyPort" `
    -WorkingDirectory $Root -WindowStyle Hidden | Out-Null
Start-Sleep -Seconds 4

Write-Host "Smoke test (2 texts) ..."
& $Python -c @"
import requests, time
t = time.time()
r = requests.post('$env:OPENCLAW_URL/api/v1/sentiment', json={'texts': ['业绩超预期，强烈看好', '风险很大建议回避']}, timeout=150)
print('status', r.status_code, 'elapsed', round(time.time()-t, 1), 's')
print(r.text[:200])
r.raise_for_status()
"@

Write-Host "`nDeepSeek ready. OPENCLAW_URL=$env:OPENCLAW_URL WS_GATEWAY_MODEL=$model"
