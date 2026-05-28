import re
from dataclasses import asdict, dataclass, field
from typing import Any

from playwright.sync_api import Error as PlaywrightError


@dataclass
class AuthStateResult:
    authState: str
    confidence: float
    failureType: str | None = None
    evidence: list[str] = field(default_factory=list)
    remainingRetries: int | None = None
    shouldStopProtectedSteps: bool = False
    requiresHumanAction: bool = False
    shouldContinue: bool = True
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


LOGIN_FAILURE_MARKERS = [
    "登录失败",
    "用户名或密码错误",
    "密码错误",
    "账号或密码错误",
    "账户或密码错误",
    "认证失败",
    "登录名或密码不正确",
    "账户被禁用",
    "账号被禁用",
    "账号已锁定",
    "账户已锁定",
    "用户不存在",
    "剩余重试次数",
    "请联系管理员",
    "login was failed",
    "wrong user name or password",
    "wrong username or password",
    "invalid username or password",
    "authentication failed",
    "account disabled",
    "account locked",
    "you have",
    "retries",
    "retry",
    "disabled or unbound regular ad account",
    "ad account password was not updated",
    "forgot password",
    "please contact the administrator",
]

CAPTCHA_MARKERS = [
    "验证码",
    "输入验证码",
    "图形验证码",
    "校验码",
    "动态码",
    "短信验证码",
    "手机验证码",
    "认证码",
    "二次认证",
    "安全验证",
    "滑块验证",
    "请输入验证码",
    "captcha",
    "verification code",
    "security code",
    "one-time password",
    "two-factor",
    "two factor",
    "authentication code",
]

MANUAL_ACTION_MARKERS = [
    "强制修改密码",
    "必须修改初始密码",
    "首次登录必须修改密码",
    "首次登录，请修改密码",
    "password change required",
    "must change password",
    "force change password",
]

LOW_RISK_INTERRUPTION_MARKERS = [
    "账号即将到期",
    "用户账号将于",
    "密码即将过期",
    "密码将于",
    "系统公告",
    "安全承诺",
    "继续访问",
    "我知道了",
]

APP_SUCCESS_MARKERS = [
    "工作台",
    "首页",
    "我的待办",
    "用户信息",
    "退出登录",
    "退出",
    "主菜单",
]


class AuthStateDetector:
    def detect_auth_state(
        self,
        page: Any,
        page_observation: Any | None = None,
        execution_context: dict[str, Any] | None = None,
    ) -> AuthStateResult:
        del execution_context
        text = _observation_text(page_observation) or _page_text(page)
        lower = text.lower()
        url = _safe_page_attr(page, "url").lower()
        title = _safe_title(page).lower()

        login_form = _login_form_state(page, lower)
        failure_evidence = _matching_markers(lower, LOGIN_FAILURE_MARKERS)
        captcha_evidence = _captcha_evidence(page, lower, login_form)
        manual_evidence = _matching_markers(lower, MANUAL_ACTION_MARKERS)
        interruption_evidence = _matching_markers(lower, LOW_RISK_INTERRUPTION_MARKERS)
        success_evidence = _success_evidence(page, lower, url, title, login_form)
        remaining_retries = _extract_remaining_retries(text)

        if captcha_evidence:
            evidence = [*captcha_evidence, *failure_evidence, *login_form["evidence"]]
            if not login_form["business_menu_visible"]:
                evidence.append("business menu not visible")
            return AuthStateResult(
                authState="login_captcha_required",
                confidence=0.9 if login_form["form_visible"] else 0.85,
                failureType="authentication_challenge_required",
                evidence=list(dict.fromkeys(evidence)),
                remainingRetries=remaining_retries,
                shouldStopProtectedSteps=True,
                requiresHumanAction=True,
                shouldContinue=False,
                reason="login captcha or authentication challenge is visible",
            )

        if failure_evidence and login_form["password_visible"] and login_form["submit_visible"]:
            evidence = [*failure_evidence, *login_form["evidence"]]
            if not login_form["business_menu_visible"]:
                evidence.append("business menu not visible")
            return AuthStateResult(
                authState="login_failed",
                confidence=0.95,
                failureType="login_failed",
                evidence=evidence,
                remainingRetries=remaining_retries,
                shouldStopProtectedSteps=True,
                shouldContinue=False,
                reason="login failure message and login form are visible",
            )

        if failure_evidence:
            return AuthStateResult(
                authState="login_failed",
                confidence=0.86,
                failureType="login_failed",
                evidence=failure_evidence,
                remainingRetries=remaining_retries,
                shouldStopProtectedSteps=True,
                shouldContinue=False,
                reason="login failure message detected",
            )

        if manual_evidence:
            return AuthStateResult(
                authState="login_requires_manual_action",
                confidence=0.9,
                failureType="login_requires_manual_action",
                evidence=manual_evidence,
                remainingRetries=remaining_retries,
                shouldStopProtectedSteps=True,
                shouldContinue=False,
                reason="manual login action is required",
            )

        if success_evidence and not login_form["form_visible"]:
            return AuthStateResult(
                authState="logged_in",
                confidence=0.86,
                evidence=success_evidence,
                shouldContinue=True,
                reason="main application evidence is visible and login form disappeared",
            )

        if interruption_evidence and _has_low_risk_continue_button(page):
            return AuthStateResult(
                authState="login_interrupted",
                confidence=0.78,
                failureType="login_interruption",
                evidence=interruption_evidence,
                remainingRetries=remaining_retries,
                shouldContinue=True,
                reason="low risk login interruption can be handled",
            )

        if login_form["form_visible"]:
            return AuthStateResult(
                authState="login_page",
                confidence=0.82,
                failureType="auth_state_not_logged_in",
                evidence=login_form["evidence"],
                remainingRetries=remaining_retries,
                shouldStopProtectedSteps=True,
                shouldContinue=False,
                reason="login form is still visible",
            )

        if success_evidence:
            return AuthStateResult(
                authState="logged_in",
                confidence=0.72,
                evidence=success_evidence,
                shouldContinue=True,
                reason="main application evidence is visible",
            )

        return AuthStateResult(
            authState="unknown",
            confidence=0.35,
            evidence=[],
            remainingRetries=remaining_retries,
            shouldContinue=True,
            reason="auth state could not be determined confidently",
        )


