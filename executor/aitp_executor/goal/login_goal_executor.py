import os
from dataclasses import asdict, dataclass, field
from typing import Any

from executor.aitp_executor.goal.login_form_resolver import LoginFormResolver
from executor.aitp_executor.goal.login_result_verifier import LoginResultVerifier
from executor.aitp_executor.locator.element_locator import LocatorResult
from executor.aitp_executor.runner.page_waiter import wait_for_page_ready


@dataclass
class LoginGoalResult:
    status: str
    authState: str
    failureType: str | None = None
    evidence: list[str] = field(default_factory=list)
    remainingRetries: int | None = None
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class LoginGoalExecutor:
    def __init__(
        self,
        *,
        login_resolver: LoginFormResolver | None = None,
        login_verifier: LoginResultVerifier | None = None,
    ) -> None:
        self.login_resolver = login_resolver or LoginFormResolver()
        self.login_verifier = login_verifier or LoginResultVerifier()

    def execute_login_goal(
        self,
        page: Any,
        step: dict[str, Any],
        execution_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ctx = execution_context or {}
        credentials = dict(step.get("credentials") or {})
        username = str(step.get("username") or credentials.get("username") or os.getenv("REAL_MIS_USERNAME") or "admin")
        password = str(step.get("password") or credentials.get("password") or os.getenv("REAL_MIS_PASSWORD") or "123456")

        _emit(ctx, "progress", "login", "正在观察登录页面。", "login_goal_executor", {})
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

        _emit(ctx, "progress", "login", "正在输入测试账号。", "login_goal_executor", {"field": "username"})
        form.username_locator.fill(username)
        _emit(ctx, "progress", "login", "正在输入测试密码。", "login_goal_executor", {"field": "password", "redacted": True})
        form.password_locator.fill(password)
        _emit(ctx, "progress", "login", "正在提交登录请求。", "login_goal_executor", {})
        if form.submit_locator is not None:
            form.submit_locator.click()
        else:
            form.password_locator.press("Enter")

        auth_result = self.login_verifier.verify_after_submit(page, ctx)
        login_result = LoginGoalResult(
            status="passed",
            authState=auth_result.authState,
            failureType=auth_result.failureType,
            evidence=auth_result.evidence,
            remainingRetries=auth_result.remainingRetries,
            reason=auth_result.reason,
        )
        outcome = _outcome(
            LocatorResult(
                form.submit_locator or form.password_locator,
                form.strategy,
                "login_form",
                form.confidence,
                form.reason,
                candidates=form.candidates,
            ),
            verified=True,
            verify_reason=f"login_result:{auth_result.authState}:{auth_result.reason}",
        )
        outcome["auth_state"] = auth_result.as_dict()
        outcome["login_goal_result"] = login_result.as_dict()
        return outcome


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


def _emit(ctx: dict[str, Any], message_type: str, phase: str, content: str, method: str, metadata: dict[str, Any]) -> None:
    emitter = ctx.get("emit_runtime")
    if callable(emitter):
        emitter(message_type, phase, content, method, metadata)
