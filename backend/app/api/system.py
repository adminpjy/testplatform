from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.health import check_database
from app.db.session import get_db
from app.models import TestProject

router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    database = check_database(db)
    return {
        "status": "ok" if database["connected"] else "error",
        "service": settings.app_name,
        "database": database,
    }


@router.get("/api/system/info")
def system_info(db: Session = Depends(get_db)) -> dict:
    database = check_database(db)
    project_count = db.query(TestProject).count()
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_environment,
        "database": database,
        "project_count": project_count,
    }
