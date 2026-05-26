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

Import-DotEnv

$backendHost = if ($env:BACKEND_HOST) { $env:BACKEND_HOST } else { "127.0.0.1" }
$backendPort = if ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { "8000" }
$apiBase = "http://$backendHost`:$backendPort"

if ([string]::IsNullOrWhiteSpace($env:REAL_MIS_BASE_URL)) {
  Write-Error "REAL_MIS_BASE_URL is required."
}

$health = Invoke-RestMethod -Uri "$apiBase/health" -TimeoutSec 5
if ($health.status -ne "ok") {
  Write-Error "Backend health check failed."
}

$code = "REAL-SMOKE-$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())"
$payload = @{
  system_code = $code
  system_name = "Real System Smoke Target"
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
  default_account = if ($env:REAL_MIS_USERNAME) {
    @{
      environment = "test"
      username = $env:REAL_MIS_USERNAME
      password = $env:REAL_MIS_PASSWORD
      role_name = "smoke"
      allow_write = $false
      allow_approval = $false
      allow_delete = $false
      status = "active"
    }
  } else {
    $null
  }
} | ConvertTo-Json -Depth 8

$system = Invoke-JsonPost -Uri "$apiBase/api/systems" -Body $payload -TimeoutSec 10
$connectivity = Invoke-JsonPost -Uri "$apiBase/api/systems/$($system.id)/check-connectivity" -Body "{}" -TimeoutSec 60
Write-Host "Connectivity: $($connectivity.status), HTTP $($connectivity.http_status), $($connectivity.response_time_ms) ms"

if ($env:REAL_MIS_LOGIN_URL -and $env:REAL_MIS_USERNAME -and $env:REAL_MIS_PASSWORD) {
  $login = Invoke-JsonPost -Uri "$apiBase/api/systems/$($system.id)/check-login" -Body "{}" -TimeoutSec 90
  Write-Host "Login: $($login.status), $($login.message)"
}
