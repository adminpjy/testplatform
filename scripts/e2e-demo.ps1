Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Resolve-Path (Join-Path $scriptDir "..")
Set-Location $projectRoot

$runtimeDir = ".runtime"
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

$hostName = "127.0.0.1"
$backendProcess = $null
$frontendProcess = $null
$mockProcess = $null
$backendPort = 0
$frontendPort = 0
$mockPort = 0

$previousLlmProvider = $env:LLM_PROVIDER
$previousLlmStream = $env:TEST_LLM_STREAM
$previousApiBase = $env:VITE_API_BASE_URL
$previousMockUrl = $env:VITE_MOCK_MIS_URL

function Assert-True {
  param(
    [bool]$Condition,
    [string]$Message
  )

  if (-not $Condition) {
    Write-Error $Message
  }
}

function Write-Step {
  param([string]$Message)
  Write-Host "[e2e] $Message"
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

function Wait-HttpOk {
  param(
    [Parameter(Mandatory = $true)][string]$Uri,
    [Parameter(Mandatory = $true)][string]$Name,
    [System.Diagnostics.Process]$Process,
    [string]$ErrorLog,
    [int]$Attempts = 60
  )

  for ($i = 0; $i -lt $Attempts; $i++) {
    if ($null -ne $Process -and $Process.HasExited) {
      $stderr = ""
      if (-not [string]::IsNullOrWhiteSpace($ErrorLog) -and (Test-Path $ErrorLog)) {
        $stderr = Get-Content $ErrorLog -Raw -Encoding UTF8
      }
      Write-Error "$Name exited before it became ready. $stderr"
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

function Resolve-ArtifactPath {
  param([string]$Path)

  if ([string]::IsNullOrWhiteSpace($Path)) {
    return $null
  }
  if ([System.IO.Path]::IsPathRooted($Path)) {
    return $Path
  }
  return Join-Path $projectRoot $Path
}

function Assert-ArtifactExists {
  param(
    [string]$Path,
    [string]$Message
  )

  $resolved = Resolve-ArtifactPath -Path $Path
  Assert-True (-not [string]::IsNullOrWhiteSpace($resolved) -and (Test-Path $resolved)) $Message
}

function Stop-PortOwners {
  param([int]$Port)

  if ($Port -le 0) {
    return
  }

  try {
    $owners = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
      Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($owner in $owners) {
      if ($owner -gt 0) {
        Stop-Process -Id $owner -Force -ErrorAction SilentlyContinue
      }
    }
  } catch {
  }
}

function New-TestRun {
  param(
    [int]$ProjectId,
    [string]$Instruction,
    [string]$CaseName,
    [string]$BaseUrl,
    [object[]]$Steps,
    [int]$TimeoutSec = 90
  )

  $payload = @{
    project_id = $ProjectId
    instruction = $Instruction
    base_url = $BaseUrl
    dsl_json = @{
      caseName = $CaseName
      baseUrl = $BaseUrl
      credentials = @{}
      settings = @{
        headless = $true
      }
      steps = $Steps
    }
  } | ConvertTo-Json -Depth 16

  Invoke-JsonPost -Uri "$script:BackendBaseUrl/api/test-runs" -Body $payload -TimeoutSec $TimeoutSec
}

function Assert-RunStatus {
  param(
    [object]$Run,
    [string]$ExpectedStatus,
    [string]$Context
  )

  if ($Run.status -ne $ExpectedStatus) {
    $summary = $Run.summary_json | ConvertTo-Json -Depth 12
    Write-Error "$Context expected status '$ExpectedStatus' but got '$($Run.status)'. $summary"
  }
}

try {
  Write-Step "Installing Node dependencies when needed"
  if (-not (Test-Path "frontend/node_modules")) {
    npm.cmd --prefix frontend install
  }
  if (-not (Test-Path "mock-mis-demo/node_modules")) {
    npm.cmd --prefix mock-mis-demo install
  }

  $backendPort = New-FreePort
  $frontendPort = New-FreePort
  $mockPort = New-FreePort
  $script:BackendBaseUrl = "http://$hostName`:$backendPort"
  $frontendBaseUrl = "http://$hostName`:$frontendPort"
  $mockBaseUrl = "http://$hostName`:$mockPort"

  $env:LLM_PROVIDER = "mock"
  $env:TEST_LLM_STREAM = "true"
  $env:VITE_API_BASE_URL = $script:BackendBaseUrl
  $env:VITE_MOCK_MIS_URL = "$mockBaseUrl/login"

  $backendOut = Join-Path $runtimeDir "e2e-backend.out.log"
  $backendErr = Join-Path $runtimeDir "e2e-backend.err.log"
  $frontendOut = Join-Path $runtimeDir "e2e-frontend.out.log"
  $frontendErr = Join-Path $runtimeDir "e2e-frontend.err.log"
  $mockOut = Join-Path $runtimeDir "e2e-mock.out.log"
  $mockErr = Join-Path $runtimeDir "e2e-mock.err.log"
  Remove-Item $backendOut, $backendErr, $frontendOut, $frontendErr, $mockOut, $mockErr -Force -ErrorAction SilentlyContinue

  Write-Step "Starting backend at $script:BackendBaseUrl"
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

  Write-Step "Starting mock MIS demo at $mockBaseUrl"
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
    -RedirectStandardOutput $mockOut `
    -RedirectStandardError $mockErr

  Write-Step "Starting frontend at $frontendBaseUrl"
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

  Write-Step "Checking service readiness"
  $healthResponse = Wait-HttpOk -Uri "$script:BackendBaseUrl/health" -Name "backend" -Process $backendProcess -ErrorLog $backendErr
  $frontendResponse = Wait-HttpOk -Uri $frontendBaseUrl -Name "frontend" -Process $frontendProcess -ErrorLog $frontendErr
  $mockResponse = Wait-HttpOk -Uri "$mockBaseUrl/login" -Name "mock MIS demo" -Process $mockProcess -ErrorLog $mockErr
  Assert-True ($healthResponse.Content -like "*ok*") "Backend health response did not include ok."
  Assert-True ($frontendResponse.StatusCode -eq 200) "Frontend did not return HTTP 200."
  Assert-True ($mockResponse.StatusCode -eq 200) "Mock MIS demo login page did not return HTTP 200."

  $health = Invoke-RestMethod -Uri "$script:BackendBaseUrl/health" -TimeoutSec 5
  Assert-True ($health.status -eq "ok") "Health status was not ok."
  Assert-True ($health.database.connected -eq $true) "Database connection was not healthy."

  $projects = Invoke-RestMethod -Uri "$script:BackendBaseUrl/api/projects" -TimeoutSec 5
  Assert-True (@($projects).Count -gt 0) "Default project was not initialized."
  $projectId = @($projects)[0].id

  Write-Step "Checking base ability rules"
  $rules = Invoke-RestMethod -Uri "$script:BackendBaseUrl/api/abilities/rules?production_enabled=true" -TimeoutSec 10
  Assert-True (@($rules).Count -ge 32) "Ability rule library was not initialized."
  foreach ($ruleCode in @("APPROVAL-PASS-v1", "APPROVAL-FLOW-VIEW-v1", "ENTER-TODO-LIST-v1")) {
    $found = $rules | Where-Object { $_.rule_code -eq $ruleCode } | Select-Object -First 1
    Assert-True ($null -ne $found) "Required ability rule '$ruleCode' was not found."
  }

  Write-Step "Calling natural-language analysis"
  $analyzePayload = @{
    project_id = $projectId
    instruction = "打开 $mockBaseUrl/login，使用账号 admin 密码 123456 登录系统，进入我的待办，确认页面存在我的待办"
    base_url = "$mockBaseUrl/login"
    credentials = @{
      username = "admin"
      password = "123456"
    }
    stream = $true
  } | ConvertTo-Json -Depth 10
  $analysis = Invoke-JsonPost -Uri "$script:BackendBaseUrl/api/test-runs/analyze" -Body $analyzePayload -TimeoutSec 10
  Assert-True ($analysis.readyToExecute -eq $true) "Analyze did not mark a complete instruction as ready."

  Write-Step "Planning executable DSL"
  $plan = Invoke-JsonPost -Uri "$script:BackendBaseUrl/api/test-runs/plan" -Body $analyzePayload -TimeoutSec 10
  Assert-True (-not [string]::IsNullOrWhiteSpace($plan.caseName)) "Planned DSL did not include caseName."
  Assert-True (@($plan.steps).Count -ge 3) "Planned DSL did not include enough steps."

  Write-Step "Executing login and todo navigation"
  $loginTodoRun = New-TestRun `
    -ProjectId $projectId `
    -Instruction "登录并进入我的待办" `
    -CaseName "E2E 登录并进入我的待办" `
    -BaseUrl "$mockBaseUrl/login" `
    -Steps @(
      @{ action = "open_url"; target = "$mockBaseUrl/login" },
      @{ action = "input"; target = "用户名"; value = "admin" },
      @{ action = "input"; target = "密码"; value = "123456" },
      @{ action = "click"; target = "登录" },
      @{ action = "business_goal"; target = "工作台/我的待办" },
      @{ action = "assert_url_contains"; target = "/todo" }
    )
  Assert-RunStatus -Run $loginTodoRun -ExpectedStatus "passed" -Context "Login todo run"

  Write-Step "Executing approval pass"
  $approvalRun = New-TestRun `
    -ProjectId $projectId `
    -Instruction "进入我的待办并审批通过" `
    -CaseName "E2E 审批通过" `
    -BaseUrl "$mockBaseUrl/login" `
    -Steps @(
      @{ action = "open_url"; target = "$mockBaseUrl/login" },
      @{ action = "input"; target = "用户名"; value = "admin" },
      @{ action = "input"; target = "密码"; value = "123456" },
      @{ action = "click"; target = "登录" },
      @{ action = "business_goal"; target = "工作台/我的待办" },
      @{ action = "business_goal"; target = "审批通过" },
      @{ action = "wait_for_text"; target = "审批成功" }
    )
  Assert-RunStatus -Run $approvalRun -ExpectedStatus "passed" -Context "Approval pass run"

  $approvalArtifacts = Invoke-RestMethod -Uri "$script:BackendBaseUrl/api/test-runs/$($approvalRun.id)/artifacts" -TimeoutSec 10
  $approvalLocator = $approvalArtifacts | Where-Object { $_.artifact_type -eq "locator_debug_jsonl" } | Select-Object -First 1
  Assert-ArtifactExists -Path $approvalLocator.file_path -Message "Approval locator debug artifact was missing."
  $approvalLocatorPath = Resolve-ArtifactPath -Path $approvalLocator.file_path
  $approvalDecision = Get-Content $approvalLocatorPath -Encoding UTF8 |
    ForEach-Object { $_ | ConvertFrom-Json } |
    Where-Object { $_.target -eq "审批通过" } |
    Select-Object -First 1
  Assert-True ($approvalDecision.element_ref -eq "审批") "Approval pass did not choose the exact approval button."

  Write-Step "Executing user management create, update, and delete"
  $demoUser = "e2e_user_$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())"
  $userRun = New-TestRun `
    -ProjectId $projectId `
    -Instruction "进入用户管理并新增、修改、删除用户" `
    -CaseName "E2E 用户管理增改删" `
    -BaseUrl "$mockBaseUrl/login" `
    -Steps @(
      @{ action = "open_url"; target = "$mockBaseUrl/login" },
      @{ action = "input"; target = "用户名"; value = "admin" },
      @{ action = "input"; target = "密码"; value = "123456" },
      @{ action = "click"; target = "登录" },
      @{ action = "navigate_menu"; target = "用户管理" },
      @{ action = "input"; target = "用户名"; value = $demoUser },
      @{ action = "input"; target = "姓名"; value = "端到端用户" },
      @{ action = "select"; target = "角色"; value = "审批员" },
      @{ action = "click"; target = "新增" },
      @{ action = "wait_for_text"; target = $demoUser },
      @{ action = "click_table_row_action"; target = "修改"; rowText = $demoUser; button = "修改" },
      @{ action = "input"; target = "姓名"; value = "端到端用户已修改" },
      @{ action = "click"; target = "保存修改" },
      @{ action = "wait_for_text"; target = "端到端用户已修改" },
      @{ action = "click_table_row_action"; target = "删除"; rowText = $demoUser; button = "删除" },
      @{ action = "assert_text_not_exists"; target = $demoUser }
    )
  Assert-RunStatus -Run $userRun -ExpectedStatus "passed" -Context "User management run"

  Write-Step "Checking runtime stream, screenshot, and report"
  $runtimeMessages = Invoke-RestMethod -Uri "$script:BackendBaseUrl/api/test-runs/$($approvalRun.id)/runtime-messages" -TimeoutSec 10
  Assert-True (@($runtimeMessages).Count -gt 0) "Runtime messages were not persisted."
  $stream = Invoke-WebRequest -Uri "$script:BackendBaseUrl/api/test-runs/$($approvalRun.id)/stream" -TimeoutSec 20 -UseBasicParsing
  foreach ($runtimeText in @("正在理解测试用例", "正在生成测试步骤", "正在启动浏览器", "正在打开系统", "正在读取页面", "正在识别业务意图", "正在分析候选元素", "正在点击", "正在验证", "正在生成报告")) {
    Assert-True ($stream.Content -like "*$runtimeText*") "Runtime stream did not include '$runtimeText'."
  }
  Assert-True ($stream.Content -like "*event: success*") "Runtime stream did not include success events."

  $screenshot = Invoke-WebRequest -Uri "$script:BackendBaseUrl/api/test-runs/$($approvalRun.id)/latest-screenshot" -TimeoutSec 10 -UseBasicParsing
  Assert-True ($screenshot.StatusCode -eq 200) "Latest screenshot endpoint did not return HTTP 200."
  $report = Invoke-WebRequest -Uri "$script:BackendBaseUrl/api/reports/$($approvalRun.id)" -TimeoutSec 10 -UseBasicParsing
  Assert-True ($report.StatusCode -eq 200 -and $report.Content -like "*测试执行报告*") "Report endpoint did not return report.html."

  Write-Step "Creating and checking a failure sample"
  $failedRun = New-TestRun `
    -ProjectId $projectId `
    -Instruction "触发失败样本采集" `
    -CaseName "E2E 失败样本采集" `
    -BaseUrl "$mockBaseUrl/login" `
    -Steps @(
      @{ action = "open_url"; target = "$mockBaseUrl/login" },
      @{ action = "click"; target = "完全不存在的按钮" }
    )
  Assert-RunStatus -Run $failedRun -ExpectedStatus "failed" -Context "Failure sample run"

  $failureSamples = Invoke-RestMethod -Uri "$script:BackendBaseUrl/api/failure-samples?run_id=$($failedRun.id)" -TimeoutSec 10
  Assert-True (@($failureSamples).Count -gt 0) "Failed run did not create a failure sample."
  $failureSample = @($failureSamples)[0]
  foreach ($fieldName in @("screenshot_path", "dom_snapshot_path", "accessibility_snapshot_path", "locator_debug_path", "runtime_stream_path", "execution_trace_path", "report_path")) {
    $path = $failureSample.PSObject.Properties[$fieldName].Value
    Assert-ArtifactExists -Path $path -Message "Failure sample evidence '$fieldName' was missing."
  }

  $failedSteps = Invoke-RestMethod -Uri "$script:BackendBaseUrl/api/test-runs/$($failedRun.id)/steps" -TimeoutSec 10
  $failedStep = $failedSteps | Where-Object { $_.status -eq "failed" } | Select-Object -First 1
  Assert-True ($null -ne $failedStep) "Failed step was not persisted."

  $interventionPayload = @{
    user_instruction = "这里先点击继续访问，然后重试原步骤。"
  } | ConvertTo-Json -Depth 6
  $intervention = Invoke-JsonPost `
    -Uri "$script:BackendBaseUrl/api/test-runs/$($failedRun.id)/steps/$($failedStep.id)/intervene" `
    -Body $interventionPayload `
    -TimeoutSec 10
  Assert-True ($intervention.status -eq "planned") "Human intervention was not planned."

  $executedIntervention = Invoke-JsonPost `
    -Uri "$script:BackendBaseUrl/api/test-runs/$($failedRun.id)/interventions/$($intervention.id)/execute" `
    -Body "{}" `
    -TimeoutSec 10
  Assert-True ($executedIntervention.status -eq "succeeded") "Human intervention execution did not succeed."

  $ruleDraft = Invoke-JsonPost `
    -Uri "$script:BackendBaseUrl/api/test-runs/$($failedRun.id)/interventions/$($intervention.id)/convert-to-rule" `
    -Body "{}" `
    -TimeoutSec 10
  Assert-True ($ruleDraft.status -eq "pending_review") "Rule draft was not created in pending_review status."

  Write-Step "Checking ability center APIs"
  $abilityRules = Invoke-RestMethod -Uri "$script:BackendBaseUrl/api/abilities/rules" -TimeoutSec 10
  $allFailureSamples = Invoke-RestMethod -Uri "$script:BackendBaseUrl/api/failure-samples" -TimeoutSec 10
  $interventions = Invoke-RestMethod -Uri "$script:BackendBaseUrl/api/human-interventions?run_id=$($failedRun.id)" -TimeoutSec 10
  $ruleDrafts = Invoke-RestMethod -Uri "$script:BackendBaseUrl/api/rule-drafts" -TimeoutSec 10
  Assert-True (@($abilityRules).Count -gt 0) "Ability rules API returned no data."
  Assert-True (@($allFailureSamples).Count -gt 0) "Failure samples API returned no data."
  Assert-True (@($interventions).Count -gt 0) "Human interventions API returned no data."
  Assert-True (@($ruleDrafts | Where-Object { $_.id -eq $ruleDraft.id }).Count -gt 0) "Rule drafts API did not include the generated draft."

  Write-Host "Production v1 end-to-end demo passed."
} finally {
  if ($null -ne $backendProcess -and -not $backendProcess.HasExited) {
    Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
  }
  if ($null -ne $frontendProcess -and -not $frontendProcess.HasExited) {
    Stop-Process -Id $frontendProcess.Id -Force -ErrorAction SilentlyContinue
  }
  if ($null -ne $mockProcess -and -not $mockProcess.HasExited) {
    Stop-Process -Id $mockProcess.Id -Force -ErrorAction SilentlyContinue
  }
  Stop-PortOwners -Port $backendPort
  Stop-PortOwners -Port $frontendPort
  Stop-PortOwners -Port $mockPort

  $env:LLM_PROVIDER = $previousLlmProvider
  $env:TEST_LLM_STREAM = $previousLlmStream
  $env:VITE_API_BASE_URL = $previousApiBase
  $env:VITE_MOCK_MIS_URL = $previousMockUrl
}
