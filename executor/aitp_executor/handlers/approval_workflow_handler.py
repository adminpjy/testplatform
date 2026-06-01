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
        clicked = False
        if not self._approval_form_ready(page):
            clicked = self._click_first(page, self.execute_labels, exclude=self.negative_labels)
        if not clicked and not self._approval_form_ready(page):
            raise RuntimeError("approval_entry_not_found: 未找到审批、审核、办理或通过入口。")
        wait_for_page_ready(page)
        completion = self._complete_dialog(page, decision="通过", step=step, dsl=dsl or {})
        if not completion.get("submitted"):
            raise RuntimeError(str(completion.get("error") or "approval_submit_failed: 未找到可用的审批提交按钮。"))
        wait_for_page_ready(page)
        return handler_outcome("approval_pass", "审批通过", 0.86, {"status": "submitted", **completion})

    def approval_reject(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        self.emit_rule_hits(ctx, self.resolve_rules(ctx, intent="approval_reject", rule_types=self.rule_types))
        self.emit(ctx, "progress", "approval_workflow", "正在执行审批驳回。")
        clicked = False
        if not self._approval_form_ready(page):
            clicked = self._click_first(page, self.reject_labels + self.execute_labels, exclude=self.view_flow_labels)
        if not clicked and not self._approval_form_ready(page):
            raise RuntimeError("approval_entry_not_found: 未找到驳回或审批入口。")
        wait_for_page_ready(page)
        completion = self._complete_dialog(page, decision="驳回", step=step, dsl=dsl or {})
        if not completion.get("submitted"):
            raise RuntimeError(str(completion.get("error") or "approval_submit_failed: 未找到可用的审批提交按钮。"))
        wait_for_page_ready(page)
        return handler_outcome("approval_reject", "审批驳回", 0.84, {"status": "submitted", **completion})

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

    def _complete_dialog(self, page: Any, *, decision: str, step: dict[str, Any] | None = None, dsl: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            radio = page.get_by_role("radio", name=decision, exact=True)
            if radio.count() > 0:
                radio.first.check()
        except PlaywrightError:
            pass
        fill_value = self._opinion_text(step or {}, dsl or {}, decision=decision)
        filled = self._fill_approval_inputs(page, decision=decision, only_invalid=False, fill_value=fill_value)
        initial_validation = self._visible_validation_messages(page)
        if initial_validation:
            filled += self._fill_approval_inputs(page, decision=decision, only_invalid=True, fill_value=fill_value)
        clicked_label = self._click_submit_button(page, decision=decision)
        if not clicked_label:
            validation = self._visible_validation_messages(page)
            if validation:
                return {
                    "submitted": False,
                    "filled_fields": filled,
                    "validation_messages": validation,
                    "error": _validation_error(validation),
                }
            return {
                "submitted": False,
                "filled_fields": filled,
                "error": "approval_submit_failed: 未找到可用的审批提交按钮。",
            }
        page.wait_for_timeout(800)
        confirmed_label = self._confirm_after_submit(page)
        if confirmed_label:
            page.wait_for_timeout(800)
        validation = self._visible_validation_messages(page)
        if validation:
            retry_filled = self._fill_approval_inputs(page, decision=decision, only_invalid=True, fill_value=fill_value)
            filled += retry_filled
            if retry_filled:
                clicked_label = self._click_submit_button(page, decision=decision) or clicked_label
                page.wait_for_timeout(800)
                confirmed_label = self._confirm_after_submit(page) or confirmed_label
                if confirmed_label:
                    page.wait_for_timeout(800)
                validation = self._visible_validation_messages(page)
        if validation:
            return {
                "submitted": False,
                "submit_button": clicked_label,
                "confirm_button": confirmed_label,
                "filled_fields": filled,
                "validation_messages": validation,
                "error": _validation_error(validation),
            }
        return {"submitted": True, "submit_button": clicked_label, "confirm_button": confirmed_label, "filled_fields": filled}

    def _click_submit_button(self, page: Any, *, decision: str) -> str | None:
        labels = [decision, "审批", "审核", "确定", "提交", "确认", "保存", "同意", "通过", "批准", "办理"]
        seen: set[str] = set()
        for label in labels:
            if label in seen:
                continue
            seen.add(label)
            try:
                button = page.get_by_role("button", name=label, exact=True)
                for index in range(min(button.count(), 8)):
                    item = button.nth(index)
                    text = " ".join(item.inner_text(timeout=500).split())
                    if any(negative in text for negative in self.negative_labels):
                        continue
                    if item.is_visible(timeout=500) and item.is_enabled(timeout=500):
                        item.click()
                        return label
            except PlaywrightError:
                continue
        return None

    def _fill_approval_inputs(self, page: Any, *, decision: str, only_invalid: bool, fill_value: str) -> list[dict[str, Any]]:
        filled: list[dict[str, Any]] = []
        for label in ["我的意见", "审批意见", "审核意见", "处理意见", "办理意见", "意见"]:
            try:
                opinion = page.get_by_label(label, exact=True)
                if self._fill_first_empty(opinion, fill_value):
                    filled.append({"label": label, "strategy": "label"})
                    if not only_invalid:
                        return filled
            except PlaywrightError:
                continue
        try:
            observation = self.locator_observation(page)
        except Exception:
            observation = None
        controls = (observation.textareas + observation.inputs) if observation is not None else []
        textarea_count = len([item for item in controls if item.get("controlType") == "textarea"])
        for control in controls:
            if not control.get("visible") or not control.get("enabled") or control.get("readonly"):
                continue
            selector = str(control.get("selector") or "")
            if not selector:
                continue
            locator = page.locator(selector)
            if only_invalid:
                if not (control.get("validationErrors") or control.get("required") or self._control_is_invalid(locator)):
                    continue
            elif not self._is_opinion_like_control(control, textarea_count=textarea_count):
                continue
            if self._fill_first_empty(locator, fill_value):
                filled.append(
                    {
                        "label": control.get("label") or control.get("text") or control.get("placeholder") or "未标识输入框",
                        "strategy": "observed_control",
                        "elementRef": control.get("elementRef"),
                    }
                )
        return filled

    def locator_observation(self, page: Any) -> Any:
        from executor.aitp_executor.observer.page_observer import PageObserver

        return PageObserver().observe(page)

    def _is_opinion_like_control(self, control: dict[str, Any], *, textarea_count: int) -> bool:
        text = " ".join(
            str(item or "")
            for item in [
                control.get("text"),
                control.get("label"),
                control.get("placeholder"),
                control.get("ariaLabel"),
                control.get("title"),
                *(control.get("nearbyText") or []),
            ]
        )
        if any(token in text for token in ["我的意见", "审批意见", "审核意见", "处理意见", "办理意见", "意见"]):
            return True
        if control.get("required"):
            return True
        return control.get("controlType") == "textarea" and textarea_count <= 3 and any(token in text for token in ["请输入", "内容"])

    def _fill_first_empty(self, locator: Any, value: str) -> bool:
        try:
            for index in range(min(locator.count(), 8)):
                item = locator.nth(index)
                if not item.is_visible(timeout=500) or not item.is_enabled(timeout=500):
                    continue
                try:
                    current = item.input_value(timeout=300)
                except PlaywrightError:
                    current = ""
                if str(current or "").strip():
                    continue
                item.fill(value)
                return True
        except PlaywrightError:
            return False
        return False

    def _approval_form_ready(self, page: Any) -> bool:
        try:
            for label in ["我的意见", "审批意见", "审核意见", "处理意见", "办理意见", "意见"]:
                locator = page.get_by_label(label, exact=True)
                if locator.count() > 0 and locator.first.is_visible(timeout=300):
                    return True
        except PlaywrightError:
            pass
        try:
            if page.locator("textarea").count() > 0 and page.locator("textarea").first.is_visible(timeout=300):
                return True
        except PlaywrightError:
            pass
        return False

    def _opinion_text(self, step: dict[str, Any], dsl: dict[str, Any], *, decision: str) -> str:
        for key in ["value", "opinion", "opinionText", "approvalOpinion", "comment", "commentText"]:
            value = step.get(key)
            if value not in (None, ""):
                return str(value)
        for mapping in [step.get("formData"), step.get("testData"), dsl.get("testData")]:
            if not isinstance(mapping, dict):
                continue
            for key in ["我的意见", "审批意见", "审核意见", "处理意见", "办理意见", "意见", "opinion", "comment"]:
                value = mapping.get(key)
                if value not in (None, ""):
                    return str(value)
        return "同意，自动化测试审批通过。" if decision == "通过" else "不同意，自动化测试审批驳回。"

    def _confirm_after_submit(self, page: Any) -> str | None:
        dialog_selectors = "[role='dialog'], .el-message-box, .ant-modal, .modal, .layui-layer, .ui-dialog"
        try:
            dialogs = page.locator(dialog_selectors)
            visible_dialogs = [dialogs.nth(index) for index in range(min(dialogs.count(), 4)) if dialogs.nth(index).is_visible(timeout=300)]
        except PlaywrightError:
            visible_dialogs = []
        if not visible_dialogs:
            return None
        for label in ["确定", "确认", "是", "继续"]:
            try:
                for dialog in visible_dialogs:
                    button = dialog.get_by_role("button", name=label, exact=True)
                    for index in range(min(button.count(), 4)):
                        item = button.nth(index)
                        if item.is_visible(timeout=300) and item.is_enabled(timeout=300):
                            item.click()
                            return label
            except PlaywrightError:
                continue
        return None

    def _control_is_invalid(self, locator: Any) -> bool:
        try:
            return bool(
                locator.first.evaluate(
                    """(el) => {
                        const container = el.closest(".el-form-item,.ant-form-item,.form-item,.form-group,td,div");
                        const text = container ? (container.innerText || "") : "";
                        const cls = [el.className, container && container.className].join(" ");
                        return el.getAttribute("aria-invalid") === "true"
                            || /is-error|has-error|error|invalid/.test(cls)
                            || /必填|不能为空|请检查/.test(text);
                    }"""
                )
            )
        except PlaywrightError:
            return False

    def _visible_validation_messages(self, page: Any) -> list[str]:
        messages: list[str] = []
        try:
            values = page.evaluate(
                """() => {
                    const selectors = [
                        ".el-message", ".el-notification", ".ant-message", ".ant-notification",
                        ".el-form-item__error", ".ant-form-item-explain-error", ".invalid-feedback",
                        "[role='alert']", ".toast", ".error", ".message"
                    ];
                    const isVisible = (el) => {
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
                    };
                    return Array.from(document.querySelectorAll(selectors.join(",")))
                        .filter(isVisible)
                        .map((el) => (el.innerText || el.textContent || "").trim())
                        .filter(Boolean)
                        .slice(0, 8);
                }"""
            )
            messages.extend(str(item) for item in values if str(item).strip())
        except PlaywrightError:
            pass
        for text in ["请检查必填项", "必填", "不能为空", "请选择", "请填写"]:
            try:
                locator = page.get_by_text(text, exact=False)
                if locator.count() > 0 and locator.first.is_visible(timeout=300):
                    messages.append(text)
            except PlaywrightError:
                continue
        return list(dict.fromkeys(message for message in messages if message))


def _validation_error(messages: list[str]) -> str:
    message = "；".join(messages[:3]) if messages else "页面存在必填项或业务校验错误"
    return f"approval_validation_failed: 审批未提交，页面提示“{message}”。请补充必填项或检查业务校验后再提交。"
