import time
from typing import Any

from playwright.sync_api import Error as PlaywrightError

from executor.aitp_executor.handlers.base import CommonOperationHandler, handler_outcome
from executor.aitp_executor.handlers.executable_rules import int_setting, list_setting, merged_rule_config
from executor.aitp_executor.runner.page_waiter import wait_for_page_ready


class ApprovalWorkflowError(RuntimeError):
    def __init__(self, message: str, *, failure_type: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.failure_type = failure_type
        self.details = details or {}


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
        resolution = self.resolve_rules(ctx, intent="approval_pass", rule_types=self.rule_types)
        ctx.step["abilityResolution"] = resolution
        self.emit_rule_hits(ctx, resolution)
        rule_config = merged_rule_config(ctx, rule_type="approval_workflow")
        labels = self._approval_entry_labels(rule_config)
        negative_labels = self._negative_labels(rule_config)
        self.emit(ctx, "progress", "approval_workflow", "正在执行审批通过。")
        surface = self._approval_surface(page, rule_config=rule_config)
        clicked = False
        before_pages = self._open_pages(page)
        if surface is None:
            clicked = self._click_first(
                page,
                labels,
                exclude=negative_labels,
                selectors=self._approval_entry_selectors(rule_config),
            )
            wait_for_page_ready(page)
            surface = self._approval_surface_after_entry_click(
                page,
                before_pages=before_pages,
                rule_config=rule_config,
                execution_context=execution_context or {},
            )
            if surface is None and clicked:
                direct_result = self._direct_result_after_entry_click(page, rule_config=rule_config)
                if direct_result.get("submitted"):
                    return handler_outcome("approval_pass", "审批通过", 0.82, {"status": "submitted", **direct_result})
        if not clicked and surface is None:
            raise RuntimeError("approval_entry_not_found: 未找到审批、审核、办理或通过入口。")
        completion = self._complete_dialog(surface or page, decision="通过", step=step, dsl=dsl or {}, rule_config=rule_config)
        if not completion.get("submitted"):
            raise RuntimeError(str(completion.get("error") or "approval_submit_failed: 未找到可用的审批提交按钮。"))
        wait_for_page_ready(page)
        return handler_outcome("approval_pass", "审批通过", 0.86, {"status": "submitted", **completion})

    def approval_reject(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        resolution = self.resolve_rules(ctx, intent="approval_reject", rule_types=self.rule_types)
        ctx.step["abilityResolution"] = resolution
        self.emit_rule_hits(ctx, resolution)
        rule_config = merged_rule_config(ctx, rule_type="approval_workflow")
        self.emit(ctx, "progress", "approval_workflow", "正在执行审批驳回。")
        surface = self._approval_surface(page, rule_config=rule_config)
        clicked = False
        before_pages = self._open_pages(page)
        if surface is None:
            clicked = self._click_first(page, self.reject_labels + self._approval_entry_labels(rule_config), exclude=self.view_flow_labels)
            wait_for_page_ready(page)
            surface = self._approval_surface_after_entry_click(
                page,
                before_pages=before_pages,
                rule_config=rule_config,
                execution_context=execution_context or {},
            )
            if surface is None and clicked:
                direct_result = self._direct_result_after_entry_click(page, rule_config=rule_config)
                if direct_result.get("submitted"):
                    return handler_outcome("approval_reject", "审批驳回", 0.8, {"status": "submitted", **direct_result})
        if not clicked and surface is None:
            raise RuntimeError("approval_entry_not_found: 未找到驳回或审批入口。")
        completion = self._complete_dialog(surface or page, decision="驳回", step=step, dsl=dsl or {}, rule_config=rule_config)
        if not completion.get("submitted"):
            raise RuntimeError(str(completion.get("error") or "approval_submit_failed: 未找到可用的审批提交按钮。"))
        wait_for_page_ready(page)
        return handler_outcome("approval_reject", "审批驳回", 0.84, {"status": "submitted", **completion})

    def view_flow(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        resolution = self.resolve_rules(ctx, intent="view_flow", rule_types=self.rule_types)
        ctx.step["abilityResolution"] = resolution
        self.emit_rule_hits(ctx, resolution)
        self.emit(ctx, "progress", "approval_workflow", "正在查看审批流程或审批记录。")
        if not self._click_first(page, self.view_flow_labels):
            raise RuntimeError("approval_entry_not_found: 未找到查看审批流程入口。")
        wait_for_page_ready(page)
        return handler_outcome("approval_flow_view", "审批流程", 0.88, "approval flow opened")

    def _click_first(self, page: Any, labels: list[str], *, exclude: list[str] | None = None, selectors: list[str] | None = None) -> bool:
        exclude = exclude or []
        for selector in selectors or []:
            try:
                locator = page.locator(selector)
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

    def _complete_dialog(
        self,
        page: Any,
        *,
        decision: str,
        step: dict[str, Any] | None = None,
        dsl: dict[str, Any] | None = None,
        rule_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            try:
                radio = page.get_by_role("radio", name=decision, exact=True)
                if radio.count() > 0:
                    radio.first.check()
            except PlaywrightError:
                pass
            fill_value = self._opinion_text(step or {}, dsl or {}, decision=decision, rule_config=rule_config or {})
            filled = self._fill_approval_inputs(page, decision=decision, only_invalid=False, fill_value=fill_value, rule_config=rule_config or {})
            required_ready = self.wait_required_approval_fields_ready(page, rule_config=rule_config or {})
            filled += required_ready.get("filled_fields") or []
            initial_validation = self._visible_validation_messages(page, rule_config=rule_config or {})
            if initial_validation:
                filled += self._fill_approval_inputs(page, decision=decision, only_invalid=True, fill_value=fill_value, rule_config=rule_config or {})
                retry_ready = self._recover_required_fields_after_validation(page, initial_validation, rule_config=rule_config or {})
                filled += retry_ready.get("filled_fields") or []
            clicked_label = self._click_submit_button(page, decision=decision, rule_config=rule_config or {})
            if not clicked_label:
                validation = self._visible_validation_messages(page, rule_config=rule_config or {})
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
            confirmed_label = self._confirm_after_submit(page, rule_config=rule_config or {})
            if confirmed_label:
                page.wait_for_timeout(800)
            validation = self._visible_validation_messages(page, rule_config=rule_config or {})
            if validation:
                recovery = self._recover_required_fields_after_validation(page, validation, rule_config=rule_config or {})
                retry_filled = self._fill_approval_inputs(page, decision=decision, only_invalid=True, fill_value=fill_value, rule_config=rule_config or {})
                filled += (recovery.get("filled_fields") or []) + retry_filled
                if retry_filled or recovery.get("changed"):
                    clicked_label = self._click_submit_button(page, decision=decision, rule_config=rule_config or {}) or clicked_label
                    page.wait_for_timeout(800)
                    confirmed_label = self._confirm_after_submit(page, rule_config=rule_config or {}) or confirmed_label
                    if confirmed_label:
                        page.wait_for_timeout(800)
                    validation = self._visible_validation_messages(page, rule_config=rule_config or {})
            if validation:
                return {
                    "submitted": False,
                    "submit_button": clicked_label,
                    "confirm_button": confirmed_label,
                    "filled_fields": filled,
                    "validation_messages": validation,
                    "error": _validation_error(validation),
                }
            submission_result = self._wait_submission_result(page, rule_config=rule_config or {})
            if not submission_result.get("submitted"):
                return {
                    "submitted": False,
                    "submit_button": clicked_label,
                    "confirm_button": confirmed_label,
                    "filled_fields": filled,
                    "submission_result": submission_result,
                    "validation_messages": submission_result.get("messages") or [],
                    "error": submission_result.get("error") or "approval_submit_uncertain: 已点击提交，但未检测到审批成功证据。",
                }
            return {
                "submitted": True,
                "submit_button": clicked_label,
                "confirm_button": confirmed_label,
                "filled_fields": filled,
                "submission_result": submission_result,
            }
        except ApprovalWorkflowError:
            raise
        except Exception as exc:
            raise ApprovalWorkflowError(
                "approval_workflow_internal_error: 审批页面已打开，但自动填写或提交过程中出现程序异常。"
                "系统已保留当前页面截图，请优先检查审批意见、下一步处理人和提交按钮是否完整。"
                f"内部错误：{exc}",
                failure_type="approval_workflow_internal_error",
                details={"decision": decision, "step": step or {}, "rootCause": type(exc).__name__},
            ) from exc

    def _click_submit_button(self, page: Any, *, decision: str, rule_config: dict[str, Any] | None = None) -> str | None:
        labels = list_setting((rule_config or {}).get("action", {}).get("submitLabels"), (rule_config or {}).get("action", {}).get("confirmLabels"))
        labels = labels or [decision, "审批", "审核", "确定", "提交", "确认", "保存", "同意", "通过", "批准", "办理"]
        seen: set[str] = set()
        default_selectors = [
            "#btnAudit",
            "a#btnAudit",
            "a.easyui-linkbutton:has-text('提交')",
            "a.l-btn:has-text('提交')",
            "a:has-text('提交')",
        ]
        selectors = list(dict.fromkeys(list_setting((rule_config or {}).get("action", {}).get("submitSelectors")) + default_selectors))
        for selector in selectors:
            try:
                locator = page.locator(selector)
                for index in range(min(locator.count(), 8)):
                    item = locator.nth(index)
                    text = " ".join(item.inner_text(timeout=500).split())
                    if any(negative in text for negative in self.negative_labels):
                        continue
                    if item.is_visible(timeout=500) and item.is_enabled(timeout=500):
                        item.click()
                        return text or selector
            except PlaywrightError:
                continue
        for label in labels:
            if label in seen:
                continue
            seen.add(label)
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
                        if any(negative in text for negative in self.negative_labels):
                            continue
                        if item.is_visible(timeout=500) and item.is_enabled(timeout=500):
                            item.click()
                            return label
                except PlaywrightError:
                    continue
        return None

    def _fill_approval_inputs(
        self,
        page: Any,
        *,
        decision: str,
        only_invalid: bool,
        fill_value: str,
        rule_config: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        filled: list[dict[str, Any]] = []
        action = (rule_config or {}).get("action") or {}
        for selector in list_setting(action.get("opinionSelectors"), action.get("fieldSelectors")):
            try:
                locator = page.locator(selector)
                if self._fill_first_empty(locator, fill_value):
                    filled.append({"label": selector, "strategy": "rule_selector"})
                    if not only_invalid:
                        return filled
            except PlaywrightError:
                continue
        labels = list_setting(action.get("opinionLabels"), action.get("fieldLabels"))
        labels = labels or ["我的意见", "审批意见", "审核意见", "处理意见", "办理意见", "意见"]
        for label in labels:
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
        textareas = observation.textareas if observation is not None and isinstance(getattr(observation, "textareas", None), list) else []
        inputs = observation.inputs if observation is not None and isinstance(getattr(observation, "inputs", None), list) else []
        controls = textareas + inputs
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

    def wait_required_approval_fields_ready(self, page: Any, *, rule_config: dict[str, Any] | None = None) -> dict[str, Any]:
        policy = self._required_approval_policy(rule_config or {})
        if not policy["enabled"]:
            return {"status": "disabled", "changed": False, "filled_fields": []}

        section_visible = self._any_text_visible(page, policy["section_labels"])
        loading_visible = bool(self._visible_loading_messages(page, policy["loading_texts"]))
        if not section_visible and not loading_visible:
            return {"status": "not_applicable", "changed": False, "filled_fields": []}

        deadline = time.monotonic() + policy["timeout_ms"] / 1000
        last_loading: list[str] = []
        while time.monotonic() < deadline:
            last_loading = self._visible_loading_messages(page, policy["loading_texts"])
            if not last_loading:
                break
            page.wait_for_timeout(policy["poll_ms"])
        if policy["settle_ms"] > 0:
            page.wait_for_timeout(policy["settle_ms"])

        selected = self._ensure_required_approval_candidates(page, policy)
        return {
            "status": "ready" if not last_loading else "timeout",
            "changed": bool(selected),
            "filled_fields": selected,
            "loading_messages": last_loading,
        }

    def _recover_required_fields_after_validation(
        self,
        page: Any,
        validation_messages: list[str],
        *,
        rule_config: dict[str, Any],
    ) -> dict[str, Any]:
        policy = self._required_approval_policy(rule_config)
        if not policy.get("enabled", True) or not policy.get("retry_after_validation", True):
            return {"changed": False, "filled_fields": []}
        joined = " ".join(validation_messages)
        if not any(text in joined for text in policy["validation_texts"]):
            return {"changed": False, "filled_fields": []}
        return self.wait_required_approval_fields_ready(page, rule_config=rule_config)

    def _required_approval_policy(self, rule_config: dict[str, Any]) -> dict[str, Any]:
        action = rule_config.get("action") or {}
        raw = (
            action.get("requiredApprovalFields")
            or action.get("required_approval_fields")
            or action.get("asyncRequiredFields")
            or action.get("async_required_fields")
            or {}
        )
        if raw is False:
            return {"enabled": False}
        if not isinstance(raw, dict):
            raw = {}
        default_section_labels = [
            "下一步审批人",
            "下一审批人",
            "下一环节审批人",
            "下一步处理人",
            "下一环节处理人",
            "下一个审批人",
            "下一个处理人",
            "下一步办理人",
            "办理人",
            "审批人",
            "处理人",
            "发送对象",
            "送相关人员办理",
        ]
        configured_section_labels = list_setting(
            raw.get("sectionLabels"),
            raw.get("section_labels"),
            raw.get("fieldLabels"),
            raw.get("field_labels"),
        )
        return {
            "enabled": self._bool_setting(raw, ["enabled"], True),
            "section_labels": list(dict.fromkeys(configured_section_labels + default_section_labels)),
            "loading_texts": list_setting(raw.get("loadingTexts"), raw.get("loading_texts"))
            or ["正在处理", "请稍待", "请稍候", "加载中", "正在加载", "处理中", "请等待"],
            "validation_texts": list_setting(raw.get("validationTexts"), raw.get("validation_texts"))
            or ["请填写", "请选择", "不能为空", "必填", "请检查必填项"],
            "timeout_ms": int_setting(raw.get("timeoutMs"), raw.get("timeout_ms"), raw.get("waitMs"), raw.get("wait_ms"), default=15_000, minimum=0, maximum=60_000),
            "poll_ms": int_setting(raw.get("pollMs"), raw.get("poll_ms"), default=250, minimum=50, maximum=2_000),
            "settle_ms": int_setting(raw.get("settleMs"), raw.get("settle_ms"), default=300, minimum=0, maximum=5_000),
            "auto_select_first": self._bool_setting(raw, ["autoSelectFirstCandidate", "auto_select_first_candidate", "autoSelectFirst", "auto_select_first"], True),
            "retry_after_validation": self._bool_setting(raw, ["retryAfterValidation", "retry_after_validation"], True),
        }

    def _ensure_required_approval_candidates(self, page: Any, policy: dict[str, Any]) -> list[dict[str, Any]]:
        if not policy["auto_select_first"]:
            return []
        try:
            result = page.evaluate(
                """(policy) => {
                    const sectionLabels = policy.section_labels || [];
                    const visible = (el) => {
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
                    };
                    const textOf = (el) => ((el.innerText || el.textContent || "") + "").replace(/\\s+/g, " ").trim();
                    const labels = Array.from(document.querySelectorAll("body *"))
                        .filter(visible)
                        .filter((el) => sectionLabels.some((label) => textOf(el).includes(label)))
                        .slice(0, 8);
                    const scopes = [];
                    for (const label of labels) {
                        const base = label.closest("tr,.el-form-item,.ant-form-item,.form-item,.form-group,.layui-form-item,.row,.form-row,section,fieldset") || label.parentElement;
                        for (const candidate of [label, label.nextElementSibling, base, base && base.nextElementSibling, base && base.parentElement]) {
                            if (candidate && !scopes.includes(candidate)) scopes.push(candidate);
                        }
                    }
                    const isEnabled = (el) => !el.disabled && el.getAttribute("aria-disabled") !== "true";
                    const selected = [];
                    for (const scope of scopes) {
                        if (!visible(scope)) continue;
                        const checked = Array.from(scope.querySelectorAll("input[type='checkbox'],input[type='radio']")).some((el) => visible(el) && el.checked);
                        const selectFilled = Array.from(scope.querySelectorAll("select")).some((el) => visible(el) && isEnabled(el) && String(el.value || "").trim());
                        const textFilled = Array.from(scope.querySelectorAll("input:not([type='hidden']):not([type='checkbox']):not([type='radio']),textarea")).some((el) => visible(el) && isEnabled(el) && !el.readOnly && String(el.value || "").trim());
                        if (checked || selectFilled || textFilled) continue;
                        const checkbox = Array.from(scope.querySelectorAll("input[type='checkbox'],input[type='radio']"))
                            .find((el) => visible(el) && isEnabled(el) && !el.checked);
                        if (checkbox) {
                            checkbox.click();
                            selected.push({ label: textOf(scope).slice(0, 80) || "下一步审批人", strategy: "required_section_first_choice" });
                            continue;
                        }
                        const option = Array.from(scope.querySelectorAll("[role='option'],.el-select-dropdown__item,.ant-select-item-option,li,button,a"))
                            .find((el) => visible(el) && isEnabled(el) && textOf(el) && !/新增|删除|刷新|查询|搜索|关闭|取消/.test(textOf(el)));
                        if (option) {
                            option.click();
                            selected.push({ label: textOf(option).slice(0, 80) || "候选处理人", strategy: "required_section_option" });
                        }
                    }
                    return selected;
                }""",
                {"section_labels": policy["section_labels"]},
            )
            if isinstance(result, list):
                return [item for item in result if isinstance(item, dict)]
        except Exception:
            return []
        return []

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

    def _approval_surface(self, page: Any, *, rule_config: dict[str, Any] | None = None) -> Any | None:
        for surface in self._page_surfaces(page):
            if self._approval_form_ready_on_surface(surface, rule_config=rule_config):
                return surface
        return None

    def _approval_surface_after_entry_click(
        self,
        page: Any,
        *,
        before_pages: list[Any],
        rule_config: dict[str, Any],
        execution_context: dict[str, Any],
    ) -> Any | None:
        action = rule_config.get("action") or {}
        wait_ms = int_setting(
            action.get("formOpenWaitMs"),
            action.get("form_open_wait_ms"),
            action.get("entryOpenWaitMs"),
            action.get("entry_open_wait_ms"),
            default=5_000,
            minimum=0,
            maximum=30_000,
        )
        before_ids = {id(item) for item in before_pages}
        deadline = time.monotonic() + wait_ms / 1000
        while time.monotonic() <= deadline:
            for candidate in self._open_pages(page):
                if id(candidate) in before_ids:
                    continue
                try:
                    candidate.bring_to_front()
                except Exception:
                    pass
                surface = self._approval_surface(candidate, rule_config=rule_config)
                if surface is not None:
                    self._set_active_page(execution_context, candidate, {"source": "approval_entry_new_page"})
                    return surface
            surface = self._approval_surface(page, rule_config=rule_config)
            if surface is not None:
                return surface
            page.wait_for_timeout(200)
        return None

    def _direct_result_after_entry_click(self, page: Any, *, rule_config: dict[str, Any]) -> dict[str, Any]:
        self._confirm_after_submit(page, rule_config=rule_config)
        result = self._wait_submission_result(page, rule_config=rule_config)
        if result.get("status") == "success_message":
            return {"submitted": True, "submission_result": result, "submit_button": "entry_direct"}
        return {"submitted": False, "submission_result": result}

    def _page_surfaces(self, page: Any) -> list[Any]:
        surfaces = [page]
        for frame in getattr(page, "frames", []) or []:
            try:
                if frame.is_detached():
                    continue
            except Exception:
                pass
            if frame is not page:
                surfaces.append(frame)
        return surfaces

    def _approval_form_ready(self, page: Any, *, rule_config: dict[str, Any] | None = None) -> bool:
        return self._approval_surface(page, rule_config=rule_config) is not None

    def _approval_form_ready_on_surface(self, page: Any, *, rule_config: dict[str, Any] | None = None) -> bool:
        action = (rule_config or {}).get("action") or {}
        success = (rule_config or {}).get("success") or {}
        for selector in list_setting(action.get("formReadySelectors"), success.get("selectors")):
            try:
                locator = page.locator(selector)
                if self._locator_has_visible(locator, timeout_ms=300):
                    return True
            except PlaywrightError:
                continue
        if self._has_approval_input_control(page) or self._has_approval_submit_control(page):
            return True

        strong_texts = [
            "流程审批",
            "我的意见",
            "审批意见",
            "审核意见",
            "处理意见",
            "办理意见",
            "意见写入方式",
            "是否同意",
            "下一审批人",
            "下一步审批人",
            "下一步处理人",
            "下一环节审批人",
            "下一环节处理人",
        ]
        weak_texts = ["审批信息", "审批结果", "审批历史记录", "审批历史"]
        configured_texts = list_setting(action.get("formReadyTexts"), success.get("texts"), success.get("pageSignals"))
        for text in list(dict.fromkeys(configured_texts + strong_texts + weak_texts)):
            try:
                locator = page.get_by_text(text, exact=False)
                if not self._locator_has_visible(locator, timeout_ms=300):
                    continue
                if text in weak_texts:
                    continue
                if self._has_approval_submit_control(page) or self._has_approval_input_control(page):
                    return True
            except PlaywrightError:
                continue
        try:
            for label in ["我的意见", "审批意见", "审核意见", "处理意见", "办理意见", "意见"]:
                locator = page.get_by_label(label, exact=True)
                if self._locator_has_visible(locator, timeout_ms=300):
                    return True
        except PlaywrightError:
            pass
        try:
            if self._locator_has_visible(page.locator("textarea"), timeout_ms=300):
                return True
        except PlaywrightError:
            pass
        return False

    def _has_approval_input_control(self, page: Any) -> bool:
        selectors = [
            "textarea",
            ".el-textarea__inner",
            "input[name*='opinion' i]",
            "input[id*='opinion' i]",
            "textarea[name*='opinion' i]",
            "textarea[id*='opinion' i]",
        ]
        for selector in selectors:
            try:
                if self._locator_has_visible(page.locator(selector), timeout_ms=250):
                    return True
            except PlaywrightError:
                continue
        for label in ["我的意见", "审批意见", "审核意见", "处理意见", "办理意见", "意见"]:
            try:
                if self._locator_has_visible(page.get_by_label(label, exact=True), timeout_ms=250):
                    return True
            except PlaywrightError:
                continue
        return False

    def _has_approval_submit_control(self, page: Any) -> bool:
        selectors = [
            "#btnAudit",
            "a#btnAudit",
            "a.easyui-linkbutton:has-text('提交')",
            "a.l-btn:has-text('提交')",
            "form button:has-text('提交')",
            "form a:has-text('提交')",
            ".el-form button:has-text('提交')",
            ".el-dialog:has(textarea) button:has-text('提交')",
            "main:has(textarea) button:has-text('提交')",
        ]
        for selector in selectors:
            try:
                if self._locator_has_visible(page.locator(selector), timeout_ms=250):
                    return True
            except PlaywrightError:
                continue
        return False

    def _opinion_text(self, step: dict[str, Any], dsl: dict[str, Any], *, decision: str, rule_config: dict[str, Any] | None = None) -> str:
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
        action = (rule_config or {}).get("action") or {}
        default_opinion = action.get("defaultOpinion") or action.get("defaultText")
        if default_opinion not in (None, ""):
            return str(default_opinion)
        return "同意，自动化测试审批通过。" if decision == "通过" else "不同意，自动化测试审批驳回。"

    def _approval_entry_labels(self, rule_config: dict[str, Any]) -> list[str]:
        action = rule_config.get("action") or {}
        match = rule_config.get("match") or {}
        labels = list_setting(action.get("entryLabels"), action.get("executeLabels"), match.get("positiveActions"))
        return labels or self.execute_labels

    def _approval_entry_selectors(self, rule_config: dict[str, Any]) -> list[str]:
        action = rule_config.get("action") or {}
        return list_setting(action.get("entrySelectors"), action.get("executeSelectors"))

    def _negative_labels(self, rule_config: dict[str, Any]) -> list[str]:
        action = rule_config.get("action") or {}
        match = rule_config.get("match") or {}
        labels = list_setting(action.get("negativeLabels"), match.get("negativeActions"))
        return labels or self.negative_labels

    def _confirm_after_submit(self, page: Any, *, rule_config: dict[str, Any] | None = None) -> str | None:
        action = (rule_config or {}).get("action") or {}
        result = action.get("submissionResult") or action.get("submission_result") or {}
        configured = list_setting(
            action.get("confirmDialogSelectors"),
            action.get("confirm_dialog_selectors"),
            result.get("confirmDialogSelectors") if isinstance(result, dict) else None,
            result.get("confirm_dialog_selectors") if isinstance(result, dict) else None,
        )
        defaults = [
            "[role='dialog']",
            ".el-message-box",
            ".ant-modal",
            ".modal",
            ".layui-layer",
            ".ui-dialog",
            ".messager-window",
            ".panel.window",
            ".window:has(.messager-body)",
            ".window:has(.messager-button)",
        ]
        dialog_selectors = ", ".join(list(dict.fromkeys(configured + defaults)))
        try:
            dialogs = page.locator(dialog_selectors)
            visible_dialogs = [dialogs.nth(index) for index in range(min(dialogs.count(), 8)) if dialogs.nth(index).is_visible(timeout=300)]
        except PlaywrightError:
            visible_dialogs = []
        labels = list_setting(
            action.get("confirmLabels"),
            action.get("confirm_labels"),
            result.get("confirmLabels") if isinstance(result, dict) else None,
            result.get("confirm_labels") if isinstance(result, dict) else None,
        ) or ["确定", "确认", "是", "继续", "OK"]
        for label in labels:
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
        for label in labels:
            try:
                button = page.get_by_role("button", name=label, exact=True)
                for index in range(min(button.count(), 6)):
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

    def _visible_validation_messages(self, page: Any, *, rule_config: dict[str, Any] | None = None) -> list[str]:
        messages: list[str] = []
        try:
            values = page.evaluate(
                """(selectors) => {
                    const isVisible = (el) => {
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
                    };
                    return Array.from(document.querySelectorAll(selectors.join(",")))
                        .filter(isVisible)
                        .map((el) => (el.innerText || el.textContent || "").trim())
                        .filter(Boolean)
                        .filter((text) => /请|必填|不能为空|错误|失败|异常|无效|不能|未|error|fail|invalid/i.test(text))
                        .slice(0, 8);
                }""",
                self._validation_message_selectors(rule_config or {}),
            )
            if isinstance(values, list):
                messages.extend(str(item) for item in values if str(item).strip())
        except Exception:
            pass
        return list(dict.fromkeys(message for message in messages if message))

    def _validation_message_selectors(self, rule_config: dict[str, Any]) -> list[str]:
        action = rule_config.get("action") or {}
        required = action.get("requiredApprovalFields") or action.get("required_approval_fields") or {}
        configured = list_setting(
            action.get("validationMessageSelectors"),
            action.get("validation_message_selectors"),
            required.get("validationMessageSelectors") if isinstance(required, dict) else None,
            required.get("validation_message_selectors") if isinstance(required, dict) else None,
        )
        defaults = [
            ".el-message",
            ".el-notification",
            ".ant-message",
            ".ant-notification",
            ".el-form-item__error",
            ".ant-form-item-explain-error",
            ".invalid-feedback",
            "[role='alert']",
            ".toast",
            ".toast-error",
            ".error",
            ".error-message",
            ".message.error",
            ".layui-layer-content",
            ".messager-body",
            ".validatebox-tip",
            ".tooltip-content",
        ]
        return list(dict.fromkeys(configured + defaults))

    def _wait_submission_result(self, page: Any, *, rule_config: dict[str, Any] | None = None) -> dict[str, Any]:
        policy = self._submission_result_policy(rule_config or {})
        deadline = time.monotonic() + policy["wait_ms"] / 1000
        last_validation: list[str] = []
        last_failure: list[str] = []
        last_success: list[str] = []
        while time.monotonic() < deadline:
            last_failure = self._visible_messages_matching(page, policy["failure_texts"], selectors=policy["message_selectors"])
            if last_failure:
                return {
                    "submitted": False,
                    "status": "failure_message",
                    "messages": last_failure,
                    "error": _validation_error(last_failure),
                }
            last_success = self._visible_messages_matching(page, policy["success_texts"], selectors=policy["message_selectors"])
            if last_success:
                confirmed = self._confirm_after_submit(page, rule_config=rule_config or {})
                return {"submitted": True, "status": "success_message", "messages": last_success, "confirm_button": confirmed}
            last_validation = self._visible_validation_messages(page, rule_config=rule_config or {})
            if last_validation:
                return {
                    "submitted": False,
                    "status": "validation_message",
                    "messages": last_validation,
                    "error": _validation_error(last_validation),
                }
            if policy["require_form_closed"] and not self._approval_submit_surface_visible(page, rule_config=rule_config or {}):
                return {"submitted": True, "status": "form_closed", "messages": []}
            page.wait_for_timeout(policy["poll_ms"])

        if policy["require_form_closed"] and self._approval_submit_surface_visible(page, rule_config=rule_config or {}):
            return {
                "submitted": False,
                "status": "submit_surface_still_visible",
                "messages": last_failure or last_validation or last_success,
                "error": "approval_submit_uncertain: 已点击提交，但审批表单仍停留在页面，未检测到成功提示或页面关闭。请检查是否需要确认弹窗、下一步处理人或业务校验。",
            }
        return {"submitted": True, "status": "wait_timeout_without_error", "messages": []}

    def _submission_result_policy(self, rule_config: dict[str, Any]) -> dict[str, Any]:
        action = rule_config.get("action") or {}
        success = rule_config.get("success") or {}
        raw = action.get("submissionResult") or action.get("submission_result") or {}
        if raw is False:
            raw = {"requireFormClosed": False, "waitMs": 0}
        if not isinstance(raw, dict):
            raw = {}
        success_texts = list_setting(raw.get("successTexts"), raw.get("success_texts"))
        success_texts += list_setting(success.get("texts"), success.get("pageSignals"), success.get("criteria"))
        if not success_texts:
            success_texts = ["提交成功", "审批成功", "审核成功", "办理成功", "处理成功", "操作成功", "保存成功", "已提交", "已审批"]
        failure_texts = list_setting(raw.get("failureTexts"), raw.get("failure_texts"))
        if not failure_texts:
            failure_texts = ["接口错误", "保存失败", "提交失败", "审批失败", "审核失败", "办理失败", "操作失败", "服务异常", "系统异常"]
        message_selectors = list_setting(raw.get("messageSelectors"), raw.get("message_selectors"))
        if not message_selectors:
            message_selectors = [
                ".el-message",
                ".el-notification",
                ".ant-message",
                ".ant-notification",
                "[role='alert']",
                ".toast",
                ".message",
                ".el-message-box",
                ".ant-modal",
                ".modal",
                ".layui-layer",
                ".ui-dialog",
                ".messager-window",
                ".messager-body",
                ".panel.window",
                ".window:has(.messager-body)",
            ]
        return {
            "wait_ms": int_setting(raw.get("waitMs"), raw.get("wait_ms"), default=10_000, minimum=0, maximum=60_000),
            "poll_ms": int_setting(raw.get("pollMs"), raw.get("poll_ms"), default=500, minimum=100, maximum=2_000),
            "success_texts": list(dict.fromkeys(success_texts)),
            "failure_texts": list(dict.fromkeys(failure_texts)),
            "message_selectors": list(dict.fromkeys(message_selectors)),
            "require_form_closed": self._bool_setting(raw, ["requireFormClosed", "require_form_closed"], True),
        }

    def _visible_messages_matching(self, page: Any, texts: list[str], *, selectors: list[str] | None = None) -> list[str]:
        if not texts:
            return []
        matched: list[str] = []
        try:
            values = page.evaluate(
                """(payload) => {
                    const { texts, selectors } = payload;
                    const visible = (el) => {
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
                    };
                    return Array.from(document.querySelectorAll(selectors.join(",")))
                        .filter(visible)
                        .map((el) => ((el.innerText || el.textContent || "") + "").replace(/\\s+/g, " ").trim())
                        .filter(Boolean)
                        .filter((text) => texts.some((item) => text.includes(item)))
                        .slice(0, 8);
                }""",
                {"texts": texts, "selectors": selectors or self._submission_result_policy({})["message_selectors"]},
            )
            if isinstance(values, list):
                matched.extend(str(item) for item in values if str(item).strip())
        except Exception:
            pass
        for text in texts:
            try:
                locator = page.get_by_text(text, exact=False)
                if self._locator_has_visible(locator, timeout_ms=200):
                    matched.append(text)
            except PlaywrightError:
                continue
        return list(dict.fromkeys(item for item in matched if item))

    def _approval_submit_surface_visible(self, page: Any, *, rule_config: dict[str, Any] | None = None) -> bool:
        return self._approval_surface(page, rule_config=rule_config or {}) is not None

    def _open_pages(self, page: Any) -> list[Any]:
        try:
            return [item for item in page.context.pages if not item.is_closed()]
        except Exception:
            return [page]

    def _set_active_page(self, execution_context: dict[str, Any], page: Any, metadata: dict[str, Any] | None = None) -> None:
        setter = execution_context.get("set_active_page")
        if callable(setter):
            setter(page, metadata or {})

    def _visible_loading_messages(self, page: Any, texts: list[str]) -> list[str]:
        if not texts:
            return []
        try:
            values = page.evaluate(
                """(texts) => {
                    const visible = (el) => {
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
                    };
                    const result = [];
                    for (const el of Array.from(document.querySelectorAll("body *"))) {
                        if (!visible(el)) continue;
                        const text = ((el.innerText || el.textContent || "") + "").replace(/\\s+/g, " ").trim();
                        if (!text) continue;
                        if (texts.some((item) => text.includes(item))) result.push(text.slice(0, 120));
                        if (result.length >= 5) break;
                    }
                    return result;
                }""",
                texts,
            )
            if isinstance(values, list):
                return list(dict.fromkeys(str(item) for item in values if str(item).strip()))
        except Exception:
            return []
        return []

    def _any_text_visible(self, page: Any, texts: list[str]) -> bool:
        for text in texts:
            try:
                locator = page.get_by_text(text, exact=False)
                if self._locator_has_visible(locator, timeout_ms=300):
                    return True
            except PlaywrightError:
                continue
        return False

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


def _validation_error(messages: list[str]) -> str:
    message = "；".join(messages[:3]) if messages else "页面存在必填项或业务校验错误"
    return f"approval_validation_failed: 审批未提交，页面提示“{message}”。请补充必填项或检查业务校验后再提交。"
