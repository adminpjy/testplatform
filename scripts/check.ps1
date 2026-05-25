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
  "frontend/src/api/client.ts",
  "frontend/src/api/platform.ts",
  "frontend/src/api/runtimeStream.ts",
  "frontend/src/App.tsx",
  "frontend/src/components",
  "frontend/src/components/DataTable.tsx",
  "frontend/src/components/DebugDrawer.tsx",
  "frontend/src/components/ErrorSummaryCard.tsx",
  "frontend/src/components/RuntimeStreamPanel.tsx",
  "frontend/src/components/ScreenshotPanel.tsx",
  "frontend/src/components/StatusBadge.tsx",
  "frontend/src/components/StepTree.tsx",
  "frontend/src/main.tsx",
  "frontend/src/pages",
  "frontend/src/pages/AbilityCenterPage.tsx",
  "frontend/src/pages/FailureSamplesPage.tsx",
  "frontend/src/pages/MockMisDemoPage.tsx",
  "frontend/src/pages/ReportsPage.tsx",
  "frontend/src/pages/SystemSettingsPage.tsx",
  "frontend/src/pages/TestRunPage.tsx",
  "frontend/src/routes",
  "frontend/src/routes/navigation.ts",
  "frontend/src/stores",
  "frontend/src/styles",
  "frontend/src/styles/app.css",
  "frontend/src/styles/runtime-stream.css",
  "frontend/src/types",
  "frontend/src/types/platform.ts",
  "frontend/src/types/runtime.ts",
  "frontend/src/vite-env.d.ts",
  "frontend/index.html",
  "frontend/package.json",
  "frontend/tsconfig.json",
  "frontend/vite.config.ts",
  "executor/aitp_executor/runner",
  "executor/aitp_executor/runner/case_runner.py",
  "executor/aitp_executor/browser",
  "executor/aitp_executor/browser/sandbox_provider.py",
  "executor/aitp_executor/browser/local_playwright_provider.py",
  "executor/aitp_executor/observer",
  "executor/aitp_executor/observer/page_observer.py",
  "executor/aitp_executor/locator",
  "executor/aitp_executor/locator/page_semantic_extractor.py",
  "executor/aitp_executor/locator/business_intent_normalizer.py",
  "executor/aitp_executor/locator/candidate_ranker.py",
  "executor/aitp_executor/locator/ambiguity_resolver.py",
  "executor/aitp_executor/locator/element_locator.py",
  "executor/aitp_executor/locator/llm_element_resolver.py",
  "executor/aitp_executor/locator/vision_resolver.py",
  "executor/aitp_executor/goal",
  "executor/aitp_executor/goal/goal_executor.py",
  "executor/aitp_executor/goal/goal_planner.py",
  "executor/aitp_executor/goal/goal_success_verifier.py",
  "executor/aitp_executor/goal/recovery_policy.py",
  "executor/aitp_executor/vision",
  "executor/aitp_executor/reports",
  "executor/aitp_executor/reports/artifact_writer.py",
  "executor/aitp_executor/reports/report_writer.py",
  "executor/aitp_executor/utils",
  "executor/aitp_executor/utils/file_paths.py",
  "executor/requirements.txt",
  "mock-mis-demo/package.json",
  "mock-mis-demo/index.html",
  "mock-mis-demo/vite.config.ts",
  "mock-mis-demo/tsconfig.json",
  "mock-mis-demo/src/main.tsx",
  "mock-mis-demo/src/styles.css",
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

if (-not (Test-Path "mock-mis-demo/node_modules")) {
  npm.cmd --prefix mock-mis-demo install
}
Push-Location "mock-mis-demo"
try {
  npx.cmd tsc --noEmit
} finally {
  Pop-Location
}
npm.cmd --prefix mock-mis-demo run build | Out-Null

