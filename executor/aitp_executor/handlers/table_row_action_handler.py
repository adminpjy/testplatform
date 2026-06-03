import time
from typing import Any

from playwright.sync_api import Error as PlaywrightError

from executor.aitp_executor.handlers.base import CommonOperationHandler, handler_outcome
from executor.aitp_executor.handlers.dialog_selector_handler import DialogSelectorHandler
from executor.aitp_executor.handlers.executable_rules import int_setting, list_setting, merged_rule_config
from executor.aitp_executor.handlers.list_page_evidence import assert_target_list_page_ready_for_empty_result
from executor.aitp_executor.handlers.query_handler import _compact_text, _extract_query_criteria, _format_criteria
from executor.aitp_executor.handlers.table_handler import TableHandler
from executor.aitp_executor.runner.page_waiter import wait_for_page_ready


class TableRowActionHandler(CommonOperationHandler):
    handler_name = "table_row_action_handler"
    rule_types = ["table_row_action", "table_detection", "candidate_ranking"]
    default_intent = "click_table_row_action"
    negative_approval_labels = ["查看审批流程", "审批记录", "流程图", "历史", "详情"]
    todo_action_labels = ["相关办理人处理", "办理人处理", "待办处理", "办理", "处理", "审批", "审核", "查看", "详情"]
    DEFAULT_MAX_ROWS = 30
    DEFAULT_LOOP_TIMEOUT_MS = 600_000
    DEFAULT_ROW_PROBE_TIMEOUT_MS = 250
    DEFAULT_ROW_ENTRY_CANDIDATES = 4
    DEFAULT_CONSECUTIVE_FAILURES = 2
    DEFAULT_LIST_SYNC_TIMEOUT_MS = 3_000
    DEFAULT_LIST_SYNC_SETTLE_MS = 300

    def __init__(self, *, table_handler: TableHandler | None = None, dialog_handler: DialogSelectorHandler | None = None) -> None:
        super().__init__()
        self.table_handler = table_handler or TableHandler()
        self.dialog_handler = dialog_handler or DialogSelectorHandler()

    def process_rows(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        resolution = self.resolve_rules(ctx, intent="process_table_rows", rule_types=self.rule_types)
        ctx.step["abilityResolution"] = resolution
        self.emit_rule_hits(ctx, resolution)
        loop_policy = dict(step.get("loopPolicy") or step.get("loop_policy") or {})
        rule_config = merged_rule_config(ctx, rule_type="table_row_action")
        loop_policy = self._apply_table_rule_config(loop_policy, rule_config)
        guard = self._loop_guard(step, loop_policy)
        max_rows = guard["max_rows"]
        stop_after_initial_rows = self._stop_after_initial_rows(loop_policy)
        empty_strategy = str(step.get("emptyStrategy") or step.get("empty_strategy") or loop_policy.get("emptyStrategy") or loop_policy.get("empty_strategy") or "pass")
        page = self._active_page(page, execution_context)
        row_selector = self._row_selector(loop_policy)
        data_indices = self.table_handler.data_row_indices(page, row_selector=row_selector)
        if not data_indices and row_selector:
            self.debug(ctx, {"strategy": "rule_row_selector_fallback", "rowSelector": row_selector})
            row_selector = None
            data_indices = self.table_handler.data_row_indices(page)
        if not data_indices:
            assert_target_list_page_ready_for_empty_result(page, step, loop_policy=loop_policy)
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
                guard=guard,
            )

        processed = 0
        attempted = 0
        failures: list[dict[str, Any]] = []
        started = time.monotonic()
        consecutive_failures = 0
        abort_reason: dict[str, Any] | None = None
        seen_signatures: set[str] = set()
        initial_row_count = len(data_indices)
        self.emit(
            ctx,
            "progress",
            "table_row_loop",
            f"已识别 {initial_row_count} 条数据，最多处理 {max_rows} 条，超过安全预算会自动停止。",
            metadata={"row_count": initial_row_count, "max_rows": max_rows, "loop_timeout_ms": guard["loop_timeout_ms"]},
        )
        while attempted < max_rows:
            if stop_after_initial_rows and processed >= initial_row_count:
                self.emit(
                    ctx,
                    "success",
                    "table_row_loop",
                    f"已完成初始识别的 {initial_row_count} 行，结束本轮列表循环。",
                    metadata={"row_count": initial_row_count, "processed_rows": processed, "attempted_rows": attempted},
                )
                break
            if self._elapsed_ms(started) >= guard["loop_timeout_ms"]:
                abort_reason = self._loop_abort_payload(
                    "timeout",
                    "表格行循环超过安全时间预算，已停止以避免死循环。",
                    processed=processed,
                    attempted=attempted,
                    row_count=initial_row_count,
                    failures=failures,
                    guard=guard,
                    elapsed_ms=self._elapsed_ms(started),
                )
                break
            page = self._active_page(page, execution_context)
            row_selector = self._row_selector(loop_policy)
            data_indices = self.table_handler.data_row_indices(page, row_selector=row_selector)
            if not data_indices and row_selector:
                self.debug(ctx, {"strategy": "rule_row_selector_fallback", "rowSelector": row_selector})
                row_selector = None
                data_indices = self.table_handler.data_row_indices(page)
            if not data_indices:
                break
            index = self._next_unprocessed_row_index(page, data_indices, seen_signatures, row_selector=row_selector)
            if index is None:
                break

            row_number = attempted + 1
            attempted += 1
            try:
                rows = self.table_handler.row_locator(page, selector=row_selector)
                row = rows.nth(index)
                row_signature = self._row_signature(row, fallback=f"row-index:{index}")
                if row_signature:
                    seen_signatures.add(row_signature)
                before_url = str(page.url)
                self.emit(
                    ctx,
                    "progress",
                    "table_row_loop",
                    f"正在处理第 {row_number} 行。",
                    metadata={"row": row_number, "source_row_index": index + 1, "processed_rows": processed},
                )
                self.capture(
                    execution_context,
                    f"row_{row_number:03d}_before_open",
                    {"row": row_number, "rowIndex": index + 1, "mode": "open_only"},
                    page=page,
                )
                target_page, opened_new_page, entry_strategy = self._open_row_target_page(
                    page,
                    rows=rows,
                    row_index=index,
                    row_number=row_number,
                    loop_policy=loop_policy,
                    guard=guard,
                    execution_context=execution_context or {},
                )
                self._set_active_page(
                    execution_context or {},
                    target_page,
                    {
                        "row": row_number,
                        "openedNewPage": opened_new_page,
                        "entryStrategy": entry_strategy,
                        "sourceUrl": before_url,
                        "targetUrl": getattr(target_page, "url", ""),
                    },
                )
                processed += 1
                consecutive_failures = 0
                self.capture(
                    execution_context,
                    f"row_{row_number:03d}_after_open",
                    {"row": row_number, "rowIndex": index + 1, "openedNewPage": opened_new_page, "entryStrategy": entry_strategy},
                    page=target_page,
                )
                self.emit(
                    ctx,
                    "success",
                    "table_row_loop",
                    f"第 {row_number} 行处理完成。",
                    metadata={"row": row_number, "processed_rows": processed},
                )
                self._return_to_list_page(
                    list_page=page,
                    active_page=target_page,
                    opened_new_page=opened_new_page,
                    before_url=before_url,
                    execution_context=execution_context or {},
                    row_number=row_number,
                )
                self._sync_list_after_row_completion(
                    list_page=page,
                    row_signature=row_signature,
                    row_selector=row_selector,
                    loop_policy=loop_policy,
                    execution_context=execution_context or {},
                    ctx=ctx,
                    row_number=row_number,
                )
            except Exception as exc:
                consecutive_failures += 1
                failure = {"row": row_number, "sourceRowIndex": index + 1, "error": str(exc)}
                failures.append(failure)
                self.capture(execution_context, f"row_{row_number:03d}_failed", failure, page=self._active_page(page, execution_context))
                self.emit(
                    ctx,
                    "warning",
                    "table_row_loop",
                    f"第 {row_number} 行未处理成功：{str(exc)[:120]}",
                    metadata={
                        "row": row_number,
                        "source_row_index": index + 1,
                        "consecutive_failures": consecutive_failures,
                        "processed_rows": processed,
                    },
                )
                if consecutive_failures >= guard["max_consecutive_failures"]:
                    abort_reason = self._loop_abort_payload(
                        "consecutive_failures",
                        f"连续 {consecutive_failures} 行处理失败，已停止以避免在错误表格或错误入口上循环。",
                        processed=processed,
                        attempted=attempted,
                        row_count=initial_row_count,
                        failures=failures,
                        guard=guard,
                        elapsed_ms=self._elapsed_ms(started),
                    )
                    break
        if failures:
            if abort_reason:
                self.emit(ctx, "warning", "table_row_loop_guard", abort_reason["message"], metadata=abort_reason)
                raise RuntimeError("table_row_loop_guard_triggered:" + str(abort_reason))
            raise RuntimeError(
                "table_row_loop_failed:"
                + str(
                    {
                        "processed_rows": processed,
                        "attempted_rows": attempted,
                        "row_count": initial_row_count,
                        "failures": failures[:5],
                    }
                )
            )
        if abort_reason:
            self.emit(ctx, "warning", "table_row_loop_guard", abort_reason["message"], metadata=abort_reason)
            raise RuntimeError("table_row_loop_failed:" + str(abort_reason))
        completed_initial_batch = stop_after_initial_rows and processed >= initial_row_count
        remaining_rows = 0 if completed_initial_batch else self._remaining_unseen_row_count(page, seen_signatures=seen_signatures, row_selector=row_selector)
        if remaining_rows > 0:
            incomplete = self._loop_abort_payload(
                "remaining_rows",
                f"列表行循环未完成：初始识别 {initial_row_count} 条，已处理 {processed} 条，当前仍检测到 {remaining_rows} 条未处理记录。",
                processed=processed,
                attempted=attempted,
                row_count=initial_row_count,
                failures=failures,
                guard=guard,
                elapsed_ms=self._elapsed_ms(started),
            )
            incomplete["remaining_rows"] = remaining_rows
            self.emit(ctx, "warning", "table_row_loop_incomplete", incomplete["message"], metadata=incomplete)
            raise RuntimeError("table_row_loop_failed:" + str(incomplete))
        self.debug(ctx, {"strategy": "process_table_rows", "rowCount": initial_row_count, "processedRows": processed})
        return handler_outcome(
            "table_row_loop",
            processed,
            0.84,
            {"row_count": initial_row_count, "processed_rows": processed, "attempted_rows": attempted, "status": "processed"},
        )

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
        guard: dict[str, int],
    ) -> dict[str, Any]:
        self.emit(
            ctx,
            "progress",
            "table_row_loop",
            f"已识别 {initial_row_count} 条待处理数据，开始逐条打开并执行行内步骤。",
            metadata={"row_count": initial_row_count, "max_rows": max_rows, "loop_timeout_ms": guard["loop_timeout_ms"]},
        )
        processed = 0
        attempted = 0
        failures: list[dict[str, Any]] = []
        row_results: list[dict[str, Any]] = []
        seen_signatures: set[str] = set()
        continue_on_failure = bool(loop_policy.get("continueOnRowFailure") or loop_policy.get("continue_on_row_failure"))
        stop_after_initial_rows = self._stop_after_initial_rows(loop_policy)
        started = time.monotonic()
        consecutive_failures = 0
        abort_reason: dict[str, Any] | None = None

        while attempted < max_rows:
            if stop_after_initial_rows and (processed >= initial_row_count or attempted >= initial_row_count):
                self.emit(
                    ctx,
                    "success" if not failures else "warning",
                    "table_row_loop",
                    f"已完成初始识别的 {initial_row_count} 条待办扫描，结束本轮列表循环。",
                    metadata={
                        "row_count": initial_row_count,
                        "processed_rows": processed,
                        "attempted_rows": attempted,
                        "failed_rows": len(failures),
                    },
                )
                break
            if self._elapsed_ms(started) >= guard["loop_timeout_ms"]:
                abort_reason = self._loop_abort_payload(
                    "timeout",
                    "表格行循环超过安全时间预算，已停止以避免死循环。",
                    processed=processed,
                    attempted=attempted,
                    row_count=initial_row_count,
                    failures=failures,
                    guard=guard,
                    elapsed_ms=self._elapsed_ms(started),
                )
                break
            page = self._active_page(page, execution_context)
            row_selector = self._row_selector(loop_policy)
            data_indices = self.table_handler.data_row_indices(page, row_selector=row_selector)
            if not data_indices and row_selector:
                self.debug(ctx, {"strategy": "rule_row_selector_fallback", "rowSelector": row_selector})
                row_selector = None
                data_indices = self.table_handler.data_row_indices(page)
            if not data_indices:
                break
            index = self._next_unprocessed_row_index(page, data_indices, seen_signatures, row_selector=row_selector)
            if index is None:
                break

            row_number = attempted + 1
            attempted += 1
            rows = self.table_handler.row_locator(page, selector=row_selector)
            row = rows.nth(index)
            row_signature = self._row_signature(row, fallback=f"row-index:{index}")
            if row_signature:
                seen_signatures.add(row_signature)
            row_result: dict[str, Any] = {"row": row_number, "sourceRowIndex": index + 1, "signature": row_signature}
            before_url = str(page.url)

            try:
                self.emit(
                    ctx,
                    "progress",
                    "table_row_loop",
                    f"正在打开第 {row_number} 条待办并执行审批步骤。",
                    metadata={"row": row_number, "source_row_index": index + 1, "processed_rows": processed},
                )
                self.capture(execution_context, f"row_{row_number:03d}_before_open", {"row": row_number, "rowIndex": index + 1}, page=page)
                target_page, opened_new_page, entry_strategy = self._open_row_target_page(
                    page,
                    rows=rows,
                    row_index=index,
                    row_number=row_number,
                    loop_policy=loop_policy,
                    guard=guard,
                    execution_context=execution_context,
                )
                self._set_active_page(
                    execution_context,
                    target_page,
                    {
                        "row": row_number,
                        "openedNewPage": opened_new_page,
                        "entryStrategy": entry_strategy,
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
                active_after_substeps = self._active_page(target_page, execution_context)
                return_opened_new_page = opened_new_page or active_after_substeps is not page
                row_result["subSteps"] = sub_outcomes
                row_result["status"] = "processed"
                processed += 1
                consecutive_failures = 0
                row_results.append(row_result)
                self.capture(
                    execution_context,
                    f"row_{row_number:03d}_after_substeps",
                    {"row": row_number, "openedNewPage": return_opened_new_page},
                    page=active_after_substeps,
                )
                self.emit(
                    ctx,
                    "success",
                    "table_row_loop",
                    f"第 {row_number} 条待办处理完成。",
                    metadata={"row": row_number, "processed_rows": processed, "opened_new_page": return_opened_new_page},
                )
                self._return_to_list_page(
                    list_page=page,
                    active_page=active_after_substeps,
                    opened_new_page=return_opened_new_page,
                    before_url=before_url,
                    execution_context=execution_context,
                    row_number=row_number,
                )
                row_result["listSync"] = self._sync_list_after_row_completion(
                    list_page=page,
                    row_signature=row_signature,
                    row_selector=row_selector,
                    loop_policy=loop_policy,
                    execution_context=execution_context,
                    ctx=ctx,
                    row_number=row_number,
                )
            except Exception as exc:
                row_result["status"] = "failed"
                row_result["error"] = str(exc)
                failures.append({"row": row_number, "sourceRowIndex": index + 1, "error": str(exc)})
                row_results.append(row_result)
                consecutive_failures += 1
                self.capture(execution_context, f"row_{row_number:03d}_failed", {"row": row_number, "error": str(exc)}, page=self._active_page(page, execution_context))
                self.emit(
                    ctx,
                    "warning",
                    "table_row_loop",
                    f"第 {row_number} 条待办处理失败：{str(exc)[:120]}",
                    metadata={
                        "row": row_number,
                        "source_row_index": index + 1,
                        "consecutive_failures": consecutive_failures,
                        "processed_rows": processed,
                    },
                )
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
                if consecutive_failures >= guard["max_consecutive_failures"]:
                    abort_reason = self._loop_abort_payload(
                        "consecutive_failures",
                        f"连续 {consecutive_failures} 行处理失败，已停止以避免在错误表格或错误入口上循环。",
                        processed=processed,
                        attempted=attempted,
                        row_count=initial_row_count,
                        failures=failures,
                        guard=guard,
                        elapsed_ms=self._elapsed_ms(started),
                    )
                    break
                if not continue_on_failure:
                    break

        if failures:
            if abort_reason:
                self.emit(ctx, "warning", "table_row_loop_guard", abort_reason["message"], metadata=abort_reason)
                raise RuntimeError("table_row_loop_guard_triggered:" + str(abort_reason))
            raise RuntimeError(
                "table_row_loop_failed:"
                + str(
                    {
                        "processed_rows": processed,
                        "attempted_rows": attempted,
                        "row_count": initial_row_count,
                        "failures": failures[:5],
                    }
                )
            )
        if abort_reason:
            self.emit(ctx, "warning", "table_row_loop_guard", abort_reason["message"], metadata=abort_reason)
            raise RuntimeError("table_row_loop_failed:" + str(abort_reason))
        if processed == 0 and empty_strategy != "pass":
            raise RuntimeError("table_row_loop_failed: 未成功处理任何数据行。")
        completed_initial_batch = stop_after_initial_rows and processed >= initial_row_count and not failures
        remaining_rows = 0 if completed_initial_batch else self._remaining_unseen_row_count(page, seen_signatures=seen_signatures, row_selector=row_selector)
        if remaining_rows > 0:
            incomplete = self._loop_abort_payload(
                "remaining_rows",
                f"列表行循环未完成：初始识别 {initial_row_count} 条，已处理 {processed} 条，当前仍检测到 {remaining_rows} 条未处理记录。",
                processed=processed,
                attempted=attempted,
                row_count=initial_row_count,
                failures=failures,
                guard=guard,
                elapsed_ms=self._elapsed_ms(started),
            )
            incomplete["remaining_rows"] = remaining_rows
            incomplete["row_results"] = row_results
            self.emit(ctx, "warning", "table_row_loop_incomplete", incomplete["message"], metadata=incomplete)
            raise RuntimeError("table_row_loop_failed:" + str(incomplete))
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
            {
                "row_count": initial_row_count,
                "processed_rows": processed,
                "attempted_rows": attempted,
                "status": "processed",
                "row_results": row_results,
            },
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
            self._wait_for_list_surface(list_page)
            if self.dialog_handler.dialog_visible(list_page, timeout_ms=500):
                self.dialog_handler.close(list_page)
                self._wait_for_list_surface(list_page)
            self.capture(execution_context, f"row_{row_number:03d}_returned", {"row": row_number, "strategy": "close_new_page"}, page=list_page)
            return

        if self.dialog_handler.dialog_visible(active_page, timeout_ms=1_000):
            self.dialog_handler.close(active_page)
            self._wait_for_list_surface(active_page)
            self._set_active_page(execution_context, list_page, {"row": row_number, "returnedTo": "list_page"})
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

    def _wait_for_list_surface(self, page: Any, *, timeout_ms: int = 800) -> None:
        try:
            page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
            return
        except PlaywrightError:
            pass
        try:
            page.wait_for_timeout(min(timeout_ms, 500))
        except PlaywrightError:
            pass

    def _sync_list_after_row_completion(
        self,
        *,
        list_page: Any,
        row_signature: str,
        row_selector: str | None,
        loop_policy: dict[str, Any],
        execution_context: dict[str, Any],
        ctx: Any,
        row_number: int,
    ) -> dict[str, Any]:
        policy = self._list_sync_policy(loop_policy)
        if not policy["enabled"]:
            return {"status": "disabled"}

        settle_ms = int(policy["settle_ms"])
        if settle_ms > 0:
            list_page.wait_for_timeout(settle_ms)

        before_refresh = self._row_removed_or_changed(list_page, row_signature=row_signature, row_selector=row_selector)
        if before_refresh["changed"]:
            self.capture(execution_context, f"row_{row_number:03d}_list_synced", {"row": row_number, **before_refresh}, page=list_page)
            return {"status": "synced", **before_refresh}

        methods_used: list[str] = []
        if policy["refresh_when_unchanged"]:
            for _attempt in range(int(policy["max_refresh_attempts"])):
                method = self._refresh_list_page(list_page, policy)
                if not method:
                    break
                methods_used.append(method)
                wait_for_page_ready(list_page)
                wait_ms = int(policy["wait_after_refresh_ms"])
                if wait_ms > 0:
                    list_page.wait_for_timeout(wait_ms)
                after_refresh = self._wait_for_row_change(
                    list_page,
                    row_signature=row_signature,
                    row_selector=row_selector,
                    timeout_ms=int(policy["wait_change_ms"]),
                )
                if after_refresh["changed"]:
                    self.emit(
                        ctx,
                        "progress",
                        "table_row_loop",
                        f"第 {row_number} 行处理后列表已刷新，继续处理下一条。",
                        metadata={"row": row_number, "refresh_methods": methods_used, **after_refresh},
                    )
                    self.capture(
                        execution_context,
                        f"row_{row_number:03d}_list_refreshed",
                        {"row": row_number, "refreshMethods": methods_used, **after_refresh},
                        page=list_page,
                    )
                    return {"status": "refreshed", "refresh_methods": methods_used, **after_refresh}

        if policy["skip_signature_when_unchanged"]:
            self.emit(
                ctx,
                "warning",
                "table_row_loop",
                f"第 {row_number} 行处理后列表未自动刷新，系统将跳过已处理行签名，避免重复点击同一条记录。",
                metadata={"row": row_number, "refresh_methods": methods_used, "row_signature": row_signature[:120]},
            )
            self.capture(
                execution_context,
                f"row_{row_number:03d}_list_unchanged_skip_signature",
                {"row": row_number, "refreshMethods": methods_used, "signature": row_signature},
                page=list_page,
            )
            return {
                "status": "unchanged_skip_signature",
                "changed": False,
                "refresh_methods": methods_used,
                "row_signature": row_signature,
            }

        raise RuntimeError(
            "table_list_not_refreshed: 当前行处理完成后列表仍显示相同记录，且规则未允许跳过已处理行。"
            "请在规则库配置处理后刷新列表或允许按行签名跳过。"
        )

    def _open_row_target_page(
        self,
        page: Any,
        *,
        rows: Any,
        row_index: int,
        row_number: int,
        loop_policy: dict[str, Any],
        guard: dict[str, int],
        execution_context: dict[str, Any],
    ) -> tuple[Any, bool, str]:
        strategies = self._click_strategies(loop_policy)
        for attempt_index, strategy in enumerate(strategies, start=1):
            before_url = str(getattr(page, "url", ""))
            before_pages = self._open_pages(page)
            row = rows.nth(row_index)
            try:
                entry_strategy = self.click_row_entry(
                    row,
                    labels=self._entry_labels(loop_policy),
                    entry_selectors=self._entry_selectors(loop_policy),
                    candidate_timeout_ms=guard["row_probe_timeout_ms"],
                    max_candidates=guard["max_candidates"],
                    click_strategy=strategy,
                )
                page.wait_for_timeout(self._open_wait_ms(loop_policy))
                target_page, opened_new_page = self._wait_for_row_target_page(
                    page,
                    before_pages,
                    before_url=before_url,
                    loop_policy=loop_policy,
                    timeout_ms=self._new_page_timeout_ms(loop_policy),
                )
                wait_for_page_ready(target_page)
                if self._row_open_reached(
                    target_page,
                    before_url=before_url,
                    opened_new_page=opened_new_page,
                    loop_policy=loop_policy,
                ):
                    return target_page, opened_new_page, entry_strategy
                self.capture(
                    execution_context,
                    f"row_{row_number:03d}_open_attempt_{attempt_index:02d}_no_effect",
                    {"row": row_number, "rowIndex": row_index + 1, "strategy": entry_strategy, "url": getattr(target_page, "url", "")},
                    page=target_page,
                )
                self._return_from_failed_open_attempt(
                    list_page=page,
                    target_page=target_page,
                    opened_new_page=opened_new_page,
                    before_url=before_url,
                )
            except Exception as exc:
                self.capture(
                    execution_context,
                    f"row_{row_number:03d}_open_attempt_{attempt_index:02d}_failed",
                    {"row": row_number, "rowIndex": row_index + 1, "strategy": strategy, "error": str(exc)},
                    page=self._active_page(page, execution_context),
                )
        raise RuntimeError(
            "table_row_open_failed: 已按规则尝试打开待办详情，但没有检测到详情页、弹窗或审批表单。"
            "请检查行入口规则、点击策略或详情页成功标识。"
        )

    def _return_from_failed_open_attempt(
        self,
        *,
        list_page: Any,
        target_page: Any,
        opened_new_page: bool,
        before_url: str,
    ) -> None:
        try:
            if opened_new_page and target_page is not list_page:
                if not target_page.is_closed():
                    target_page.close()
                return
            if self.dialog_handler.dialog_visible(target_page, timeout_ms=300):
                self.dialog_handler.close(target_page)
                return
            if str(getattr(target_page, "url", "")) != before_url:
                target_page.go_back(wait_until="domcontentloaded")
                wait_for_page_ready(target_page)
        except Exception:
            return

    def _wait_for_row_target_page(
        self,
        page: Any,
        before_pages: list[Any],
        *,
        before_url: str,
        loop_policy: dict[str, Any],
        timeout_ms: int | None = None,
    ) -> tuple[Any, bool]:
        before_ids = {id(item) for item in before_pages}
        deadline = time.monotonic() + (timeout_ms or 4_000) / 1000
        while time.monotonic() < deadline:
            for candidate in self._open_pages(page):
                if id(candidate) not in before_ids:
                    try:
                        candidate.bring_to_front()
                    except Exception:
                        pass
                    return candidate, True
            if self._row_open_reached(page, before_url=before_url, opened_new_page=False, loop_policy=loop_policy):
                return page, False
            page.wait_for_timeout(100)
        return page, False

    def _resolve_row_target_page(self, page: Any, before_pages: list[Any], *, timeout_ms: int | None = None) -> tuple[Any, bool]:
        before_ids = {id(item) for item in before_pages}
        deadline = time.monotonic() + (timeout_ms or 4_000) / 1000
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

    def _next_unprocessed_row_index(
        self,
        page: Any,
        data_indices: list[int],
        seen_signatures: set[str],
        *,
        row_selector: str | None = None,
    ) -> int | None:
        rows = self.table_handler.row_locator(page, selector=row_selector)
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

    def _row_removed_or_changed(self, page: Any, *, row_signature: str, row_selector: str | None) -> dict[str, Any]:
        signatures = self._current_row_signatures(page, row_selector=row_selector)
        if not row_signature:
            return {"changed": False, "reason": "missing_signature", "row_count": len(signatures)}
        if row_signature not in signatures:
            return {"changed": True, "reason": "processed_row_removed_or_changed", "row_count": len(signatures)}
        return {"changed": False, "reason": "processed_row_still_visible", "row_count": len(signatures)}

    def _wait_for_row_change(self, page: Any, *, row_signature: str, row_selector: str | None, timeout_ms: int) -> dict[str, Any]:
        deadline = time.monotonic() + max(0, timeout_ms) / 1000
        last = self._row_removed_or_changed(page, row_signature=row_signature, row_selector=row_selector)
        while time.monotonic() < deadline:
            if last["changed"]:
                return last
            page.wait_for_timeout(150)
            last = self._row_removed_or_changed(page, row_signature=row_signature, row_selector=row_selector)
        return last

    def _current_row_signatures(self, page: Any, *, row_selector: str | None) -> set[str]:
        data_indices = self.table_handler.data_row_indices(page, row_selector=row_selector)
        if not data_indices and row_selector:
            row_selector = None
            data_indices = self.table_handler.data_row_indices(page)
        rows = self.table_handler.row_locator(page, selector=row_selector)
        signatures: set[str] = set()
        for index in data_indices:
            signature = self._row_signature(rows.nth(index), fallback=f"row-index:{index}")
            if signature:
                signatures.add(signature)
        return signatures

    def _remaining_unseen_row_count(self, page: Any, *, seen_signatures: set[str], row_selector: str | None) -> int:
        signatures = self._current_row_signatures(page, row_selector=row_selector)
        if not signatures:
            return 0
        return len([signature for signature in signatures if signature not in seen_signatures])

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

    def _entry_selectors(self, loop_policy: dict[str, Any]) -> list[str]:
        return list_setting(
            loop_policy.get("rowLinkSelectors"),
            loop_policy.get("row_link_selectors"),
            loop_policy.get("entrySelectors"),
            loop_policy.get("entry_selectors"),
            loop_policy.get("businessLinkSelectors"),
            loop_policy.get("business_link_selectors"),
        )

    def _click_strategies(self, loop_policy: dict[str, Any]) -> list[str]:
        strategies = list_setting(loop_policy.get("clickStrategies"), loop_policy.get("click_strategies"))
        return strategies or ["click", "dblclick", "js_click"]

    def _row_selector(self, loop_policy: dict[str, Any]) -> str | None:
        values = list_setting(
            loop_policy.get("tableRowSelector"),
            loop_policy.get("table_row_selector"),
            loop_policy.get("rowSelector"),
            loop_policy.get("row_selector"),
            loop_policy.get("dataRowSelector"),
            loop_policy.get("data_row_selector"),
        )
        return values[0] if values else None

    def _open_wait_ms(self, loop_policy: dict[str, Any]) -> int:
        return int_setting(loop_policy.get("openWaitMs"), loop_policy.get("open_wait_ms"), default=800, minimum=100, maximum=10_000)

    def _new_page_timeout_ms(self, loop_policy: dict[str, Any]) -> int:
        return int_setting(loop_policy.get("newPageTimeoutMs"), loop_policy.get("new_page_timeout_ms"), default=4_000, minimum=500, maximum=30_000)

    def _row_open_reached(
        self,
        page: Any,
        *,
        before_url: str,
        opened_new_page: bool,
        loop_policy: dict[str, Any],
    ) -> bool:
        if opened_new_page:
            return True
        if str(getattr(page, "url", "")) != before_url:
            return True
        if self.dialog_handler.dialog_visible(page, timeout_ms=300):
            return True
        for selector in self._open_success_selectors(loop_policy):
            try:
                locator = page.locator(selector)
                if self._locator_has_visible(locator, timeout_ms=300):
                    return True
            except PlaywrightError:
                continue
        for text in self._open_success_texts(loop_policy):
            try:
                locator = page.get_by_text(text, exact=False)
                if self._locator_has_visible(locator, timeout_ms=300):
                    return True
            except PlaywrightError:
                continue
        return False

    def _open_success_texts(self, loop_policy: dict[str, Any]) -> list[str]:
        values = list_setting(
            loop_policy.get("openSuccessTexts"),
            loop_policy.get("open_success_texts"),
            loop_policy.get("detailPageTexts"),
            loop_policy.get("detail_page_texts"),
        )
        return values or ["我的意见", "审批意见", "审核意见", "处理意见", "办理意见", "提交", "审批历史记录", "审批结果", "下一审批人", "下一步处理人", "意见写入方式"]

    def _open_success_selectors(self, loop_policy: dict[str, Any]) -> list[str]:
        values = list_setting(
            loop_policy.get("openSuccessSelectors"),
            loop_policy.get("open_success_selectors"),
            loop_policy.get("detailPageSelectors"),
            loop_policy.get("detail_page_selectors"),
        )
        return values or ["textarea", "[role='dialog']", "[aria-modal='true']", ".el-dialog", ".el-overlay:not([style*='display: none']) .el-dialog", ".el-drawer", ".ant-modal", ".ant-drawer"]

    def _apply_table_rule_config(self, loop_policy: dict[str, Any], rule_config: dict[str, Any]) -> dict[str, Any]:
        current = dict(loop_policy)
        match = rule_config.get("match") or {}
        action = rule_config.get("action") or {}
        success = rule_config.get("success") or {}
        fallback = rule_config.get("fallback") or {}
        defaults = {
            "rowEntryLabels": list_setting(action.get("rowEntryLabels"), action.get("entryLabels"), match.get("positiveActions")),
            "rowLinkSelectors": list_setting(action.get("rowLinkSelectors"), action.get("entrySelectors"), action.get("businessLinkSelectors")),
            "clickStrategies": list_setting(action.get("clickStrategies"), fallback.get("clickStrategies")),
            "tableRowSelector": list_setting(action.get("tableRowSelector"), action.get("rowSelector"), action.get("dataRowSelector")),
            "openSuccessTexts": list_setting(action.get("openSuccessTexts"), action.get("detailPageTexts"), success.get("texts"), success.get("pageSignals")),
            "openSuccessSelectors": list_setting(action.get("openSuccessSelectors"), action.get("detailPageSelectors"), success.get("selectors")),
            "openWaitMs": action.get("openWaitMs"),
            "newPageTimeoutMs": action.get("newPageTimeoutMs"),
            "continueOnRowFailure": self._first_config_value(action, fallback, key="continueOnRowFailure"),
            "stopAfterInitialRows": self._first_config_value(action, fallback, key="stopAfterInitialRows"),
            "followNewRows": self._first_config_value(action, fallback, key="followNewRows"),
            "afterRowComplete": action.get("afterRowComplete") or action.get("after_row_complete") or fallback.get("afterRowComplete"),
        }
        for key, value in defaults.items():
            if key in current or value in (None, "", [], {}):
                continue
            current[key] = value[0] if key.endswith("Selector") and isinstance(value, list) and len(value) == 1 else value
        if rule_config.get("rules"):
            current.setdefault("executableRuleHits", rule_config["rules"])
        return current

    @staticmethod
    def _first_config_value(*sources: dict[str, Any], key: str) -> Any:
        for source in sources:
            if isinstance(source, dict) and key in source:
                return source.get(key)
        return None

    def _stop_after_initial_rows(self, loop_policy: dict[str, Any]) -> bool:
        follow_new_rows = self._bool_setting(loop_policy, ["followNewRows", "follow_new_rows"], False)
        return self._bool_setting(
            loop_policy,
            ["stopAfterInitialRows", "stop_after_initial_rows", "stopAfterInitialBatch", "stop_after_initial_batch"],
            not follow_new_rows,
        )

    def _list_sync_policy(self, loop_policy: dict[str, Any]) -> dict[str, Any]:
        raw = loop_policy.get("afterRowComplete") or loop_policy.get("after_row_complete") or loop_policy.get("listSync") or loop_policy.get("list_sync") or {}
        if raw is False:
            return {"enabled": False}
        if not isinstance(raw, dict):
            raw = {}
        enabled = self._bool_setting(raw, ["enabled"], True)
        refresh_methods = list_setting(raw.get("refreshMethods"), raw.get("refresh_methods"))
        return {
            "enabled": enabled,
            "settle_ms": int_setting(raw.get("settleMs"), raw.get("settle_ms"), raw.get("waitAfterReturnMs"), raw.get("wait_after_return_ms"), default=self.DEFAULT_LIST_SYNC_SETTLE_MS, minimum=0, maximum=10_000),
            "wait_change_ms": int_setting(raw.get("waitForListChangeMs"), raw.get("wait_for_list_change_ms"), raw.get("waitRowChangeMs"), raw.get("wait_row_change_ms"), default=self.DEFAULT_LIST_SYNC_TIMEOUT_MS, minimum=0, maximum=30_000),
            "refresh_when_unchanged": self._bool_setting(raw, ["refreshListWhenUnchanged", "refresh_list_when_unchanged", "refreshWhenUnchanged", "refresh_when_unchanged"], False),
            "skip_signature_when_unchanged": self._bool_setting(raw, ["skipProcessedSignatureIfUnchanged", "skip_processed_signature_if_unchanged", "skipWhenUnchanged", "skip_when_unchanged"], True),
            "max_refresh_attempts": int_setting(raw.get("maxRefreshAttempts"), raw.get("max_refresh_attempts"), default=1, minimum=0, maximum=5),
            "wait_after_refresh_ms": int_setting(raw.get("waitAfterRefreshMs"), raw.get("wait_after_refresh_ms"), default=800, minimum=0, maximum=15_000),
            "refresh_methods": refresh_methods,
            "refresh_button_selectors": list_setting(raw.get("refreshButtonSelectors"), raw.get("refresh_button_selectors")),
            "refresh_button_texts": list_setting(raw.get("refreshButtonTexts"), raw.get("refresh_button_texts")),
            "query_button_texts": list_setting(raw.get("queryButtonTexts"), raw.get("query_button_texts")),
        }

    def _refresh_list_page(self, page: Any, policy: dict[str, Any]) -> str | None:
        methods = policy["refresh_methods"] or ["click_refresh_button", "repeat_query"]
        for method in methods:
            normalized = str(method)
            if normalized in {"click_refresh_button", "refresh_button"} and self._click_refresh_or_query_button(
                page,
                selectors=policy["refresh_button_selectors"],
                labels=policy["refresh_button_texts"] or ["刷新", "重新加载"],
            ):
                return normalized
            if normalized in {"repeat_query", "click_query_button"} and self._click_refresh_or_query_button(
                page,
                selectors=[],
                labels=policy["query_button_texts"] or ["查询", "搜索"],
            ):
                return normalized
            if normalized in {"reload_page", "page_reload"}:
                page.reload(wait_until="domcontentloaded")
                return normalized
        return None

    def _click_refresh_or_query_button(self, page: Any, *, selectors: list[str], labels: list[str]) -> bool:
        for selector in selectors:
            try:
                locator = page.locator(selector)
                if locator.count() > 0 and locator.first.is_visible(timeout=500) and locator.first.is_enabled(timeout=500):
                    locator.first.click()
                    return True
            except PlaywrightError:
                continue
        for label in labels:
            for locator in self._button_candidates_by_text(page, label):
                try:
                    if locator.count() > 0 and locator.first.is_visible(timeout=500) and locator.first.is_enabled(timeout=500):
                        locator.first.click()
                        return True
                except PlaywrightError:
                    continue
        return False

    def _button_candidates_by_text(self, page: Any, label: str) -> list[Any]:
        return [
            page.get_by_role("button", name=label, exact=True),
            page.get_by_role("button", name=label, exact=False),
        ]

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

    def click_row_entry(
        self,
        row: Any,
        *,
        labels: list[str] | None = None,
        entry_selectors: list[str] | None = None,
        candidate_timeout_ms: int | None = None,
        max_candidates: int | None = None,
        click_strategy: str = "click",
    ) -> str:
        timeout_ms = int(candidate_timeout_ms or self.DEFAULT_ROW_PROBE_TIMEOUT_MS)
        candidate_limit = int(max_candidates or self.DEFAULT_ROW_ENTRY_CANDIDATES)
        for selector in entry_selectors or []:
            if self._click_row_selector(row, selector, timeout_ms=timeout_ms, max_candidates=candidate_limit, click_strategy=click_strategy):
                return f"{click_strategy}:{selector}"
        for label in labels or self.todo_action_labels:
            if self.click_row_action_control(row, label, timeout_ms=timeout_ms, click_strategy=click_strategy):
                return f"{click_strategy}:label:{label}"
        for selector in ["a", "button", "[role='button']", ".ant-btn", ".el-button", "td a", "td button"]:
            try:
                candidate = row.locator(selector)
                for index in range(min(candidate.count(), candidate_limit)):
                    item = candidate.nth(index)
                    text = " ".join(item.inner_text(timeout=timeout_ms).split())
                    if any(negative in text for negative in self.negative_approval_labels):
                        continue
                    if item.is_visible(timeout=timeout_ms) and item.is_enabled(timeout=timeout_ms):
                        self._activate(item, click_strategy)
                        return f"{click_strategy}:selector:{selector}"
            except PlaywrightError:
                continue
        try:
            row.dblclick(timeout=max(500, timeout_ms * 2))
            return "double_click"
        except PlaywrightError as exc:
            raise RuntimeError("table_no_action_found: 当前数据行没有可点击入口。") from exc

    def _click_row_selector(
        self,
        row: Any,
        selector: str,
        *,
        timeout_ms: int,
        max_candidates: int,
        click_strategy: str,
    ) -> bool:
        try:
            candidate = row.locator(selector)
            for index in range(min(candidate.count(), max_candidates)):
                item = candidate.nth(index)
                text = " ".join(item.inner_text(timeout=timeout_ms).split())
                if any(negative in text for negative in self.negative_approval_labels):
                    continue
                if item.is_visible(timeout=timeout_ms) and item.is_enabled(timeout=timeout_ms):
                    self._activate(item, click_strategy)
                    return True
        except PlaywrightError:
            return False
        return False

    def click_row_action_control(
        self,
        row: Any,
        action_name: str,
        *,
        page: Any | None = None,
        timeout_ms: int = 500,
        click_strategy: str = "click",
    ) -> bool:
        if not action_name:
            return False
        if action_name in {"审批通过", "通过", "同意", "批准"}:
            labels = ["审批", "审核", "办理", "处理", "通过", "同意", "批准"]
        else:
            labels = [action_name]
        for label in labels:
            try:
                button = row.get_by_role("button", name=label, exact=True)
                if button.count() > 0 and button.first.is_visible(timeout=timeout_ms):
                    self._activate(button.first, click_strategy)
                    return True
                link = row.get_by_role("link", name=label, exact=True)
                if link.count() > 0 and link.first.is_visible(timeout=timeout_ms):
                    self._activate(link.first, click_strategy)
                    return True
                text = row.get_by_text(label, exact=True)
                if text.count() > 0 and text.first.is_visible(timeout=timeout_ms):
                    self._activate(text.first, click_strategy)
                    return True
            except PlaywrightError:
                continue
        if action_name not in {"更多", "..."} and page is not None:
            return self._click_more_action(page, row, action_name)
        return False

    def _activate(self, locator: Any, click_strategy: str) -> None:
        strategy = str(click_strategy or "click")
        if strategy in {"dblclick", "double_click"}:
            locator.dblclick()
            return
        if strategy in {"js_click", "javascript_click"}:
            locator.evaluate("(el) => el.click()")
            return
        locator.click()

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

    def _loop_guard(self, step: dict[str, Any], loop_policy: dict[str, Any]) -> dict[str, int]:
        return {
            "max_rows": self._int_setting(
                step,
                loop_policy,
                ["maxRows", "max_rows"],
                self.DEFAULT_MAX_ROWS,
                minimum=1,
                maximum=500,
            ),
            "loop_timeout_ms": self._int_setting(
                step,
                loop_policy,
                ["maxDurationMs", "max_duration_ms", "timeoutMs", "timeout_ms"],
                self.DEFAULT_LOOP_TIMEOUT_MS,
                minimum=5_000,
                maximum=900_000,
            ),
            "row_probe_timeout_ms": self._int_setting(
                step,
                loop_policy,
                ["rowProbeTimeoutMs", "row_probe_timeout_ms", "candidateTimeoutMs", "candidate_timeout_ms"],
                self.DEFAULT_ROW_PROBE_TIMEOUT_MS,
                minimum=50,
                maximum=2_000,
            ),
            "max_candidates": self._int_setting(
                step,
                loop_policy,
                ["maxRowActionCandidates", "max_row_action_candidates"],
                self.DEFAULT_ROW_ENTRY_CANDIDATES,
                minimum=1,
                maximum=20,
            ),
            "max_consecutive_failures": self._int_setting(
                step,
                loop_policy,
                ["maxConsecutiveFailures", "max_consecutive_failures"],
                self.DEFAULT_CONSECUTIVE_FAILURES,
                minimum=1,
                maximum=20,
            ),
        }

    @staticmethod
    def _int_setting(
        step: dict[str, Any],
        loop_policy: dict[str, Any],
        keys: list[str],
        default: int,
        *,
        minimum: int,
        maximum: int,
    ) -> int:
        for source in [step, loop_policy]:
            for key in keys:
                value = source.get(key)
                if value in (None, ""):
                    continue
                try:
                    parsed = int(float(str(value).strip()))
                except (TypeError, ValueError):
                    continue
                return max(minimum, min(parsed, maximum))
        return default

    @staticmethod
    def _bool_setting(source: dict[str, Any], keys: list[str], default: bool) -> bool:
        for key in keys:
            value = source.get(key)
            if isinstance(value, bool):
                return value
            if value in (None, ""):
                continue
            normalized = str(value).strip().lower()
            if normalized in {"1", "true", "yes", "y", "on", "是", "启用", "开启"}:
                return True
            if normalized in {"0", "false", "no", "n", "off", "否", "禁用", "关闭"}:
                return False
        return default

    def _locator_has_visible(self, locator: Any, *, timeout_ms: int, limit: int = 12) -> bool:
        try:
            count = min(locator.count(), limit)
        except PlaywrightError:
            return False
        for index in range(count):
            try:
                if locator.nth(index).is_visible(timeout=timeout_ms):
                    return True
            except PlaywrightError:
                continue
        return False

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return int((time.monotonic() - started) * 1000)

    @staticmethod
    def _loop_abort_payload(
        reason: str,
        message: str,
        *,
        processed: int,
        attempted: int,
        row_count: int,
        failures: list[dict[str, Any]],
        guard: dict[str, int],
        elapsed_ms: int,
    ) -> dict[str, Any]:
        return {
            "reason": reason,
            "message": message,
            "processed_rows": processed,
            "attempted_rows": attempted,
            "row_count": row_count,
            "failures": failures[:5],
            "guard": guard,
            "elapsed_ms": elapsed_ms,
            "suggestion": "请检查当前页面是否为目标列表、行内是否存在办理入口；必要时在规则库补充行入口选择器或待办打开规则。",
        }
