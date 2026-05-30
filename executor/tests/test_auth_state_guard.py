from collections.abc import Iterator
from pathlib import Path
import sys

import pytest
from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from executor.aitp_executor.observer.auth_state_detector import AuthStateDetector
from executor.aitp_executor.goal.login_goal_executor import LoginGoalExecutor
from executor.aitp_executor.goal.protected_step_guard import ProtectedStepGuard
from executor.aitp_executor.reports.artifact_writer import ArtifactWriter
from executor.aitp_executor.runner.case_runner import CaseRunner


@pytest.fixture(scope="module")
def page() -> Iterator[Page]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        yield page
        context.close()
        browser.close()


def test_auth_state_detects_login_failed_page(page: Page) -> None:
    page.set_content(
        """
        <main>
          <p>Login was failed, and you have 4 retries.</p>
          <p>Possible reasons: Wrong user name or password. Please contact the administrator.</p>
          <input name="username" value="tester" />
          <input type="password" placeholder="Password" />
          <button>Login</button>
        </main>
        """
    )
    result = AuthStateDetector().detect_auth_state(page)
    assert result.authState == "login_failed"
    assert result.failureType == "login_failed"
    assert result.confidence >= 0.9
    assert result.remainingRetries == 4
    assert any("login was failed" in item.lower() for item in result.evidence)


def test_auth_state_detects_login_captcha_required(page: Page) -> None:
    page.set_content(
        """
        <main>
          <p>Login was failed, and you have 3 retries.</p>
          <p>Wrong user name or password.</p>
          <label>验证码</label>
          <input name="captcha" placeholder="请输入验证码" />
          <input name="username" />
          <input type="password" placeholder="Password" />
          <button>Login</button>
        </main>
        """
    )
    result = AuthStateDetector().detect_auth_state(page)
    assert result.authState == "login_requires_manual_action"
    assert result.failureType == "login_captcha_required"
    assert result.remainingRetries == 3
    assert result.shouldStopProtectedSteps is True
    assert result.requiresHumanAction is True


def test_auth_state_does_not_treat_alternate_auth_links_as_challenge(page: Page) -> None:
    page.set_content(
        """
        <main>
          <button>OTP</button>
          <p>About OTP</p>
          <p>code scanning authentication</p>
          <input name="username" />
          <input type="password" placeholder="Password" />
          <button>Login</button>
        </main>
        """
    )
    result = AuthStateDetector().detect_auth_state(page)
    assert result.authState == "login_page"
    assert result.failureType == "auth_state_not_logged_in"


def test_auth_state_detects_visible_otp_challenge(page: Page) -> None:
    page.set_content(
        """
        <main>
          <input name="username" />
          <input type="password" placeholder="Password" />
          <label>OTP</label>
          <input name="j_otpcode" placeholder="OTP(One-Time Password)" />
          <button>Login</button>
        </main>
        """
    )
    result = AuthStateDetector().detect_auth_state(page)
    assert result.authState == "login_requires_manual_action"
    assert result.failureType == "login_captcha_required"
    assert result.requiresHumanAction is True


def test_auth_state_detects_login_page_without_error(page: Page) -> None:
    page.set_content(
        """
        <main>
          <input name="username" />
          <input type="password" placeholder="Password" />
          <button>Login</button>
        </main>
        """
    )
    result = AuthStateDetector().detect_auth_state(page)
    assert result.authState == "login_page"
    assert result.failureType == "auth_state_not_logged_in"
    assert result.shouldContinue is False


def test_auth_state_detects_login_success(page: Page) -> None:
    page.set_content(
        """
        <header><button>退出登录</button></header>
        <aside role="menu"><button>工作台</button><button>我的待办</button></aside>
        <main><h1>首页</h1></main>
        """
    )
    result = AuthStateDetector().detect_auth_state(page)
    assert result.authState == "logged_in"
    assert result.shouldContinue is True


def test_auth_state_detects_logged_in_portal_home(page: Page) -> None:
    page.set_content(
        """
        <header class="TopMenu">
          <a>新闻公告</a>
          <a>单位导航</a>
          <a>系统导航</a>
          <a class="login1">中燕信息</a>
          <a class="login1">测试用户</a>
        </header>
        <main class="HomeComponent">
          <section>系统导航</section>
          <section>办公自动化</section>
        </main>
        """
    )
    result = AuthStateDetector().detect_auth_state(page)
    assert result.authState == "logged_in"
    assert result.failureType is None
    assert any("portal system navigation" in item for item in result.evidence)


