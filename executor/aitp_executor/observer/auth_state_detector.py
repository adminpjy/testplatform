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
    "disabled or unbound regular ad account",
    "ad account password was not updated",
    "please contact the administrator",
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
    "我的待办",
    "用户信息",
    "退出登录",
    "退出系统",
    "退出",
    "系统导航",
    "个人中心",
    "用户中心",
]

WEAK_APP_SUCCESS_MARKERS = [
    "首页",
    "主菜单",
]

APP_SHELL_SELECTORS = [
    "aside",
    "nav",
    "[role='menu']",
    ".ant-menu",
    ".el-menu",
    ".sidebar",
    ".top-nav",
    ".TopMenu",
    ".topMenu",
    ".top-menu",
    ".home_header",
    ".HeaderComponent",
    ".HomeComponent",
    "#layout_sider",
    ".el-aside",
]

PORTAL_USER_SELECTORS = [
    ".login1",
    ".userName",
    ".username",
    ".user-info",
    ".userInfo",
    "[class*='userName']",
    "[class*='user-info']",
    "[class*='userInfo']",
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
        manual_evidence = _matching_markers(lower, MANUAL_ACTION_MARKERS)
        challenge_evidence = _auth_challenge_evidence(page, lower)
        interruption_evidence = _matching_markers(lower, LOW_RISK_INTERRUPTION_MARKERS)
        success_evidence = _success_evidence(page, lower, url, title, login_form)
        remaining_retries = _extract_remaining_retries(text)

        if success_evidence and not login_form["form_visible"]:
            return AuthStateResult(
                authState="logged_in",
                confidence=0.9 if login_form["business_menu_visible"] else 0.86,
                evidence=success_evidence,
                shouldContinue=True,
                reason="main application evidence is visible and login form disappeared",
            )

        if challenge_evidence:
            evidence = [*challenge_evidence, *failure_evidence, *login_form["evidence"]]
            return AuthStateResult(
                authState="login_requires_manual_action",
                confidence=0.9,
                failureType="login_captcha_required",
                evidence=list(dict.fromkeys(evidence)),
                remainingRetries=remaining_retries,
                shouldStopProtectedSteps=True,
                requiresHumanAction=True,
                shouldContinue=False,
                reason="visible captcha, OTP, SMS code, or MFA field requires human action",
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

        if login_form["login_entry_visible"]:
            return AuthStateResult(
                authState="login_page",
                confidence=0.68,
                failureType="auth_state_not_logged_in",
                evidence=login_form["evidence"],
                remainingRetries=remaining_retries,
                shouldStopProtectedSteps=True,
                shouldContinue=False,
                reason="portal login entry is visible and authenticated portal evidence is absent",
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
            "input[name*='account' i]",
            "input[id*='account' i]",
            "input[name*='mobile' i]",
            "input[id*='mobile' i]",
            "input[placeholder*='用户名']",
            "input[placeholder*='账号']",
            "input[placeholder*='账户']",
            "input[placeholder*='手机号']",
            "input[placeholder*='User' i]",
            "input[placeholder*='Account' i]",
            "input[title*='Login' i]",
            "input[title*='User' i]",
            "input[title*='Account' i]",
            "input[title*='Mobile' i]",
        ],
    )
    submit_visible = _login_submit_visible(page)
    authentication_center_visible = "authentication center" in lower_text or "用户认证中心" in lower_text
    business_menu_visible = _any_visible(page, APP_SHELL_SELECTORS)
    login_entry_visible = (not password_visible) and _login_entry_visible(page)
    login_context = authentication_center_visible or "login" in lower_text or "authn" in lower_text or "idp" in lower_text or login_entry_visible or (password_visible and submit_visible)
    evidence: list[str] = []
    if username_visible:
        evidence.append("username input visible")
    if password_visible:
        evidence.append("password input visible")
    if submit_visible:
        evidence.append("login button visible")
    if login_entry_visible:
        evidence.append("portal login entry visible")
    if authentication_center_visible:
        evidence.append("Authentication Center visible")
    return {
        "username_visible": username_visible,
        "password_visible": password_visible,
        "submit_visible": submit_visible,
        "login_entry_visible": login_entry_visible,
        "authentication_center_visible": authentication_center_visible,
        "business_menu_visible": business_menu_visible,
        "login_context": login_context,
        "form_visible": password_visible and (username_visible or submit_visible),
        "evidence": evidence,
    }


def _login_submit_visible(page: Any) -> bool:
    for name in ["登录", "Login", "LOGIN", "Sign in", "Sign In", "进入系统"]:
        try:
            candidate = page.get_by_role("button", name=name, exact=False)
            if candidate.count() > 0 and candidate.first.is_visible(timeout=300):
                return True
        except PlaywrightError:
            continue
    return _any_visible(page, ["button[type='submit']", "input[type='submit']", ".login-btn", ".login-button"])


def _login_entry_visible(page: Any) -> bool:
    selectors = [
        ".notLogin .login",
        ".not-login .login",
        "a.login",
        "button.login",
        "a[href*='login' i]",
    ]
    if _any_visible(page, selectors):
        return True
    for selector in ["a", "button", "[role='button']", "[role='link']"]:
        try:
            locator = page.locator(selector)
            for index in range(min(locator.count(), 20)):
                candidate = locator.nth(index)
                if not candidate.is_visible(timeout=300):
                    continue
                text = str(candidate.inner_text(timeout=300) or "").strip()
                if re.fullmatch(r"(登录|用户登录|login|sign\s*in)", text, flags=re.IGNORECASE):
                    return True
        except PlaywrightError:
            continue
    return False


def _auth_challenge_evidence(page: Any, lower_text: str) -> list[str]:
    evidence: list[str] = []
    selectors = [
        "input[name*='captcha' i]",
        "input[id*='captcha' i]",
        "input[placeholder*='captcha' i]",
        "input[placeholder*='验证码']",
        "input[name*='otp' i]",
        "input[id*='otp' i]",
        "input[placeholder*='otp' i]",
        "input[name*='sms' i]",
        "input[id*='sms' i]",
        "input[placeholder*='短信']",
        "input[placeholder*='动态码']",
        "input[placeholder*='一次性密码']",
        "input[placeholder*='one-time' i]",
    ]
    if _any_visible(page, selectors):
        evidence.append("visible captcha/otp/sms input")
    if evidence and any(token in lower_text for token in ["验证码", "captcha", "otp", "one-time password", "短信", "动态码", "二次认证", "mfa"]):
        return evidence
    return evidence


def _success_evidence(page: Any, lower_text: str, url: str, title: str, login_form: dict[str, Any]) -> list[str]:
    evidence: list[str] = []
    has_app_shell = _any_visible(page, APP_SHELL_SELECTORS)
    has_strong_marker = False
    has_weak_marker = False
    if has_app_shell:
        evidence.append("main menu visible")
    for marker in APP_SUCCESS_MARKERS:
        if marker.lower() in lower_text:
            evidence.append(marker)
            has_strong_marker = True
            break
    for marker in WEAK_APP_SUCCESS_MARKERS:
        if marker.lower() in lower_text:
            evidence.append(marker)
            has_weak_marker = True
            break
    portal_evidence = _portal_logged_in_evidence(page, lower_text, login_form)
    if portal_evidence:
        evidence.extend(portal_evidence)
        has_strong_marker = True
    if login_form.get("login_entry_visible") and not has_strong_marker:
        return []
    if "login" not in url and "登录" not in title and not login_form["form_visible"] and (has_app_shell or has_strong_marker or has_weak_marker):
        evidence.append("url left login page")
    return list(dict.fromkeys(evidence))


def _portal_logged_in_evidence(page: Any, lower_text: str, login_form: dict[str, Any]) -> list[str]:
    if login_form.get("form_visible"):
        return []
    evidence: list[str] = []
    if "系统导航" in lower_text:
        evidence.append("portal system navigation visible")
    if "系统导航" in lower_text and _any_visible(page, [".TopMenu", ".topMenu", ".top-menu", ".HomeComponent"]):
        evidence.append("portal navigation shell visible")
    if not login_form.get("login_entry_visible") and _portal_user_identity_visible(page):
        evidence.append("portal user identity visible")
    return evidence


def _portal_user_identity_visible(page: Any) -> bool:
    try:
        for selector in PORTAL_USER_SELECTORS:
            locator = page.locator(selector)
            for index in range(min(locator.count(), 10)):
                candidate = locator.nth(index)
                if not candidate.is_visible(timeout=300):
                    continue
                text = str(candidate.inner_text(timeout=300) or "").strip()
                if _looks_like_user_identity(text):
                    return True
    except PlaywrightError:
        return False
    return False


def _looks_like_user_identity(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    if not compact or len(compact) > 32:
        return False
    rejected = {
        "登录",
        "用户登录",
        "退出",
        "退出登录",
        "退出系统",
        "首页",
        "系统导航",
        "单位导航",
        "新闻公告",
        "移动应用中心",
        "满意度调研",
    }
    if compact in rejected:
        return False
    return bool(re.search(r"[\u4e00-\u9fffA-Za-z]", compact))


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
