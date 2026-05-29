import os
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import TestArtifact, TestRun
from executor.aitp_executor.utils.file_paths import PROJECT_ROOT, relative_to_project, resolve_project_path, run_dir


TRACE_ARTIFACT_TYPES = {"playwright_trace", "trace", "trace_zip"}


@dataclass
class TraceViewerSession:
    run_id: int
    trace_path: str
    port: int
    viewer_url: str
    process: subprocess.Popen
    status: str
    started_at: datetime
    last_accessed_at: datetime
    error: str | None = None

    @property
    def pid(self) -> int | None:
        return self.process.pid if self.process else None


_sessions: dict[int, TraceViewerSession] = {}


def start_trace_viewer(db: Session, run_id: int) -> dict:
    cleanup_trace_viewers()
    run = db.get(TestRun, run_id)
    if run is None:
        raise ValueError("Test run not found.")
    if not settings.trace_viewer_enabled:
        return _failed_response("trace_viewer_disabled", "Trace Viewer 功能未启用。")

    trace_path = find_trace_path(db, run)
    if trace_path is None:
        return _failed_response("trace_file_not_found", "当前运行未生成 trace.zip。")

    existing = _sessions.get(run_id)
    if existing and _is_process_running(existing.process):
        existing.last_accessed_at = _utc_now()
        return _session_response(existing)

    npx = shutil.which("npx.cmd") or shutil.which("npx")
    if not npx:
        return _dependency_missing_response()
    if not _playwright_cli_available(npx):
        return _dependency_missing_response()

    port = _allocate_port()
    if port is None:
        return _failed_response("trace_viewer_port_unavailable", "Trace Viewer 端口范围内没有可用端口。")

    resolved_trace_path = resolve_project_path(trace_path)
    runtime_dir = Path(".runtime")
    runtime_dir.mkdir(parents=True, exist_ok=True)
    out_log = runtime_dir / f"trace-viewer-{run_id}-{port}.out.log"
    err_log = runtime_dir / f"trace-viewer-{run_id}-{port}.err.log"
    command = [
        npx,
        "playwright",
        "show-trace",
        str(resolved_trace_path),
        "--host",
        settings.trace_viewer_host,
        "--port",
        str(port),
    ]

    try:
        with out_log.open("w", encoding="utf-8") as stdout, err_log.open("w", encoding="utf-8") as stderr:
            process = subprocess.Popen(
                command,
                cwd=PROJECT_ROOT,
                stdout=stdout,
                stderr=stderr,
                creationflags=_creation_flags(),
            )
    except FileNotFoundError:
        return _dependency_missing_response()
    except Exception as exc:
        return _failed_response("trace_viewer_start_failed", str(exc))

    time.sleep(1.0)
    if process.poll() is not None:
        error_text = _read_text(err_log) or _read_text(out_log)
        if _looks_like_missing_dependency(error_text):
            return _dependency_missing_response(error_text)
        return _failed_response("trace_viewer_start_failed", error_text or "Trace Viewer 启动失败。")

    now = _utc_now()
    session = TraceViewerSession(
        run_id=run_id,
        trace_path=trace_path,
        port=port,
        viewer_url=f"http://{settings.trace_viewer_public_host}:{port}",
        process=process,
        status="running",
        started_at=now,
        last_accessed_at=now,
    )
    _sessions[run_id] = session
    return _session_response(session)


def trace_viewer_status(run_id: int) -> dict:
    cleanup_trace_viewers()
    session = _sessions.get(run_id)
    if session is None:
        return {"enabled": settings.trace_viewer_enabled, "status": "not_started", "viewerUrl": "", "error": ""}
    if not _is_process_running(session.process):
        session.status = "stopped"
        return _session_response(session)
    session.last_accessed_at = _utc_now()
    return _session_response(session)


def stop_trace_viewer(run_id: int) -> dict:
    session = _sessions.get(run_id)
    if session is None:
        return {"enabled": settings.trace_viewer_enabled, "status": "stopped"}
    _stop_process(session.process)
    session.status = "stopped"
    return _session_response(session)


def find_trace_path(db: Session, run: TestRun) -> str | None:
    artifact = db.scalars(
        select(TestArtifact)
        .where(TestArtifact.run_id == run.id)
        .where(TestArtifact.artifact_type.in_(TRACE_ARTIFACT_TYPES))
        .order_by(TestArtifact.id.desc())
    ).first()
    if artifact and _path_exists(artifact.file_path):
        return artifact.file_path

    file_artifact = db.scalars(
        select(TestArtifact)
        .where(TestArtifact.run_id == run.id)
        .order_by(TestArtifact.id.desc())
    ).all()
    for item in file_artifact:
        if str(item.file_path).replace("\\", "/").endswith("/traces/trace.zip") and _path_exists(item.file_path):
            return item.file_path

    if run.run_code:
        candidate = run_dir(run.run_code) / "traces" / "trace.zip"
        if candidate.exists():
            return relative_to_project(candidate)
    return None


def cleanup_trace_viewers() -> None:
    timeout = max(settings.trace_viewer_idle_timeout_seconds, 1)
    now = _utc_now()
    for run_id, session in list(_sessions.items()):
        if not _is_process_running(session.process):
            session.status = "stopped"
            _sessions.pop(run_id, None)
            continue
        idle_seconds = (now - session.last_accessed_at).total_seconds()
        if idle_seconds >= timeout:
            _stop_process(session.process)
            session.status = "stopped"
            _sessions.pop(run_id, None)


def _allocate_port() -> int | None:
    start = settings.trace_viewer_port_start
    end = settings.trace_viewer_port_end
    for port in range(start, end + 1):
        if _port_available(port):
            return port
    return None


def _playwright_cli_available(npx: str) -> bool:
    try:
        completed = subprocess.run(
            [npx, "--no-install", "playwright", "--version"],
            cwd=PROJECT_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
            creationflags=_creation_flags(),
        )
        return completed.returncode == 0
    except Exception:
        return False


def _port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _path_exists(file_path: str) -> bool:
    try:
        return resolve_project_path(file_path).exists()
    except ValueError:
        return False


def _session_response(session: TraceViewerSession) -> dict:
    return {
        "enabled": settings.trace_viewer_enabled,
        "status": session.status,
        "viewerUrl": session.viewer_url if session.status == "running" else "",
        "port": session.port,
        "tracePath": session.trace_path,
        "pid": session.pid,
        "startedAt": session.started_at.isoformat(),
        "lastAccessedAt": session.last_accessed_at.isoformat(),
        "error": session.error or "",
    }


def _failed_response(error: str, message: str) -> dict:
    return {
        "enabled": settings.trace_viewer_enabled,
        "status": "failed",
        "viewerUrl": "",
        "error": error,
        "message": message,
    }


def _dependency_missing_response(raw_error: str | None = None) -> dict:
    message = "服务器未安装 Playwright CLI，请安装 Node.js 后执行 npm install -g playwright"
    if raw_error:
        message = f"{message}。原始错误：{raw_error[:500]}"
    return _failed_response("trace_viewer_dependency_missing", message)


def _looks_like_missing_dependency(value: str) -> bool:
    text = (value or "").lower()
    return "could not determine executable" in text or "not found" in text or "playwright" in text and "install" in text


def _is_process_running(process: subprocess.Popen) -> bool:
    return process.poll() is None


def _stop_process(process: subprocess.Popen) -> None:
    if not _is_process_running(process):
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        return ""


def _creation_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW") else 0


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
