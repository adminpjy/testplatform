Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$hostName = $env:BACKEND_HOST
if ([string]::IsNullOrWhiteSpace($hostName)) {
  $hostName = "127.0.0.1"
}

$port = $env:BACKEND_PORT
if ([string]::IsNullOrWhiteSpace($port)) {
  $port = "8000"
}

$runtimeDir = ".runtime"
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

$pidFile = Join-Path $runtimeDir "backend.pid"
$outFile = Join-Path $runtimeDir "backend.out.log"
$errFile = Join-Path $runtimeDir "backend.err.log"

if (Test-Path $pidFile) {
  $existingPid = Get-Content $pidFile -Raw
  if (-not [string]::IsNullOrWhiteSpace($existingPid)) {
    $existingProcess = Get-Process -Id ([int]$existingPid) -ErrorAction SilentlyContinue
    if ($null -ne $existingProcess) {
      Write-Host "Backend is already running with PID $existingPid."
      exit 0
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
