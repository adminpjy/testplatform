import re
from typing import Any

from executor.aitp_executor.handlers.base import CommonOperationHandler, handler_outcome, locator_outcome, require_locator
from executor.aitp_executor.goal.login_form_resolver import LoginFormResolver
from executor.aitp_executor.locator.auto_form_filler import AutoFormFiller
from executor.aitp_executor.locator.element_locator import ElementLocator
from executor.aitp_executor.observer.auth_state_detector import AuthStateDetector
from executor.aitp_executor.runner.page_waiter import wait_for_page_ready


class FormFillHandler(CommonOperationHandler):
    handler_name = "form_fill_handler"
    rule_types = ["form_fill", "form_control", "dropdown", "date_picker", "org_selector", "person_selector", "tree_selector", "dialog_selector", "file_upload"]
    default_intent = "fill_form"

    def __init__(
        self,
        *,
        locator: ElementLocator | None = None,
        form_filler: AutoFormFiller | None = None,
        login_resolver: LoginFormResolver | None = None,
        auth_detector: AuthStateDetector | None = None,
    ) -> None:
        super().__init__()
        self.locator = locator or ElementLocator()
        self.form_filler = form_filler or AutoFormFiller()
        self.login_resolver = login_resolver or LoginFormResolver()
        self.auth_detector = auth_detector or AuthStateDetector()

    def fill_form(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        resolution = self.resolve_rules(ctx, intent="fill_form", rule_types=self.rule_types)
        self.emit_rule_hits(ctx, resolution)
        self.emit(ctx, "progress", "form_fill", "正在按表单字段语义填写。")
        test_data = self._merged_test_data(step, dsl or {})
        if self._is_login_form_step(step):
            login_result = self._fill_login_form(page, step=step, test_data=test_data, ctx=ctx)
            self.debug(
                ctx,
                {
                    "strategy": "login_form_filler",
                    "filled": login_result["filled"],
                    "openedLoginEntry": login_result["opened_login_entry"],
                },
            )
            return handler_outcome("login_form_filler", "login_form", 0.92, login_result)
        result = self.form_filler.fill(page, test_data=test_data)
        if result.defaults_used:
            self.emit(ctx, "text", "form_fill", "已按规则使用默认测试数据。", metadata={"defaults_used": result.defaults_used})
        if result.needs_clarification:
            raise RuntimeError("needs_clarification:" + ",".join(result.needs_clarification))
        if not result.filled:
            self._raise_noop_fill(step, result)
        self.debug(ctx, {"strategy": "auto_form_filler", "filled": result.filled, "defaultsUsed": result.defaults_used, "skipped": result.skipped})
        return handler_outcome(
            "auto_form_filler",
            "form",
            0.84,
            {"filled": result.filled, "defaults_used": result.defaults_used, "skipped": result.skipped},
        )

    def _merged_test_data(self, step: dict[str, Any], dsl: dict[str, Any]) -> dict[str, Any]:
        test_data = dict(dsl.get("testData") or {})
        for key in ("credentials",):
            value = dsl.get(key)
            if isinstance(value, dict):
                test_data.update({field: field_value for field, field_value in value.items() if field_value not in (None, "")})
        for key in ("formData", "testData", "credentials"):
            value = step.get(key)
            if isinstance(value, dict):
                test_data.update({field: field_value for field, field_value in value.items() if field_value not in (None, "")})
        if step.get("username"):
            test_data["username"] = step["username"]
        if step.get("password"):
            test_data["password"] = step["password"]
        return test_data

    def _is_login_form_step(self, step: dict[str, Any]) -> bool:
        target = str(step.get("target") or "")
        action = str(step.get("action") or "")
        text = f"{action} {target}".lower()
        return "登录" in target or "login" in text or "signin" in text

    def _fill_login_form(self, page: Any, *, step: dict[str, Any], test_data: dict[str, Any], ctx: Any) -> dict[str, Any]:
        opened_login_entry = False
        auth_result = self.auth_detector.detect_auth_state(page)
        if auth_result.authState == "logged_in":
            return {
                "filled": [],
                "defaults_used": {},
                "skipped": [{"label": "login_form", "reason": "already_authenticated"}],
                "opened_login_entry": False,
                "strategy": "already_authenticated",
            }
        form = self.login_resolver.resolve(page)
        if form.username_locator is None or form.password_locator is None:
            opened_login_entry = self._open_login_entry(page, ctx)
            if opened_login_entry:
                wait_for_page_ready(page)
                form = self.login_resolver.resolve(page)

        if form.username_locator is None or form.password_locator is None:
            raise RuntimeError(f"login_form_fields_not_found:{form.reason}")

        username = _credential_value(test_data, "username", "用户名", "账号", "登录名", "user", "account")
        password = _credential_value(test_data, "password", "密码", "口令", "pass")
        if not username:
            raise RuntimeError("login_credentials_missing:username")
        if not password:
            raise RuntimeError("login_credentials_missing:password")

        self.emit(ctx, "progress", "form_fill", "正在输入测试账号。", metadata={"field": "username"})
        form.username_locator.fill(str(username))
        self.emit(ctx, "progress", "form_fill", "正在输入测试密码。", metadata={"field": "password", "redacted": True})
        form.password_locator.fill(str(password))
        page.wait_for_timeout(100)
        return {
            "filled": [
                {"label": "username", "value": str(username)},
                {"label": "password", "value": "***REDACTED***"},
            ],
            "defaults_used": {},
            "skipped": [],
            "opened_login_entry": opened_login_entry,
            "strategy": form.strategy,
        }

    def _raise_noop_fill(self, step: dict[str, Any], result: Any) -> None:
        target = str(step.get("target") or step.get("name") or "当前表单")
        labels = [str(item.get("label")) for item in result.skipped if isinstance(item, dict) and item.get("label")]
        if labels:
            preview = "、".join(labels[:6])
            raise RuntimeError(
                "form_no_fields_filled:"
                f"已识别到字段但没有填写任何值（目标：{target}，字段：{preview}）。"
                "请在测试数据中补充这些字段，或把关键字段标记为需要人工介入。"
            )
        raise RuntimeError(
            "form_no_fields_detected:"
            f"当前页面未识别到可填写字段（目标：{target}）。"
            "请确认已经进入正确表单页；如果这是登录流程，使用“登录表单”或“登录系统”目标，执行器会先打开登录入口再填写。"
        )

    def _open_login_entry(self, page: Any, ctx: Any) -> bool:
        self.emit(ctx, "progress", "form_fill", "正在打开登录入口。")
        for role in ("link", "button"):
            try:
                locator = page.get_by_role(role, name=re.compile(r"^\s*(登录|Login|Sign in|Sign In)\s*$"))
                for index in range(min(locator.count(), 5)):
                    candidate = locator.nth(index)
                    if candidate.is_visible(timeout=500) and candidate.is_enabled(timeout=500):
                        candidate.click()
                        return True
            except Exception:
                continue
        for text in ("登录", "Login", "Sign in", "Sign In"):
            try:
                locator = page.get_by_text(text, exact=True)
                for index in range(min(locator.count(), 5)):
                    candidate = locator.nth(index)
                    if candidate.is_visible(timeout=500):
                        candidate.click()
                        return True
            except Exception:
                continue
        return False

    def fill_field(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        self.emit_rule_hits(ctx, self.resolve_rules(ctx, intent="fill_field", rule_types=["form_fill", "form_control"]))
        target = str(step.get("target") or step.get("selector") or "")
        value = str(step.get("value") or "")
        self.emit(ctx, "progress", "form_fill", f"正在填写字段：{target}。")
        result = self.locator.locate(page, action="input", target=target, step=step)
        if result.locator is None:
            raise RuntimeError(f"form_field_not_found: {target}")
        require_locator(result).fill(value)
        self.debug(ctx, {"strategy": "fill_field", "target": target, "locatorStrategy": result.strategy})
        return locator_outcome(result)


def _credential_value(data: dict[str, Any], *keys: str) -> Any:
    lower_lookup = {str(key).lower(): value for key, value in data.items()}
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
        value = lower_lookup.get(key.lower())
        if value not in (None, ""):
            return value
    return None