$hostName = "127.0.0.1"
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
$listener.Start()
$port = [int]$listener.LocalEndpoint.Port
$listener.Stop()
$baseUrl = "http://$hostName`:$port"
$mockListener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
$mockListener.Start()
$mockPort = [int]$mockListener.LocalEndpoint.Port
$mockListener.Stop()
$mockBaseUrl = "http://$hostName`:$mockPort"
$runtimeDir = ".runtime"
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

$env:LLM_PROVIDER = "mock"
$env:TEST_LLM_STREAM = "true"

$outFile = Join-Path $runtimeDir "backend-check.out.log"
$errFile = Join-Path $runtimeDir "backend-check.err.log"
$mockOutFile = Join-Path $runtimeDir "mock-mis-demo-check.out.log"
$mockErrFile = Join-Path $runtimeDir "mock-mis-demo-check.err.log"
Remove-Item $outFile, $errFile, $mockOutFile, $mockErrFile -Force -ErrorAction SilentlyContinue

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

$mockArgs = @(
  "--prefix", "mock-mis-demo",
  "run", "dev",
  "--",
  "--host", $hostName,
  "--port", $mockPort,
  "--strictPort",
  "--logLevel", "silent"
)

$mockProcess = Start-Process `
  -FilePath "npm.cmd" `
  -ArgumentList $mockArgs `
  -PassThru `
  -WindowStyle Hidden `
  -RedirectStandardOutput $mockOutFile `
  -RedirectStandardError $mockErrFile

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

  $loginHtml = $null
  for ($i = 0; $i -lt 30; $i++) {
    if ($mockProcess.HasExited) {
      $stderr = ""
      if (Test-Path $mockErrFile) {
        $stderr = Get-Content $mockErrFile -Raw
      }
      Write-Error "Mock MIS demo exited before access check completed. $stderr"
    }

    try {
      $loginHtml = Invoke-WebRequest -Uri "$mockBaseUrl/login" -TimeoutSec 2
      break
    } catch {
      Start-Sleep -Milliseconds 500
    }
  }

  if ($null -eq $loginHtml) {
    Write-Error "Mock MIS demo access check timed out."
  }

  if ($loginHtml.StatusCode -ne 200) {
    Write-Error "Mock MIS demo /login did not return HTTP 200."
  }

  $noticeHtml = Invoke-WebRequest -Uri "$mockBaseUrl/login?notice=account-expiry" -TimeoutSec 5
  if ($noticeHtml.StatusCode -ne 200) {
    Write-Error "Mock MIS demo notice login URL did not return HTTP 200."
  }

  $todoHtml = Invoke-WebRequest -Uri "$mockBaseUrl/todo" -TimeoutSec 5
  if ($todoHtml.StatusCode -ne 200) {
    Write-Error "Mock MIS demo /todo did not return HTTP 200."
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
  $approvalPass = Invoke-JsonPost -Uri "$baseUrl/api/abilities/resolve" -Body $approvalPassPayload -TimeoutSec 5
  if ($approvalPass.selectedRule.rule_code -ne "APPROVAL-PASS-v1") {
    Write-Error "RuleResolver did not select APPROVAL-PASS-v1 for approval pass."
  }
  if ($approvalPass.reason -notlike "*APPROVAL-PASS-v1*") {
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
  $flowView = Invoke-JsonPost -Uri "$baseUrl/api/abilities/resolve" -Body $flowViewPayload -TimeoutSec 5
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
  $todoResolve = Invoke-JsonPost -Uri "$baseUrl/api/abilities/resolve" -Body $todoPayload -TimeoutSec 5
  if ($todoResolve.selectedRule.rule_code -ne "ENTER-TODO-LIST-v1") {
    Write-Error "RuleResolver did not select ENTER-TODO-LIST-v1."
  }

  $insufficientPayload = @{
    instruction = "登录系统"
    stream = $true
  } | ConvertTo-Json -Depth 8
  $analysis = Invoke-JsonPost -Uri "$baseUrl/api/test-runs/analyze" -Body $insufficientPayload -TimeoutSec 5
  if ($analysis.readyToExecute -ne $false) {
    Write-Error "Natural language analysis should request more information for an incomplete goal."
  }
  if (@($analysis.clarifyingQuestions).Count -lt 1) {
    Write-Error "Natural language analysis did not return clarifying questions."
  }

  $planPayload = @{
    project_id = $projectId
    instruction = "打开 $mockBaseUrl/login，使用账号 admin 密码 123456 登录系统，进入我的待办，确认页面存在我的待办"
    stream = $true
  } | ConvertTo-Json -Depth 8
  $dsl = Invoke-JsonPost -Uri "$baseUrl/api/test-runs/plan" -Body $planPayload -TimeoutSec 5
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

  $runPayload = @{
    project_id = $projectId
    instruction = "打开 Mock MIS 登录页并验证登录成功"
    base_url = "$mockBaseUrl/login"
    dsl_json = @{
      caseName = "打开 Mock MIS 登录页"
      baseUrl = "$mockBaseUrl/login"
      credentials = @{}
      settings = @{
        headless = $true
      }
      steps = @(
        @{
          action = "open_url"
          target = "$mockBaseUrl/login"
        },
        @{
          action = "input"
          target = "用户名"
          value = "admin"
        },
        @{
          action = "input"
          target = "密码"
          value = "123456"
        },
        @{
          action = "click"
          target = "登录"
        },
        @{
          action = "wait_for_text"
          target = "华东生产验证环境"
        },
        @{
          action = "assert_url_contains"
          target = "/dashboard"
        }
      )
    }
  } | ConvertTo-Json -Depth 12
  $run = Invoke-JsonPost -Uri "$baseUrl/api/test-runs" -Body $runPayload -TimeoutSec 60
  if ($run.status -ne "passed") {
    Write-Error "Playwright executor run did not pass. Status: $($run.status)"
  }
  if ([string]::IsNullOrWhiteSpace($run.summary_json.status)) {
    Write-Error "Test run summary was not persisted."
  }
  $storedRunJson = $run | ConvertTo-Json -Depth 20
  if ($storedRunJson -like "*123456*") {
    Write-Error "Persisted test run exposed a plaintext password."
  }

  $runSteps = Invoke-RestMethod -Uri "$baseUrl/api/test-runs/$($run.id)/steps" -TimeoutSec 5
  if (@($runSteps).Count -lt 6) {
    Write-Error "Test run steps were not persisted."
  }

  $runArtifacts = Invoke-RestMethod -Uri "$baseUrl/api/test-runs/$($run.id)/artifacts" -TimeoutSec 5
  if (@($runArtifacts | Where-Object { $_.artifact_type -eq "screenshot" }).Count -lt 1) {
    Write-Error "Screenshot artifact was not persisted."
  }
  $summaryArtifact = $runArtifacts | Where-Object { $_.artifact_type -eq "summary_json" } | Select-Object -First 1
  if ($null -eq $summaryArtifact -or -not (Test-Path $summaryArtifact.file_path)) {
    Write-Error "summary.json artifact does not exist on disk."
  }
  $reportArtifact = $runArtifacts | Where-Object { $_.artifact_type -eq "report_html" } | Select-Object -First 1
  if ($null -eq $reportArtifact -or -not (Test-Path $reportArtifact.file_path)) {
    Write-Error "report.html artifact does not exist on disk."
  }

  $latestScreenshot = Invoke-WebRequest -Uri "$baseUrl/api/test-runs/$($run.id)/latest-screenshot" -TimeoutSec 10
  if ($latestScreenshot.StatusCode -ne 200) {
    Write-Error "Latest screenshot endpoint did not return HTTP 200."
  }
  $reportResponse = Invoke-WebRequest -Uri "$baseUrl/api/reports/$($run.id)" -TimeoutSec 10
  if ($reportResponse.StatusCode -ne 200 -or $reportResponse.Content -notlike "*测试执行报告*") {
    Write-Error "Report endpoint did not return report.html."
  }
  $fileResponse = Invoke-WebRequest -Uri "$baseUrl/files/$($summaryArtifact.file_path)" -TimeoutSec 10
  if ($fileResponse.StatusCode -ne 200 -or $fileResponse.Content -notlike "*runCode*") {
    Write-Error "File endpoint did not return summary artifact."
  }

  $approvalGoalPayload = @{
    project_id = $projectId
    instruction = "目标驱动：进入我的待办并审批通过"
    base_url = "$mockBaseUrl/login"
    dsl_json = @{
      caseName = "目标驱动审批通过"
      baseUrl = "$mockBaseUrl/login"
      credentials = @{}
      settings = @{}
      steps = @(
        @{ action = "open_url"; target = "$mockBaseUrl/login" },
        @{ action = "input"; target = "用户名"; value = "admin" },
        @{ action = "input"; target = "密码"; value = "123456" },
        @{ action = "click"; target = "登录" },
        @{ action = "business_goal"; target = "工作台/我的待办" },
        @{ action = "business_goal"; target = "审批通过" },
        @{ action = "wait_for_text"; target = "审批成功" }
      )
    }
  } | ConvertTo-Json -Depth 12
  $approvalGoalRun = Invoke-JsonPost -Uri "$baseUrl/api/test-runs" -Body $approvalGoalPayload -TimeoutSec 60
  if ($approvalGoalRun.status -ne "passed") {
    Write-Error "Goal executor did not pass approval_pass scenario."
  }
  $approvalGoalArtifacts = Invoke-RestMethod -Uri "$baseUrl/api/test-runs/$($approvalGoalRun.id)/artifacts" -TimeoutSec 5
  $approvalLocatorArtifact = $approvalGoalArtifacts | Where-Object { $_.artifact_type -eq "locator_debug_jsonl" } | Select-Object -First 1
  $approvalLocatorEvents = Get-Content $approvalLocatorArtifact.file_path -Encoding UTF8 | ForEach-Object { $_ | ConvertFrom-Json }
  $approvalDecision = $approvalLocatorEvents | Where-Object { $_.target -eq "审批通过" } | Select-Object -First 1
  if ($approvalDecision.element_ref -ne "审批") {
    Write-Error "Approval pass target did not select the exact approval action."
  }

  $flowGoalPayload = @{
    project_id = $projectId
    instruction = "目标驱动：进入我的待办并查看审批流程"
    base_url = "$mockBaseUrl/login"
    dsl_json = @{
      caseName = "目标驱动查看审批流程"
      baseUrl = "$mockBaseUrl/login"
      credentials = @{}
      settings = @{}
      steps = @(
        @{ action = "open_url"; target = "$mockBaseUrl/login" },
        @{ action = "input"; target = "用户名"; value = "admin" },
        @{ action = "input"; target = "密码"; value = "123456" },
        @{ action = "click"; target = "登录" },
        @{ action = "business_goal"; target = "工作台/我的待办" },
        @{ action = "business_goal"; target = "查看审批流程" },
        @{ action = "assert_url_contains"; target = "flow=true" }
      )
    }
  } | ConvertTo-Json -Depth 12
  $flowGoalRun = Invoke-JsonPost -Uri "$baseUrl/api/test-runs" -Body $flowGoalPayload -TimeoutSec 60
  if ($flowGoalRun.status -ne "passed") {
    Write-Error "Goal executor did not pass approval_flow_view scenario."
  }
  $flowGoalArtifacts = Invoke-RestMethod -Uri "$baseUrl/api/test-runs/$($flowGoalRun.id)/artifacts" -TimeoutSec 5
  $flowLocatorArtifact = $flowGoalArtifacts | Where-Object { $_.artifact_type -eq "locator_debug_jsonl" } | Select-Object -First 1
  $flowLocatorEvents = Get-Content $flowLocatorArtifact.file_path -Encoding UTF8 | ForEach-Object { $_ | ConvertFrom-Json }
  $flowDecision = $flowLocatorEvents | Where-Object { $_.target -eq "查看审批流程" } | Select-Object -First 1
  if ($flowDecision.element_ref -ne "查看审批流程") {
    Write-Error "Approval flow target did not select 查看审批流程."
  }

  $userGoalPayload = @{
    project_id = $projectId
    instruction = "目标驱动：进入用户管理并新增用户"
    base_url = "$mockBaseUrl/login"
    dsl_json = @{
      caseName = "目标驱动用户管理新增"
      baseUrl = "$mockBaseUrl/login"
      credentials = @{}
      settings = @{}
      steps = @(
        @{ action = "open_url"; target = "$mockBaseUrl/login" },
        @{ action = "input"; target = "用户名"; value = "admin" },
        @{ action = "input"; target = "密码"; value = "123456" },
        @{ action = "click"; target = "登录" },
        @{ action = "navigate_menu"; target = "用户管理" },
        @{ action = "input"; target = "用户名"; value = "goal_user" },
        @{ action = "input"; target = "姓名"; value = "目标用户" },
        @{ action = "click"; target = "新增" },
        @{ action = "wait_for_text"; target = "goal_user" }
      )
    }
  } | ConvertTo-Json -Depth 12
  $userGoalRun = Invoke-JsonPost -Uri "$baseUrl/api/test-runs" -Body $userGoalPayload -TimeoutSec 60
  if ($userGoalRun.status -ne "passed") {
    Write-Error "Goal executor did not fill the non-standard username field."
  }
  $userGoalArtifacts = Invoke-RestMethod -Uri "$baseUrl/api/test-runs/$($userGoalRun.id)/artifacts" -TimeoutSec 5
  $userLocatorArtifact = $userGoalArtifacts | Where-Object { $_.artifact_type -eq "locator_debug_jsonl" } | Select-Object -First 1
  $userLocatorEvents = Get-Content $userLocatorArtifact.file_path -Encoding UTF8 | ForEach-Object { $_ | ConvertFrom-Json }
  $userNameDecision = $userLocatorEvents | Where-Object { $_.target -eq "用户名" -and $_.step_number -eq 6 } | Select-Object -First 1
  if ($userNameDecision.locator_strategy -ne "playwright_label_exact") {
    Write-Error "Username field was not resolved through the label-backed non-standard DOM field."
  }
  $userDomArtifacts = $userGoalArtifacts | Where-Object { $_.artifact_type -eq "dom_snapshot" }
  $hasLegacyUserField = $false
  foreach ($domArtifact in $userDomArtifacts) {
    if ((Get-Content $domArtifact.file_path -Raw -Encoding UTF8) -like "*id=`"j_name`"*") {
      $hasLegacyUserField = $true
      break
    }
  }
  if (-not $hasLegacyUserField) {
    Write-Error "User management DOM evidence did not include id=j_name."
  }

  $lowConfidencePayload = @{
    project_id = $projectId
    instruction = "目标驱动：触发低置信度定位"
    base_url = "$mockBaseUrl/login"
    dsl_json = @{
      caseName = "低置信度视觉兜底验证"
      baseUrl = "$mockBaseUrl/login"
      credentials = @{}
      settings = @{}
      steps = @(
        @{ action = "open_url"; target = "$mockBaseUrl/login" },
        @{ action = "click"; target = "完全不存在的按钮" }
      )
    }
  } | ConvertTo-Json -Depth 12
  $lowConfidenceRun = Invoke-JsonPost -Uri "$baseUrl/api/test-runs" -Body $lowConfidencePayload -TimeoutSec 60
  if ($lowConfidenceRun.status -ne "failed") {
    Write-Error "Low confidence run should fail when vision fallback is not configured."
  }
  $lowConfidenceArtifacts = Invoke-RestMethod -Uri "$baseUrl/api/test-runs/$($lowConfidenceRun.id)/artifacts" -TimeoutSec 5
  $lowLocatorArtifact = $lowConfidenceArtifacts | Where-Object { $_.artifact_type -eq "locator_debug_jsonl" } | Select-Object -First 1
  $lowLocatorEvents = Get-Content $lowLocatorArtifact.file_path -Encoding UTF8 | ForEach-Object { $_ | ConvertFrom-Json }
  $lowDecision = $lowLocatorEvents | Where-Object { $_.target -eq "完全不存在的按钮" } | Select-Object -First 1
  if ($lowDecision.needs_vision_fallback -ne $true) {
    Write-Error "Low confidence locator did not record vision fallback requirement."
  }
  if ($lowDecision.fallback_reason -ne "vision_fallback_not_configured") {
    Write-Error "Vision fallback missing status was not recorded."
  }

  $runtimeMessages = Invoke-RestMethod -Uri "$baseUrl/api/test-runs/$($approvalGoalRun.id)/runtime-messages" -TimeoutSec 5
  if (@($runtimeMessages).Count -lt 1) {
    Write-Error "Runtime messages were not persisted to the database."
  }

  $normalStream = Invoke-WebRequest -Uri "$baseUrl/api/test-runs/$($approvalGoalRun.id)/stream" -TimeoutSec 20
  $lowStream = Invoke-WebRequest -Uri "$baseUrl/api/test-runs/$($lowConfidenceRun.id)/stream" -TimeoutSec 20
  $streamContent = "$($normalStream.Content)`n$($lowStream.Content)"
  $requiredRuntimeMessages = @(
    "正在理解测试用例",
    "正在生成测试步骤",
    "正在启动浏览器",
    "正在打开系统",
    "正在读取页面",
    "正在识别业务意图",
    "正在分析候选元素",
    "正在调用 LLM",
    "正在启用视觉兜底",
    "正在点击",
    "正在验证",
    "正在生成报告"
  )
  foreach ($runtimeText in $requiredRuntimeMessages) {
    if ($streamContent -notlike "*$runtimeText*") {
      Write-Error "Runtime stream did not include required message '$runtimeText'."
    }
  }

  if ($normalStream.Content -notlike "*event: progress*" -or $normalStream.Content -notlike "*event: success*") {
    Write-Error "Runtime stream did not expose typed SSE events."
  }

  $approvalRuntimeArtifact = $approvalGoalArtifacts |
    Where-Object { $_.artifact_type -eq "runtime_stream_jsonl" } |
    Select-Object -First 1
  if ($null -eq $approvalRuntimeArtifact -or -not (Test-Path $approvalRuntimeArtifact.file_path)) {
    Write-Error "runtime-stream.jsonl artifact was not persisted."
  }
  $approvalRuntimeFile = Get-Content $approvalRuntimeArtifact.file_path -Raw -Encoding UTF8
  if ($approvalRuntimeFile -notlike "*正在生成报告*") {
    Write-Error "runtime-stream.jsonl did not include runtime messages."
  }

  $replayedStream = Invoke-WebRequest -Uri "$baseUrl/api/test-runs/$($approvalGoalRun.id)/stream" -TimeoutSec 20
  if ($replayedStream.Content -notlike "*正在理解测试用例*") {
    Write-Error "Runtime stream did not replay history after completion."
  }

  Write-Host "Stage 8 frontend pages check passed."
} finally {
  if ($null -ne $process -and -not $process.HasExited) {
    Stop-Process -Id $process.Id -Force
  }
  if ($null -ne $mockProcess -and -not $mockProcess.HasExited) {
    Stop-Process -Id $mockProcess.Id -Force
  }
  $mockOwners = Get-NetTCPConnection -LocalPort $mockPort -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique
  foreach ($owner in $mockOwners) {
    if ($owner -gt 0) {
      Stop-Process -Id $owner -Force -ErrorAction SilentlyContinue
    }
  }
}