def test_auth_state_does_not_treat_anonymous_portal_home_as_logged_in(page: Page) -> None:
    page.set_content(
        """
        <header class="TopMenu">
          <a>首页</a>
          <a>新闻公告</a>
          <a>单位导航</a>
          <a class="login">登录</a>
        </header>
        <main class="HomeComponent">
          <input class="ant-input" />
          <button>搜一下</button>
        </main>
        """
    )
    result = AuthStateDetector().detect_auth_state(page)
    assert result.authState == "login_page"
    assert result.failureType == "auth_state_not_logged_in"
    assert "portal login entry visible" in result.evidence


def test_auth_state_does_not_treat_business_dashboard_canvas_as_captcha(page: Page) -> None:
    page.set_content(
        """
        <header class="home_header">
          <span>中燕信息一体化运营平台</span>
          <button>退出系统</button>
          <span class="userName">测试用户</span>
        </header>
        <aside id="layout_sider" class="el-aside">
          <ul class="el-menu" role="menu">
            <li>工作台</li>
            <li>我的待办</li>
          </ul>
        </aside>
        <main>
          <h1>首页</h1>
          <input role="combobox" value="2026-05" />
          <div id="map-container"><canvas data-zr-dom-id="zr_0"></canvas></div>
        </main>
        """
    )
    result = AuthStateDetector().detect_auth_state(page)
    assert result.authState == "logged_in"
    assert result.failureType is None
    assert "captcha image visible" not in result.evidence


def test_auth_state_detects_low_risk_login_interruption(page: Page) -> None:
    page.set_content(
        """
        <main>
          <p>用户账号将于 5 天后到期。</p>
          <button>继续访问</button>
        </main>
        """
    )
    result = AuthStateDetector().detect_auth_state(page)
    assert result.authState == "login_interrupted"
    assert result.shouldContinue is True


def test_auth_state_detects_force_change_password(page: Page) -> None:
    page.set_content(
        """
        <main>
          <h1>首次登录必须修改密码</h1>
          <input type="password" />
          <button>确定</button>
        </main>
        """
    )
    result = AuthStateDetector().detect_auth_state(page)
    assert result.authState == "login_requires_manual_action"
    assert result.failureType == "login_requires_manual_action"
    assert result.shouldContinue is False


