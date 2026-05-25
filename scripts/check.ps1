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

Write-Host "Stage 0 skeleton check passed."
