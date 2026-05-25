Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$pidFile = Join-Path ".runtime" "backend.pid"
if (-not (Test-Path $pidFile)) {
  Write-Host "No backend PID file found."
  exit 0
}

$backendPid = Get-Content $pidFile -Raw
if ([string]::IsNullOrWhiteSpace($backendPid)) {
  Remove-Item $pidFile -Force
  Write-Host "Empty backend PID file removed."
  exit 0
}

$process = Get-Process -Id ([int]$backendPid) -ErrorAction SilentlyContinue
if ($null -ne $process) {
  Stop-Process -Id $process.Id -Force
  Write-Host "Backend process $backendPid stopped."
} else {
  Write-Host "Backend process $backendPid was not running."
}

Remove-Item $pidFile -Force
