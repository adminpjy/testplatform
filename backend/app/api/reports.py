from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.test_run_execution import get_run, report_artifact
from executor.aitp_executor.utils.file_paths import resolve_project_path

router = APIRouter()


@router.get("/{run_id}")
def read_report(run_id: int, db: Session = Depends(get_db)):
    if get_run(db, run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test run not found.")
    artifact = report_artifact(db, run_id)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    path = resolve_project_path(artifact.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report file not found.")
    return FileResponse(path, media_type="text/html")
