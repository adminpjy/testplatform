import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from executor.aitp_executor.utils.file_paths import relative_to_project, run_dir


class ArtifactWriter:
    def __init__(self, run_code: str) -> None:
        self.run_code = run_code
        self.run_dir = run_dir(run_code)
        (self.run_dir / "screenshots").mkdir(parents=True, exist_ok=True)
        (self.run_dir / "dom").mkdir(parents=True, exist_ok=True)
        (self.run_dir / "accessibility").mkdir(parents=True, exist_ok=True)

    def path(self, *parts: str) -> Path:
        return self.run_dir.joinpath(*parts)

    def relative(self, path: Path) -> str:
        return relative_to_project(path)

    def screenshot_path(self, step_number: int) -> Path:
        return self.path("screenshots", f"step-{step_number:03d}.png")

    def dom_snapshot_path(self, step_number: int) -> Path:
        return self.path("dom", f"step-{step_number:03d}.html")

    def accessibility_snapshot_path(self, step_number: int) -> Path:
        return self.path("accessibility", f"step-{step_number:03d}.json")

    def write_json(self, filename: str, data: Any) -> str:
        path = self.path(filename)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.relative(path)

    def write_text(self, filename: str, content: str) -> str:
        path = self.path(filename)
        path.write_text(content, encoding="utf-8")
        return self.relative(path)

    def append_jsonl(self, filename: str, record: dict[str, Any]) -> str:
        path = self.path(filename)
        event = {"created_at": _utc_now(), **record}
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
        return self.relative(path)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
