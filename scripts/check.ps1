Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-JsonPost {
  param(
    [Parameter(Mandatory = $true)][string]$Uri,
    [Parameter(Mandatory = $true)][string]$Body,
    [int]$TimeoutSec = 30
  )

  $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($Body)
  Invoke-RestMethod `
    -Uri $Uri `
    -Method Post `
    -ContentType "application/json; charset=utf-8" `
    -Body $bodyBytes `
    -TimeoutSec $TimeoutSec
}

function Assert-True {
  param([bool]$Condition, [string]$Message)
  if (-not $Condition) {
    Write-Error $Message
  }
}

function New-FreePort {
  $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
  $listener.Start()
  try {
    return [int]$listener.LocalEndpoint.Port
  } finally {
    $listener.Stop()
  }
}

function Wait-HttpOk {
  param(
    [string]$Uri,
    [string]$Name,
    [System.Diagnostics.Process]$Process,
    [string]$ErrorLog
  )

  for ($i = 0; $i -lt 60; $i++) {
    if ($Process.HasExited) {
      $stderr = ""
      if (Test-Path $ErrorLog) {
        $stderr = Get-Content $ErrorLog -Raw -Encoding UTF8
      }
      Write-Error "$Name exited before readiness check completed. $stderr"
    }
    try {
      $response = Invoke-WebRequest -Uri $Uri -TimeoutSec 2 -UseBasicParsing
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
        return $response
      }
    } catch {
      Start-Sleep -Milliseconds 500
    }
  }
  Write-Error "$Name did not become ready at $Uri."
}

$requiredPaths = @(
  "backend/app/api",
  "backend/app/api/systems.py",
  "backend/app/core",
  "backend/app/db",
  "backend/app/models",
  "backend/app/schemas/systems.py",
  "backend/app/services/systems.py",
  "backend/app/llm",
  "backend/app/execution",
  "backend/app/abilities",
  "backend/app/reports",
  "backend/app/utils/secrets.py",
  "backend/tests",
  "backend/requirements.txt",
  "backend/Dockerfile",
  "frontend/src/api",
  "frontend/src/components",
  "frontend/src/pages/TestSystemsPage.tsx",
  "frontend/src/pages/TestRunPage.tsx",
  "frontend/src/routes",
  "frontend/src/stores",
  "frontend/src/styles",
  "frontend/src/types",
  "frontend/package.json",
  "frontend/vite.config.ts",
  "frontend/Dockerfile",
  "executor/aitp_executor/runner",
  "executor/aitp_executor/browser/sandbox_provider.py",
  "executor/aitp_executor/locator/auto_form_filler.py",
  "executor/requirements.txt",
  "config/abilities/form-fill.yaml",
  "config/abilities/dropdown.yaml",
  "config/abilities/date-picker.yaml",
  "config/abilities/org-selector.yaml",
  "config/abilities/person-selector.yaml",
  "config/abilities/tree-selector.yaml",
  "config/abilities/dialog-selector.yaml",
  "config/abilities/file-upload.yaml",
  "scripts/start.ps1",
  "scripts/stop.ps1",
  "scripts/check.ps1",
  "scripts/init-db.ps1",
  "scripts/run-smoke.ps1",
  "scripts/e2e-real-system.ps1",
  "data/.gitkeep",
  "artifacts/.gitkeep",
  "reports/.gitkeep",
  ".env.example",
  ".gitignore",
  "README.md",
  "AGENTS.md",
  "docker-compose.yml"
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

$removedLocalDemoDir = ("mock-" + "mis-demo")
Assert-True (-not (Test-Path $removedLocalDemoDir)) "Legacy local validation app directory should not exist."

python -m compileall backend executor | Out-Null

if (-not (Test-Path "frontend/node_modules")) {
  npm.cmd --prefix frontend install
}
Push-Location "frontend"
try {
  npx.cmd tsc --noEmit
} finally {
  Pop-Location
}
npm.cmd --prefix frontend run build | Out-Null

$hostName = "127.0.0.1"
$backendPort = New-FreePort
$frontendPort = New-FreePort
$baseUrl = "http://$hostName`:$backendPort"
$frontendUrl = "http://$hostName`:$frontendPort"
$runtimeDir = ".runtime"
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

$env:LLM_PROVIDER = "mock"
$env:TEST_LLM_STREAM = "true"
$env:VITE_API_BASE_URL = $baseUrl

$backendOut = Join-Path $runtimeDir "backend-check.out.log"
$backendErr = Join-Path $runtimeDir "backend-check.err.log"
$frontendOut = Join-Path $runtimeDir "frontend-check.out.log"
$frontendErr = Join-Path $runtimeDir "frontend-check.err.log"
Remove-Item $backendOut, $backendErr, $frontendOut, $frontendErr -Force -ErrorAction SilentlyContinue

$backendArgs = @(
  "-m", "uvicorn",
  "app.main:app",
  "--app-dir", "backend",
  "--host", $hostName,
  "--port", $backendPort,
  "--log-level", "warning"
)
$backendProcess = Start-Process `
  -FilePath "python" `
  -ArgumentList $backendArgs `
  -PassThru `
  -WindowStyle Hidden `
  -RedirectStandardOutput $backendOut `
  -RedirectStandardError $backendErr

$frontendArgs = @(
  "--prefix", "frontend",
  "run", "dev",
  "--",
  "--host", $hostName,
  "--port", $frontendPort,
  "--strictPort",
  "--logLevel", "silent"
)
$frontendProcess = Start-Process `
  -FilePath "npm.cmd" `
  -ArgumentList $frontendArgs `
  -PassThru `
  -WindowStyle Hidden `
  -RedirectStandardOutput $frontendOut `
  -RedirectStandardError $frontendErr

try {
  Wait-HttpOk -Uri "$baseUrl/health" -Name "backend" -Process $backendProcess -ErrorLog $backendErr | Out-Null
  Wait-HttpOk -Uri $frontendUrl -Name "frontend" -Process $frontendProcess -ErrorLog $frontendErr | Out-Null

  $health = Invoke-RestMethod -Uri "$baseUrl/health" -TimeoutSec 5
  Assert-True ($health.status -eq "ok") "Health check did not return ok."
  Assert-True ($health.database.connected -eq $true) "Database connection check failed."

  $systemInfo = Invoke-RestMethod -Uri "$baseUrl/api/system/info" -TimeoutSec 5
  Assert-True ($systemInfo.database.connected -eq $true) "System info database check failed."

  $projects = Invoke-RestMethod -Uri "$baseUrl/api/projects" -TimeoutSec 5
  Assert-True (@($projects).Count -gt 0) "Default project was not initialized."

  $rules = Invoke-RestMethod -Uri "$baseUrl/api/abilities/rules?production_enabled=true" -TimeoutSec 10
  foreach ($ruleType in @(
    "login",
    "global_interruption",
    "navigation",
    "query",
    "create",
    "update",
    "delete",
    "table_operation",
    "detail_navigation",
    "approval_workflow",
    "form_control",
    "form_fill",
    "dropdown",
    "date_picker",
    "org_selector",
    "person_selector",
    "tree_selector",
    "dialog_selector",
    "file_upload",
    "assertion",
    "dialog_handler",
    "risk_policy",
    "vision_fallback",
    "recovery_policy"
  )) {
    $typeCount = @($rules | Where-Object { $_.rule_type -eq $ruleType }).Count
    Assert-True ($typeCount -ge 2) "Rule type '$ruleType' has fewer than two enabled rules."
  }

  $systemPayload = @{
    system_code = "CHECK-$backendPort"
    system_name = "Check Target System"
    description = "Temporary system created by check.ps1."
    base_url = "$baseUrl/health"
    login_url = "$baseUrl/health"
    home_url = "$baseUrl/health"
    environment = "test"
    auth_type = "username_password"
    default_timeout_ms = 10000
    allow_write = $false
    allow_approval = $false
    allow_delete = $false
    status = "active"
    config_json = @{
      verify_tls = $true
    }
  } | ConvertTo-Json -Depth 8
  $testSystem = Invoke-JsonPost -Uri "$baseUrl/api/systems" -Body $systemPayload -TimeoutSec 10
  Assert-True ($testSystem.id -gt 0) "System create API did not return an id."

  $systems = Invoke-RestMethod -Uri "$baseUrl/api/systems" -TimeoutSec 5
  Assert-True (@($systems).Count -gt 0) "Systems API returned no systems."

  $connectivity = Invoke-JsonPost -Uri "$baseUrl/api/systems/$($testSystem.id)/check-connectivity" -Body "{}" -TimeoutSec 30
  Assert-True ($connectivity.status -eq "passed") "Connectivity check did not pass."
  Assert-True ($connectivity.http_status -eq 200) "Connectivity check did not record HTTP 200."

  $analysisPayload = @{
    project_id = @($projects)[0].id
    system_id = $testSystem.id
    instruction = "打开真实系统入口，确认页面可访问"
    base_url = "$baseUrl/health"
    stream = $true
  } | ConvertTo-Json -Depth 8
  $analysis = Invoke-JsonPost -Uri "$baseUrl/api/test-runs/analyze" -Body $analysisPayload -TimeoutSec 10
  Assert-True ($analysis.readyToExecute -eq $true) "Natural-language analysis did not mark a complete connectivity goal as ready."

  $knowledge = Invoke-RestMethod -Uri "$baseUrl/api/abilities/knowledge" -TimeoutSec 5
  Assert-True ($null -ne $knowledge) "Ability knowledge API did not respond."

  Write-Host "Production v1 check passed."
} finally {
  if ($null -ne $backendProcess -and -not $backendProcess.HasExited) {
    Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
  }
  if ($null -ne $frontendProcess -and -not $frontendProcess.HasExited) {
    Stop-Process -Id $frontendProcess.Id -Force -ErrorAction SilentlyContinue
  }
}
