from fastapi import APIRouter

from app.api.accounts import router as accounts_router
from app.api.abilities import router as abilities_router
from app.api.cases import router as cases_router
from app.api.failure_analyses import router as failure_analyses_router
from app.api.failure_samples import router as failure_samples_router
from app.api.files import router as files_router
from app.api.human_interventions import router as human_interventions_router
from app.api.projects import router as projects_router
from app.api.prompts import router as prompts_router
from app.api.reports import router as reports_router
from app.api.rule_drafts import router as rule_drafts_router
from app.api.systems import router as systems_router
from app.api.system import router as system_router
from app.api.test_runs import router as test_runs_router

api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(systems_router, prefix="/api/systems", tags=["systems"])
api_router.include_router(projects_router, prefix="/api/projects", tags=["projects"])
api_router.include_router(accounts_router, prefix="/api/accounts", tags=["accounts"])
api_router.include_router(cases_router, prefix="/api/cases", tags=["cases"])
api_router.include_router(prompts_router, prefix="/api/prompts", tags=["prompts"])
api_router.include_router(abilities_router, prefix="/api/abilities", tags=["abilities"])
api_router.include_router(test_runs_router, prefix="/api/test-runs", tags=["test-runs"])
api_router.include_router(failure_samples_router, prefix="/api/failure-samples", tags=["failure-samples"])
api_router.include_router(failure_analyses_router, prefix="/api/failure-analyses", tags=["failure-analyses"])
api_router.include_router(human_interventions_router, prefix="/api/human-interventions", tags=["human-interventions"])
api_router.include_router(rule_drafts_router, prefix="/api/rule-drafts", tags=["rule-drafts"])
api_router.include_router(reports_router, prefix="/api/reports", tags=["reports"])
api_router.include_router(files_router, prefix="/files", tags=["files"])
