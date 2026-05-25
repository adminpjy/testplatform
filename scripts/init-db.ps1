Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$env:PYTHONPATH = Join-Path (Get-Location) "backend"
python -c "from app.db.init_db import init_db; init_db(); print('Database initialized.')"
