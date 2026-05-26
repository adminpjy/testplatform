Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

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

function Invoke-JsonPost {
  param([string]$Uri, [string]$Body, [int]$TimeoutSec = 30)
  $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($Body)
  Invoke-RestMethod -Uri $Uri -Method Post -ContentType "application/json; charset=utf-8" -Body $bodyBytes -TimeoutSec $TimeoutSec
}

function Assert-Value {
  param([bool]$Condition, [string]$Message)
  if (-not $Condition) {
    Write-Error $Message
  }
}

Import-DotEnv

foreach ($name in @("REAL_MIS_BASE_URL", "REAL_MIS_LOGIN_URL", "REAL_MIS_USERNAME", "REAL_MIS_PASSWORD")) {
  if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name))) {
    Write-Error "$name is required for real-system end-to-end validation."
  }
}

$backendHost = if ($env:BACKEND_HOST) { $env:BACKEND_HOST } else { "127.0.0.1" }
$backendPort = if ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { "8000" }
$apiBase = "http://$backendHost`:$backendPort"

$health = Invoke-RestMethod -Uri "$apiBase/health" -TimeoutSec 5
Assert-Value ($health.status -eq "ok") "Backend health check failed."

$projects = Invoke-RestMethod -Uri "$apiBase/api/projects" -TimeoutSec 5
Assert-Value (@($projects).Count -gt 0) "No project exists."
$projectId = @($projects)[0].id

$code = "REAL-E2E-$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())"
$systemPayload = @{
  system_code = $code
  system_name = "Real System E2E Target"
  base_url = $env:REAL_MIS_BASE_URL
  login_url = $env:REAL_MIS_LOGIN_URL
  home_url = $env:REAL_MIS_BASE_URL
  environment = "test"
  auth_type = "username_password"
  default_timeout_ms = 15000
  allow_write = $false
  allow_approval = $false
  allow_delete = $false
  status = "active"
  default_account = @{
    environment = "test"
    username = $env:REAL_MIS_USERNAME
    password = $env:REAL_MIS_PASSWORD
    role_name = "e2e"
    allow_write = $false
    allow_approval = $false
    allow_delete = $false
    status = "active"
  }
} | ConvertTo-Json -Depth 8

$system = Invoke-JsonPost -Uri "$apiBase/api/systems" -Body $systemPayload -TimeoutSec 10
Write-Host "System created: $($system.id)"

$connectivity = Invoke-JsonPost -Uri "$apiBase/api/systems/$($system.id)/check-connectivity" -Body "{}" -TimeoutSec 60
Assert-Value ($connectivity.status -eq "passed") "Connectivity check failed: $($connectivity.message)"
Write-Host "Connectivity passed: HTTP $($connectivity.http_status)"

$login = Invoke-JsonPost -Uri "$apiBase/api/systems/$($system.id)/check-login" -Body "{}" -TimeoutSec 90
Assert-Value ($login.status -eq "passed") "Login check failed: $($login.message)"
Write-Host "Login check passed."

$analysisPayload = @{
  project_id = $projectId
  system_id = $system.id
  instruction = "登录真实系统，确认主页面可以访问"
  base_url = $env:REAL_MIS_LOGIN_URL
  credentials = @{
    username = $env:REAL_MIS_USERNAME
    password = $env:REAL_MIS_PASSWORD
  }
  stream = $true
} | ConvertTo-Json -Depth 8

$analysis = Invoke-JsonPost -Uri "$apiBase/api/test-runs/analyze" -Body $analysisPayload -TimeoutSec 15
Assert-Value ($analysis.readyToExecute -eq $true) "Natural-language analysis requested more information."

$plan = Invoke-JsonPost -Uri "$apiBase/api/test-runs/plan" -Body $analysisPayload -TimeoutSec 15
Assert-Value (@($plan.steps).Count -gt 0) "Plan did not return executable steps."

Write-Host "Real-system end-to-end validation passed."
