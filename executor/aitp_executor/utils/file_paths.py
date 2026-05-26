import re
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUNS_PUBLIC_PREFIX = "runs-root"


def runs_root() -> Path:
    configured = os.getenv("RUNS_ROOT", "").strip()
    if not configured:
        return PROJECT_ROOT / "artifacts" / "runs"
    path = Path(configured)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    return cleaned.strip("-") or "run"


def run_dir(run_code: str) -> Path:
    path = runs_root() / safe_name(run_code)
    path.mkdir(parents=True, exist_ok=True)
    return path


def relative_to_project(path: Path) -> str:
    resolved = path.resolve()
    project_root = PROJECT_ROOT.resolve()
    try:
        return resolved.relative_to(project_root).as_posix()
    except ValueError:
        root = runs_root()
        try:
            return f"{RUNS_PUBLIC_PREFIX}/{resolved.relative_to(root).as_posix()}"
        except ValueError as exc:
            raise ValueError("Path is outside the project and configured run roots.") from exc


def resolve_project_path(relative_path: str) -> Path:
    normalized = relative_path.replace("\\", "/").lstrip("/")
    if normalized == RUNS_PUBLIC_PREFIX:
        return runs_root()
    if normalized.startswith(f"{RUNS_PUBLIC_PREFIX}/"):
        path = (runs_root() / normalized.removeprefix(f"{RUNS_PUBLIC_PREFIX}/")).resolve()
        root = runs_root()
        if path != root and root not in path.parents:
            raise ValueError("Path is outside configured run root.")
        return path
    path = (PROJECT_ROOT / normalized).resolve()
    project_root = PROJECT_ROOT.resolve()
    if path != project_root and project_root not in path.parents:
        raise ValueError("Path is outside project root.")
    return path


def public_root_name(relative_path: str) -> str:
    normalized = relative_path.replace("\\", "/").lstrip("/")
    if normalized == RUNS_PUBLIC_PREFIX or normalized.startswith(f"{RUNS_PUBLIC_PREFIX}/"):
        return RUNS_PUBLIC_PREFIX
    return normalized.split("/", 1)[0]
