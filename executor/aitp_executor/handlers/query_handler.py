from typing import Any

from playwright.sync_api import Error as PlaywrightError

from executor.aitp_executor.handlers.base import CommonOperationHandler, handler_outcome
from executor.aitp_executor.handlers.dropdown_handler import DropdownHandler
from executor.aitp_executor.handlers.table_handler import TableHandler
from executor.aitp_executor.locator.element_locator import ElementLocator
from executor.aitp_executor.runner.page_waiter import wait_for_page_ready


class QueryHandler(CommonOperationHandler):
    handler_name = "query_handler"
    rule_types = ["query", "table_detection"]
    default_intent = "query_list"

    def __init__(self, *, locator: ElementLocator | None = None, table_handler: TableHandler | None = None) -> None:
        super().__init__()
        self.locator = locator or ElementLocator()
        self.table_handler = table_handler or TableHandler()
        self.dropdown_handler = DropdownHandler(locator=self.locator)

    def execute(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        resolution = self.resolve_rules(ctx, intent="query_list", rule_types=["query", "table_detection"])
        self.emit_rule_hits(ctx, resolution)
        self.emit(ctx, "progress", "query", "正在处理查询条件并刷新列表。")
        criteria = dict(step.get("criteria") or step.get("query") or {})
        for label, value in criteria.items():
            self._fill_query_field(page, str(label), value)
        clicked = self._click_query_button(page)
        wait_for_page_ready(page)
        table_outcome = self.table_handler.wait_for_table(page, step=step, dsl=dsl, execution_context=execution_context)
        row_count = self.table_handler.row_count(page)
        empty_strategy = str(step.get("emptyStrategy") or step.get("empty_strategy") or "pass")
        if row_count == 0 and empty_strategy != "pass":
            raise AssertionError("table_no_data_rows: 查询结果没有数据行。")
        self.debug(ctx, {"strategy": "query_list", "criteriaKeys": list(criteria), "queryButtonClicked": clicked, "rowCount": row_count})
        return handler_outcome(
            "query_handler",
            "table",
            0.88,
            {"query_button_clicked": clicked, "row_count": row_count, "table": table_outcome.get("reason")},
        )

    def count_rows(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        resolution = self.resolve_rules(ctx, intent="query_list", rule_types=["query", "table_detection"])
        self.emit_rule_hits(ctx, resolution)
        row_count = self.table_handler.row_count(page)
        empty_strategy = str(step.get("emptyStrategy") or step.get("empty_strategy") or "pass")
        if row_count == 0 and empty_strategy != "pass":
            raise AssertionError("table_no_data_rows: 查询结果没有数据行。")
        self.debug(ctx, {"strategy": "query_table_count", "rowCount": row_count, "emptyStrategy": empty_strategy})
        return handler_outcome("table_count", row_count, 0.92, {"row_count": row_count, "empty_strategy": empty_strategy})

    def _fill_query_field(self, page: Any, label: str, value: Any) -> None:
        try:
            field = page.get_by_label(label, exact=True)
            if field.count() > 0:
                field.first.fill(str(value))
                return
        except PlaywrightError:
            pass
        try:
            field = page.get_by_placeholder(label, exact=False)
            if field.count() > 0:
                field.first.fill(str(value))
        except PlaywrightError:
            return

    def _click_query_button(self, page: Any) -> bool:
        for name in ["查询", "搜索", "筛选"]:
            try:
                button = page.get_by_role("button", name=name, exact=True)
                if button.count() > 0 and button.first.is_visible(timeout=500):
                    button.first.click()
                    return True
            except PlaywrightError:
                continue
        return False
