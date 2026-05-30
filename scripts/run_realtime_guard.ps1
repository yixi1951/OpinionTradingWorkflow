param(
  [string]$PythonPath = ".\.venv\Scripts\python.exe",
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
  [int]$MaxRestarts = 9999
)

$ErrorActionPreference = "Continue"
$env:OPENCLAW_URL = $OpenClawUrl
if ([string]::IsNullOrWhiteSpace($OpenClawToken)) {
  Remove-Item Env:OPENCLAW_TOKEN -ErrorAction SilentlyContinue
} else {
  $env:OPENCLAW_TOKEN = $OpenClawToken
}

$restartCount = 0
while ($restartCount -le $MaxRestarts) {
  Write-Host "[guard] starting realtime pipeline (restart=$restartCount)" -ForegroundColor Cyan

  & $PythonPath run_pipeline.py --mode realtime --iterations $Iterations --interval-seconds $IntervalSeconds --top-n $TopN --alert-threshold $AlertThreshold --yellow-threshold $YellowThreshold --orange-threshold $OrangeThreshold --red-threshold $RedThreshold
  $code = $LASTEXITCODE

  if ($code -eq 0) {
    Write-Host "[guard] process exited normally (code=0), restarting in $RestartDelaySeconds sec..." -ForegroundColor Green
  } else {
    Write-Host "[guard] process crashed (code=$code), restarting in $RestartDelaySeconds sec..." -ForegroundColor Yellow
  }

  $restartCount += 1
  Start-Sleep -Seconds $RestartDelaySeconds
}

Write-Host "[guard] reached MaxRestarts=$MaxRestarts, exiting." -ForegroundColor Red
