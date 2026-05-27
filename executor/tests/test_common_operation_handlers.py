from collections.abc import Iterator
from pathlib import Path
import sys

import pytest
from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from executor.aitp_executor.handlers.date_picker_handler import DatePickerHandler
from executor.aitp_executor.handlers.dropdown_handler import DropdownHandler
from executor.aitp_executor.handlers.form_fill_handler import FormFillHandler
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
