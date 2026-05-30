param(
  [string]$TaskName = "OpinionTradingRealtimeGuard",
  [string]$ProjectRoot = "",
  [string]$OpenClawUrl = "http://127.0.0.1:18080",
  [string]$OpenClawToken = "",
  [int]$Iterations = 10,
  [int]$IntervalSeconds = 30,
  [int]$TopN = 3,
  [double]$AlertThreshold = 0.25,
  [double]$YellowThreshold = 0.20,
  [double]$OrangeThreshold = 0.35,
  [double]$RedThreshold = 0.50,
  [int]$RestartDelaySeconds = 5,
  [int]$MaxRestarts = 9999,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
  $ProjectRoot = Split-Path -Parent $PSScriptRoot
}

$guardScript = Join-Path $ProjectRoot "scripts\run_realtime_guard.ps1"
if (-not (Test-Path $guardScript)) {
  throw "Guard script not found: $guardScript"
}

$escapedRoot = $ProjectRoot.Replace('"', '""')
$escapedGuard = $guardScript.Replace('"', '""')
$escapedUrl = $OpenClawUrl.Replace('"', '""')
$escapedToken = $OpenClawToken.Replace('"', '""')

$argList = @(
  "-NoProfile",
  "-ExecutionPolicy", "Bypass",
  "-File", "`"$escapedGuard`"",
  "-OpenClawUrl", "`"$escapedUrl`"",
  "-OpenClawToken", "`"$escapedToken`"",
  "-Iterations", "$Iterations",
  "-IntervalSeconds", "$IntervalSeconds",
  "-TopN", "$TopN",
  "-AlertThreshold", "$AlertThreshold",
  "-YellowThreshold", "$YellowThreshold",
  "-OrangeThreshold", "$OrangeThreshold",
  "-RedThreshold", "$RedThreshold",
  "-RestartDelaySeconds", "$RestartDelaySeconds",
  "-MaxRestarts", "$MaxRestarts"
)

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument ($argList -join " ") -WorkingDirectory $escapedRoot
$triggerStartup = New-ScheduledTaskTrigger -AtStartup
$triggerLogon = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

if ($DryRun) {
  Write-Host "[dry-run] TaskName: $TaskName"
  Write-Host "[dry-run] ProjectRoot: $ProjectRoot"
  Write-Host "[dry-run] GuardScript: $guardScript"
  Write-Host "[dry-run] Action: powershell.exe $($argList -join ' ')"
  Write-Host "[dry-run] Triggers: AtStartup + AtLogOn"
  exit 0
}

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger @($triggerStartup, $triggerLogon) -Settings $settings -Principal $principal | Out-Null
Write-Host "[ok] Registered scheduled task: $TaskName"
Write-Host "[ok] Start now with: Start-ScheduledTask -TaskName $TaskName"
