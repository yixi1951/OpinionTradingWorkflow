# Capture dashboard screenshots for README (Streamlit must be running)
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\capture_ui_screenshots.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\capture_ui_screenshots.ps1 -Port 8502

param(
    [int]$Port = 8501,
    [int]$WaitSeconds = 3
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error "Missing .venv. Run: python -m venv .venv; pip install -r requirements.txt"
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

if (-not (Test-PortOpen $Port)) {
    Write-Host "Streamlit not on port $Port — starting UI ..."
    Start-Process powershell -ArgumentList @(
        "-ExecutionPolicy", "Bypass",
        "-File", (Join-Path $Root "scripts\run_ui.ps1"),
        "-Port", $Port,
        "-NoBrowser"
    ) -WindowStyle Minimized
    $deadline = (Get-Date).AddSeconds(90)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortOpen $Port) { break }
        Start-Sleep -Seconds 2
    }
    if (-not (Test-PortOpen $Port)) {
        Write-Error "Streamlit did not start on port $Port within 90s"
    }
    Start-Sleep -Seconds 5
}

& $Python -m pip install playwright -q 2>$null
& $Python -m playwright install chromium 2>$null

& $Python (Join-Path $Root "scripts\capture_ui_screenshots.py") `
    --url "http://localhost:$Port" `
    --wait $WaitSeconds

Write-Host ""
Write-Host "Screenshots saved to docs/screenshots/ — commit and push for GitHub README preview."
