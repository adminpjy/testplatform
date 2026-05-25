Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Stop-ManagedProcess {
  param(
    [string]$Name,
    [string]$PidFile
  )

  if (-not (Test-Path $PidFile)) {
    Write-Host "No $Name PID file found."
    return
  }

  $processPid = Get-Content $PidFile -Raw
  if ([string]::IsNullOrWhiteSpace($processPid)) {
    Remove-Item $PidFile -Force
    Write-Host "Empty $Name PID file removed."
    return
  }

  $process = Get-Process -Id ([int]$processPid) -ErrorAction SilentlyContinue
  if ($null -ne $process) {
    Stop-Process -Id $process.Id -Force
    Write-Host "$Name process $processPid stopped."
  } else {
    Write-Host "$Name process $processPid was not running."
  }

  Remove-Item $PidFile -Force
}

Stop-ManagedProcess -Name "Backend" -PidFile (Join-Path ".runtime" "backend.pid")
Stop-ManagedProcess -Name "Frontend" -PidFile (Join-Path ".runtime" "frontend.pid")
Stop-ManagedProcess -Name "Mock MIS demo" -PidFile (Join-Path ".runtime" "mock-mis-demo.pid")

$projectPath = (Resolve-Path -LiteralPath ".").Path
$frontendProcesses = Get-CimInstance Win32_Process |
  Where-Object {
    $_.CommandLine -and
    $_.CommandLine.Contains($projectPath) -and
    $_.CommandLine.Contains("frontend") -and
    $_.CommandLine.Contains("vite")
  }

foreach ($frontendProcess in $frontendProcesses) {
  Stop-Process -Id $frontendProcess.ProcessId -Force -ErrorAction SilentlyContinue
  Write-Host "Frontend child process $($frontendProcess.ProcessId) stopped."
}

$demoProcesses = Get-CimInstance Win32_Process |
  Where-Object {
    $_.CommandLine -and
    $_.CommandLine.Contains($projectPath) -and
    $_.CommandLine.Contains("mock-mis-demo") -and
    $_.CommandLine.Contains("vite")
  }

foreach ($demoProcess in $demoProcesses) {
  Stop-Process -Id $demoProcess.ProcessId -Force -ErrorAction SilentlyContinue
  Write-Host "Mock MIS demo child process $($demoProcess.ProcessId) stopped."
}
