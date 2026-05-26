Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Stop-ManagedProcess {
  param(
    [string]$Name,
    [string]$PidFile
  )

  if (-not (Test-Path $PidFile)) {
    Write-Host "$Name is not tracked."
    return
  }

  $pidValue = Get-Content $PidFile -Raw
  if ([string]::IsNullOrWhiteSpace($pidValue)) {
    Remove-Item $PidFile -Force
    return
  }

  $process = Get-Process -Id ([int]$pidValue) -ErrorAction SilentlyContinue
  if ($null -ne $process) {
    Stop-Process -Id $process.Id -Force
    Write-Host "$Name process $pidValue stopped."
  }
  Remove-Item $PidFile -Force
}

Stop-ManagedProcess -Name "Backend" -PidFile (Join-Path ".runtime" "backend.pid")
Stop-ManagedProcess -Name "Frontend" -PidFile (Join-Path ".runtime" "frontend.pid")

$frontendProcesses = Get-CimInstance Win32_Process |
  Where-Object {
    $null -ne $_.CommandLine -and
    $_.CommandLine.Contains("frontend") -and
    $_.CommandLine.Contains("vite")
  }

foreach ($frontendProcess in $frontendProcesses) {
  Stop-Process -Id $frontendProcess.ProcessId -Force -ErrorAction SilentlyContinue
  Write-Host "Frontend child process $($frontendProcess.ProcessId) stopped."
}
