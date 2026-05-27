from datetime import datetime, timedelta
from typing import Any

from playwright.sync_api import Error as PlaywrightError

from executor.aitp_executor.handlers.base import CommonOperationHandler, handler_outcome, locator_outcome, require_locator
from executor.aitp_executor.locator.element_locator import ElementLocator


class DatePickerHandler(CommonOperationHandler):
    handler_name = "date_picker_handler"
    rule_types = ["date_picker", "form_control"]
    default_intent = "select_date"

    def __init__(self, *, locator: ElementLocator | None = None) -> None:
        super().__init__()
        self.locator = locator or ElementLocator()

    def select_date(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        self.emit_rule_hits(ctx, self.resolve_rules(ctx, intent=ctx.intent or "select_date", rule_types=self.rule_types))
        target = str(step.get("target") or "")
        value = str(step.get("value") or self._default_date(target))
        self.emit(ctx, "progress", "date_picker", f"正在填写日期字段：{target}。", metadata={"value": value})
        result = self.locator.locate(page, action="input", target=target, step=step)
        locator = require_locator(result)
        try:
            locator.fill(value)
            return locator_outcome(result, reason=f"{result.reason};date_direct_input")
        except PlaywrightError:
            locator.click()
            date_text = page.get_by_text(value[-2:].lstrip("0") or value[-2:], exact=True)
            if date_text.count() > 0:
                date_text.first.click()
                return handler_outcome("date_picker_popup", target, 0.72, {"value": value})
            raise RuntimeError(f"date_not_selectable: {target}={value}")

    def _default_date(self, target: str) -> str:
        now = datetime.now()
        if any(token in target for token in ["结束", "计划完成"]):
            return (now + timedelta(days=7)).strftime("%Y-%m-%d")
        if "有效期结束" in target:
            return (now + timedelta(days=30)).strftime("%Y-%m-%d")
        if "出差结束" in target:
            return (now + timedelta(days=1)).strftime("%Y-%m-%d")
        return now.strftime("%Y-%m-%d")
