Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Test-Path "mock-mis-demo/node_modules")) {
  npm.cmd --prefix mock-mis-demo install
}

npm.cmd --prefix mock-mis-demo run dev -- --host 127.0.0.1 --port 5174 --strictPort
