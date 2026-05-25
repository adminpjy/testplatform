# Enterprise MIS Intelligent Functional Testing Platform Production v1

This repository contains the project skeleton for an AI-assisted functional testing platform for existing enterprise MIS systems.

Stage 0 establishes a clean engineering foundation only:

- Backend skeleton: FastAPI, SQLAlchemy, Pydantic.
- Frontend skeleton: React, Vite, TypeScript.
- Executor skeleton: Python Playwright.
- Mock MIS demo placeholder for future local verification.
- Runtime data directories for artifacts and reports.
- PowerShell scripts for local lifecycle commands.

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

## Stage 0 Check

```powershell
.\scripts\check.ps1
```

The stage 0 check validates the expected project skeleton and required files.
