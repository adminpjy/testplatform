param(
  [string]$BackendHost = "127.0.0.1",
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 5173,
  [switch]$NoHealthCheck
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$runtimeDir = Join-Path $root ".runtime"
$logsDir = Join-Path $root "logs"

function Stop-ProcessByCommandLine {
  param(
    [string]$Name,
    [scriptblock]$Predicate
  )

  $currentProcessId = $PID
  $items = Get-CimInstance Win32_Process |
    Where-Object {
      $_.ProcessId -ne $currentProcessId -and
      $null -ne $_.CommandLine -and
      (& $Predicate $_)
    }

  foreach ($item in $items) {
    Stop-Process -Id $item.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "$Name process $($item.ProcessId) stopped."
  }
}

function Stop-PortOwnerIfManaged {
  param(
    [int]$Port,
    [string]$Name,
    [scriptblock]$Predicate
  )

  $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  foreach ($connection in $connections) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($connection.OwningProcess)" -ErrorAction SilentlyContinue
    if ($null -eq $process -or $null -eq $process.CommandLine) {
      continue
    }
    if (& $Predicate $process) {
      Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
      Write-Host "$Name port $Port owner process $($process.ProcessId) stopped."
    }
  }
}

function Wait-HttpOk {
  param(
    [string]$Name,
    [string]$Url,
    [int]$TimeoutSeconds = 30
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  do {
    try {
      $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
        Write-Host "$Name is responding: $Url"
        return
      }
    } catch {
      Start-Sleep -Milliseconds 500
    }
  } while ((Get-Date) -lt $deadline)

  throw "$Name did not respond within $TimeoutSeconds seconds: $Url"
}

Push-Location $root
try {
  New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
  New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

  $env:BACKEND_HOST = $BackendHost
  $env:BACKEND_PORT = [string]$BackendPort
  $env:FRONTEND_PORT = [string]$FrontendPort

  if (Test-Path ".\scripts\stop.ps1") {
    & ".\scripts\stop.ps1"
  }

  $rootPattern = [Regex]::Escape($root)
  Stop-ProcessByCommandLine -Name "Backend" -Predicate {
    param($process)
    $command = [string]$process.CommandLine
    ($command -match "uvicorn" -and $command -match "backend\.app\.main:app") -or
    ($command -match "python" -and $command -match "uvicorn" -and $command -match $rootPattern)
  }
  Stop-ProcessByCommandLine -Name "Frontend" -Predicate {
    param($process)
    $command = [string]$process.CommandLine
    $command -match $rootPattern -and $command -match "frontend" -and $command -match "vite"
  }
  Stop-PortOwnerIfManaged -Port $BackendPort -Name "Backend" -Predicate {
    param($process)
    $command = [string]$process.CommandLine
    $command -match "uvicorn" -and ($command -match "backend\.app\.main:app" -or $command -match "app\.main:app")
  }
  Stop-PortOwnerIfManaged -Port $FrontendPort -Name "Frontend" -Predicate {
    param($process)
    $command = [string]$process.CommandLine
    $command -match $rootPattern -and $command -match "frontend" -and $command -match "vite"
  }

  Start-Sleep -Seconds 1
  & ".\scripts\start.ps1"

  if (-not $NoHealthCheck) {
    Wait-HttpOk -Name "Backend" -Url "http://$BackendHost`:$BackendPort/docs"
    Wait-HttpOk -Name "Frontend" -Url "http://127.0.0.1:$FrontendPort/"
  }

  Write-Host ""
  Write-Host "Restart completed."
  Write-Host "Backend:  http://$BackendHost`:$BackendPort"
  Write-Host "Frontend: http://127.0.0.1:$FrontendPort"
  Write-Host "Logs:     .runtime\backend.err.log, .runtime\frontend.err.log"
} finally {
  Pop-Location
}
