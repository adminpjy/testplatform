import os
from typing import Any

from playwright.sync_api import Error as PlaywrightError

from executor.aitp_executor.observer.auth_state_detector import AuthStateDetector, AuthStateResult
from executor.aitp_executor.runner.page_waiter import wait_for_page_ready


class LoginStateError(RuntimeError):
    def __init__(self, auth_result: AuthStateResult) -> None:
        self.auth_result = auth_result
        self.failure_type = auth_result.failureType or auth_result.authState
        self.details = {"auth_state": auth_result.as_dict()}
        super().__init__(_message_for(auth_result))


class LoginResultVerifier:
    def __init__(self, *, detector: AuthStateDetector | None = None) -> None:
        self.detector = detector or AuthStateDetector()
        self.wait_ms = _int_env("LOGIN_RESULT_WAIT_MS", 5_000)
        self.recheck_times = _int_env("LOGIN_RESULT_RECHECK_TIMES", 2)
        self.auto_retry_on_failure = _bool_env("LOGIN_AUTO_RETRY_ON_FAILURE", False)
        self.max_auto_retry = _int_env("LOGIN_MAX_AUTO_RETRY", 0)
        self.stop_on_captcha = _bool_env("LOGIN_STOP_ON_CAPTCHA", True)
        self.stop_on_remaining_retries = _bool_env("LOGIN_STOP_ON_REMAINING_RETRIES", True)

    def verify_after_submit(
        self,
        page: Any,
        execution_context: dict[str, Any] | None = None,
    ) -> AuthStateResult:
        ctx = execution_context or {}
        _emit(ctx, "progress", "login_result", "正在验证登录结果。", "login_result_verifier", {})

        last_result: AuthStateResult | None = None
        for attempt in range(self.recheck_times + 1):
            if attempt == 0:
                _short_wait(page, min(self.wait_ms, 1_000))
            else:
                _emit(
                    ctx,
                    "progress",
                    "login_result",
                    "登录结果尚不明确，正在重新观察页面。",
                    "login_result_verifier",
                    {"attempt": attempt + 1},
                )
                _short_wait(page, self.wait_ms)
            wait_for_page_ready(page, timeout_ms=max(self.wait_ms, 1_000), settle_ms=250)
            result = self.detector.detect_auth_state(page, execution_context=ctx)
            last_result = result
            _append_auth_debug(ctx, result, step_id=ctx.get("step_id") or "login", decision=_decision_for(result))

            if result.authState == "login_interrupted" and _handle_low_risk_interruption(page, ctx):
                wait_for_page_ready(page, timeout_ms=max(self.wait_ms, 1_000), settle_ms=250)
                result = self.detector.detect_auth_state(page, execution_context=ctx)
                last_result = result
                _append_auth_debug(ctx, result, step_id=ctx.get("step_id") or "login", decision=_decision_for(result))

            if result.authState == "logged_in":
                _emit(
                    ctx,
                    "success",
                    "login_result",
                    "登录结果验证通过，已进入目标系统。",
                    "login_result_verifier",
                    result.as_dict(),
                )
                return result

            if result.authState == "login_captcha_required":
                _emit(
                    ctx,
                    "error",
                    "login_result",
                    "检测到登录失败后出现验证码或二次认证。",
                    "login_result_verifier",
                    {
                        **result.as_dict(),
                        "autoRetryOnFailure": self.auto_retry_on_failure,
                        "maxAutoRetry": self.max_auto_retry,
                        "stopOnCaptcha": self.stop_on_captcha,
                    },
                )
                _emit(
                    ctx,
                    "warning",
                    "login_result",
                    "当前仍停留在登录页面，尚未进入业务系统。为避免账号被锁定，系统不会继续自动重试。",
                    "login_result_verifier",
                    {
                        **result.as_dict(),
                        "autoRetryDisabled": True,
                        "stopOnRemainingRetries": self.stop_on_remaining_retries,
                    },
                )
                _emit(
                    ctx,
                    "warning",
                    "human_intervention",
                    "建议检查测试账号，或人工处理验证码后重新执行。",
                    "login_result_verifier",
                    result.as_dict(),
                )
                raise LoginStateError(result)

            if result.authState == "login_failed":
                _emit(
                    ctx,
                    "error",
                    "login_result",
                    f"检测到登录失败提示：{_first_evidence(result)}。",
                    "login_result_verifier",
                    result.as_dict(),
                )
                if result.remainingRetries is not None:
                    _emit(
                        ctx,
                        "warning",
                        "login_result",
                        f"认证系统提示还剩 {result.remainingRetries} 次重试。为避免账号锁定，系统不会继续自动重试。",
                        "login_result_verifier",
                        {**result.as_dict(), "autoRetryOnFailure": self.auto_retry_on_failure, "maxAutoRetry": self.max_auto_retry},
                    )
                _emit(
                    ctx,
                    "error",
                    "auth_guard",
                    "当前仍停留在登录页面，后续业务步骤不会继续执行。",
                    "auth_state_detector",
                    result.as_dict(),
                )
                raise LoginStateError(result)

            if result.authState == "login_requires_manual_action":
                _emit(
                    ctx,
                    "warning",
                    "login_result",
                    "登录后需要人工处理，已停止后续自动业务步骤。",
                    "login_result_verifier",
                    result.as_dict(),
                )
                raise LoginStateError(result)

        unknown = last_result or AuthStateResult(
            authState="unknown",
            confidence=0.0,
            failureType="login_state_unknown",
            shouldContinue=False,
            reason="login result was not observed",
        )
        if unknown.authState == "unknown":
            unknown.failureType = "login_state_unknown"
            unknown.shouldContinue = False
        _emit(
            ctx,
            "warning",
            "login_result",
            "登录结果无法确认，已停止后续业务步骤并保留证据。",
            "login_result_verifier",
            unknown.as_dict(),
        )
        raise LoginStateError(unknown)


