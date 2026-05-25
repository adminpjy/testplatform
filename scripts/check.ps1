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

$env:LLM_PROVIDER = "mock"
$env:TEST_LLM_STREAM = "true"

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
  $projectId = @($projects)[0].id

  $rules = Invoke-RestMethod -Uri "$baseUrl/api/abilities/rules?production_enabled=true" -TimeoutSec 5
  $requiredRuleTypes = @(
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
    "assertion",
    "dialog_handler",
    "risk_policy",
    "vision_fallback",
    "recovery_policy"
  )

  foreach ($ruleType in $requiredRuleTypes) {
    $typeCount = @($rules | Where-Object { $_.rule_type -eq $ruleType }).Count
    if ($typeCount -lt 2) {
      Write-Error "Ability rule type '$ruleType' has fewer than 2 enabled rules."
    }
  }

  $requiredRuleCodes = @("APPROVAL-PASS-v1", "APPROVAL-FLOW-VIEW-v1", "ENTER-TODO-LIST-v1")
  foreach ($ruleCode in $requiredRuleCodes) {
    $rule = $rules | Where-Object { $_.rule_code -eq $ruleCode } | Select-Object -First 1
    if ($null -eq $rule) {
      Write-Error "Required ability rule '$ruleCode' was not initialized."
    }
  }

  $approvalPassPayload = @{
    project_id = $projectId
    goal = "审批通过"
    action = "通过"
    target = "待办审批单"
    business_intent = "同意申请并完成审批"
    rule_types = @("approval_workflow")
    page_context = @{
      title = "我的待办"
      visible_text = "审批 通过 同意"
    }
  } | ConvertTo-Json -Depth 8
  $approvalPass = Invoke-RestMethod `
    -Uri "$baseUrl/api/abilities/resolve" `
    -Method Post `
    -ContentType "application/json" `
    -Body $approvalPassPayload `
    -TimeoutSec 5
  if ($approvalPass.selectedRule.rule_code -ne "APPROVAL-PASS-v1") {
    Write-Error "RuleResolver did not select APPROVAL-PASS-v1 for approval pass."
  }
  if ($approvalPass.reason -notlike "*命中规则 APPROVAL-PASS-v1*") {
    Write-Error "RuleResolver did not produce the expected runtime message."
  }

  $flowViewPayload = @{
    project_id = $projectId
    goal = "查看审批流程"
    action = "查看审批流程"
    target = "流程图"
    business_intent = "查看审批记录"
    rule_types = @("approval_workflow")
    page_context = @{
      visible_text = "审批流程 流程图 审批记录"
    }
  } | ConvertTo-Json -Depth 8
  $flowView = Invoke-RestMethod `
    -Uri "$baseUrl/api/abilities/resolve" `
    -Method Post `
    -ContentType "application/json" `
    -Body $flowViewPayload `
    -TimeoutSec 5
  if ($flowView.selectedRule.rule_code -ne "APPROVAL-FLOW-VIEW-v1") {
    Write-Error "RuleResolver misclassified approval flow view."
  }

  $todoPayload = @{
    project_id = $projectId
    goal = "进入我的待办"
    action = "打开"
    target = "工作台/我的待办"
    business_intent = "查看待办事项"
    rule_types = @("navigation")
    page_context = @{
      visible_text = "工作台 我的待办 待办表格"
    }
  } | ConvertTo-Json -Depth 8
  $todoResolve = Invoke-RestMethod `
    -Uri "$baseUrl/api/abilities/resolve" `
    -Method Post `
    -ContentType "application/json" `
    -Body $todoPayload `
    -TimeoutSec 5
  if ($todoResolve.selectedRule.rule_code -ne "ENTER-TODO-LIST-v1") {
    Write-Error "RuleResolver did not select ENTER-TODO-LIST-v1."
  }

  $insufficientPayload = @{
    instruction = "登录系统"
    stream = $true
  } | ConvertTo-Json -Depth 8
  $analysis = Invoke-RestMethod `
    -Uri "$baseUrl/api/test-runs/analyze" `
    -Method Post `
    -ContentType "application/json" `
    -Body $insufficientPayload `
    -TimeoutSec 5
  if ($analysis.readyToExecute -ne $false) {
    Write-Error "Natural language analysis should request more information for an incomplete goal."
  }
  if (@($analysis.clarifyingQuestions).Count -lt 1) {
    Write-Error "Natural language analysis did not return clarifying questions."
  }

  $planPayload = @{
    project_id = $projectId
    instruction = "打开 http://127.0.0.1:5174/login，使用账号 admin 密码 123456 登录系统，进入我的待办，确认页面存在我的待办"
    stream = $true
  } | ConvertTo-Json -Depth 8
  $dsl = Invoke-RestMethod `
    -Uri "$baseUrl/api/test-runs/plan" `
    -Method Post `
    -ContentType "application/json" `
    -Body $planPayload `
    -TimeoutSec 5
  if ([string]::IsNullOrWhiteSpace($dsl.caseName)) {
    Write-Error "TestCaseDSL did not include caseName."
  }
  if ([string]::IsNullOrWhiteSpace($dsl.baseUrl)) {
    Write-Error "TestCaseDSL did not include baseUrl."
  }
  if (@($dsl.steps).Count -lt 3) {
    Write-Error "TestCaseDSL did not include enough executable steps."
  }
  $allowedActions = @(
    "open_url",
    "input",
    "click",
    "navigate_menu",
    "wait_for_text",
    "assert_text_exists",
    "assert_text_not_exists",
    "assert_url_contains",
    "select",
    "upload_file",
    "wait",
    "confirm_dialog",
    "query_table",
    "click_table_row_action",
    "business_goal"
  )
  foreach ($step in $dsl.steps) {
    if ($allowedActions -notcontains $step.action) {
      Write-Error "TestCaseDSL returned unsupported action '$($step.action)'."
    }
  }
  $dslJson = $dsl | ConvertTo-Json -Depth 12
  if ($dslJson -like "*123456*") {
    Write-Error "TestCaseDSL exposed a plaintext password."
  }

  Write-Host "Stage 3 LLM parser check passed."
} finally {
  if ($null -ne $process -and -not $process.HasExited) {
    Stop-Process -Id $process.Id -Force
  }
}
