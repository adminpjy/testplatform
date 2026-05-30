from dataclasses import asdict, dataclass, field
from typing import Any

from executor.aitp_executor.observer.auth_state_detector import AuthStateDetector, AuthStateResult
from executor.aitp_executor.observer.page_observer import PageObserver


@dataclass
class GuardResult:
    allowed: bool
    blockedBy: str | None = None
    failureType: str | None = None
    rootCause: str | None = None
    reason: str = ""
    evidence: list[str] = field(default_factory=list)
    authState: str | None = None
    remainingRetries: int | None = None
    authResult: dict[str, Any] | None = None
    requiresHumanAction: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProtectedStepGuard:
    def __init__(
        self,
        *,
        detector: AuthStateDetector | None = None,
        observer: PageObserver | None = None,
    ) -> None:
        self.detector = detector or AuthStateDetector()
        self.observer = observer or PageObserver()

    def check_before_step(
        self,
        step: dict[str, Any],
        page: Any,
        observation: Any | None = None,
        execution_context: dict[str, Any] | None = None,
    ) -> GuardResult:
        if not step_requires_auth(step):
            return GuardResult(allowed=True, reason="step does not require authenticated business page")

        page_observation = observation
        if page_observation is None:
            try:
                page_observation = self.observer.observe(page)
            except Exception:
                page_observation = None
        auth_result = self.detector.detect_auth_state(page, page_observation, execution_context)

        if auth_result.authState == "logged_in":
            return GuardResult(
                allowed=True,
                reason="authenticated business page is visible",
                evidence=auth_result.evidence,
                authState=auth_result.authState,
                remainingRetries=auth_result.remainingRetries,
                authResult=auth_result.as_dict(),
            )

        if auth_result.authState == "login_failed":
            return _blocked(
                auth_result,
                failure_type="protected_step_blocked_by_login_failure",
                root_cause="login_failed",
                reason="当前页面仍是登录页，且检测到登录失败提示，受保护业务步骤已阻断。",
            )

        if auth_result.authState == "login_page":
            return _blocked(
                auth_result,
                failure_type="auth_state_not_logged_in",
                root_cause="auth_state_not_logged_in",
                reason="当前页面仍是登录页，受保护业务步骤已阻断。",
            )

        if auth_result.authState == "login_requires_manual_action":
            if auth_result.failureType == "login_captcha_required":
                return _blocked(
                    auth_result,
                    failure_type="protected_step_blocked_by_auth_challenge",
                    root_cause="login_captcha_required",
                    reason="登录流程出现验证码、OTP、短信验证码或二次认证，受保护业务步骤已阻断。",
                )
            return _blocked(
                auth_result,
                failure_type="login_requires_manual_action",
                root_cause="login_requires_manual_action",
                reason="登录后需要人工处理，受保护业务步骤已阻断。",
            )

        return GuardResult(
            allowed=True,
            reason="auth state is not blocking this step",
            evidence=auth_result.evidence,
            authState=auth_result.authState,
            remainingRetries=auth_result.remainingRetries,
            authResult=auth_result.as_dict(),
        )


AUTH_REQUIRED_ACTIONS = {
    "navigate_path",
    "navigate_menu",
    "query_table",
    "query_table_count",
    "open_table_row",
    "open_row_link_or_detail",
    "process_table_rows",
    "for_each_table_row",
    "click_table_row_action",
    "create_record",
    "update_record",
    "delete_record",
    "approval_pass",
    "approval_reject",
    "view_detail",
    "auto_fill_form",
    "fill_form",
    "select",
    "upload_file",
    "wait_for_dialog",
    "close_dialog_by_common_controls",
    "summary_assert",
    "assert_result",
}

AUTH_REQUIRED_INTENTS = {
    "enter_page",
    "navigate_path",
    "query_list",
    "open_table_row",
    "process_table_rows",
    "click_table_row_action",
    "create_record",
    "update_record",
    "delete_record",
    "view_detail",
    "view_flow",
    "approval_pass",
    "approval_reject",
    "approval_flow_view",
    "fill_form",
    "fill_field",
    "select_dropdown",
    "select_date",
    "select_date_range",
    "select_org",
    "select_person",
    "select_tree_node",
    "select_from_dialog",
    "upload_file",
    "assert_result",
}


def step_requires_auth(step: dict[str, Any]) -> bool:
    action = str(step.get("action") or "")
    if action == "open_url":
        return False
    if _is_login_flow_step(step):
        return False

    preconditions = step.get("preconditions")
    if isinstance(preconditions, dict) and preconditions.get("authState") == "logged_in":
        return True
    if isinstance(preconditions, list) and "auth_state_logged_in" in [str(item) for item in preconditions]:
        return True

    target = str(step.get("target") or "")
    intent = str(step.get("intent") or (step.get("operationIntent") or {}).get("intent") or "")
    if action in AUTH_REQUIRED_ACTIONS:
        return True
    if action == "business_goal":
        return intent in AUTH_REQUIRED_INTENTS or bool(intent)
    return intent in AUTH_REQUIRED_INTENTS


def _is_login_flow_step(step: dict[str, Any]) -> bool:
    action = str(step.get("action") or "")
    target = str(step.get("target") or "")
    intent = str(step.get("intent") or (step.get("operationIntent") or {}).get("intent") or "")
    description = str(step.get("description") or step.get("readableDescription") or step.get("name") or step.get("step_name") or "")
    if _is_login_transition_wait(action, target, description):
        return True
    if _is_login_target(f"{target} {description}", intent):
        return action in {"business_goal", "click", "confirm_dialog", "submit", "fill_form", "auto_fill_form", "wait"}
    return False


def _is_login_transition_wait(action: str, target: str, description: str) -> bool:
    if action != "wait":
        return False
    compact = f"{target}{description}".replace(" ", "")
    return any(token in compact for token in ["登录后页面稳定", "登陆后页面稳定", "登录后", "登陆后", "登录完成", "登陆完成"])


def _is_login_target(target: str, intent: str) -> bool:
    lower = target.strip().lower().replace(" ", "")
    if any(token in target for token in ["退出登录", "注销登录", "登出"]):
        return False
    return (
        "登录" in target
        or "登陆" in target
        or "login" in lower
        or "signin" in lower
        or "sign-in" in lower
        or intent in {"login", "login_system", "username_password_login"}
    )


def _blocked(auth_result: AuthStateResult, *, failure_type: str, root_cause: str, reason: str) -> GuardResult:
    return GuardResult(
        allowed=False,
        blockedBy=auth_result.authState,
        failureType=failure_type,
        rootCause=root_cause,
        reason=reason,
        evidence=auth_result.evidence,
        authState=auth_result.authState,
        remainingRetries=auth_result.remainingRetries,
        authResult=auth_result.as_dict(),
        requiresHumanAction=auth_result.requiresHumanAction,
    )