def _page_text(page: Any) -> str:
    try:
        return str(page.evaluate("() => document.body ? document.body.innerText || '' : ''") or "")
    except PlaywrightError:
        return ""


def _observation_text(page_observation: Any | None) -> str:
    if page_observation is None:
        return ""
    if isinstance(page_observation, dict):
        texts = page_observation.get("visibleTexts")
        if isinstance(texts, list):
            return "\n".join(str(item) for item in texts)
        return str(page_observation.get("visible_text") or "")
    visible_texts = getattr(page_observation, "visibleTexts", None)
    if isinstance(visible_texts, list):
        return "\n".join(str(item) for item in visible_texts)
    return str(getattr(page_observation, "visible_text", "") or "")


def _safe_page_attr(page: Any, attr: str) -> str:
    try:
        return str(getattr(page, attr) or "")
    except PlaywrightError:
        return ""


def _safe_title(page: Any) -> str:
    try:
        return str(page.title() or "")
    except PlaywrightError:
        return ""


def _matching_markers(lower_text: str, markers: list[str]) -> list[str]:
    return [marker for marker in markers if marker.lower() in lower_text]


def _login_form_state(page: Any, lower_text: str) -> dict[str, Any]:
    password_visible = _any_visible(page, ["input[type='password']", "input[placeholder*='Password' i]", "input[placeholder*='密码']"])
    username_visible = _any_visible(
        page,
        [
            "input[autocomplete='username']",
            "input[name*='user' i]",
            "input[id*='user' i]",
            "input[name*='login' i]",
            "input[id*='login' i]",
            "input:not([type='hidden']):not([type='password']):not([type='checkbox']):not([type='radio']):not([type='submit'])",
        ],
    )
    submit_visible = _login_submit_visible(page)
    authentication_center_visible = "authentication center" in lower_text or "用户认证中心" in lower_text
    business_menu_visible = _any_visible(page, ["aside", "nav", "[role='menu']", ".ant-menu", ".el-menu", ".sidebar", ".top-nav"])
    evidence: list[str] = []
    if username_visible:
        evidence.append("username input visible")
    if password_visible:
        evidence.append("password input visible")
    if submit_visible:
        evidence.append("login button visible")
    if authentication_center_visible:
        evidence.append("Authentication Center visible")
    return {
        "username_visible": username_visible,
        "password_visible": password_visible,
        "submit_visible": submit_visible,
        "authentication_center_visible": authentication_center_visible,
        "business_menu_visible": business_menu_visible,
        "form_visible": password_visible and (username_visible or submit_visible),
        "evidence": evidence,
    }


