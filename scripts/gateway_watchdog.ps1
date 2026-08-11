<#
.SYNOPSIS
    Health-check watchdog for the OpenClaw Gateway + WS Proxy pair.
    Checks TCP ports every N seconds; restarts dead services automatically.
    Designed to run as a background task alongside the pipeline.

.DESCRIPTION
    - PORT_GATEWAY (18789): OpenClaw gateway Python process
    - PORT_PROXY   (18790): WebSocket proxy Python process
    - Checks both ports via Test-NetConnection.
    - If either is down, kills any stale processes, then runs the restart script.
    - Logs to data/logs/gateway_watchdog.log.

.PARAMETER IntervalSeconds
    How often to check (default: 30).

.PARAMETER RestartScript
    Path to the restart script (default: ..\scripts\restart_openclaw_deepseek.ps1).

.EXAMPLE
    .\gateway_watchdog.ps1 -IntervalSeconds 60
#>

param(
    [int]$IntervalSeconds = 30,
    [string]$RestartScript = "$PSScriptRoot\restart_openclaw_deepseek.ps1"
)

$LogDir = "$PSScriptRoot\..\data\logs"
$null = New-Item -ItemType Directory -Path $LogDir -Force
$LogFile = "$LogDir\gateway_watchdog.log"
$PortGateway = 18789
$PortProxy = 18790

function Write-Log {
    param([string]$Message)
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$Timestamp | $Message" | Out-File -FilePath $LogFile -Append -Encoding utf8
    Write-Host "$Timestamp | $Message"
}

Write-Log "Watchdog started (interval=${IntervalSeconds}s, gateway=${PortGateway}, proxy=${PortProxy})"

while ($true) {
    $gwOk = $false
    $pxOk = $false
    try {
        $gwResult = Test-NetConnection -ComputerName 127.0.0.1 -Port $PortGateway -WarningAction SilentlyContinue -InformationLevel Quiet -ErrorAction Stop
        $gwOk = $gwResult
    } catch { $gwOk = $false }

    try {
        $pxResult = Test-NetConnection -ComputerName 127.0.0.1 -Port $PortProxy -WarningAction SilentlyContinue -InformationLevel Quiet -ErrorAction Stop
        $pxOk = $pxResult
    } catch { $pxOk = $false }

    if ($gwOk -and $pxOk) {
        Write-Log "Health OK  gateway=:$PortGateway proxy=:$PortProxy"
    } else {
        Write-Log "Health FAIL gateway=:$PortGateway($gwOk) proxy=:$PortProxy($pxOk) — restarting..."
        try {
            # Kill any stale gateway/proxy processes
            Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
                $_.CommandLine -match "openclaw" -or $_.CommandLine -match "ws_proxy"
            } | Stop-Process -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
            & $RestartScript
            Write-Log "Restart script completed"
        } catch {
            Write-Log "Restart FAILED: $_"
        }
    }

    Start-Sleep -Seconds $IntervalSeconds
}
