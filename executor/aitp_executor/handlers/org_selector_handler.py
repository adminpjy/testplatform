from typing import Any

from executor.aitp_executor.handlers.base import CommonOperationHandler, handler_outcome
from executor.aitp_executor.handlers.dialog_selector_handler import DialogSelectorHandler
from executor.aitp_executor.locator.element_locator import ElementLocator


class OrgSelectorHandler(CommonOperationHandler):
    handler_name = "org_selector_handler"
    rule_types = ["org_selector", "tree_selector", "dialog_selector"]
    default_intent = "select_org"

    def __init__(self, *, locator: ElementLocator | None = None, dialog_handler: DialogSelectorHandler | None = None) -> None:
        super().__init__()
        self.locator = locator or ElementLocator()
        self.dialog_handler = dialog_handler or DialogSelectorHandler()

    def select(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        self.emit_rule_hits(ctx, self.resolve_rules(ctx, intent="select_org", rule_types=self.rule_types))
        value = str(step.get("value") or (dsl or {}).get("testData", {}).get(step.get("target")) or "")
        target = str(step.get("target") or "组织机构")
        if not value:
            self.emit(ctx, "warning", "org_selector", "组织机构是关键业务字段，当前用例未提供具体机构，需要补充。")
            raise RuntimeError("needs_clarification:组织机构")
        self.emit(ctx, "progress", "org_selector", f"正在选择组织机构：{value}。")
        try:
            field = page.get_by_label(target, exact=True)
            if field.count() > 0:
                field.first.fill(value)
                return handler_outcome("org_direct_input", target, 0.74, {"value": value})
        except Exception:
            pass
        return self.dialog_handler.select_from_dialog(page, step={**step, "value": value}, dsl=dsl, execution_context=execution_context)
