from typing import Any

from playwright.sync_api import Error as PlaywrightError

from executor.aitp_executor.handlers.base import CommonOperationHandler, HandlerContext, handler_outcome
from executor.aitp_executor.observer.page_observer import PageObserver


class TableHandler(CommonOperationHandler):
    handler_name = "table_handler"
    rule_types = ["table_detection"]
    default_intent = "query_list"

    def __init__(self, *, observer: PageObserver | None = None) -> None:
        super().__init__()
        self.observer = observer or PageObserver()

    def wait_for_table(self, page: Any, *, step: dict[str, Any] | None = None, dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        resolution = self.resolve_rules(ctx, intent="query_list", rule_types=["table_detection"])
        self.emit_rule_hits(ctx, resolution)
        self.emit(ctx, "progress", "table_detection", "正在识别列表或表格。")
        selector = self._best_table_selector(page)
        if selector is None:
            raise RuntimeError("table_not_found: 未识别到可见表格。")
        table = page.locator(selector).first
        table.wait_for(state="visible", timeout=8_000)
        row_count = self.row_count(page)
        self.debug(ctx, {"strategy": "table_detection", "selector": selector, "rowCount": row_count})
        return handler_outcome("table_detection", selector, 0.9, {"row_count": row_count, "selector": selector})

    def row_count(self, page: Any) -> int:
        return len(self.data_row_indices(page))

    def data_rows(self, page: Any, *, max_rows: int = 200, row_selector: str | None = None) -> list[Any]:
        rows = self.row_locator(page, selector=row_selector)
        indices = self.data_row_indices(page, max_rows=max_rows, row_selector=row_selector)
        return [rows.nth(index) for index in indices]

    def data_row_indices(self, page: Any, *, max_rows: int = 200, row_selector: str | None = None) -> list[int]:
        rows = self.row_locator(page, selector=row_selector)
        indices: list[int] = []
        try:
            count = min(rows.count(), max_rows)
        except PlaywrightError:
            return []
        for index in range(count):
            row = rows.nth(index)
            if self.is_data_row(row):
                indices.append(index)
        return indices

    def row_locator(self, page: Any, *, selector: str | None = None) -> Any:
        if selector:
            return page.locator(selector)
        selectors = [
            "table tbody tr",
            ".ant-table-tbody tr",
            ".el-table__body tbody tr",
            ".vxe-table--body tbody tr",
            "[role='row']",
            ".table-row",
            ".grid-row",
        ]
        best = page.locator(selectors[0])
        best_count = 0
        for selector in selectors:
            try:
                locator = page.locator(selector)
                count = locator.count()
                if count > best_count:
                    best = locator
                    best_count = count
            except PlaywrightError:
                continue
        return best

    def is_data_row(self, row: Any) -> bool:
        try:
            if not row.is_visible(timeout=500):
                return False
            text = " ".join(row.inner_text(timeout=800).split())
            if not text:
                return False
            class_name = str(row.get_attribute("class") or "").lower()
            if any(token in class_name for token in ["summary", "pagination", "placeholder", "skeleton", "loading", "expanded"]):
                return False
            if any(token in text for token in ["合计", "总计", "暂无数据", "无数据", "没有可显示", "没有显示的记录", "加载中", "上一页", "下一页", "每页", "条/页"]):
                return False
            cells = row.locator("td, [role='cell'], .cell")
            if cells.count() == 0 and row.locator("th, [role='columnheader']").count() > 0:
                return False
            return True
        except PlaywrightError:
            return False

    def observe_tables(self, page: Any, ctx: HandlerContext) -> list[dict[str, Any]]:
        observation = self.observer.observe(page)
        tables = observation.tables
        self.debug(ctx, {"strategy": "page_observer_table_detection", "tableCount": len(tables), "tables": tables[:3]})
        return tables

    def _best_table_selector(self, page: Any) -> str | None:
        selectors = [
            "table",
            ".ant-table",
            ".el-table",
            ".vxe-table",
            "[role='grid']",
            ".table",
            ".grid",
        ]
        for selector in selectors:
            try:
                locator = page.locator(selector)
                for index in range(min(locator.count(), 4)):
                    item = locator.nth(index)
                    if item.is_visible(timeout=500):
                        return selector
            except PlaywrightError:
                continue
        return None
