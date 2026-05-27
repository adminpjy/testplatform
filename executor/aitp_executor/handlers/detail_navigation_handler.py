from typing import Any

from playwright.sync_api import Error as PlaywrightError

from executor.aitp_executor.handlers.base import CommonOperationHandler, handler_outcome
from executor.aitp_executor.runner.page_waiter import wait_for_page_ready


class DetailNavigationHandler(CommonOperationHandler):
    handler_name = "detail_navigation_handler"
    rule_types = ["detail_navigation", "table_row_action"]
    default_intent = "view_detail"

    def open_detail(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        self.emit_rule_hits(ctx, self.resolve_rules(ctx, intent="view_detail", rule_types=self.rule_types))
        target = str(step.get("target") or "详情")
        self.emit(ctx, "progress", "detail_navigation", f"正在打开详情：{target}。")
        for name in [target, "详情", "查看", "查看详情"]:
            try:
                locator = page.get_by_role("link", name=name, exact=True)
                if locator.count() > 0:
                    locator.first.click()
                    wait_for_page_ready(page)
                    return handler_outcome("detail_link", name, 0.86, "detail opened")
                button = page.get_by_role("button", name=name, exact=True)
                if button.count() > 0:
                    button.first.click()
                    wait_for_page_ready(page)
                    return handler_outcome("detail_button", name, 0.84, "detail opened")
            except PlaywrightError:
                continue
        raise RuntimeError(f"table_no_action_found: 未找到详情入口“{target}”。")
