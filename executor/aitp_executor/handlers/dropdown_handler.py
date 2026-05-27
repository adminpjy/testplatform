from typing import Any

from playwright.sync_api import Error as PlaywrightError

from executor.aitp_executor.handlers.base import CommonOperationHandler, handler_outcome, locator_outcome, require_locator
from executor.aitp_executor.locator.element_locator import ElementLocator


class DropdownHandler(CommonOperationHandler):
    handler_name = "dropdown_handler"
    rule_types = ["dropdown", "form_control"]
    default_intent = "select_dropdown"

    def __init__(self, *, locator: ElementLocator | None = None) -> None:
        super().__init__()
        self.locator = locator or ElementLocator()

    def select(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        resolution = self.resolve_rules(ctx, intent="select_dropdown", rule_types=self.rule_types)
        self.emit_rule_hits(ctx, resolution)
        target = str(step.get("target") or "")
        value = str(step.get("value") or step.get("option") or target)
        self.emit(ctx, "progress", "dropdown", f"正在选择下拉项：{target} = {value}。")
        result = self.locator.locate(page, action="select", target=target, step=step)
        control = require_locator(result)
        try:
            control.select_option(label=value)
            self.debug(ctx, {"strategy": "native_select", "target": target, "value": value})
            return locator_outcome(result, reason=f"{result.reason};native_select")
        except PlaywrightError:
            pass
        try:
            control.click()
            page.wait_for_timeout(200)
            option = self._find_option(page, value)
            option.click()
            self.debug(ctx, {"strategy": "custom_select", "target": target, "value": value})
            return handler_outcome("custom_dropdown", value, 0.78, {"target": target, "value": value})
        except PlaywrightError as exc:
            raise RuntimeError(f"dropdown_option_not_found: {value}") from exc

    def _find_option(self, page: Any, value: str) -> Any:
        selectors = [
            "[role='option']",
            ".ant-select-item-option",
            ".el-select-dropdown__item",
            ".el-select-dropdown li",
            ".v-select-list .v-list-item",
        ]
        for selector in selectors:
            try:
                option = page.locator(selector).filter(has_text=value)
                if option.count() > 0 and option.first.is_visible(timeout=500):
                    return option.first
            except PlaywrightError:
                continue
        text = page.get_by_text(value, exact=True)
        if text.count() > 0:
            return text.first
        raise PlaywrightError(f"Option not found: {value}")
