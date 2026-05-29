# Enterprise MIS Intelligent Functional Testing Platform Production v1

This repository contains a first-phase production system for intelligent functional testing of existing enterprise MIS systems.

It includes:

- FastAPI backend with SQLAlchemy models, PostgreSQL support, and SQLite fallback.
- React + Vite + TypeScript frontend with a concise management-console layout.
- Python Playwright executor using local headless Chromium.
- Real tested-system management, connectivity checks, login checks, natural-language planning, runtime stream, evidence capture, reports, failure samples, human intervention, rule drafts, and ability knowledge.

## Requirements

- Windows PowerShell
- Python 3.11+
- Node.js 18+
- PostgreSQL for production use

Install dependencies:

```powershell
pip install -r backend\requirements.txt
pip install -r executor\requirements.txt
python -m playwright install chromium
npm --prefix frontend install
```

## Environment

Create a local environment file:

```powershell
Copy-Item .env.example .env
```

Default database:

```text
DATABASE_URL=postgresql+psycopg2://admin:123456@host.docker.internal:5432/postgres
```

If `DATABASE_URL` is absent, the backend falls back to:

```text
sqlite:///./data/aitp.db
```

Real system smoke variables:

```text
REAL_MIS_BASE_URL=
REAL_MIS_LOGIN_URL=
REAL_MIS_USERNAME=
REAL_MIS_PASSWORD=
```

LLM defaults:

```text
LLM_PROVIDER=openai_compatible
TEST_LLM_BASE_URL=https://ds.ai.sinopec.com/ds_v4_pro/v1/chat/completions
TEST_LLM_API_KEY=
TEST_LLM_MODEL=DeepSeek-V4
TEST_LLM_TIMEOUT_SECONDS=120
TEST_LLM_MAX_TOKENS=8192
TEST_LLM_TEMPERATURE=0.6
TEST_LLM_TOP_P=0.95
TEST_LLM_STREAM=true
TEST_LLM_VERIFY_SSL=false
```

Keep `TEST_LLM_API_KEY` only in local `.env` or the deployment secret store. Do not commit it.

Formal runtime controls:

```text
EXECUTOR_MODE=cube
LOCAL_BROWSER=true
RUNS_ROOT=artifacts/runs
ALLOWED_BASE_URL_PREFIXES=https://work.bypc.com.cn
PLAYWRIGHT_IGNORE_HTTPS_ERRORS=true
```

When `RUNS_ROOT` points outside this repository, run evidence is still available through `/files/runs-root/...`.

## Start

Start backend and frontend:

```powershell
.\scripts\start.ps1
```

Typical URLs:

```text
Backend:  http://127.0.0.1:8000
Frontend: http://127.0.0.1:5173
```

Stop local services:

```powershell
.\scripts\stop.ps1
```

Initialize database tables:

```powershell
.\scripts\init-db.ps1
```

## Validation

Run the normal project check:

```powershell
.\scripts\check.ps1
```

Run a real-system smoke check after filling `REAL_MIS_BASE_URL`:

```powershell
.\scripts\run-smoke.ps1
```

Run real-system end-to-end validation after filling all `REAL_MIS_*` variables:

```powershell
.\scripts\e2e-real-system.ps1
```

## Real System Onboarding

1. Open the frontend and enter “被测系统管理”.
2. Create a system with `base_url`, `login_url`, `home_url`, environment, authentication type, and operation guard flags.
3. Add a test account. Password fields are never shown after saving.
4. Run “连通性检查” to verify HTTP status, response time, and screenshot capture.
5. Run “登录检查” to verify login flow and main-page reachability.
6. Use “测试运行” to select the system, provide a natural-language test goal, optionally add JSON test data, analyze, and execute.

## Test Data JSON

The test run page accepts optional supplemental data:

```json
{
  "用户名": "test001",
  "手机号": "13800000000",
  "组织机构": "信息中心",
  "负责人": "张三",
  "开始日期": "2026-06-01",
  "结束日期": "2026-06-03"
}
```

When values are absent, non-sensitive defaults are generated from the ability rules. Critical fields such as organizations, roles, data permissions, approvers, and uploads request clarification instead of choosing arbitrary values.

## Runtime Artifacts

Each execution writes evidence under:

```text
{RUNS_ROOT}/{run_code}/
```

Expected evidence:

```text
summary.json
report.html
step-result.jsonl
locator-debug.jsonl
execution-trace.jsonl
runtime-stream.jsonl
screenshots/
dom/
accessibility/
```

System checks write evidence under:

```text
artifacts/system-checks/{system_code}/
```

## Main APIs

```text
GET  /health
GET  /api/system/info

GET  /api/systems
POST /api/systems
GET  /api/systems/{id}
PUT  /api/systems/{id}
POST /api/systems/{id}/check-connectivity
POST /api/systems/{id}/check-login

POST /api/test-runs/analyze
POST /api/test-runs/plan
POST /api/test-runs
GET  /api/test-runs
GET  /api/test-runs/{runId}
GET  /api/test-runs/{runId}/steps
GET  /api/test-runs/{runId}/artifacts
GET  /api/test-runs/{runId}/logs
GET  /api/test-runs/{runId}/latest-screenshot
GET  /api/test-runs/{runId}/stream
POST /api/test-runs/{runId}/stop

GET  /api/abilities/rules
POST /api/abilities/rules
PUT  /api/abilities/rules/{id}
POST /api/abilities/rules/{id}/enable
POST /api/abilities/rules/{id}/disable
GET  /api/abilities/knowledge
GET  /api/failure-samples
POST /api/failure-samples/{id}/analyze

POST /api/test-runs/{runId}/steps/{stepId}/intervene
POST /api/test-runs/{runId}/interventions/{interventionId}/execute
POST /api/test-runs/{runId}/interventions/{interventionId}/convert-to-rule

GET  /api/reports/{runId}
GET  /files/{path}
```

## Extension Points

- `executor/aitp_executor/browser/sandbox_provider.py` is the browser-provider boundary.
- A future Cube provider can implement the same provider interface and be selected by configuration.
- Vision fallback currently records overlay screenshots and returns `vision_fallback_not_configured` unless a real vision provider is configured.
- A real vision model can be wired through `VISION_MODEL_PROVIDER`, `VISION_MODEL_ENDPOINT`, and `VISION_MODEL_API_KEY`.

## Internal Deployment

1. Provision PostgreSQL and set `DATABASE_URL`.
2. Create `.env` from `.env.example` and fill LLM and real-system values.
3. Install dependencies or build with Docker Compose.
4. Run `.\scripts\check.ps1` on the target host.
5. Start services with `.\scripts\start.ps1` or a process manager.
6. Put the backend and frontend behind the internal reverse proxy.
7. Mount `data/`, `artifacts/`, and `reports/` on persistent storage.
