from typing import Any

from playwright.sync_api import Error as PlaywrightError

from executor.aitp_executor.handlers.base import CommonOperationHandler, handler_outcome
from executor.aitp_executor.runner.page_waiter import wait_for_page_ready


class ApprovalWorkflowHandler(CommonOperationHandler):
    handler_name = "approval_workflow_handler"
    rule_types = ["approval_workflow"]
    default_intent = "approval_pass"
    execute_labels = ["审批", "审核", "办理", "处理", "通过", "同意", "批准"]
    reject_labels = ["驳回", "退回", "拒绝", "不通过"]
    view_flow_labels = ["查看审批流程", "审批流程", "流程图", "审批记录"]
    negative_labels = ["查看审批流程", "审批记录", "流程图", "历史", "详情"]

    def approval_pass(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        self.emit_rule_hits(ctx, self.resolve_rules(ctx, intent="approval_pass", rule_types=self.rule_types))
        self.emit(ctx, "progress", "approval_workflow", "正在执行审批通过。")
        clicked = self._click_first(page, self.execute_labels, exclude=self.negative_labels)
        if not clicked:
            raise RuntimeError("approval_entry_not_found: 未找到审批、审核、办理或通过入口。")
        wait_for_page_ready(page)
        if not self._complete_dialog(page, decision="通过"):
            raise RuntimeError("approval_submit_failed: 未找到可用的审批提交按钮。")
        wait_for_page_ready(page)
        return handler_outcome("approval_pass", "审批通过", 0.86, "approval pass submitted")

    def approval_reject(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        self.emit_rule_hits(ctx, self.resolve_rules(ctx, intent="approval_reject", rule_types=self.rule_types))
        self.emit(ctx, "progress", "approval_workflow", "正在执行审批驳回。")
        clicked = self._click_first(page, self.reject_labels + self.execute_labels, exclude=self.view_flow_labels)
        if not clicked:
            raise RuntimeError("approval_entry_not_found: 未找到驳回或审批入口。")
        wait_for_page_ready(page)
        if not self._complete_dialog(page, decision="驳回"):
            raise RuntimeError("approval_submit_failed: 未找到可用的审批提交按钮。")
        wait_for_page_ready(page)
        return handler_outcome("approval_reject", "审批驳回", 0.84, "approval reject submitted")

    def view_flow(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        self.emit_rule_hits(ctx, self.resolve_rules(ctx, intent="view_flow", rule_types=self.rule_types))
        self.emit(ctx, "progress", "approval_workflow", "正在查看审批流程或审批记录。")
        if not self._click_first(page, self.view_flow_labels):
            raise RuntimeError("approval_entry_not_found: 未找到查看审批流程入口。")
        wait_for_page_ready(page)
        return handler_outcome("approval_flow_view", "审批流程", 0.88, "approval flow opened")

    def _click_first(self, page: Any, labels: list[str], *, exclude: list[str] | None = None) -> bool:
        exclude = exclude or []
        for label in labels:
            for finder in [
                lambda value: page.get_by_role("button", name=value, exact=True),
                lambda value: page.get_by_role("link", name=value, exact=True),
                lambda value: page.get_by_text(value, exact=True),
            ]:
                try:
                    locator = finder(label)
                    for index in range(min(locator.count(), 8)):
                        item = locator.nth(index)
                        text = " ".join(item.inner_text(timeout=500).split())
                        if any(negative in text for negative in exclude):
                            continue
                        if item.is_visible(timeout=500) and item.is_enabled(timeout=500):
                            item.click()
                            return True
                except PlaywrightError:
                    continue
        return False

    def _complete_dialog(self, page: Any, *, decision: str) -> bool:
        try:
            radio = page.get_by_role("radio", name=decision, exact=True)
            if radio.count() > 0:
                radio.first.check()
        except PlaywrightError:
            pass
        for label in ["审批意见", "审核意见", "处理意见", "意见"]:
            try:
                opinion = page.get_by_label(label, exact=True)
                if opinion.count() > 0 and opinion.first.is_visible(timeout=500):
                    opinion.first.fill("自动化测试审批通过" if decision == "通过" else "自动化测试审批驳回")
                    break
            except PlaywrightError:
                continue
        for name in [decision, "确定", "提交", "确认"]:
            try:
                button = page.get_by_role("button", name=name, exact=True)
                if button.count() > 0 and button.first.is_visible(timeout=500):
                    button.first.click()
                    return True
            except PlaywrightError:
                continue
        return False
