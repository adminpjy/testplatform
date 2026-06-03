from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models import PlatformUser
from app.services.permissions import require_project_permission
from app.services.test_run_execution import get_run, report_artifact
from executor.aitp_executor.utils.file_paths import resolve_project_path

router = APIRouter()


@router.get("/{run_id}")
def read_report(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
):
    run = get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test run not found.")
    require_project_permission(db, current_user, run.project_id, "view_reports")
    artifact = report_artifact(db, run_id)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    path = resolve_project_path(artifact.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report file not found.")
    return FileResponse(path, media_type="text/html")
