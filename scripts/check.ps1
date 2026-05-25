Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$requiredPaths = @(
  "backend/app/api",
  "backend/app/core",
  "backend/app/db",
  "backend/app/models",
  "backend/app/schemas",
  "backend/app/services",
  "backend/app/llm",
  "backend/app/execution",
  "backend/app/abilities",
  "backend/app/reports",
  "backend/app/utils",
  "backend/tests",
  "backend/requirements.txt",
  "frontend/src/api",
  "frontend/src/components",
  "frontend/src/pages",
  "frontend/src/routes",
  "frontend/src/stores",
  "frontend/src/styles",
  "frontend/src/types",
  "frontend/package.json",
  "frontend/vite.config.ts",
  "executor/aitp_executor/runner",
  "executor/aitp_executor/browser",
  "executor/aitp_executor/observer",
  "executor/aitp_executor/locator",
  "executor/aitp_executor/goal",
  "executor/aitp_executor/vision",
  "executor/aitp_executor/reports",
  "executor/aitp_executor/utils",
  "executor/requirements.txt",
  "mock-mis-demo/package.json",
  "mock-mis-demo/index.html",
  "mock-mis-demo/src",
  "config/abilities",
  "scripts/start.ps1",
  "scripts/stop.ps1",
  "scripts/check.ps1",
  "scripts/init-db.ps1",
  "scripts/run-demo.ps1",
  "scripts/e2e-demo.ps1",
  "data",
  "artifacts",
  "reports",
  ".env.example",
  ".gitignore",
  "README.md",
  "AGENTS.md"
)

$missing = @()
foreach ($path in $requiredPaths) {
  if (-not (Test-Path $path)) {
    $missing += $path
  }
}

if ($missing.Count -gt 0) {
  Write-Error ("Missing required paths:`n" + ($missing -join "`n"))
}

python -m compileall backend | Out-Null

$hostName = "127.0.0.1"
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
$listener.Start()
$port = [int]$listener.LocalEndpoint.Port
$listener.Stop()
$baseUrl = "http://$hostName`:$port"
$runtimeDir = ".runtime"
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

$outFile = Join-Path $runtimeDir "backend-check.out.log"
$errFile = Join-Path $runtimeDir "backend-check.err.log"
Remove-Item $outFile, $errFile -Force -ErrorAction SilentlyContinue

$args = @(
  "-m", "uvicorn",
  "app.main:app",
  "--app-dir", "backend",
  "--host", $hostName,
  "--port", $port,
  "--log-level", "warning"
)

$process = Start-Process `
  -FilePath "python" `
  -ArgumentList $args `
  -PassThru `
  -WindowStyle Hidden `
  -RedirectStandardOutput $outFile `
  -RedirectStandardError $errFile

try {
  $health = $null
  for ($i = 0; $i -lt 30; $i++) {
    if ($process.HasExited) {
      $stderr = ""
      if (Test-Path $errFile) {
        $stderr = Get-Content $errFile -Raw
      }
      Write-Error "Backend exited before health check completed. $stderr"
    }

    try {
      $health = Invoke-RestMethod -Uri "$baseUrl/health" -TimeoutSec 2
      break
    } catch {
      Start-Sleep -Milliseconds 500
    }
  }

  if ($null -eq $health) {
    Write-Error "Health check timed out."
  }

  if ($health.status -ne "ok") {
    Write-Error "Health check did not return ok status."
  }

  if ($health.service -ne "Enterprise MIS Intelligent Functional Testing Platform") {
    Write-Error "Health check reached an unexpected service."
  }

  if (-not $health.database.connected) {
    Write-Error "Database connection check failed."
  }

  $systemInfo = Invoke-RestMethod -Uri "$baseUrl/api/system/info" -TimeoutSec 5
  if (-not $systemInfo.database.connected) {
    Write-Error "System info database check failed."
  }

  $projects = Invoke-RestMethod -Uri "$baseUrl/api/projects" -TimeoutSec 5
  if (@($projects).Count -lt 1) {
    Write-Error "Default project was not initialized."
  }

  Write-Host "Stage 1 backend check passed."
} finally {
  if ($null -ne $process -and -not $process.HasExited) {
    Stop-Process -Id $process.Id -Force
  }
}
