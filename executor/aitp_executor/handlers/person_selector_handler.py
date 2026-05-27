from typing import Any

from executor.aitp_executor.handlers.base import CommonOperationHandler, handler_outcome
from executor.aitp_executor.handlers.dialog_selector_handler import DialogSelectorHandler


class PersonSelectorHandler(CommonOperationHandler):
    handler_name = "person_selector_handler"
    rule_types = ["person_selector", "tree_selector", "dialog_selector"]
    default_intent = "select_person"

    def __init__(self, *, dialog_handler: DialogSelectorHandler | None = None) -> None:
        super().__init__()
        self.dialog_handler = dialog_handler or DialogSelectorHandler()

    def select(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        self.emit_rule_hits(ctx, self.resolve_rules(ctx, intent="select_person", rule_types=self.rule_types))
        target = str(step.get("target") or "人员")
        value = str(step.get("value") or (dsl or {}).get("testData", {}).get(target) or "")
        if not value and any(token in target for token in ["申请人", "经办人"]):
            self.emit(ctx, "text", "person_selector", f"{target}未提供，按当前用户默认值处理。")
            return handler_outcome("person_current_user_default", target, 0.7, "current user default")
        if not value:
            self.emit(ctx, "warning", "person_selector", f"{target}是关键人员字段，需要补充。")
            raise RuntimeError(f"needs_clarification:{target}")
        self.emit(ctx, "progress", "person_selector", f"正在选择人员：{value}。")
        return self.dialog_handler.select_from_dialog(page, step={**step, "value": value}, dsl=dsl, execution_context=execution_context)