def _message_for(result: AuthStateResult) -> str:
    if result.authState == "login_failed":
        return (
            "login_failed: 检测到目标系统返回登录失败提示。"
            "可能原因包括用户名或密码错误、账号被禁用、账号未绑定或密码未同步。"
        )
    if result.authState == "login_captcha_required":
        return (
            "login_captcha_required: 检测到验证码或二次认证，当前未进入业务系统。"
            "为避免账号锁定，系统不会继续自动重试。"
        )
    if result.authState == "login_requires_manual_action":
        return "login_requires_manual_action: 登录后需要人工处理。"
    if result.authState == "login_page":
        return "auth_state_not_logged_in: 当前仍停留在登录页面。"
    return f"{result.failureType or result.authState}: {result.reason}"


def _handle_low_risk_interruption(page: Any, ctx: dict[str, Any]) -> bool:
    for name in ["继续访问", "继续", "进入系统", "我知道了", "确定", "关闭", "稍后修改"]:
        try:
            button = page.get_by_role("button", name=name, exact=False)
            if button.count() > 0 and button.first.is_visible(timeout=500):
                _emit(ctx, "warning", "global_interruption", f"检测到登录后提示，正在点击“{name}”。", "global_interruption_handler", {"button": name})
                button.first.click()
                _short_wait(page, 500)
                return True
            text = page.get_by_text(name, exact=False)
            if text.count() > 0 and text.first.is_visible(timeout=500):
                _emit(ctx, "warning", "global_interruption", f"检测到登录后提示，正在点击“{name}”。", "global_interruption_handler", {"button": name})
                text.first.click()
                _short_wait(page, 500)
                return True
        except PlaywrightError:
            continue
    return False


def _emit(ctx: dict[str, Any], message_type: str, phase: str, content: str, method: str, metadata: dict[str, Any]) -> None:
    emitter = ctx.get("emit_runtime")
    if callable(emitter):
        emitter(message_type, phase, content, method, metadata)


def _append_auth_debug(ctx: dict[str, Any], result: AuthStateResult, *, step_id: Any, decision: str) -> None:
    append_debug = ctx.get("append_debug")
    if callable(append_debug):
        append_debug(
            {
                "phase": "auth_state_detected",
                "stepId": step_id,
                "authState": result.authState,
                "confidence": result.confidence,
                "failureType": result.failureType,
                "evidence": result.evidence,
                "remainingRetries": result.remainingRetries,
                "requiresHumanAction": result.requiresHumanAction,
                "decision": decision,
                "reason": result.reason,
            }
        )


def _decision_for(result: AuthStateResult) -> str:
    if result.authState == "logged_in":
        return "continue_run"
    if result.authState in {"login_failed", "login_captcha_required", "login_page", "login_requires_manual_action"}:
        return "stop_run"
    return "observe_again"


def _first_evidence(result: AuthStateResult) -> str:
    return str(result.evidence[0]) if result.evidence else result.reason or result.authState


def _short_wait(page: Any, timeout_ms: int) -> None:
    try:
        page.wait_for_timeout(max(timeout_ms, 1))
    except PlaywrightError:
        return


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
