import os
from typing import Any

from executor.aitp_executor.goal.goal_success_verifier import GoalSuccessVerifier
from executor.aitp_executor.goal.login_form_resolver import LoginFormResolver
from executor.aitp_executor.goal.recovery_policy import RecoveryPolicy
from executor.aitp_executor.locator.business_intent_normalizer import BusinessIntentNormalizer
from executor.aitp_executor.locator.element_locator import ElementLocator, LocatorResult
from executor.aitp_executor.runner.page_waiter import wait_for_page_ready


class GoalExecutor:
    def __init__(
        self,
        *,
        locator: ElementLocator | None = None,
        verifier: GoalSuccessVerifier | None = None,
        recovery_policy: RecoveryPolicy | None = None,
        login_resolver: LoginFormResolver | None = None,
    ) -> None:
        self.locator = locator or ElementLocator()
        self.normalizer = BusinessIntentNormalizer()
        self.verifier = verifier or GoalSuccessVerifier()
        self.recovery_policy = recovery_policy or RecoveryPolicy()
        self.login_resolver = login_resolver or LoginFormResolver()

    def execute(self, page: Any, *, target: str, step: dict[str, Any]) -> dict[str, Any]:
        intent = self.normalizer.normalize(action="business_goal", target=target)

        if intent.name == "login_system":
            return self._login(page, step)
        if intent.name == "enter_todo_list":
            return self._click_goal(page, "navigate_menu", "工作台/我的待办", step, intent.name)
        if intent.name == "approval_pass":
            return self._approval_pass(page, step)
        if intent.name == "approval_reject":
            return self._approval_reject(page, step)
        if intent.name == "approval_flow_view":
            return self._click_goal(page, "click", "查看审批流程", step, intent.name)
        if intent.name == "query_record":
            return self._click_goal(page, "click", "查询", step, intent.name)
        if intent.name == "create_record":
            return self._click_goal(page, "click", "新增", step, intent.name)
        if intent.name == "update_record":
            return self._click_goal(page, "click", "修改", step, intent.name)
        if intent.name == "delete_record":
            return self._click_goal(page, "click", "删除", step, intent.name)
        if intent.name == "open_detail":
            return self._click_goal(page, "click", "详情", step, intent.name)

        return self._click_goal(page, "click", target, step, intent.name)

    def _login(self, page: Any, step: dict[str, Any]) -> dict[str, Any]:
        credentials = dict(step.get("credentials") or {})
        username = str(step.get("username") or credentials.get("username") or os.getenv("REAL_MIS_USERNAME") or "admin")
        password = str(step.get("password") or credentials.get("password") or os.getenv("REAL_MIS_PASSWORD") or "123456")
        wait_for_page_ready(page)
        form = self.login_resolver.resolve(page)
        if form.username_locator is None or form.password_locator is None:
            raise RuntimeError(
                "login_form_fields_not_found:"
                + form.reason
                + ". The page may use iframe, delayed SSO widgets, or non-standard inputs. "
                + "Captured candidates: "
                + str(form.candidates[:6])
            )
        form.username_locator.fill(username)
        form.password_locator.fill(password)
        if form.submit_locator is not None:
            form.submit_locator.click()
        else:
            form.password_locator.press("Enter")
        page.wait_for_timeout(600)
        wait_for_page_ready(page)
        return _outcome(
            LocatorResult(
                form.submit_locator or form.password_locator,
                form.strategy,
                "login_form",
                form.confidence,
                form.reason,
                candidates=form.candidates,
            ),
            verified=True,
            verify_reason="login_submitted",
        )

    def _approval_pass(self, page: Any, step: dict[str, Any]) -> dict[str, Any]:
        wait_for_page_ready(page)
        approval = self.locator.locate(page, action="click", target="审批通过", step=step)
        self._require_locator(approval).click()
        wait_for_page_ready(page)
        self._complete_approval_dialog(page, decision="通过")
        wait_for_page_ready(page)
        verified, verify_reason = self.verifier.verify(page, "approval_pass")
        return _outcome(approval, verified=verified, verify_reason=verify_reason)

    def _approval_reject(self, page: Any, step: dict[str, Any]) -> dict[str, Any]:
        wait_for_page_ready(page)
        approval = self.locator.locate(page, action="click", target="审批驳回", step=step)
        self._require_locator(approval).click()
        wait_for_page_ready(page)
        self._complete_approval_dialog(page, decision="驳回")
        wait_for_page_ready(page)
        return _outcome(approval, verified=True, verify_reason="approval_reject_submitted")

    def _click_goal(self, page: Any, action: str, target: str, step: dict[str, Any], intent_name: str) -> dict[str, Any]:
        wait_for_page_ready(page)
        result = self.locator.locate(page, action=action, target=target, step=step)
        self._require_locator(result).click()
        page.wait_for_timeout(500)
        wait_for_page_ready(page)
        verified, verify_reason = self.verifier.verify(page, intent_name)
        return _outcome(result, verified=verified, verify_reason=verify_reason)

    def _complete_approval_dialog(self, page: Any, *, decision: str) -> None:
        if page.get_by_role("radio", name=decision, exact=True).count() > 0:
            page.get_by_role("radio", name=decision, exact=True).check()
        if page.get_by_label("审批意见", exact=True).count() > 0:
            page.get_by_label("审批意见", exact=True).fill("同意，自动化测试审批意见。")
        if page.get_by_role("button", name=decision, exact=True).count() > 0:
            page.get_by_role("button", name=decision, exact=True).click()
            return
        for button_name in ["确定", "提交"]:
            button = page.get_by_role("button", name=button_name, exact=True)
            if button.count() > 0:
                button.click()
                return

    @staticmethod
    def _require_locator(result: LocatorResult) -> Any:
        if result.locator is None:
            raise RuntimeError(result.fallback_reason or result.reason)
        return result.locator


def _outcome(result: LocatorResult, *, verified: bool, verify_reason: str) -> dict[str, Any]:
    return {
        "locator_strategy": result.strategy,
        "element_ref": result.element_ref,
        "confidence": result.confidence,
        "reason": f"{result.reason};{verify_reason}",
        "needs_vision_fallback": result.needs_vision_fallback,
        "fallback_reason": result.fallback_reason,
        "candidates": result.candidates,
        "verified": verified,
    }
