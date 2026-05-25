import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS_ROOT = PROJECT_ROOT / "artifacts" / "runs"


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    return cleaned.strip("-") or "run"


def run_dir(run_code: str) -> Path:
    path = ARTIFACTS_ROOT / safe_name(run_code)
    path.mkdir(parents=True, exist_ok=True)
    return path


def relative_to_project(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def resolve_project_path(relative_path: str) -> Path:
    normalized = relative_path.replace("\\", "/").lstrip("/")
    path = (PROJECT_ROOT / normalized).resolve()
    project_root = PROJECT_ROOT.resolve()
    if path != project_root and project_root not in path.parents:
        raise ValueError("Path is outside project root.")
    return path
