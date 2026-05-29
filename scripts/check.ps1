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
  "config/abilities/table-detection.yaml",
  "config/abilities/table-row-action.yaml",
  "config/abilities/recovery-policy.yaml",
  "config/abilities/vision-fallback.yaml",
  "config/abilities/candidate-ranking.yaml",
  "config/prompts/prompt-registry.yaml",
  "config/prompts/llm-analysis.yaml",
  "config/prompts/dsl-generation.yaml",
  "config/prompts/dsl-post-processing.yaml",
  "config/prompts/navigation-path.yaml",
  "config/prompts/element-location.yaml",
  "config/prompts/action-resolution.yaml",
  "config/prompts/vision-fallback.yaml",
  "config/prompts/failure-analysis.yaml",
  "config/prompts/human-intervention.yaml",
  "config/prompts/rule-suggestion.yaml",
  "config/prompts/form-autofill.yaml",
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

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  Write-Warning "Playwright Trace Viewer 依赖未安装：未找到 node。Trace 播放功能不可用。可安装 Node.js 后执行 npm install -g playwright。"
} elseif (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  Write-Warning "Playwright Trace Viewer 依赖未安装：未找到 npm。Trace 播放功能不可用。可安装 Node.js 后执行 npm install -g playwright。"
} elseif (-not (Get-Command npx -ErrorAction SilentlyContinue)) {
  Write-Warning "Playwright Trace Viewer 依赖未安装：未找到 npx。Trace 播放功能不可用。可执行 npm install -g playwright。"
} else {
  try {
    $traceCheck = Start-Process -FilePath "npx.cmd" -ArgumentList "--no-install playwright --version" -PassThru -Wait -WindowStyle Hidden
    if ($traceCheck.ExitCode -ne 0) {
      Write-Warning "Playwright Trace Viewer 依赖未安装，Trace 播放功能不可用。可执行 npm install -g playwright。"
    }
  } catch {
    Write-Warning "Playwright Trace Viewer 依赖未安装，Trace 播放功能不可用。可执行 npm install -g playwright。"
  }
}

$hostName = "127.0.0.1"
$backendPort = New-FreePort
$frontendPort = New-FreePort
$baseUrl = "http://$hostName`:$backendPort"
$frontendUrl = "http://$hostName`:$frontendPort"
$runtimeDir = ".runtime"
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

$env:TEST_LLM_STREAM = "true"
$env:VITE_API_BASE_URL = $baseUrl
$env:ALLOWED_BASE_URL_PREFIXES = "$baseUrl,$frontendUrl"

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
    "table_detection",
    "table_row_action",
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
    "recovery_policy",
    "candidate_ranking"
  )) {
    $typeCount = @($rules | Where-Object { $_.rule_type -eq $ruleType }).Count
    Assert-True ($typeCount -ge 2) "Rule type '$ruleType' has fewer than two enabled rules."
  }

  $prompts = Invoke-RestMethod -Uri "$baseUrl/api/prompts" -TimeoutSec 10
  Assert-True (@($prompts).Count -ge 11) "Prompt registry did not load expected prompts."
  $dslPrompt = @($prompts | Where-Object { $_.key -eq "test_dsl_generation" })[0]
  Assert-True ($null -ne $dslPrompt) "DSL generation prompt is missing."
  Assert-True ($dslPrompt.version -eq "1.0.0") "DSL generation prompt version is unexpected."
  $reloadResult = Invoke-JsonPost -Uri "$baseUrl/api/prompts/reload" -Body "{}" -TimeoutSec 10
  Assert-True ($reloadResult.loaded -ge 11) "Prompt reload did not load expected prompts."
  $promptPreviewPayload = @{
    variables = @{
      instruction = "进入工作台/我的待办"
      allowed_actions = "open_url,navigate_path"
      input_json = "{}"
    }
  } | ConvertTo-Json -Depth 8
  $promptPreview = Invoke-JsonPost -Uri "$baseUrl/api/prompts/test_dsl_generation/preview" -Body $promptPreviewPayload -TimeoutSec 10
  Assert-True ($promptPreview.prompt_key -eq "test_dsl_generation") "Prompt preview returned unexpected key."
  Assert-True ($promptPreview.user.Contains("navigate_path")) "Prompt preview did not include menu path navigation guidance."

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

  if ($env:CHECK_LLM_NETWORK -eq "true") {
    $analysisPayload = @{
      project_id = @($projects)[0].id
      system_id = $testSystem.id
      instruction = "打开真实系统入口，确认页面可访问"
      base_url = "$baseUrl/health"
      stream = $true
    } | ConvertTo-Json -Depth 8
    $analysis = Invoke-JsonPost -Uri "$baseUrl/api/test-runs/analyze" -Body $analysisPayload -TimeoutSec 60
    Assert-True ($analysis.readyToExecute -eq $true) "Natural-language analysis did not mark a complete connectivity goal as ready."
  } else {
    Write-Warning "LLM network check skipped. Set CHECK_LLM_NETWORK=true to verify the configured provider endpoint."
  }

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
