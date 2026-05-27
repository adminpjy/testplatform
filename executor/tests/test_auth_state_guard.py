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
        LoginGoalExecutor().execute_login_goal(page, {"action": "business_goal", "target": "登录系统"}, {})
    assert getattr(exc_info.value, "failure_type") == "login_failed"
    assert getattr(exc_info.value, "details")["auth_state"]["remainingRetries"] == 3


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
