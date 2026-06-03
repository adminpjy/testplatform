from typing import Any

from executor.aitp_executor.goal.goal_success_verifier import GoalSuccessVerifier
from executor.aitp_executor.goal.login_form_resolver import LoginFormResolver
from executor.aitp_executor.goal.login_goal_executor import LoginGoalExecutor
from executor.aitp_executor.goal.login_result_verifier import LoginResultVerifier
from executor.aitp_executor.goal.menu_path_navigator import MenuPathNavigator
from executor.aitp_executor.goal.recovery_policy import RecoveryPolicy
from executor.aitp_executor.handlers.approval_workflow_handler import ApprovalWorkflowHandler
from executor.aitp_executor.handlers.date_picker_handler import DatePickerHandler
from executor.aitp_executor.handlers.detail_navigation_handler import DetailNavigationHandler
from executor.aitp_executor.handlers.dropdown_handler import DropdownHandler
from executor.aitp_executor.handlers.form_fill_handler import FormFillHandler
from executor.aitp_executor.handlers.navigation_handler import NavigationHandler
from executor.aitp_executor.handlers.org_selector_handler import OrgSelectorHandler
from executor.aitp_executor.handlers.person_selector_handler import PersonSelectorHandler
from executor.aitp_executor.handlers.query_handler import QueryHandler
from executor.aitp_executor.handlers.table_handler import TableHandler
from executor.aitp_executor.handlers.table_row_action_handler import TableRowActionHandler
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
        login_verifier: LoginResultVerifier | None = None,
        menu_path_navigator: MenuPathNavigator | None = None,
    ) -> None:
        self.locator = locator or ElementLocator()
        self.normalizer = BusinessIntentNormalizer()
        self.verifier = verifier or GoalSuccessVerifier()
        self.recovery_policy = recovery_policy or RecoveryPolicy()
        self.login_resolver = login_resolver or LoginFormResolver()
        self.login_verifier = login_verifier or LoginResultVerifier()
        self.login_goal_executor = LoginGoalExecutor(login_resolver=self.login_resolver, login_verifier=self.login_verifier)
        self.menu_path_navigator = menu_path_navigator or MenuPathNavigator()
        self.table_handler = TableHandler(observer=self.locator.observer)
        self.navigation_handler = NavigationHandler(locator=self.locator, menu_path_navigator=self.menu_path_navigator)
        self.query_handler = QueryHandler(locator=self.locator, table_handler=self.table_handler)
        self.table_row_action_handler = TableRowActionHandler(table_handler=self.table_handler)
        self.form_fill_handler = FormFillHandler(locator=self.locator)
        self.dropdown_handler = DropdownHandler(locator=self.locator)
        self.date_picker_handler = DatePickerHandler(locator=self.locator)
        self.org_selector_handler = OrgSelectorHandler(locator=self.locator)
        self.person_selector_handler = PersonSelectorHandler()
        self.detail_navigation_handler = DetailNavigationHandler()
        self.approval_workflow_handler = ApprovalWorkflowHandler()

    def execute(
        self,
        page: Any,
        *,
        target: str,
        step: dict[str, Any],
        dsl: dict[str, Any] | None = None,
        execution_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        dsl = dsl or {}
        intent = self.normalizer.normalize(action="business_goal", target=target)
        classified_intent = str((step.get("operationIntent") or {}).get("intent") or "")

        if classified_intent == "navigate_path" or intent.goal_type == "navigation_path":
            nav_step = dict(step)
            if intent.path_segments and not nav_step.get("pathSegments"):
                nav_step["pathSegments"] = intent.path_segments
            return self.navigation_handler.execute(page, step=nav_step, dsl=dsl, execution_context=execution_context)
        if intent.name == "login_system":
            return self._login(page, step, execution_context=execution_context)
        if classified_intent == "query_list":
            return self.query_handler.execute(page, step={**step, "target": target or "查询"}, dsl=dsl, execution_context=execution_context)
        if classified_intent in {"open_table_row", "view_detail"}:
            return self.detail_navigation_handler.open_detail(page, step={**step, "target": target or "详情"}, dsl=dsl, execution_context=execution_context)
        if classified_intent == "process_table_rows":
            return self.table_row_action_handler.process_rows(page, step={**step, "target": target}, dsl=dsl, execution_context=execution_context)
        if classified_intent == "click_table_row_action":
            return self.table_row_action_handler.click_row_action(page, step={**step, "target": target}, dsl=dsl, execution_context=execution_context)
        if classified_intent == "fill_form":
            return self.form_fill_handler.fill_form(page, step=step, dsl=dsl, execution_context=execution_context)
        if classified_intent == "select_dropdown":
            return self.dropdown_handler.select(page, step={**step, "target": target}, dsl=dsl, execution_context=execution_context)
        if classified_intent in {"select_date", "select_date_range"}:
            return self.date_picker_handler.select_date(page, step={**step, "target": target}, dsl=dsl, execution_context=execution_context)
        if classified_intent == "select_org":
            return self.org_selector_handler.select(page, step={**step, "target": target}, dsl=dsl, execution_context=execution_context)
        if classified_intent == "select_person":
            return self.person_selector_handler.select(page, step={**step, "target": target}, dsl=dsl, execution_context=execution_context)
        if classified_intent == "approval_pass":
            return self.approval_workflow_handler.approval_pass(page, step=step, dsl=dsl, execution_context=execution_context)
        if classified_intent == "approval_reject":
            return self.approval_workflow_handler.approval_reject(page, step=step, dsl=dsl, execution_context=execution_context)
        if classified_intent == "view_flow":
            return self.approval_workflow_handler.view_flow(page, step=step, dsl=dsl, execution_context=execution_context)
        if intent.name == "enter_todo_list":
            return self.navigation_handler.execute(
                page,
                step={**step, "target": "工作台/我的待办", "pathSegments": ["工作台", "我的待办"]},
                dsl=dsl,
                execution_context=execution_context,
            )
        if intent.name == "approval_pass":
            return self.approval_workflow_handler.approval_pass(page, step=step, dsl=dsl, execution_context=execution_context)
        if intent.name == "approval_reject":
            return self.approval_workflow_handler.approval_reject(page, step=step, dsl=dsl, execution_context=execution_context)
        if intent.name == "approval_flow_view":
            return self.approval_workflow_handler.view_flow(page, step=step, dsl=dsl, execution_context=execution_context)
        if intent.name == "query_record":
            return self.query_handler.execute(page, step={**step, "target": "查询"}, dsl=dsl, execution_context=execution_context)
        if intent.name == "create_record":
            return self._click_goal(page, "click", "新增", step, intent.name)
        if intent.name == "update_record":
            return self._click_goal(page, "click", "修改", step, intent.name)
        if intent.name == "delete_record":
            return self._click_goal(page, "click", "删除", step, intent.name)
        if intent.name == "open_detail":
            return self.detail_navigation_handler.open_detail(page, step={**step, "target": "详情"}, dsl=dsl, execution_context=execution_context)

        return self._click_goal(page, "click", target, step, intent.name)

    def _login(self, page: Any, step: dict[str, Any], *, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.login_goal_executor.execute_login_goal(page, step, execution_context)

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
