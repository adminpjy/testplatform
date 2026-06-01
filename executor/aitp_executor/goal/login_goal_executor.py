import os
from dataclasses import asdict, dataclass, field
from typing import Any

from playwright.sync_api import Error as PlaywrightError

from executor.aitp_executor.observer.auth_state_detector import AuthStateDetector, AuthStateResult
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
        auth_detector: AuthStateDetector | None = None,
    ) -> None:
        self.login_resolver = login_resolver or LoginFormResolver()
        self.login_verifier = login_verifier or LoginResultVerifier()
        self.auth_detector = auth_detector or AuthStateDetector()

    def execute_login_goal(
        self,
        page: Any,
        step: dict[str, Any],
        execution_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ctx = execution_context or {}
        credentials = dict(step.get("credentials") or {})
        username = step.get("username") or credentials.get("username") or os.getenv("REAL_MIS_USERNAME")
        password = step.get("password") or credentials.get("password") or os.getenv("REAL_MIS_PASSWORD")

        _emit(ctx, "progress", "login", "正在观察登录页面。", "login_goal_executor", {})
        wait_for_page_ready(page)
        initial_auth = self.auth_detector.detect_auth_state(page, execution_context=ctx)
        if initial_auth.authState == "logged_in":
            return _login_state_outcome(initial_auth, strategy="already_authenticated", reason="当前已经处于登录后的系统页面。")

        form = self.login_resolver.resolve(page)
        if form.username_locator is None or form.password_locator is None:
            _emit(ctx, "progress", "login", "当前还不是统一身份认证登录页，正在点击门户登录入口。", "login_goal_executor", {})
            entry_opened = _open_unified_login_entry(page)
            if entry_opened:
                wait_for_page_ready(page)
                auth_after_entry = self.auth_detector.detect_auth_state(page, execution_context=ctx)
                if auth_after_entry.authState == "logged_in":
                    return _login_state_outcome(auth_after_entry, strategy="sso_login_entry", reason="点击登录入口后已进入系统。")
                form = self.login_resolver.resolve(page)
            if form.username_locator is None or form.password_locator is None:
                raise RuntimeError(
                    "login_form_fields_not_found:"
                    + form.reason
                    + "。未进入统一身份认证登录页，或统一认证页未出现账号密码输入框。"
                    + " 已捕获候选："
                    + str(form.candidates[:6])
                )

        if not username:
            raise RuntimeError("login_credentials_missing:username")
        if not password:
            raise RuntimeError("login_credentials_missing:password")

        _emit(ctx, "progress", "login", "正在输入测试账号。", "login_goal_executor", {"field": "username"})
        form.username_locator.fill(str(username))
        _capture(ctx, "login_username_filled", page, {"field": "username"})
        _emit(ctx, "progress", "login", "正在输入测试密码。", "login_goal_executor", {"field": "password", "redacted": True})
        form.password_locator.fill(str(password))
        _capture(ctx, "login_password_filled", page, {"field": "password", "redacted": True})
        _emit(ctx, "progress", "login", "正在提交登录请求。", "login_goal_executor", {})
        _capture(ctx, "login_before_submit", page, {"field": "submit"})
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


def _login_state_outcome(auth_result: AuthStateResult, *, strategy: str, reason: str) -> dict[str, Any]:
    return {
        "locator_strategy": strategy,
        "element_ref": auth_result.authState,
        "confidence": auth_result.confidence,
        "reason": reason,
        "needs_vision_fallback": False,
        "fallback_reason": auth_result.failureType,
        "candidates": [{"kind": "auth_state", "evidence": auth_result.evidence}],
        "verified": True,
        "auth_state": auth_result.as_dict(),
        "login_goal_result": LoginGoalResult(
            status="passed",
            authState=auth_result.authState,
            failureType=auth_result.failureType,
            evidence=auth_result.evidence,
            remainingRetries=auth_result.remainingRetries,
            reason=auth_result.reason,
        ).as_dict(),
    }


def _open_unified_login_entry(page: Any) -> bool:
    selectors = [
        ".notLogin .login",
        "a.login",
        ".login",
        "a[href*='login' i]",
        "a[href*='auth' i]",
        "a[href*='idp' i]",
    ]
    for selector in selectors:
        try:
            locator = page.locator(selector)
            for index in range(min(locator.count(), 8)):
                candidate = locator.nth(index)
                if candidate.is_visible(timeout=400):
                    text = str(candidate.inner_text(timeout=400) or "").strip()
                    href = str(candidate.get_attribute("href", timeout=400) or "")
                    if "登录" in text or "Login" in text or "login" in href.lower() or "auth" in href.lower() or "idp" in href.lower():
                        candidate.click(timeout=3_000)
                        return True
        except PlaywrightError:
            continue

    for text in ["登录", "用户登录", "统一身份认证", "Login", "Sign in", "Sign In"]:
        try:
            locator = page.get_by_text(text, exact=True)
            for index in range(min(locator.count(), 8)):
                candidate = locator.nth(index)
                if candidate.is_visible(timeout=400):
                    candidate.click(timeout=3_000)
                    return True
        except PlaywrightError:
            continue

    for role in ["link", "button"]:
        for name in ["登录", "用户登录", "Login", "Sign in", "Sign In"]:
            try:
                locator = page.get_by_role(role, name=name, exact=False)
                for index in range(min(locator.count(), 8)):
                    candidate = locator.nth(index)
                    if candidate.is_visible(timeout=400):
                        candidate.click(timeout=3_000)
                        return True
            except PlaywrightError:
                continue
    return False


def _emit(ctx: dict[str, Any], message_type: str, phase: str, content: str, method: str, metadata: dict[str, Any]) -> None:
    emitter = ctx.get("emit_runtime")
    if callable(emitter):
        emitter(message_type, phase, content, method, metadata)


def _capture(ctx: dict[str, Any], label: str, page: Any, metadata: dict[str, Any]) -> None:
    capturer = ctx.get("capture_process_screenshot")
    if callable(capturer):
        capturer(label, metadata, page)
