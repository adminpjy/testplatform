from dataclasses import dataclass, field
from typing import Any

from playwright.sync_api import Error as PlaywrightError


@dataclass
class LoginFormResult:
    username_locator: Any | None
    password_locator: Any | None
    submit_locator: Any | None
    strategy: str
    confidence: float
    reason: str
    candidates: list[dict[str, Any]] = field(default_factory=list)


class LoginFormResolver:
    def resolve(self, page: Any) -> LoginFormResult:
        scopes = self._scopes(page)
        candidates: list[dict[str, Any]] = []
        best_password = None
        best_scope = page
        best_password_meta: dict[str, Any] | None = None

        for scope in scopes:
            password = self._password_locator(scope)
            if password.locator is not None:
                best_password = password.locator
                best_scope = scope
                best_password_meta = password.meta
                candidates.append({"kind": "password", **password.meta})
                break

        username = self._username_locator(best_scope, best_password)
        submit = self._submit_locator(best_scope)
        if username.locator is not None:
            candidates.append({"kind": "username", **username.meta})
        if submit.locator is not None:
            candidates.append({"kind": "submit", **submit.meta})

        confidence = 0.0
        if username.locator is not None:
            confidence += 0.42
        if best_password is not None:
            confidence += 0.42
        if submit.locator is not None:
            confidence += 0.14

        missing = []
        if username.locator is None:
            missing.append("username_input")
        if best_password is None:
            missing.append("password_input")
        if submit.locator is None:
            missing.append("submit_button")

        return LoginFormResult(
            username_locator=username.locator,
            password_locator=best_password,
            submit_locator=submit.locator,
            strategy="generic_login_form",
            confidence=min(confidence, 0.98),
            reason="login form resolved" if not missing else "login form incomplete:" + ",".join(missing),
            candidates=candidates + ([{"kind": "password", **best_password_meta}] if best_password_meta and not candidates else []),
        )

    def _scopes(self, page: Any) -> list[Any]:
        scopes = [page]
        try:
            frames = page.frame_locator("iframe")
            # Keep this as a coarse fallback. Playwright frame_locator can target
            # all iframes; locators inside it still resolve lazily.
            scopes.append(frames)
        except PlaywrightError:
            pass
        return scopes

    def _password_locator(self, scope: Any) -> "_LocatorCandidate":
        selectors = [
            "input[type='password']",
            "input[placeholder*='Password' i]",
            "input[placeholder*='密码']",
            "input[name*='pass' i]",
            "input[id*='pass' i]",
        ]
        for selector in selectors:
            locator = self._first_visible(scope.locator(selector))
            if locator is not None:
                return _LocatorCandidate(locator, {"selector": selector, "strategy": "password_selector"})
        for label in ["密码", "口令", "Password", "password"]:
            try:
                locator = scope.get_by_label(label, exact=False)
                visible = self._first_visible(locator)
                if visible is not None:
                    return _LocatorCandidate(visible, {"label": label, "strategy": "password_label"})
            except PlaywrightError:
                continue
        return _LocatorCandidate(None, {})

    def _username_locator(self, scope: Any, password_locator: Any | None) -> "_LocatorCandidate":
        selectors = [
            "input[autocomplete='username']",
            "input[name*='user' i]",
            "input[id*='user' i]",
            "input[name*='login' i]",
            "input[id*='login' i]",
            "input[name*='account' i]",
            "input[id*='account' i]",
            "input[placeholder*='用户名']",
            "input[placeholder*='账号']",
            "input[placeholder*='登录名']",
            "input[placeholder*='User' i]",
            "input[placeholder*='Account' i]",
        ]
        for selector in selectors:
            locator = self._first_visible(scope.locator(selector))
            if locator is not None and not self._is_password(locator):
                return _LocatorCandidate(locator, {"selector": selector, "strategy": "username_selector"})
        for label in ["用户名", "账号", "登录名", "用户", "User", "Username", "Account", "Login"]:
            try:
                locator = scope.get_by_label(label, exact=False)
                visible = self._first_visible(locator)
                if visible is not None and not self._is_password(visible):
                    return _LocatorCandidate(visible, {"label": label, "strategy": "username_label"})
            except PlaywrightError:
                continue

        inputs = self._visible_text_inputs(scope)
        if password_locator is not None and inputs:
            password_box = self._box(password_locator)
            ranked = sorted(inputs, key=lambda item: self._distance_to_password(item["box"], password_box))
            return _LocatorCandidate(ranked[0]["locator"], {"selector": ranked[0]["selector"], "strategy": "nearest_text_input_before_password"})
        if inputs:
            return _LocatorCandidate(inputs[0]["locator"], {"selector": inputs[0]["selector"], "strategy": "first_visible_text_input"})
        return _LocatorCandidate(None, {})

    def _submit_locator(self, scope: Any) -> "_LocatorCandidate":
        for name in ["登录", "Login", "LOGIN", "Sign in", "Sign In", "进入系统"]:
            try:
                button = scope.get_by_role("button", name=name, exact=False)
                visible = self._first_visible(button)
                if visible is not None:
                    return _LocatorCandidate(visible, {"text": name, "strategy": "submit_button_role"})
            except PlaywrightError:
                continue
        selectors = [
            "button[type='submit']",
            "input[type='submit']",
            ".login-btn",
            ".login-button",
            "button:has-text('Login')",
            "button:has-text('登录')",
        ]
        for selector in selectors:
            try:
                visible = self._first_visible(scope.locator(selector))
                if visible is not None:
                    return _LocatorCandidate(visible, {"selector": selector, "strategy": "submit_selector"})
            except PlaywrightError:
                continue
        return _LocatorCandidate(None, {})

    def _visible_text_inputs(self, scope: Any) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        selector = "input:not([type='hidden']):not([type='password']):not([type='checkbox']):not([type='radio']):not([type='submit']), textarea"
        try:
            inputs = scope.locator(selector)
            for index in range(min(inputs.count(), 20)):
                locator = inputs.nth(index)
                if self._is_visible_enabled(locator):
                    result.append({"locator": locator, "selector": f"{selector} >> nth={index}", "box": self._box(locator)})
        except PlaywrightError:
            return result
        return result

    def _first_visible(self, locator: Any) -> Any | None:
        try:
            for index in range(min(locator.count(), 20)):
                item = locator.nth(index)
                if self._is_visible_enabled(item):
                    return item
        except PlaywrightError:
            return None
        return None

    def _is_visible_enabled(self, locator: Any) -> bool:
        try:
            return locator.is_visible(timeout=500) and locator.is_enabled(timeout=500)
        except PlaywrightError:
            return False

    def _is_password(self, locator: Any) -> bool:
        try:
            return str(locator.get_attribute("type", timeout=500) or "").lower() == "password"
        except PlaywrightError:
            return False

    def _box(self, locator: Any) -> dict[str, float] | None:
        try:
            return locator.bounding_box(timeout=500)
        except PlaywrightError:
            return None

    def _distance_to_password(self, box: dict[str, float] | None, password_box: dict[str, float] | None) -> float:
        if not box or not password_box:
            return 10_000.0
        x1 = float(box.get("x", 0)) + float(box.get("width", 0)) / 2
        y1 = float(box.get("y", 0)) + float(box.get("height", 0)) / 2
        x2 = float(password_box.get("x", 0)) + float(password_box.get("width", 0)) / 2
        y2 = float(password_box.get("y", 0)) + float(password_box.get("height", 0)) / 2
        vertical_penalty = 0 if y1 <= y2 else 1000
        return abs(x1 - x2) + abs(y1 - y2) + vertical_penalty


@dataclass
class _LocatorCandidate:
    locator: Any | None
    meta: dict[str, Any]
