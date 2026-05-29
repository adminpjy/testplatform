from collections.abc import Iterator
from pathlib import Path
import sys

import pytest
from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from executor.aitp_executor.handlers.date_picker_handler import DatePickerHandler
from executor.aitp_executor.handlers.dropdown_handler import DropdownHandler
from executor.aitp_executor.handlers.form_fill_handler import FormFillHandler
from executor.aitp_executor.handlers.assertion_handler import AssertionHandler
from executor.aitp_executor.locator.element_locator import ElementLocator
from executor.aitp_executor.handlers.table_handler import TableHandler
from executor.aitp_executor.handlers.table_row_action_handler import TableRowActionHandler


@pytest.fixture(scope="module")
def page() -> Iterator[Page]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        yield page
        context.close()
        browser.close()


def _runtime_context() -> tuple[dict, list[dict], list[dict]]:
    events: list[dict] = []
    debug: list[dict] = []
    return (
        {
            "step_id": "S001",
            "step_number": 1,
            "emit_runtime": lambda message_type, phase, content, method, metadata: events.append(
                {"type": message_type, "phase": phase, "content": content, "method": method, "metadata": metadata}
            ),
            "append_debug": debug.append,
        },
        events,
        debug,
    )


def test_table_handler_counts_only_data_rows(page: Page) -> None:
    page.set_content(
        """
        <table>
          <thead><tr><th>编号</th><th>操作</th></tr></thead>
          <tbody>
            <tr><td>A001</td><td><button>详情</button></td></tr>
            <tr class="summary"><td>合计</td><td></td></tr>
            <tr><td>下一页</td><td>每页 10 条</td></tr>
          </tbody>
        </table>
        """
    )
    context, events, debug = _runtime_context()
    outcome = TableHandler().wait_for_table(
        page,
        step={"operationIntent": {"intent": "query_list"}},
        execution_context=context,
    )
    assert TableHandler().row_count(page) == 1
    assert outcome["locator_strategy"] == "table_detection"
    assert any("命中规则" in event["content"] for event in events)
    assert any(item.get("phase") == "handler_ability_resolve" for item in debug)


def test_table_row_action_prefers_process_action_over_flow_view(page: Page) -> None:
    page.set_content(
        """
        <table><tbody>
          <tr>
            <td>A001</td>
            <td>
              <button onclick="window.clicked='flow'">查看审批流程</button>
              <button onclick="window.clicked='approve'">审批</button>
            </td>
          </tr>
        </tbody></table>
        """
    )
    context, _events, _debug = _runtime_context()
    outcome = TableRowActionHandler().click_row_action(
        page,
        step={"target": "审批通过", "operationIntent": {"intent": "click_table_row_action"}},
        execution_context=context,
    )
    assert outcome["locator_strategy"] == "table_row_action"
    assert page.evaluate("window.clicked") == "approve"


def test_dropdown_handler_selects_native_select(page: Page) -> None:
    page.set_content(
        """
        <label for="status">状态</label>
        <select id="status"><option>停用</option><option>启用</option></select>
        """
    )
    context, _events, _debug = _runtime_context()
    outcome = DropdownHandler().select(
        page,
        step={"target": "状态", "value": "启用", "operationIntent": {"intent": "select_dropdown"}},
        execution_context=context,
    )
    assert outcome["locator_strategy"] in {"playwright_label_exact", "native_select"}
    assert page.locator("#status").input_value() == "启用"


def test_date_picker_handler_uses_direct_input(page: Page) -> None:
    page.set_content('<label for="start">开始日期</label><input id="start" />')
    context, _events, _debug = _runtime_context()
    DatePickerHandler().select_date(
        page,
        step={"target": "开始日期", "value": "2026-06-01", "operationIntent": {"intent": "select_date"}},
        execution_context=context,
    )
    assert page.locator("#start").input_value() == "2026-06-01"


