from pathlib import Path
from typing import Any

from executor.aitp_executor.handlers.base import CommonOperationHandler, locator_outcome, require_locator
from executor.aitp_executor.locator.element_locator import ElementLocator


class FileUploadHandler(CommonOperationHandler):
    handler_name = "file_upload_handler"
    rule_types = ["file_upload"]
    default_intent = "upload_file"

    def __init__(self, *, locator: ElementLocator | None = None) -> None:
        super().__init__()
        self.locator = locator or ElementLocator()

    def upload(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        self.emit_rule_hits(ctx, self.resolve_rules(ctx, intent="upload_file", rule_types=self.rule_types))
        file_path = str(step.get("file_path") or step.get("filePath") or step.get("value") or "")
        if not file_path:
            raise RuntimeError("needs_clarification:文件上传步骤未提供文件。")
        if not Path(file_path).exists():
            raise RuntimeError(f"file_not_found: {file_path}")
        target = str(step.get("target") or "附件")
        self.emit(ctx, "progress", "file_upload", f"正在上传文件：{Path(file_path).name}。")
        result = self.locator.locate(page, action="upload_file", target=target, step=step)
        require_locator(result).set_input_files(file_path)
        self.debug(ctx, {"strategy": "file_upload", "target": target, "file": Path(file_path).name})
        return locator_outcome(result)
