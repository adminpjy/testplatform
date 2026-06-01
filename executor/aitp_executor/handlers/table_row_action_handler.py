import time
from typing import Any

from playwright.sync_api import Error as PlaywrightError

from executor.aitp_executor.handlers.base import CommonOperationHandler, handler_outcome
from executor.aitp_executor.handlers.dialog_selector_handler import DialogSelectorHandler
from executor.aitp_executor.handlers.query_handler import _compact_text, _extract_query_criteria, _format_criteria
from executor.aitp_executor.handlers.table_handler import TableHandler
from executor.aitp_executor.runner.page_waiter import wait_for_page_ready


class TableRowActionHandler(CommonOperationHandler):
    handler_name = "table_row_action_handler"
    rule_types = ["table_row_action", "table_detection", "candidate_ranking"]
    default_intent = "click_table_row_action"
    negative_approval_labels = ["查看审批流程", "审批记录", "流程图", "历史", "详情"]
    todo_action_labels = ["相关办理人处理", "办理人处理", "待办处理", "办理", "处理", "审批", "审核", "查看", "详情"]

    def __init__(self, *, table_handler: TableHandler | None = None, dialog_handler: DialogSelectorHandler | None = None) -> None:
        super().__init__()
        self.table_handler = table_handler or TableHandler()
        self.dialog_handler = dialog_handler or DialogSelectorHandler()

    def process_rows(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        self.emit_rule_hits(ctx, self.resolve_rules(ctx, intent="process_table_rows", rule_types=self.rule_types))
        loop_policy = dict(step.get("loopPolicy") or step.get("loop_policy") or {})
        max_rows = int(step.get("maxRows") or step.get("max_rows") or loop_policy.get("maxRows") or loop_policy.get("max_rows") or 200)
        empty_strategy = str(step.get("emptyStrategy") or step.get("empty_strategy") or loop_policy.get("emptyStrategy") or loop_policy.get("empty_strategy") or "pass")
        page = self._active_page(page, execution_context)
        data_indices = self.table_handler.data_row_indices(page)
        if not data_indices:
            if empty_strategy == "pass":
                return handler_outcome("table_row_loop", "0", 0.82, {"row_count": 0, "processed_rows": 0, "status": "empty_pass"})
            raise AssertionError("table_no_data_rows: 表格没有可处理数据行。")

        row_steps = self._row_steps(step, loop_policy)
        if row_steps:
            return self._process_rows_with_sub_steps(
                page,
                step=step,
                dsl=dsl or {},
                execution_context=execution_context or {},
                ctx=ctx,
                max_rows=max_rows,
                empty_strategy=empty_strategy,
                initial_row_count=len(data_indices),
                row_steps=row_steps,
                loop_policy=loop_policy,
            )

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

    def _process_rows_with_sub_steps(
        self,
        page: Any,
        *,
        step: dict[str, Any],
        dsl: dict[str, Any],
        execution_context: dict[str, Any],
        ctx: Any,
        max_rows: int,
        empty_strategy: str,
        initial_row_count: int,
        row_steps: list[dict[str, Any]],
        loop_policy: dict[str, Any],
    ) -> dict[str, Any]:
        self.emit(ctx, "progress", "table_row_loop", f"已识别 {initial_row_count} 条待处理数据，开始逐条打开并执行行内步骤。")
        processed = 0
        failures: list[dict[str, Any]] = []
        row_results: list[dict[str, Any]] = []
        seen_signatures: set[str] = set()
        continue_on_failure = bool(loop_policy.get("continueOnRowFailure") or loop_policy.get("continue_on_row_failure"))

        while processed < max_rows:
            page = self._active_page(page, execution_context)
            data_indices = self.table_handler.data_row_indices(page)
            if not data_indices:
                break
            index = self._next_unprocessed_row_index(page, data_indices, seen_signatures)
            if index is None:
                break

            row_number = processed + 1
            rows = self.table_handler.row_locator(page)
            row = rows.nth(index)
            row_signature = self._row_signature(row, fallback=f"row-index:{index}")
            if row_signature:
                seen_signatures.add(row_signature)
            row_result: dict[str, Any] = {"row": row_number, "sourceRowIndex": index + 1, "signature": row_signature}
            before_url = str(page.url)
            before_pages = self._open_pages(page)

            try:
                self.capture(execution_context, f"row_{row_number:03d}_before_open", {"row": row_number, "rowIndex": index + 1}, page=page)
                self.click_row_entry(row, labels=self._entry_labels(loop_policy))
                target_page, opened_new_page = self._resolve_row_target_page(page, before_pages)
                wait_for_page_ready(target_page)
                self._set_active_page(
                    execution_context,
                    target_page,
                    {
                        "row": row_number,
                        "openedNewPage": opened_new_page,
                        "sourceUrl": before_url,
                        "targetUrl": getattr(target_page, "url", ""),
                    },
                )
                self.capture(
                    execution_context,
                    f"row_{row_number:03d}_opened",
                    {"row": row_number, "openedNewPage": opened_new_page, "url": getattr(target_page, "url", "")},
                    page=target_page,
                )
                sub_outcomes = self._execute_row_steps(
                    target_page,
                    row_steps=row_steps,
                    row_number=row_number,
                    dsl=dsl,
                    execution_context=execution_context,
                )
                row_result["subSteps"] = sub_outcomes
                row_result["status"] = "processed"
                processed += 1
                row_results.append(row_result)
                self.capture(
                    execution_context,
                    f"row_{row_number:03d}_after_substeps",
                    {"row": row_number, "openedNewPage": opened_new_page},
                    page=target_page,
                )
                self._return_to_list_page(
                    list_page=page,
                    active_page=target_page,
                    opened_new_page=opened_new_page,
                    before_url=before_url,
                    execution_context=execution_context,
                    row_number=row_number,
                )
            except Exception as exc:
                row_result["status"] = "failed"
                row_result["error"] = str(exc)
                failures.append({"row": row_number, "sourceRowIndex": index + 1, "error": str(exc)})
                row_results.append(row_result)
                self.capture(execution_context, f"row_{row_number:03d}_failed", {"row": row_number, "error": str(exc)}, page=self._active_page(page, execution_context))
                try:
                    active = self._active_page(page, execution_context)
                    self._return_to_list_page(
                        list_page=page,
                        active_page=active,
                        opened_new_page=active is not page,
                        before_url=before_url,
                        execution_context=execution_context,
                        row_number=row_number,
                    )
                except Exception:
                    pass
                if not continue_on_failure:
                    break

        if failures:
            raise RuntimeError(
                "table_row_loop_failed:"
                + str({"processed_rows": processed, "row_count": initial_row_count, "failures": failures[:5]})
            )
        if processed == 0 and empty_strategy != "pass":
            raise RuntimeError("table_row_loop_failed: 未成功处理任何数据行。")
        self.debug(
            ctx,
            {
                "strategy": "process_table_rows_with_substeps",
                "rowCount": initial_row_count,
                "processedRows": processed,
                "rowSteps": len(row_steps),
            },
        )
        return handler_outcome(
            "table_row_loop",
            processed,
            0.88,
            {"row_count": initial_row_count, "processed_rows": processed, "status": "processed", "row_results": row_results},
        )

    def _execute_row_steps(
        self,
        page: Any,
        *,
        row_steps: list[dict[str, Any]],
        row_number: int,
        dsl: dict[str, Any],
        execution_context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        execute_sub_step = execution_context.get("execute_sub_step")
        if not callable(execute_sub_step):
            raise RuntimeError("table_row_loop_not_executable: 表格行循环缺少子步骤执行器，无法在打开的待办页继续填写和提交。")
        outcomes: list[dict[str, Any]] = []
        for sub_index, sub_step in enumerate(row_steps, start=1):
            current = dict(sub_step)
            current.setdefault("source", "table_row_loop")
            current.setdefault("rowNumber", row_number)
            self.capture(
                execution_context,
                f"row_{row_number:03d}_substep_{sub_index:03d}_before",
                {"row": row_number, "subStep": sub_index, "action": current.get("action"), "target": current.get("target")},
                page=page,
            )
            outcome = execute_sub_step(current, page, {"row": row_number, "subStep": sub_index})
            outcomes.append(
                {
                    "subStep": sub_index,
                    "action": current.get("action"),
                    "target": current.get("target"),
                    "locator_strategy": outcome.get("locator_strategy"),
                    "element_ref": outcome.get("element_ref"),
                    "reason": outcome.get("reason"),
                }
            )
            self.capture(
                execution_context,
                f"row_{row_number:03d}_substep_{sub_index:03d}_after",
                {"row": row_number, "subStep": sub_index, "action": current.get("action"), "target": current.get("target")},
                page=self._active_page(page, execution_context),
            )
        return outcomes

    def _return_to_list_page(
        self,
        *,
        list_page: Any,
        active_page: Any,
        opened_new_page: bool,
        before_url: str,
        execution_context: dict[str, Any],
        row_number: int,
    ) -> None:
        if opened_new_page and active_page is not list_page:
            try:
                if not active_page.is_closed():
                    active_page.close()
            except Exception:
                pass
            self._set_active_page(execution_context, list_page, {"row": row_number, "returnedTo": "list_page"})
            wait_for_page_ready(list_page)
            self.capture(execution_context, f"row_{row_number:03d}_returned", {"row": row_number, "strategy": "close_new_page"}, page=list_page)
            return

        if self.dialog_handler.dialog_visible(active_page, timeout_ms=1_000):
            self.dialog_handler.close(active_page)
            wait_for_page_ready(active_page)
            self.capture(execution_context, f"row_{row_number:03d}_returned", {"row": row_number, "strategy": "close_dialog"}, page=active_page)
            return
        if str(getattr(active_page, "url", "")) != before_url:
            try:
                active_page.go_back(wait_until="domcontentloaded")
                wait_for_page_ready(active_page)
            except Exception:
                pass
        self._set_active_page(execution_context, list_page, {"row": row_number, "returnedTo": "list_page"})
        self.capture(execution_context, f"row_{row_number:03d}_returned", {"row": row_number, "strategy": "same_page_back"}, page=list_page)

    def _resolve_row_target_page(self, page: Any, before_pages: list[Any]) -> tuple[Any, bool]:
        before_ids = {id(item) for item in before_pages}
        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline:
            for candidate in self._open_pages(page):
                if id(candidate) not in before_ids:
                    try:
                        candidate.bring_to_front()
                    except Exception:
                        pass
                    return candidate, True
            page.wait_for_timeout(100)
        return page, False

    def _open_pages(self, page: Any) -> list[Any]:
        try:
            return [item for item in page.context.pages if not item.is_closed()]
        except Exception:
            return [page]

    def _active_page(self, page: Any, execution_context: dict[str, Any] | None) -> Any:
        getter = (execution_context or {}).get("get_active_page")
        if callable(getter):
            try:
                active = getter()
                if active is not None:
                    return active
            except Exception:
                pass
        return page

    def _set_active_page(self, execution_context: dict[str, Any], page: Any, metadata: dict[str, Any] | None = None) -> None:
        setter = execution_context.get("set_active_page")
        if callable(setter):
            setter(page, metadata or {})

    def _next_unprocessed_row_index(self, page: Any, data_indices: list[int], seen_signatures: set[str]) -> int | None:
        rows = self.table_handler.row_locator(page)
        fallback: int | None = None
        for index in data_indices:
            row = rows.nth(index)
            signature = self._row_signature(row, fallback=f"row-index:{index}")
            if not signature or signature not in seen_signatures:
                return index
            if fallback is None:
                fallback = index
        return None if len(seen_signatures) >= len(data_indices) else fallback

    def _row_signature(self, row: Any, *, fallback: str = "") -> str:
        try:
            return " ".join(row.inner_text(timeout=800).split())[:500] or fallback
        except PlaywrightError:
            return fallback

    def _row_steps(self, step: dict[str, Any], loop_policy: dict[str, Any]) -> list[dict[str, Any]]:
        for key in ["rowSteps", "row_steps", "subSteps", "sub_steps", "bodySteps", "body_steps"]:
            value = step.get(key)
            if isinstance(value, list):
                return [dict(item) for item in value if isinstance(item, dict)]
            value = loop_policy.get(key)
            if isinstance(value, list):
                return [dict(item) for item in value if isinstance(item, dict)]
        return []

    def _entry_labels(self, loop_policy: dict[str, Any]) -> list[str]:
        value = loop_policy.get("rowEntryLabels") or loop_policy.get("row_entry_labels")
        if isinstance(value, list):
            labels = [str(item).strip() for item in value if str(item).strip()]
            if labels:
                return labels
        return self.todo_action_labels

    def open_first_row(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        self.emit_rule_hits(ctx, self.resolve_rules(ctx, intent="open_table_row", rule_types=self.rule_types))
        rows = self.table_handler.data_rows(page, max_rows=20)
        if not rows:
            return handler_outcome("row_link_or_detail", "first_row", 0.7, {"row_count": 0, "opened": False})
        criteria = self._target_row_criteria(step, dsl or {}, execution_context or {})
        target_row = rows[0]
        element_ref = "first_row"
        strategy = "open_first_table_row"
        confidence = 0.78
        if criteria:
            target_row = self._find_matching_row(rows, criteria)
            if target_row is None:
                raise RuntimeError(
                    "table_target_row_not_found: 未找到满足条件的数据行，已停止以避免打开错误记录："
                    + _format_criteria(criteria)
                    + "。"
                )
            element_ref = f"row:{_format_criteria(criteria)}"
            strategy = "open_matched_table_row"
            confidence = 0.91
        self.click_row_entry(target_row)
        page.wait_for_timeout(500)
        self.debug(ctx, {"strategy": strategy, "rowCount": len(rows), "criteria": criteria})
        return handler_outcome("row_link_or_detail", element_ref, confidence, {"row_count": len(rows), "opened": True, "criteria": criteria})

    def click_row_action(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        self.emit_rule_hits(ctx, self.resolve_rules(ctx, intent="click_table_row_action", rule_types=self.rule_types))
        row_text = str(step.get("rowText") or step.get("row_text") or "")
        action_name = str(step.get("button") or step.get("buttonText") or step.get("target") or "")
        rows = self.table_handler.row_locator(page)
        criteria = self._target_row_criteria(step, dsl or {}, execution_context or {})
        if row_text:
            row = rows.filter(has_text=row_text).first
        elif criteria:
            row = self._find_matching_row(self.table_handler.data_rows(page, max_rows=100), criteria)
        else:
            row = (self.table_handler.data_rows(page, max_rows=1) or [None])[0]
        if row is None:
            detail = f"：{_format_criteria(criteria)}" if criteria else ""
            raise RuntimeError(f"table_target_row_not_found: 未找到可操作数据行{detail}。")
        if not self.click_row_action_control(row, action_name, page=page):
            raise RuntimeError(f"table_no_action_found: 未找到行内操作“{action_name}”。")
        self.debug(ctx, {"strategy": "click_table_row_action", "rowText": row_text, "criteria": criteria, "actionName": action_name})
        return handler_outcome("table_row_action", f"{row_text or _format_criteria(criteria)}:{action_name}", 0.9, "table row action")

    def click_row_entry(self, row: Any, *, labels: list[str] | None = None) -> None:
        for label in labels or self.todo_action_labels:
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

    def _target_row_criteria(
        self,
        step: dict[str, Any],
        dsl: dict[str, Any],
        execution_context: dict[str, Any],
    ) -> dict[str, Any]:
        criteria: dict[str, Any] = {}
        for key in ["rowCriteria", "row_criteria", "recordCondition", "record_condition", "targetRecord", "target_record"]:
            value = step.get(key)
            if isinstance(value, dict):
                for field, field_value in value.items():
                    if field_value not in (None, ""):
                        criteria[str(field)] = field_value
        criteria.update({key: value for key, value in _extract_query_criteria(step).items() if value not in (None, "")})
        if criteria:
            return criteria
        return self._criteria_from_nearby_query_step(dsl, execution_context)

    def _criteria_from_nearby_query_step(self, dsl: dict[str, Any], execution_context: dict[str, Any]) -> dict[str, Any]:
        steps = [step for step in dsl.get("steps") or [] if isinstance(step, dict)]
        current_number = execution_context.get("step_number")
        last_query_criteria: dict[str, Any] = {}
        for index, candidate in enumerate(steps, start=1):
            if current_number is not None and index >= int(current_number):
                break
            action = str(candidate.get("action") or "")
            intent = str((candidate.get("operationIntent") or {}).get("intent") or candidate.get("intent") or "")
            criteria = _extract_query_criteria(candidate)
            if criteria and (action in {"query_table", "query_table_count"} or intent == "query_list"):
                last_query_criteria = criteria
        return last_query_criteria

    def _find_matching_row(self, rows: list[Any], criteria: dict[str, Any]) -> Any | None:
        values = [_compact_text(value) for value in criteria.values() if value not in (None, "")]
        if not values:
            return None
        for row in rows:
            try:
                row_text = _compact_text(row.inner_text(timeout=800))
            except PlaywrightError:
                continue
            if all(value in row_text for value in values):
                return row
        return None