def test_business_step_is_blocked_after_login_failure(page: Page, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLAYWRIGHT_WAIT_NETWORK_IDLE", "false")
    monkeypatch.setenv("PAGE_READY_TIMEOUT_MS", "1000")
    page.set_content(
        """
        <main>
          <p>Login was failed, and you have 3 retries.</p>
          <p>Wrong user name or password.</p>
          <input name="username" />
          <input type="password" placeholder="Password" />
          <button>Login</button>
        </main>
        """
    )
    writer = ArtifactWriter("TEST-AUTH-GUARD")
    result = CaseRunner()._run_step(
        page,
        writer,
        3,
        {"id": "3", "action": "navigate_path", "target": "工作台/我的待办", "pathSegments": ["工作台", "我的待办"]},
        {"settings": {}},
    )
    assert result["status"] == "failed"
    assert result["failure_type"] == "protected_step_blocked_by_login_failure"
    assert result["failure_details"]["rootCause"] == "login_failed"
    assert result["failure_details"]["remainingRetries"] == 3
    assert result["locator_strategy"] == "protected_step_guard"
    runtime_text = writer.path("runtime-stream.jsonl").read_text(encoding="utf-8")
    assert "后续业务步骤不会继续执行" in runtime_text
    assert "正在查找一级菜单" not in runtime_text


def test_business_step_is_blocked_after_login_captcha(page: Page, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLAYWRIGHT_WAIT_NETWORK_IDLE", "false")
    monkeypatch.setenv("PAGE_READY_TIMEOUT_MS", "1000")
    page.set_content(
        """
        <main>
          <p>Login was failed, and you have 3 retries.</p>
          <p>Wrong user name or password.</p>
          <label>验证码</label>
          <input id="captcha" placeholder="verification code" />
          <input name="username" />
          <input type="password" placeholder="Password" />
          <button>Login</button>
        </main>
        """
    )
    writer = ArtifactWriter("TEST-AUTH-CAPTCHA-GUARD")
    result = CaseRunner()._run_step(
        page,
        writer,
        3,
        {"id": "3", "action": "navigate_path", "target": "工作台/我的待办", "pathSegments": ["工作台", "我的待办"]},
        {"settings": {}},
    )
    assert result["status"] == "failed"
    assert result["failure_type"] == "protected_step_blocked_by_auth_challenge"
    assert result["failure_details"]["rootCause"] == "login_captcha_required"
    assert result["locator_strategy"] == "protected_step_guard"
    runtime_text = writer.path("runtime-stream.jsonl").read_text(encoding="utf-8")
    assert "后续业务步骤" in runtime_text
    assert "正在查找一级菜单" not in runtime_text


def test_open_url_is_not_blocked_by_auth_guard_even_with_auth_precondition(page: Page) -> None:
    page.set_content(
        """
        <main>
          <button>OTP</button>
          <p>About OTP</p>
          <p>About code scanning authentication</p>
          <input name="username" />
          <input type="password" placeholder="Password" />
          <button>Login</button>
        </main>
        """
    )
    result = ProtectedStepGuard().check_before_step(
        {
            "action": "open_url",
            "target": "https://work.bypc.com.cn",
            "preconditions": {"authState": "logged_in"},
            "operationIntent": {"intent": "fill_form"},
        },
        page,
    )
    assert result.allowed is True


def test_login_submit_step_is_not_blocked_on_login_page(page: Page) -> None:
    page.set_content(
        """
        <main>
          <input name="username" value="tester" />
          <input type="password" value="secret" />
          <button>Login</button>
        </main>
        """
    )
    result = ProtectedStepGuard().check_before_step(
        {
            "action": "click",
            "target": "登录按钮",
            "operationIntent": {"intent": "enter_page"},
        },
        page,
    )
    assert result.allowed is True
    assert result.reason == "step does not require authenticated business page"


def test_case_runner_login_submit_clicks_login_and_verifies(page: Page, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLAYWRIGHT_WAIT_NETWORK_IDLE", "false")
    monkeypatch.setenv("PAGE_READY_TIMEOUT_MS", "1000")
    monkeypatch.setenv("LOGIN_RESULT_WAIT_MS", "200")
    monkeypatch.setenv("LOGIN_RESULT_RECHECK_TIMES", "0")
    page.set_content(
        """
        <main>
          <input name="username" value="tester" />
          <input type="password" value="secret" />
          <button onclick="document.body.innerHTML='<header><button>退出登录</button></header><aside role=menu><button>系统导航</button></aside><main><h1>首页</h1></main>'">Login</button>
        </main>
        """
    )
    writer = ArtifactWriter("TEST-LOGIN-SUBMIT")
    result = CaseRunner()._run_step(
        page,
        writer,
        3,
        {"id": "3", "action": "click", "target": "登录按钮", "operationIntent": {"intent": "enter_page"}},
        {"settings": {}},
    )
    assert result["status"] == "passed"
    assert result["locator_strategy"] == "login_submit"
    assert result["failure_type"] is None


def test_login_goal_opens_portal_login_entry_before_resolving_form(page: Page, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGIN_RESULT_WAIT_MS", "200")
    monkeypatch.setenv("LOGIN_RESULT_RECHECK_TIMES", "0")
    page.set_content(
        """
        <header>
          <input class="ant-input" />
          <button>搜一下</button>
          <a class="login" onclick="document.body.innerHTML='<main><input name=&quot;j_username&quot; /><input type=&quot;password&quot; name=&quot;j_password&quot; /><button onclick=&quot;document.body.innerHTML=\\'<header><button>退出登录</button></header><aside role=menu><button>系统导航</button></aside><main><h1>首页</h1></main>\\'&quot;>Login</button></main>'">登录</a>
        </header>
        """
    )
    outcome = LoginGoalExecutor().execute_login_goal(
        page,
        {"action": "business_goal", "target": "用户登录", "credentials": {"username": "tester", "password": "secret"}},
        {},
    )
    assert outcome["locator_strategy"] == "generic_login_form"
    assert outcome["auth_state"]["authState"] == "logged_in"


def test_case_runner_uses_popup_page_for_navigation_evidence(page: Page, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLAYWRIGHT_WAIT_NETWORK_IDLE", "false")
    monkeypatch.setenv("PAGE_READY_TIMEOUT_MS", "1000")
    page.set_content(
        """
        <header class="TopMenu">
          <a>系统导航</a>
          <a class="login1">测试用户</a>
        </header>
        <main class="HomeComponent">
          <button role="tab" aria-selected="true">办公自动化(14)</button>
          <button onclick="const w=window.open('about:blank', '_blank'); w.document.write('<!doctype html><title>中国石化公文管理系统</title><h1>中国石化公文管理系统</h1><main>业务首页 操作</main>'); w.document.close();">中国石化公文管理系统</button>
        </main>
        """
    )
    holder = {"page": page}
    writer = ArtifactWriter("TEST-POPUP-NAVIGATION")

    try:
        result = CaseRunner()._run_step(
            page,
            writer,
            3,
            {
                "id": "3",
                "action": "navigate_path",
                "target": "系统导航/办公自动化/中国石化公文管理系统",
                "pathSegments": ["系统导航", "办公自动化", "中国石化公文管理系统"],
                "preconditions": {"authState": "logged_in"},
            },
            {"settings": {}},
            page_holder=holder,
        )
        assert result["status"] == "passed"
        assert holder["page"] is not page
        assert "中国石化公文管理系统" in writer.dom_snapshot_path(3).read_text(encoding="utf-8")
        assert "active_page.changed" in writer.path("execution-trace.jsonl").read_text(encoding="utf-8")
    finally:
        if holder["page"] is not page:
            holder["page"].close()


def test_login_form_resolver_does_not_treat_portal_search_as_username(page: Page) -> None:
    page.set_content(
        """
        <header>
          <input class="ant-input" />
          <button>搜一下</button>
          <a class="login">登录</a>
        </header>
        """
    )
    result = LoginGoalExecutor().login_resolver.resolve(page)
    assert result.username_locator is None
    assert result.password_locator is None


def test_login_goal_fails_when_submit_returns_error(page: Page, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGIN_RESULT_WAIT_MS", "200")
    monkeypatch.setenv("LOGIN_RESULT_RECHECK_TIMES", "0")
    page.set_content(
        """
        <main>
          <input name="username" />
          <input type="password" placeholder="Password" />
          <button onclick="document.querySelector('#error').hidden=false">Login</button>
          <p id="error" hidden>Login was failed, and you have 3 retries. Wrong user name or password.</p>
        </main>
        """
    )
    with pytest.raises(RuntimeError) as exc_info:
        LoginGoalExecutor().execute_login_goal(
            page,
            {"action": "business_goal", "target": "登录系统", "credentials": {"username": "tester", "password": "secret"}},
            {},
        )
    assert getattr(exc_info.value, "failure_type") == "login_failed"
    assert getattr(exc_info.value, "details")["auth_state"]["remainingRetries"] == 3


def test_login_goal_stops_when_captcha_is_required(page: Page, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGIN_RESULT_WAIT_MS", "200")
    monkeypatch.setenv("LOGIN_RESULT_RECHECK_TIMES", "0")
    page.set_content(
        """
        <main>
          <input name="username" />
          <input type="password" placeholder="Password" />
          <button onclick="document.querySelector('#captcha').hidden=false">Login</button>
          <section id="captcha" hidden>
            <p>Login was failed, and you have 3 retries.</p>
            <label>验证码</label>
            <input name="captcha" placeholder="verification code" />
          </section>
        </main>
        """
    )
    with pytest.raises(RuntimeError) as exc_info:
        LoginGoalExecutor().execute_login_goal(
            page,
            {"action": "business_goal", "target": "登录系统", "credentials": {"username": "tester", "password": "secret"}},
            {},
        )
    assert getattr(exc_info.value, "failure_type") == "login_captcha_required"
    auth_state = getattr(exc_info.value, "details")["auth_state"]
    assert auth_state["authState"] == "login_requires_manual_action"


def test_protected_guard_allows_business_page_without_menu_target(page: Page) -> None:
    page.set_content(
        """
        <aside role="menu"><button>系统管理</button></aside>
        <main><h1>首页</h1></main>
        """
    )
    result = ProtectedStepGuard().check_before_step({"action": "navigate_path", "target": "工作台/我的待办"}, page)
    assert result.allowed is True
    assert result.authState == "logged_in"


def test_protected_guard_allows_after_manual_challenge_completion(page: Page) -> None:
    page.set_content(
        """
        <header><button>退出登录</button></header>
        <aside role="menu"><button>工作台</button><button>我的待办</button></aside>
        <main><h1>首页</h1></main>
        """
    )
    result = ProtectedStepGuard().check_before_step({"action": "navigate_path", "target": "工作台/我的待办"}, page)
    assert result.allowed is True
    assert result.authState == "logged_in"
