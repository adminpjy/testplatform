Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$runtimeDir = ".runtime"
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

function Find-AvailablePort {
  param(
    [int]$PreferredPort
  )

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
    if (-not [string]::IsNullOrWhiteSpace($existingPid)) {
      $existingProcess = Get-Process -Id ([int]$existingPid) -ErrorAction SilentlyContinue
      if ($null -ne $existingProcess) {
        Write-Host "Backend is already running with PID $existingPid."
        return
      }
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

function Start-MockMisDemo {
  $mockHost = "127.0.0.1"
  $mockPort = $env:MOCK_MIS_PORT
  $hasExplicitPort = -not [string]::IsNullOrWhiteSpace($mockPort)
  if ([string]::IsNullOrWhiteSpace($mockPort)) {
    $mockPort = "5174"
  }
  if (Get-NetTCPConnection -LocalPort ([int]$mockPort) -ErrorAction SilentlyContinue) {
    if ($hasExplicitPort) {
      Write-Error "Mock MIS demo port $mockPort is already in use."
    }
    $mockPort = Find-AvailablePort -PreferredPort ([int]$mockPort)
  }

  $pidFile = Join-Path $runtimeDir "mock-mis-demo.pid"
  $outFile = Join-Path $runtimeDir "mock-mis-demo.out.log"
  $errFile = Join-Path $runtimeDir "mock-mis-demo.err.log"

  if (Test-Path $pidFile) {
    $existingPid = Get-Content $pidFile -Raw
    if (-not [string]::IsNullOrWhiteSpace($existingPid)) {
      $existingProcess = Get-Process -Id ([int]$existingPid) -ErrorAction SilentlyContinue
      if ($null -ne $existingProcess) {
        Write-Host "Mock MIS demo is already running with PID $existingPid."
        return
      }
    }
  }

  if (-not (Test-Path "mock-mis-demo/node_modules")) {
    npm.cmd --prefix mock-mis-demo install
  }

  $args = @(
    "--prefix", "mock-mis-demo",
    "run", "dev",
    "--",
    "--host", $mockHost,
    "--port", $mockPort,
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
  Write-Host "Mock MIS demo started at http://$mockHost`:$mockPort with PID $($process.Id)."
}

Start-Backend
Start-MockMisDemo