def _captcha_evidence(page: Any, lower_text: str, login_form: dict[str, Any]) -> list[str]:
    evidence = _matching_markers(lower_text, CAPTCHA_MARKERS)
    if _any_visible(
        page,
        [
            "input[name*='captcha' i]",
            "input[id*='captcha' i]",
            "input[placeholder*='验证码']",
            "input[placeholder*='verification' i]",
            "input[placeholder*='security code' i]",
            "input[name*='otp' i]",
            "input[id*='otp' i]",
            "input[name*='sms_checkcode' i]",
            "input[id*='sms' i][id*='otp' i]",
        ],
    ):
        evidence.append("captcha input visible")
    if _any_visible(
        page,
        [
            "img[src*='captcha' i]",
            "img[id*='captcha' i]",
            "img[class*='captcha' i]",
            "canvas",
            ".captcha",
            ".verify-code",
            ".verification-code",
        ],
    ):
        evidence.append("captcha image visible")
    if _any_visible(
        page,
        [
            "button:has-text('刷新')",
            "a:has-text('换一张')",
            "button:has-text('Refresh')",
            "[title*='验证码']",
            "[title*='refresh' i]",
        ],
    ):
        evidence.append("captcha refresh control visible")
    if _any_visible(page, ["input[name*='otp' i]", "input[id*='otp' i]", "input[name*='sms_checkcode' i]"]):
        evidence.append("OTP challenge visible")
    if _qr_challenge_visible(page):
        evidence.append("code scanning authentication visible")
    if evidence and login_form.get("form_visible"):
        evidence.append("login form visible")
    return list(dict.fromkeys(evidence))


def _qr_challenge_visible(page: Any) -> bool:
    return _any_visible(
        page,
        [
            "img[src*='qr' i]",
            "img[id*='qr' i]",
            "img[class*='qr' i]",
            "canvas[id*='qr' i]",
            "canvas[class*='qr' i]",
            ".qrcode",
            ".qr-code",
        ],
    )


def _login_submit_visible(page: Any) -> bool:
    for name in ["登录", "Login", "LOGIN", "Sign in", "Sign In", "进入系统"]:
        try:
            candidate = page.get_by_role("button", name=name, exact=False)
            if candidate.count() > 0 and candidate.first.is_visible(timeout=300):
                return True
        except PlaywrightError:
            continue
    return _any_visible(page, ["button[type='submit']", "input[type='submit']", ".login-btn", ".login-button"])


def _success_evidence(page: Any, lower_text: str, url: str, title: str, login_form: dict[str, Any]) -> list[str]:
    evidence: list[str] = []
    has_app_shell = _any_visible(page, ["aside", "nav", "[role='menu']", ".ant-menu", ".el-menu", ".sidebar", ".top-nav"])
    has_text_marker = False
    if has_app_shell:
        evidence.append("main menu visible")
    for marker in APP_SUCCESS_MARKERS:
        if marker.lower() in lower_text:
            evidence.append(marker)
            has_text_marker = True
            break
    if "login" not in url and "登录" not in title and not login_form["form_visible"] and (has_app_shell or has_text_marker):
        evidence.append("url left login page")
    return list(dict.fromkeys(evidence))


def _has_low_risk_continue_button(page: Any) -> bool:
    for name in ["继续访问", "继续", "进入系统", "我知道了", "确定", "关闭", "稍后修改"]:
        try:
            button = page.get_by_role("button", name=name, exact=False)
            if button.count() > 0 and button.first.is_visible(timeout=300):
                return True
            text = page.get_by_text(name, exact=False)
            if text.count() > 0 and text.first.is_visible(timeout=300):
                return True
        except PlaywrightError:
            continue
    return False


def _any_visible(page: Any, selectors: list[str]) -> bool:
    for selector in selectors:
        try:
            locator = page.locator(selector)
            for index in range(min(locator.count(), 10)):
                if locator.nth(index).is_visible(timeout=300):
                    return True
        except PlaywrightError:
            continue
    return False


def _extract_remaining_retries(text: str) -> int | None:
    patterns = [
        r"you\s+have\s+(\d+)\s+retr(?:y|ies)",
        r"还有\s*(\d+)\s*次",
        r"剩余\s*(\d+)\s*次",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
    return None
