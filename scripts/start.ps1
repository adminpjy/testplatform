Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$runtimeDir = ".runtime"
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

function Import-DotEnv {
  if (-not (Test-Path ".env")) {
    return
  }
  Get-Content ".env" | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
      return
    }
    $name, $value = $line.Split("=", 2)
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name))) {
      [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
  }
}

function Find-AvailablePort {
  param([int]$PreferredPort)

  $port = $PreferredPort
  while (Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue) {
    $port++
  }
  return $port
}

function Start-Backend {
  $hostName = $env:BACKEND_HOST
  if ([string]::IsNullOrWhiteSpace($hostName)) {
    $hostName = "127.0.0.1"
  }
  $port = $env:BACKEND_PORT
  if ([string]::IsNullOrWhiteSpace($port)) {
    $port = "8000"
  }

  $pidFile = Join-Path $runtimeDir "backend.pid"
  $outFile = Join-Path $runtimeDir "backend.out.log"
  $errFile = Join-Path $runtimeDir "backend.err.log"

  if (Test-Path $pidFile) {
    $existingPid = Get-Content $pidFile -Raw
    $existingProcess = Get-Process -Id ([int]$existingPid) -ErrorAction SilentlyContinue
    if ($null -ne $existingProcess) {
      Write-Host "Backend is already running with PID $existingPid."
      return
    }
  }

  $args = @(
    "-m", "uvicorn",
    "app.main:app",
    "--app-dir", "backend",
    "--host", $hostName,
    "--port", $port
  )

  $process = Start-Process `
    -FilePath "python" `
    -ArgumentList $args `
    -PassThru `
    -WindowStyle Hidden `
    -RedirectStandardOutput $outFile `
    -RedirectStandardError $errFile

  Set-Content -Path $pidFile -Value $process.Id
  Write-Host "Backend started at http://$hostName`:$port with PID $($process.Id)."
}

function Start-Frontend {
  $frontendHost = "127.0.0.1"
  $backendHost = $env:BACKEND_HOST
  if ([string]::IsNullOrWhiteSpace($backendHost)) {
    $backendHost = "127.0.0.1"
  }
  $backendPort = $env:BACKEND_PORT
  if ([string]::IsNullOrWhiteSpace($backendPort)) {
    $backendPort = "8000"
  }
  $env:VITE_API_BASE_URL = "http://$backendHost`:$backendPort"

  $frontendPort = $env:FRONTEND_PORT
  $hasExplicitPort = -not [string]::IsNullOrWhiteSpace($frontendPort)
  if ([string]::IsNullOrWhiteSpace($frontendPort)) {
    $frontendPort = "5173"
  }
  if (Get-NetTCPConnection -LocalPort ([int]$frontendPort) -ErrorAction SilentlyContinue) {
    if ($hasExplicitPort) {
      Write-Error "Frontend port $frontendPort is already in use."
    }
    $frontendPort = Find-AvailablePort -PreferredPort ([int]$frontendPort)
  }

  $pidFile = Join-Path $runtimeDir "frontend.pid"
  $outFile = Join-Path $runtimeDir "frontend.out.log"
  $errFile = Join-Path $runtimeDir "frontend.err.log"

  if (Test-Path $pidFile) {
    $existingPid = Get-Content $pidFile -Raw
    $existingProcess = Get-Process -Id ([int]$existingPid) -ErrorAction SilentlyContinue
    if ($null -ne $existingProcess) {
      Write-Host "Frontend is already running with PID $existingPid."
      return
    }
  }

  if (-not (Test-Path "frontend/node_modules")) {
    npm.cmd --prefix frontend install
  }

  $args = @(
    "--prefix", "frontend",
    "run", "dev",
    "--",
    "--host", $frontendHost,
    "--port", $frontendPort,
    "--strictPort"
  )

  $process = Start-Process `
    -FilePath "npm.cmd" `
    -ArgumentList $args `
    -PassThru `
    -WindowStyle Hidden `
    -RedirectStandardOutput $outFile `
    -RedirectStandardError $errFile

  Set-Content -Path $pidFile -Value $process.Id
  Write-Host "Frontend started at http://$frontendHost`:$frontendPort with PID $($process.Id)."
}

Import-DotEnv
Start-Backend
Start-Frontend
