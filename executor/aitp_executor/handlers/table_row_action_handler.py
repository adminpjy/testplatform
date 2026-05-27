from typing import Any

from playwright.sync_api import Error as PlaywrightError

from executor.aitp_executor.handlers.base import CommonOperationHandler, handler_outcome
from executor.aitp_executor.handlers.dialog_selector_handler import DialogSelectorHandler
from executor.aitp_executor.handlers.table_handler import TableHandler
from executor.aitp_executor.runner.page_waiter import wait_for_page_ready


class TableRowActionHandler(CommonOperationHandler):
    handler_name = "table_row_action_handler"
    rule_types = ["table_row_action", "table_detection", "candidate_ranking"]
    default_intent = "click_table_row_action"
    negative_approval_labels = ["查看审批流程", "审批记录", "流程图", "历史", "详情"]
    todo_action_labels = ["办理", "处理", "审批", "审核", "查看", "详情"]

    def __init__(self, *, table_handler: TableHandler | None = None, dialog_handler: DialogSelectorHandler | None = None) -> None:
        super().__init__()
        self.table_handler = table_handler or TableHandler()
        self.dialog_handler = dialog_handler or DialogSelectorHandler()

    def process_rows(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        self.emit_rule_hits(ctx, self.resolve_rules(ctx, intent="process_table_rows", rule_types=self.rule_types))
        max_rows = int(step.get("maxRows") or step.get("max_rows") or 200)
        empty_strategy = str(step.get("emptyStrategy") or step.get("empty_strategy") or "pass")
        data_indices = self.table_handler.data_row_indices(page)
        if not data_indices:
            if empty_strategy == "pass":
                return handler_outcome("table_row_loop", "0", 0.82, {"row_count": 0, "processed_rows": 0, "status": "empty_pass"})
            raise AssertionError("table_no_data_rows: 表格没有可处理数据行。")
        processed = 0
        failures: list[dict[str, Any]] = []
        for index in data_indices[:max_rows]:
            try:
                rows = self.table_handler.row_locator(page)
                row = rows.nth(index)
                before_url = page.url
                self.click_row_entry(row)
                page.wait_for_timeout(500)
                dialog_opened = self.dialog_handler.dialog_visible(page, timeout_ms=2_000)
                closed = False
                if dialog_opened:
                    closed = self.dialog_handler.close(page)
                elif page.url != before_url:
                    page.go_back(wait_until="domcontentloaded")
                    wait_for_page_ready(page)
                    closed = True
                processed += 1
                if dialog_opened and not closed:
                    failures.append({"row": index + 1, "error": "dialog_close_failed"})
            except Exception as exc:
                failures.append({"row": index + 1, "error": str(exc)})
        if failures:
            raise RuntimeError("table_row_loop_failed:" + str({"processed_rows": processed, "failures": failures[:5]}))
        self.debug(ctx, {"strategy": "process_table_rows", "rowCount": len(data_indices), "processedRows": processed})
        return handler_outcome("table_row_loop", processed, 0.84, {"row_count": len(data_indices), "processed_rows": processed, "status": "processed"})

    def open_first_row(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        self.emit_rule_hits(ctx, self.resolve_rules(ctx, intent="open_table_row", rule_types=self.rule_types))
        rows = self.table_handler.data_rows(page, max_rows=20)
        if not rows:
            return handler_outcome("row_link_or_detail", "first_row", 0.7, {"row_count": 0, "opened": False})
        self.click_row_entry(rows[0])
        page.wait_for_timeout(500)
        self.debug(ctx, {"strategy": "open_first_table_row", "rowCount": len(rows)})
        return handler_outcome("row_link_or_detail", "first_row", 0.78, {"row_count": len(rows), "opened": True})

    def click_row_action(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        self.emit_rule_hits(ctx, self.resolve_rules(ctx, intent="click_table_row_action", rule_types=self.rule_types))
        row_text = str(step.get("rowText") or step.get("row_text") or "")
        action_name = str(step.get("button") or step.get("buttonText") or step.get("target") or "")
        rows = self.table_handler.row_locator(page)
        row = rows.filter(has_text=row_text).first if row_text else (self.table_handler.data_rows(page, max_rows=1) or [None])[0]
        if row is None:
            raise RuntimeError("table_target_row_not_found: 未找到可操作数据行。")
        if not self.click_row_action_control(row, action_name, page=page):
            raise RuntimeError(f"table_no_action_found: 未找到行内操作“{action_name}”。")
        self.debug(ctx, {"strategy": "click_table_row_action", "rowText": row_text, "actionName": action_name})
        return handler_outcome("table_row_action", f"{row_text}:{action_name}", 0.9, "table row action")

    def click_row_entry(self, row: Any) -> None:
        for label in self.todo_action_labels:
            if self.click_row_action_control(row, label):
                return
        for selector in ["a", "button", "[role='button']", ".ant-btn", ".el-button", "td a", "td button"]:
            try:
                candidate = row.locator(selector)
                for index in range(min(candidate.count(), 8)):
                    item = candidate.nth(index)
                    text = " ".join(item.inner_text(timeout=500).split())
                    if any(negative in text for negative in self.negative_approval_labels):
                        continue
                    if item.is_visible(timeout=500) and item.is_enabled(timeout=500):
                        item.click()
                        return
            except PlaywrightError:
                continue
        try:
            row.dblclick()
            return
        except PlaywrightError as exc:
            raise RuntimeError("table_no_action_found: 当前数据行没有可点击入口。") from exc

    def click_row_action_control(self, row: Any, action_name: str, *, page: Any | None = None) -> bool:
        if not action_name:
            return False
        if action_name in {"审批通过", "通过", "同意", "批准"}:
            labels = ["审批", "审核", "办理", "处理", "通过", "同意", "批准"]
        else:
            labels = [action_name]
        for label in labels:
            try:
                button = row.get_by_role("button", name=label, exact=True)
                if button.count() > 0 and button.first.is_visible(timeout=500):
                    button.first.click()
                    return True
                link = row.get_by_role("link", name=label, exact=True)
                if link.count() > 0 and link.first.is_visible(timeout=500):
                    link.first.click()
                    return True
                text = row.get_by_text(label, exact=True)
                if text.count() > 0 and text.first.is_visible(timeout=500):
                    text.first.click()
                    return True
            except PlaywrightError:
                continue
        if action_name not in {"更多", "..."} and page is not None:
            return self._click_more_action(page, row, action_name)
        return False

    def _click_more_action(self, page: Any, row: Any, action_name: str) -> bool:
        for label in ["更多", "...", "操作"]:
            try:
                more = row.get_by_role("button", name=label, exact=True)
                if more.count() == 0:
                    continue
                more.first.click()
                page.wait_for_timeout(200)
                option = page.get_by_text(action_name, exact=True)
                if option.count() > 0:
                    option.first.click()
                    return True
            except PlaywrightError:
                continue
        return False
