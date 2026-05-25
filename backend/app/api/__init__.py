from fastapi import APIRouter

from app.api.projects import router as projects_router
from app.api.system import router as system_router

api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(projects_router, prefix="/api/projects", tags=["projects"])
