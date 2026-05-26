from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from executor.aitp_executor.utils.file_paths import public_root_name, resolve_project_path

router = APIRouter()


@router.get("/{file_path:path}")
def read_file(file_path: str):
    try:
        path = resolve_project_path(file_path)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    allowed_roots = {"artifacts", "reports", "runs-root"}
    if public_root_name(file_path) not in allowed_roots:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="File path is not public.")
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")
    return FileResponse(path)
