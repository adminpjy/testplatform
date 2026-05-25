from fastapi import APIRouter

from app.api.abilities import router as abilities_router
from app.api.files import router as files_router
from app.api.projects import router as projects_router
from app.api.reports import router as reports_router
from app.api.system import router as system_router
from app.api.test_runs import router as test_runs_router

api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(projects_router, prefix="/api/projects", tags=["projects"])
api_router.include_router(abilities_router, prefix="/api/abilities", tags=["abilities"])
api_router.include_router(test_runs_router, prefix="/api/test-runs", tags=["test-runs"])
api_router.include_router(reports_router, prefix="/api/reports", tags=["reports"])
api_router.include_router(files_router, prefix="/files", tags=["files"])
