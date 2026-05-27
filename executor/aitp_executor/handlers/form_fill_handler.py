from typing import Any

from executor.aitp_executor.handlers.base import CommonOperationHandler, handler_outcome, locator_outcome, require_locator
from executor.aitp_executor.locator.auto_form_filler import AutoFormFiller
from executor.aitp_executor.locator.element_locator import ElementLocator


class FormFillHandler(CommonOperationHandler):
    handler_name = "form_fill_handler"
    rule_types = ["form_fill", "form_control", "dropdown", "date_picker", "org_selector", "person_selector", "tree_selector", "dialog_selector", "file_upload"]
    default_intent = "fill_form"

    def __init__(self, *, locator: ElementLocator | None = None, form_filler: AutoFormFiller | None = None) -> None:
        super().__init__()
        self.locator = locator or ElementLocator()
        self.form_filler = form_filler or AutoFormFiller()

    def fill_form(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        resolution = self.resolve_rules(ctx, intent="fill_form", rule_types=self.rule_types)
        self.emit_rule_hits(ctx, resolution)
        self.emit(ctx, "progress", "form_fill", "正在按表单字段语义填写。")
        test_data = dict((dsl or {}).get("testData") or {})
        test_data.update(step.get("testData") or {})
        result = self.form_filler.fill(page, test_data=test_data)
        if result.defaults_used:
            self.emit(ctx, "text", "form_fill", "已按规则使用默认测试数据。", metadata={"defaults_used": result.defaults_used})
        if result.needs_clarification:
            raise RuntimeError("needs_clarification:" + ",".join(result.needs_clarification))
        self.debug(ctx, {"strategy": "auto_form_filler", "filled": result.filled, "defaultsUsed": result.defaults_used, "skipped": result.skipped})
        return handler_outcome(
            "auto_form_filler",
            "form",
            0.84,
            {"filled": result.filled, "defaults_used": result.defaults_used, "skipped": result.skipped},
        )

    def fill_field(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        self.emit_rule_hits(ctx, self.resolve_rules(ctx, intent="fill_field", rule_types=["form_fill", "form_control"]))
        target = str(step.get("target") or step.get("selector") or "")
        value = str(step.get("value") or "")
        self.emit(ctx, "progress", "form_fill", f"正在填写字段：{target}。")
        result = self.locator.locate(page, action="input", target=target, step=step)
        require_locator(result).fill(value)
        self.debug(ctx, {"strategy": "fill_field", "target": target, "locatorStrategy": result.strategy})
        return locator_outcome(result)
