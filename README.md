# Enterprise MIS Intelligent Functional Testing Platform Production v1

This repository contains the project skeleton for an AI-assisted functional testing platform for existing enterprise MIS systems.

The current foundation includes:

- Backend skeleton: FastAPI, SQLAlchemy, Pydantic.
- Frontend skeleton: React, Vite, TypeScript.
- Executor skeleton: Python Playwright.
- Mock MIS demo placeholder for future local verification.
- Runtime data directories for artifacts and reports.
- PowerShell scripts for local lifecycle commands.
- Backend stage 1 service startup, database connection, automatic table creation, default project initialization, and project APIs.
- MIS base ability pack initialization and RuleResolver for common enterprise MIS testing goals.

No complex business implementation is included in this stage.

## Repository Layout

```text
backend/          FastAPI service skeleton
frontend/         React + Vite frontend skeleton
executor/         Playwright executor package skeleton
mock-mis-demo/    Local MIS-like demo app placeholder
config/           Ability and runtime configuration
scripts/          Local lifecycle scripts
data/             Local persistent runtime data
artifacts/        Execution artifacts
reports/          Generated test reports
```

## Environment

Copy `.env.example` to `.env` before running later phases.

```powershell
Copy-Item .env.example .env
```

## Backend

The backend reads `DATABASE_URL` from the environment or `.env`.

When `DATABASE_URL` is absent, it falls back to:

```text
sqlite:///./data/aitp.db
```

Start the backend:

```powershell
.\scripts\start.ps1
```

Stop the backend:

```powershell
.\scripts\stop.ps1
```

Initialize tables without starting the HTTP service:

```powershell
.\scripts\init-db.ps1
```

Implemented endpoints:

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
```

## Check

```powershell
.\scripts\check.ps1
```

The check validates the expected skeleton, compiles the backend, starts a temporary API process, verifies `/health`, checks database connectivity, and confirms that at least one project exists.