def test_form_fill_handler_uses_default_rule_data(page: Page) -> None:
    page.set_content(
        """
        <label for="username">用户名</label><input id="username" />
        <label for="phone">手机号</label><input id="phone" />
        """
    )
    context, events, _debug = _runtime_context()
    outcome = FormFillHandler().fill_form(
        page,
        step={"operationIntent": {"intent": "fill_form"}},
        execution_context=context,
    )
    assert outcome["locator_strategy"] == "auto_form_filler"
    assert page.locator("#username").input_value().startswith("test_ai_")
    assert page.locator("#phone").input_value() == "13800000000"
    assert any("默认测试数据" in event["content"] for event in events)


def test_form_fill_handler_fails_when_no_fields_are_filled(page: Page) -> None:
    page.set_content("<main><button>保存</button></main>")
    context, _events, _debug = _runtime_context()
    with pytest.raises(RuntimeError, match="form_no_fields_detected"):
        FormFillHandler().fill_form(
            page,
            step={"action": "fill_form", "target": "新增用户表单"},
            execution_context=context,
        )


def test_form_fill_handler_fails_when_all_fields_are_skipped(page: Page) -> None:
    page.set_content('<label for="nickname">昵称</label><input id="nickname" />')
    context, _events, _debug = _runtime_context()
    with pytest.raises(RuntimeError, match="form_no_fields_filled"):
        FormFillHandler().fill_form(
            page,
            step={"action": "fill_form", "target": "新增用户表单"},
            execution_context=context,
        )


def test_form_fill_handler_opens_login_entry_before_filling_credentials(page: Page) -> None:
    page.set_content(
        """
        <main id="app">
          <a href="#" onclick="document.querySelector('#app').innerHTML = `
            <input id='j_username' name='j_username' value='LoginName/UserAccount/ADAccount/Mobile' />
            <input id='j_password' name='j_password' type='password' />
            <button>Login</button>
          `">登录</a>
        </main>
        """
    )
    context, _events, _debug = _runtime_context()
    outcome = FormFillHandler().fill_form(
        page,
        step={"action": "fill_form", "target": "登录表单"},
        dsl={"testData": {"username": "tester01", "password": "secret123"}},
        execution_context=context,
    )
    assert outcome["locator_strategy"] == "login_form_filler"
    assert page.locator("#j_username").input_value() == "tester01"
    assert page.locator("#j_password").input_value() == "secret123"
    assert '"opened_login_entry": true' in outcome["reason"]
    assert "secret123" not in outcome["reason"]


def test_login_form_fill_fails_when_credentials_are_missing(page: Page) -> None:
    page.set_content(
        """
        <main>
          <input name="username" />
          <input type="password" />
          <button>Login</button>
        </main>
        """
    )
    context, _events, _debug = _runtime_context()
    with pytest.raises(RuntimeError, match="login_credentials_missing:password"):
        FormFillHandler().fill_form(
            page,
            step={"action": "fill_form", "target": "登录表单"},
            dsl={"testData": {"username": "tester01"}},
            execution_context=context,
        )


def test_assertion_handler_wait_for_text_uses_text_field(page: Page) -> None:
    page.set_content("<main><h1>工作台</h1></main>")
    context, _events, _debug = _runtime_context()
    outcome = AssertionHandler().assert_step(
        page,
        step={"action": "wait_for_text", "target": "登录成功标识", "text": "工作台"},
        execution_context=context,
    )
    assert outcome["element_ref"] == "工作台"


def test_login_button_target_matches_english_login_button(page: Page) -> None:
    page.set_content(
        """
        <main>
          <input name="username" value="tester01" />
          <input type="password" value="secret123" />
          <button onclick="window.submitted = true">Login</button>
        </main>
        """
    )

    result = ElementLocator().locate(page, action="click", target="登录按钮")

    assert result.locator is not None
    assert result.element_ref == "Login"
    assert result.confidence >= 0.62
