# Enterprise MIS Intelligent Functional Testing Platform Production v1

This repository contains a production-ready first phase for an intelligent functional testing platform focused on existing enterprise MIS systems.

It includes:

- FastAPI backend with persistent SQLAlchemy models and automatic table initialization.
- React + Vite + TypeScript frontend for test runs, ability center, failure samples, reports, demo entry, and settings.
- Python Playwright executor with local headless browser execution and evidence capture.
- Built-in MIS ability rules, RuleResolver, natural-language analysis, runtime stream, failure samples, human intervention, and rule drafts.
- Local Mock MIS Demo for validating login, todo approval, approval flow, user management, and detail navigation.

## Requirements

- Windows PowerShell
- Python 3.11+
- Node.js 18+
- PostgreSQL is recommended. If `DATABASE_URL` is not set, the backend uses SQLite at `data/aitp.db`.

Install Python and browser dependencies:

```powershell
pip install -r backend\requirements.txt
pip install -r executor\requirements.txt
python -m playwright install chromium
```

Install frontend dependencies:

```powershell
npm --prefix frontend install
npm --prefix mock-mis-demo install
```

## Environment

Create a local environment file:

```powershell
Copy-Item .env.example .env
```

Default PostgreSQL connection:

```text
DATABASE_URL=postgresql+psycopg2://admin:123456@host.docker.internal:5432/postgres
```

Fallback when `DATABASE_URL` is absent:

```text
sqlite:///./data/aitp.db
```

LLM defaults:

```text
LLM_PROVIDER=mock
TEST_LLM_BASE_URL=
TEST_LLM_API_KEY=
TEST_LLM_MODEL=DeepSeek-V4
TEST_LLM_STREAM=true
```

The mock provider works without external credentials. External provider secrets are read from environment variables.

## Start Locally

Start backend, frontend, and the local MIS demo:

```powershell
.\scripts\start.ps1
```

Typical URLs:

```text
Backend:       http://127.0.0.1:8000
Frontend:      http://127.0.0.1:5173
Mock MIS Demo: http://127.0.0.1:5174/login
```

If a default frontend or demo port is occupied, the script chooses the next available port and prints it.

Stop managed local services:

```powershell
.\scripts\stop.ps1
```

Initialize database tables without starting the HTTP service:

```powershell
.\scripts\init-db.ps1
```

## Validation

Run the normal project check:

```powershell
.\scripts\check.ps1
```

Run the full local end-to-end validation:

```powershell
.\scripts\e2e-demo.ps1
```

The end-to-end script starts temporary backend, frontend, and demo services, then verifies:

- `/health` and database connectivity.
- Base ability rule initialization.
- Natural-language analysis and DSL planning.
- Login and navigation to todo.
- Approval pass with conflicting todo actions.
- User management create, update, and delete.
- Runtime stream persistence and SSE replay.
- Latest screenshot and HTML report endpoints.
- Failure sample evidence files.
- Ability center APIs for rules, failure samples, interventions, and rule drafts.

## Mock MIS Demo

Login:

```text
admin / 123456
```

Routes:

```text
/login
/login?notice=account-expiry
/login?notice=system-announcement
/login?notice=force-change-password
/dashboard
/todo
/users
```

The todo page intentionally contains both `审批` and `查看审批流程` actions to validate business-intent disambiguation.

## Runtime Artifacts

Each execution writes evidence under:

```text
artifacts/runs/{run_code}/
```

Expected files include:

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

## Main APIs

```text
GET  /health
GET  /api/system/info
GET  /api/projects
POST /api/projects
GET  /api/projects/{id}

GET  /api/abilities/rules
POST /api/abilities/rules
PUT  /api/abilities/rules/{id}
POST /api/abilities/rules/{id}/enable
POST /api/abilities/rules/{id}/disable
POST /api/abilities/resolve

POST /api/test-runs/analyze
POST /api/test-runs/plan
POST /api/test-runs
GET  /api/test-runs
GET  /api/test-runs/{runId}
GET  /api/test-runs/{runId}/steps
GET  /api/test-runs/{runId}/artifacts
GET  /api/test-runs/{runId}/latest-screenshot
GET  /api/test-runs/{runId}/stream
GET  /api/test-runs/{runId}/runtime-messages

POST /api/test-runs/{runId}/steps/{stepId}/intervene
POST /api/test-runs/{runId}/interventions/{interventionId}/execute
POST /api/test-runs/{runId}/interventions/{interventionId}/convert-to-rule

GET  /api/failure-samples
GET  /api/human-interventions
GET  /api/rule-drafts
POST /api/rule-drafts/{draftId}/enable

GET  /api/reports/{runId}
GET  /files/{path}
```

## Notes

- Test data persists in the configured database.
- Execution artifacts persist on disk.
- Long error details are folded in the frontend to keep pages usable.
- The first phase runs locally with Playwright headless and keeps the browser-provider boundary for later remote execution.
