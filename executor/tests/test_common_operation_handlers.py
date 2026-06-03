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
from executor.aitp_executor.handlers.approval_workflow_handler import ApprovalWorkflowHandler
from executor.aitp_executor.locator.element_locator import ElementLocator
from executor.aitp_executor.handlers.table_handler import TableHandler
from executor.aitp_executor.handlers.query_handler import QueryHandler
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


def test_query_handler_uses_query_conditions_and_semantic_form_label(page: Page) -> None:
    page.set_content(
        """
        <form>
          <div class="el-form-item">
            <label class="el-form-item__label">实例号</label>
            <div class="el-form-item__content"><input id="instanceNo" /></div>
          </div>
          <button type="button">查询</button>
        </form>
        <table><tbody>
          <tr><td>1</td><td>26097</td><td>杨得草，张龙加班申请</td></tr>
        </tbody></table>
        """
    )
    context, _events, debug = _runtime_context()

    outcome = QueryHandler().execute(
        page,
        step={"action": "query_table", "queryConditions": {"实例号": "26097"}, "operationIntent": {"intent": "query_list"}},
        execution_context=context,
    )

    assert page.locator("#instanceNo").input_value() == "26097"
    assert '"matched_rows": 1' in outcome["reason"]
    assert any(item.get("criteriaKeys") == ["实例号"] for item in debug)


def test_query_count_does_not_empty_pass_todo_when_still_on_portal_home(page: Page) -> None:
    page.set_content(
        """
        <aside><button>工作台</button><button>我的待办 <span>14</span></button></aside>
        <main><h1>门户首页</h1><section>常用应用</section></main>
        """
    )

    with pytest.raises(AssertionError, match="target_list_page_not_reached"):
        QueryHandler().count_rows(
            page,
            step={"action": "query_table_count", "target": "我的待办列表", "emptyStrategy": "pass"},
        )


def test_open_table_row_uses_previous_query_criteria(page: Page) -> None:
    page.set_content(
        """
        <table><tbody>
          <tr><td>1</td><td>26110</td><td><a href="#" onclick="window.opened='26110'">第一条</a></td></tr>
          <tr><td>2</td><td>26097</td><td><a href="#" onclick="window.opened='26097'">杨得草，张龙加班申请</a></td></tr>
        </tbody></table>
        """
    )
    dsl = {
        "steps": [
            {"action": "query_table", "queryConditions": {"实例号": "26097"}, "operationIntent": {"intent": "query_list"}},
            {"action": "open_table_row", "target": "我的待办列表", "operationIntent": {"intent": "open_table_row"}},
        ]
    }
    context, _events, _debug = _runtime_context()
    context["step_number"] = 2

    outcome = TableRowActionHandler().open_first_row(
        page,
        step=dsl["steps"][1],
        dsl=dsl,
        execution_context=context,
    )

    assert page.evaluate("window.opened") == "26097"
    assert outcome["element_ref"] == "row:实例号=26097"


def test_process_table_rows_opens_new_page_and_runs_approval_row_steps(page: Page) -> None:
    page.set_content(
        """
        <table><tbody>
          <tr><td>ZYXX202659</td><td><a href="#" onclick="
            const w = window.open('', '_blank');
            w.document.write(`<main>
              <label for='opinion'>我的意见</label>
              <textarea id='opinion'></textarea>
              <button onclick='window.submitted = document.querySelector(&quot;#opinion&quot;).value; document.body.insertAdjacentHTML(&quot;beforeend&quot;, &quot;<div>审批成功</div>&quot;)'>提交</button>
            </main>`);
            w.document.close();
          ">相关办理人处理</a></td></tr>
        </tbody></table>
        """
    )
    try:
        screenshots: list[dict] = []
        holder = {"page": page}
        context, _events, _debug = _runtime_context()
        context.update(
            {
                "get_active_page": lambda: holder["page"],
                "set_active_page": lambda new_page, metadata=None: holder.update({"page": new_page}),
                "capture_process_screenshot": lambda label, metadata=None, page=None: screenshots.append(
                    {"label": label, "metadata": metadata or {}, "url": (page or holder["page"]).url}
                ),
            }
        )

        approval_handler = ApprovalWorkflowHandler()

        def execute_sub_step(sub_step: dict, sub_page: Page, metadata: dict | None = None) -> dict:
            outcome = approval_handler.approval_pass(sub_page, step=sub_step, dsl={}, execution_context=context)
            assert sub_page.locator("#opinion").input_value() == "按要求执行"
            assert sub_page.evaluate("window.submitted") == "按要求执行"
            return outcome

        context["execute_sub_step"] = execute_sub_step
        outcome = TableRowActionHandler().process_rows(
            page,
            step={
                "action": "process_table_rows",
                "target": "我的待办列表",
                "loopPolicy": {
                    "rowEntryLabels": ["相关办理人处理"],
                    "rowSteps": [
                        {
                            "action": "business_goal",
                            "target": "审批通过",
                            "intent": "approval_pass",
                            "value": "按要求执行",
                        }
                    ],
                },
                "operationIntent": {"intent": "process_table_rows"},
            },
            execution_context=context,
        )

        assert outcome["locator_strategy"] == "table_row_loop"
        assert '"processed_rows": 1' in outcome["reason"]
        assert holder["page"] is page
        assert any(item["label"] == "row_001_opened" for item in screenshots)
        assert any(item["label"] == "row_001_substep_001_after" for item in screenshots)
    finally:
        for opened_page in list(page.context.pages):
            if opened_page is not page and not opened_page.is_closed():
                opened_page.close()


def test_approval_history_dialog_is_entry_not_submit_surface(page: Page) -> None:
    page.set_content(
        """
        <main>
          <script>
            function submitApproval(event) {
              event.preventDefault();
              window.submitted = document.querySelector("#opinion").value;
              document.body.insertAdjacentHTML("beforeend", "<div class='messager-window'><div class='messager-body'>提交成功</div><button>确定</button></div>");
            }
            function openApprovalForm() {
              document.body.insertAdjacentHTML("beforeend", `
                <section id="realForm">
                  <label for="opinion">审批意见</label>
                  <textarea id="opinion"></textarea>
                  <a id="btnAudit" href="#" onclick="submitApproval(event)">提交</a>
                </section>
              `);
            }
          </script>
          <div class="el-dialog" style="display:block">
            <h2>加班申请</h2>
            <table>
              <thead><tr><th>审批状态</th><th>审批结果</th></tr></thead>
              <tbody><tr><td>待办</td><td></td></tr></tbody>
            </table>
            <button id="entry" onclick="openApprovalForm()">审批</button>
          </div>
        </main>
        """
    )

    outcome = ApprovalWorkflowHandler().approval_pass(
        page,
        step={"target": "审批通过", "value": "按要求执行", "operationIntent": {"intent": "approval_pass"}},
        dsl={},
    )

    assert outcome["locator_strategy"] == "approval_pass"
    assert page.evaluate("window.submitted") == "按要求执行"


def test_approval_success_dialog_wins_over_select_placeholder(page: Page) -> None:
    page.set_content(
        """
        <main>
          <h1>员工休假申请流程</h1>
          <label for="opinion">审批意见</label>
          <textarea id="opinion"></textarea>
          <button type="button">请选择</button>
          <a id="btnAudit" href="#" onclick="
            window.submitted = document.querySelector('#opinion').value;
            document.body.insertAdjacentHTML('beforeend', '<div class=&quot;messager-window&quot;><div class=&quot;messager-body&quot;>提交成功</div><button>确定</button></div>');
            return false;
          ">提交</a>
        </main>
        """
    )

    outcome = ApprovalWorkflowHandler().approval_pass(
        page,
        step={"target": "审批通过", "value": "按要求执行", "operationIntent": {"intent": "approval_pass"}},
        dsl={},
    )

    assert outcome["locator_strategy"] == "approval_pass"
    assert page.evaluate("window.submitted") == "按要求执行"
    assert "approval_validation_failed" not in outcome["reason"]


def test_process_table_rows_does_not_empty_pass_todo_when_still_on_portal_home(page: Page) -> None:
    page.set_content(
        """
        <aside><button>工作台</button><button>我的待办 <span>14</span></button></aside>
        <main><h1>门户首页</h1><section>常用应用</section></main>
        """
    )

    with pytest.raises(AssertionError, match="target_list_page_not_reached"):
        TableRowActionHandler().process_rows(
            page,
            step={
                "action": "process_table_rows",
                "target": "我的待办列表",
                "loopPolicy": {"emptyStrategy": "pass"},
                "operationIntent": {"intent": "process_table_rows"},
            },
        )


def test_process_table_rows_allows_empty_todo_on_real_list_page(page: Page) -> None:
    page.set_content(
        """
        <main>
          <h1>我的待办</h1>
          <section class="ant-table">
            <div class="ant-table-thead">流程标题 当前处理人 操作</div>
            <div class="ant-empty">暂无数据</div>
          </section>
          <footer>共 0 条</footer>
        </main>
        """
    )

    outcome = TableRowActionHandler().process_rows(
        page,
        step={
            "action": "process_table_rows",
            "target": "我的待办列表",
            "loopPolicy": {"emptyStrategy": "pass"},
            "operationIntent": {"intent": "process_table_rows"},
        },
    )

    assert outcome["locator_strategy"] == "table_row_loop"
    assert '"status": "empty_pass"' in outcome["reason"]


def test_process_table_rows_refreshes_stale_list_after_popup_completion(page: Page) -> None:
    page.set_content(
        """
        <script>
          window.openedRows = [];
          window.processedRows = [];
          window.refreshCount = 0;
          function refreshList() {
            window.refreshCount += 1;
            for (const id of window.processedRows) {
              const row = document.querySelector(`[data-row="${id}"]`);
              if (row) row.remove();
            }
          }
          function openApproval(id) {
            window.openedRows.push(id);
            const w = window.open('', '_blank');
            w.document.write(`<main>
              <button onclick="window.opener.processedRows.push('${id}')">提交</button>
            </main>`);
            w.document.close();
          }
        </script>
        <button type="button" onclick="refreshList()">刷新</button>
        <table class="el-table__body"><tbody>
          <tr data-row="A001"><td>A001</td><td><a href="#" onclick="openApproval('A001'); return false;">办理</a></td></tr>
          <tr data-row="A002"><td>A002</td><td><a href="#" onclick="openApproval('A002'); return false;">办理</a></td></tr>
        </tbody></table>
        """
    )
    try:
        holder = {"page": page}
        context, _events, _debug = _runtime_context()
        context.update(
            {
                "get_active_page": lambda: holder["page"],
                "set_active_page": lambda new_page, metadata=None: holder.update({"page": new_page}),
                "capture_process_screenshot": lambda label, metadata=None, page=None: None,
            }
        )

        def execute_sub_step(sub_step: dict, sub_page: Page, metadata: dict | None = None) -> dict:
            sub_page.get_by_role("button", name="提交").click()
            return {"locator_strategy": "approval_submit", "element_ref": "提交", "reason": "ok"}

        context["execute_sub_step"] = execute_sub_step
        outcome = TableRowActionHandler().process_rows(
            page,
            step={
                "action": "process_table_rows",
                "target": "我的待办列表",
                "loopPolicy": {
                    "maxRows": 5,
                    "rowProbeTimeoutMs": 50,
                    "rowLinkSelectors": ["a"],
                    "rowEntryLabels": ["办理"],
                    "clickStrategies": ["click"],
                    "openWaitMs": 100,
                    "newPageTimeoutMs": 2000,
                    "afterRowComplete": {
                        "settleMs": 0,
                        "waitForListChangeMs": 100,
                        "refreshListWhenUnchanged": True,
                        "refreshMethods": ["click_refresh_button"],
                        "refreshButtonTexts": ["刷新"],
                        "waitAfterRefreshMs": 100,
                        "skipProcessedSignatureIfUnchanged": True,
                    },
                    "rowSteps": [{"action": "business_goal", "target": "审批通过", "intent": "approval_pass"}],
                },
                "operationIntent": {"intent": "process_table_rows"},
            },
            execution_context=context,
        )

        assert '"processed_rows": 2' in outcome["reason"]
        assert page.evaluate("window.openedRows") == ["A001", "A002"]
        assert page.evaluate("window.processedRows") == ["A001", "A002"]
        assert page.evaluate("window.refreshCount") == 2
        assert page.locator("tbody tr").count() == 0
    finally:
        for opened_page in list(page.context.pages):
            if opened_page is not page and not opened_page.is_closed():
                opened_page.close()


def test_process_table_rows_stops_after_initial_batch_when_list_becomes_empty(page: Page) -> None:
    page.set_content(
        """
        <script>
          window.openedRows = [];
          function openApproval(id) {
            window.openedRows.push(id);
            const w = window.open('', '_blank');
            w.document.write(`<main data-id="${id}">
              <button onclick="
                window.opener.document.querySelector('tbody').innerHTML = '<tr><td colspan=2>没有可显示的记录</td></tr>';
              ">提交</button>
            </main>`);
            w.document.close();
          }
        </script>
        <table><tbody>
          <tr data-row="A001"><td>A001</td><td><a href="#" onclick="openApproval('A001'); return false;">办理</a></td></tr>
        </tbody></table>
        """
    )
    try:
        holder = {"page": page}
        context, events, _debug = _runtime_context()
        context.update(
            {
                "get_active_page": lambda: holder["page"],
                "set_active_page": lambda new_page, metadata=None: holder.update({"page": new_page}),
                "capture_process_screenshot": lambda label, metadata=None, page=None: None,
            }
        )
        context["execute_sub_step"] = lambda sub_step, sub_page, metadata=None: (
            sub_page.get_by_role("button", name="提交").click()
            or {"locator_strategy": "approval_submit", "element_ref": "提交", "reason": "ok"}
        )

        outcome = TableRowActionHandler().process_rows(
            page,
            step={
                "action": "process_table_rows",
                "target": "我的待办列表",
                "loopPolicy": {
                    "maxRows": 5,
                    "rowProbeTimeoutMs": 50,
                    "rowEntryLabels": ["办理"],
                    "rowLinkSelectors": ["a"],
                    "rowSteps": [{"action": "business_goal", "target": "审批通过", "intent": "approval_pass"}],
                },
                "operationIntent": {"intent": "process_table_rows"},
            },
            execution_context=context,
        )

        assert '"processed_rows": 1' in outcome["reason"]
        assert page.evaluate("window.openedRows") == ["A001"]
        assert any("已完成初始识别" in event["content"] for event in events)
    finally:
        for opened_page in list(page.context.pages):
            if opened_page is not page and not opened_page.is_closed():
                opened_page.close()


def test_process_table_rows_continues_failed_row_when_configured_and_summarizes(page: Page) -> None:
    page.set_content(
        """
        <script>
          window.processedRows = [];
          function openApproval(id) {
            const w = window.open('', '_blank');
            w.document.write(`<main data-id="${id}">
              <button onclick="window.opener.processedRows.push('${id}')">提交</button>
            </main>`);
            w.document.close();
          }
        </script>
        <table><tbody>
          <tr data-row="A001"><td>A001</td><td><a href="#" onclick="openApproval('A001'); return false;">办理</a></td></tr>
          <tr data-row="A002"><td>A002</td><td><a href="#" onclick="openApproval('A002'); return false;">办理</a></td></tr>
          <tr data-row="A003"><td>A003</td><td><a href="#" onclick="openApproval('A003'); return false;">办理</a></td></tr>
        </tbody></table>
        """
    )
    try:
        holder = {"page": page}
        context, events, _debug = _runtime_context()
        context.update(
            {
                "get_active_page": lambda: holder["page"],
                "set_active_page": lambda new_page, metadata=None: holder.update({"page": new_page}),
                "capture_process_screenshot": lambda label, metadata=None, page=None: None,
            }
        )

        def execute_sub_step(sub_step: dict, sub_page: Page, metadata: dict | None = None) -> dict:
            row_id = sub_page.locator("main").get_attribute("data-id")
            if row_id == "A001":
                raise RuntimeError("approval_validation_failed: 审批未提交，页面提示“请填写”。")
            sub_page.get_by_role("button", name="提交").click()
            return {"locator_strategy": "approval_submit", "element_ref": "提交", "reason": "ok"}

        context["execute_sub_step"] = execute_sub_step
        with pytest.raises(RuntimeError) as exc:
            TableRowActionHandler().process_rows(
                page,
                step={
                    "action": "process_table_rows",
                    "target": "我的待办列表",
                    "loopPolicy": {
                        "maxRows": 5,
                        "rowProbeTimeoutMs": 50,
                        "rowEntryLabels": ["办理"],
                        "rowLinkSelectors": ["a"],
                        "continueOnRowFailure": True,
                        "maxConsecutiveFailures": 3,
                        "rowSteps": [{"action": "business_goal", "target": "审批通过", "intent": "approval_pass"}],
                    },
                    "operationIntent": {"intent": "process_table_rows"},
                },
                execution_context=context,
            )

        message = str(exc.value)
        assert "table_row_loop_failed" in message
        assert "'processed_rows': 2" in message
        assert "'attempted_rows': 3" in message
        assert page.evaluate("window.processedRows") == ["A002", "A003"]
        assert any("已完成初始识别" in event["content"] for event in events)
    finally:
        for opened_page in list(page.context.pages):
            if opened_page is not page and not opened_page.is_closed():
                opened_page.close()


def test_process_table_rows_timeout_with_remaining_rows_fails(page: Page, monkeypatch: pytest.MonkeyPatch) -> None:
    page.set_content(
        """
        <script>
          function openApproval(id) {
            const w = window.open('', '_blank');
            w.document.write(`<main>
              <button onclick="window.opener.document.querySelector('[data-row=${id}]').remove()">提交</button>
            </main>`);
            w.document.close();
          }
        </script>
        <table><tbody>
          <tr data-row="A001"><td>A001</td><td><a href="#" onclick="openApproval('A001'); return false;">办理</a></td></tr>
          <tr data-row="A002"><td>A002</td><td><a href="#" onclick="openApproval('A002'); return false;">办理</a></td></tr>
        </tbody></table>
        """
    )
    try:
        holder = {"page": page}
        context, events, _debug = _runtime_context()
        context.update(
            {
                "get_active_page": lambda: holder["page"],
                "set_active_page": lambda new_page, metadata=None: holder.update({"page": new_page}),
                "capture_process_screenshot": lambda label, metadata=None, page=None: None,
            }
        )

        def execute_sub_step(sub_step: dict, sub_page: Page, metadata: dict | None = None) -> dict:
            sub_page.get_by_role("button", name="提交").click()
            return {"locator_strategy": "approval_submit", "element_ref": "提交", "reason": "ok"}

        handler = TableRowActionHandler()
        calls = {"count": 0}

        def fake_elapsed(started: float) -> int:
            calls["count"] += 1
            return 0 if calls["count"] == 1 else 600_000

        monkeypatch.setattr(handler, "_elapsed_ms", fake_elapsed)
        context["execute_sub_step"] = execute_sub_step

        with pytest.raises(RuntimeError) as exc:
            handler.process_rows(
                page,
                step={
                    "action": "process_table_rows",
                    "target": "我的待办列表",
                    "loopPolicy": {
                        "maxRows": 5,
                        "maxDurationMs": 5000,
                        "rowProbeTimeoutMs": 50,
                        "rowLinkSelectors": ["a"],
                        "rowEntryLabels": ["办理"],
                        "rowSteps": [{"action": "business_goal", "target": "审批通过", "intent": "approval_pass"}],
                    },
                    "operationIntent": {"intent": "process_table_rows"},
                },
                execution_context=context,
            )

        message = str(exc.value)
        assert "table_row_loop_failed" in message
        assert "'reason': 'timeout'" in message
        assert "'processed_rows': 1" in message
        assert "'row_count': 2" in message
        assert any(event["phase"] == "table_row_loop_guard" for event in events)
    finally:
        for opened_page in list(page.context.pages):
            if opened_page is not page and not opened_page.is_closed():
                opened_page.close()


def test_process_table_rows_max_rows_with_remaining_rows_fails(page: Page) -> None:
    page.set_content(
        """
        <script>
          function openApproval(id) {
            const w = window.open('', '_blank');
            w.document.write(`<main><button>提交</button></main>`);
            w.document.close();
          }
        </script>
        <table><tbody>
          <tr data-row="A001"><td>A001</td><td><a href="#" onclick="openApproval('A001'); return false;">办理</a></td></tr>
          <tr data-row="A002"><td>A002</td><td><a href="#" onclick="openApproval('A002'); return false;">办理</a></td></tr>
        </tbody></table>
        """
    )
    try:
        holder = {"page": page}
        context, events, _debug = _runtime_context()
        context.update(
            {
                "get_active_page": lambda: holder["page"],
                "set_active_page": lambda new_page, metadata=None: holder.update({"page": new_page}),
                "capture_process_screenshot": lambda label, metadata=None, page=None: None,
            }
        )
        context["execute_sub_step"] = lambda sub_step, sub_page, metadata=None: {
            "locator_strategy": "approval_submit",
            "element_ref": "提交",
            "reason": "ok",
        }

        with pytest.raises(RuntimeError) as exc:
            TableRowActionHandler().process_rows(
                page,
                step={
                    "action": "process_table_rows",
                    "target": "我的待办列表",
                    "loopPolicy": {
                        "maxRows": 1,
                        "rowProbeTimeoutMs": 50,
                        "rowLinkSelectors": ["a"],
                        "rowEntryLabels": ["办理"],
                        "rowSteps": [{"action": "business_goal", "target": "审批通过", "intent": "approval_pass"}],
                    },
                    "operationIntent": {"intent": "process_table_rows"},
                },
                execution_context=context,
            )

        message = str(exc.value)
        assert "table_row_loop_failed" in message
        assert "'remaining_rows': 1" in message
        assert "已处理 1 条" in message
        assert any(event["phase"] == "table_row_loop_incomplete" for event in events)
    finally:
        for opened_page in list(page.context.pages):
            if opened_page is not page and not opened_page.is_closed():
                opened_page.close()


def test_process_table_rows_stops_after_consecutive_no_action_failures(page: Page) -> None:
    page.set_content(
        """
        <table><tbody>
          <tr><td>待办 1</td><td>只读</td></tr>
          <tr><td>待办 2</td><td>只读</td></tr>
          <tr><td>待办 3</td><td>只读</td></tr>
          <tr><td>待办 4</td><td>只读</td></tr>
        </tbody></table>
        """
    )
    screenshots: list[str] = []
    context, events, _debug = _runtime_context()
    context["capture_process_screenshot"] = lambda label, metadata=None, page=None: screenshots.append(label)

    with pytest.raises(RuntimeError) as exc:
        TableRowActionHandler().process_rows(
            page,
            step={
                "action": "process_table_rows",
                "target": "我的待办列表",
                "loopPolicy": {
                    "maxRows": 10,
                    "rowEntryLabels": ["办理"],
                    "rowProbeTimeoutMs": 50,
                    "maxConsecutiveFailures": 2,
                },
                "operationIntent": {"intent": "process_table_rows"},
            },
            execution_context=context,
        )

    message = str(exc.value)
    assert "table_row_loop_guard_triggered" in message
    assert "'attempted_rows': 2" in message
    assert "row_001_failed" in screenshots
    assert "row_002_failed" in screenshots
    assert any(event["phase"] == "table_row_loop_guard" for event in events)


def test_process_table_rows_requires_rule_open_success_before_row_substeps(page: Page) -> None:
    page.set_content(
        """
        <table class="el-table__body"><tbody>
          <tr><td>1</td><td>26371</td><td><a class="el-link el-link--primary" href="#">流程标题</a></td></tr>
        </tbody></table>
        """
    )
    screenshots: list[str] = []
    context, _events, _debug = _runtime_context()
    context["capture_process_screenshot"] = lambda label, metadata=None, page=None: screenshots.append(label)
    context["execute_sub_step"] = lambda sub_step, sub_page, metadata=None: pytest.fail("详情页未打开时不应执行审批子步骤")

    with pytest.raises(RuntimeError) as exc:
        TableRowActionHandler().process_rows(
            page,
            step={
                "action": "process_table_rows",
                "target": "我的待办列表",
                "loopPolicy": {
                    "maxRows": 1,
                    "rowProbeTimeoutMs": 50,
                    "rowLinkSelectors": ["a.el-link.el-link--primary"],
                    "clickStrategies": ["click"],
                    "openSuccessTexts": ["我的意见"],
                },
                "rowSteps": [{"action": "business_goal", "target": "审批通过", "intent": "approval_pass"}],
                "operationIntent": {"intent": "process_table_rows"},
            },
            execution_context=context,
        )

    assert "table_row_open_failed" in str(exc.value)
    assert any("open_attempt_01_no_effect" in label for label in screenshots)


def test_process_table_rows_treats_visible_dialog_as_open_when_hidden_dialog_exists(page: Page) -> None:
    page.set_content(
        """
        <div role="dialog" style="display:none">旧弹窗</div>
        <script>
          function openDialog() {
            document.querySelector('#approvalDialog').style.display = 'block';
          }
        </script>
        <table class="el-table__body"><tbody>
          <tr><td>1</td><td>26148</td><td><a class="el-link el-link--primary" href="#" onclick="openDialog(); return false;">【换休】1天</a></td></tr>
        </tbody></table>
        <div id="approvalDialog" class="el-dialog" role="dialog" style="display:none">
          <h2>加班申请</h2>
          <section>审批历史记录</section>
          <button>审批</button>
          <button onclick="document.querySelector('#approvalDialog').style.display = 'none'">取消</button>
        </div>
        """
    )
    context, _events, _debug = _runtime_context()
    executed: list[dict] = []

    def execute_sub_step(sub_step: dict, sub_page: Page, metadata: dict | None = None) -> dict:
        executed.append(sub_step)
        assert sub_page.get_by_role("button", name="审批").is_visible()
        return {"locator_strategy": "approval_pass", "element_ref": "审批", "reason": "ok"}

    context["execute_sub_step"] = execute_sub_step
    outcome = TableRowActionHandler().process_rows(
        page,
        step={
            "action": "process_table_rows",
            "target": "我的待办列表",
            "loopPolicy": {
                "maxRows": 1,
                "rowProbeTimeoutMs": 50,
                "rowLinkSelectors": ["a.el-link.el-link--primary"],
                "clickStrategies": ["click"],
                "openWaitMs": 100,
                "newPageTimeoutMs": 800,
                "openSuccessTexts": ["审批历史记录"],
                "openSuccessSelectors": [".el-dialog", "[role='dialog']"],
            },
            "rowSteps": [{"action": "business_goal", "target": "审批通过", "intent": "approval_pass"}],
            "operationIntent": {"intent": "process_table_rows"},
        },
        execution_context=context,
    )

    assert executed
    assert '"processed_rows": 1' in outcome["reason"]


def test_process_table_rows_uses_executable_rule_selectors_and_success_signals(page: Page) -> None:
    page.set_content(
        """
        <table class="el-table__body"><tbody>
          <tr><td>1</td><td>26371</td><td><a class="el-link el-link--primary" href="#"
            onclick="document.body.innerHTML = `<main><label for='opinion'>我的意见</label><textarea id='opinion'></textarea><button>提交</button></main>`">流程标题</a></td></tr>
        </tbody></table>
        """
    )
    context, _events, _debug = _runtime_context()
    executed: list[dict] = []

    def execute_sub_step(sub_step: dict, sub_page: Page, metadata: dict | None = None) -> dict:
        executed.append(sub_step)
        assert sub_page.get_by_label("我的意见").count() == 1
        return {"locator_strategy": "approval_pass", "element_ref": "提交", "reason": "ok"}

    context["execute_sub_step"] = execute_sub_step
    outcome = TableRowActionHandler().process_rows(
        page,
        step={
            "action": "process_table_rows",
            "target": "我的待办列表",
            "loopPolicy": {
                "maxRows": 1,
                "rowEntryLabels": ["不存在的入口"],
                "rowLinkSelectors": ["a.el-link.el-link--primary"],
                "clickStrategies": ["js_click"],
                "openSuccessTexts": ["我的意见"],
            },
            "rowSteps": [{"action": "business_goal", "target": "审批通过", "intent": "approval_pass"}],
            "operationIntent": {"intent": "process_table_rows"},
        },
        execution_context=context,
    )

    assert executed
    assert '"processed_rows": 1' in outcome["reason"]


def test_approval_handler_fills_required_opinion_after_validation(page: Page) -> None:
    page.set_content(
        """
        <main>
          <textarea id="opinion" placeholder="请输入内容"></textarea>
          <div id="err" class="el-message" style="display:none">请检查必填项</div>
          <button onclick="
            if (document.querySelector('#opinion').value) {
              window.submitted = true;
              document.querySelector('#err').style.display = 'none';
              document.querySelector('main').insertAdjacentHTML('beforeend', '<div>审批成功</div>');
            } else {
              document.querySelector('#err').style.display = 'block';
            }
          ">审批</button>
        </main>
        """
    )
    context, _events, _debug = _runtime_context()

    outcome = ApprovalWorkflowHandler().approval_pass(
        page,
        step={"action": "business_goal", "target": "审批通过", "operationIntent": {"intent": "approval_pass"}},
        execution_context=context,
    )

    assert page.evaluate("window.submitted") is True
    assert page.locator("#opinion").input_value().startswith("同意")
    assert outcome["locator_strategy"] == "approval_pass"


def test_approval_handler_uses_instruction_opinion_text(page: Page) -> None:
    page.set_content(
        """
        <main>
          <label for="opinion">我的意见</label>
          <textarea id="opinion"></textarea>
          <button onclick="window.submitted = document.querySelector('#opinion').value; document.querySelector('main').insertAdjacentHTML('beforeend', '<div>审批成功</div>')">提交</button>
        </main>
        """
    )
    context, _events, _debug = _runtime_context()

    outcome = ApprovalWorkflowHandler().approval_pass(
        page,
        step={"action": "business_goal", "target": "审批通过", "intent": "approval_pass", "value": "按要求执行"},
        execution_context=context,
    )

    assert page.locator("#opinion").input_value() == "按要求执行"
    assert page.evaluate("window.submitted") == "按要求执行"
    assert outcome["locator_strategy"] == "approval_pass"


def test_approval_handler_waits_async_next_approver_before_submit(page: Page) -> None:
    page.set_content(
        """
        <main>
          <label for="opinion">审批意见</label>
          <textarea id="opinion"></textarea>
          <table>
            <tr id="nextApprover">
              <td>下一步审批人</td>
              <td>
                <div id="loading">正在处理，请稍待...</div>
                <label id="candidate" style="display:none"><input id="person" type="checkbox" /> 张三</label>
              </td>
            </tr>
          </table>
          <div id="err" class="el-message" style="display:none">请填写</div>
          <button onclick="
            if (document.querySelector('#opinion').value && document.querySelector('#person').checked) {
              window.submitted = true;
              document.querySelector('#err').style.display = 'none';
              document.querySelector('main').insertAdjacentHTML('beforeend', '<div>审批成功</div>');
            } else {
              document.querySelector('#err').style.display = 'block';
            }
          ">审核</button>
          <script>
            setTimeout(() => {
              document.querySelector('#loading').style.display = 'none';
              document.querySelector('#candidate').style.display = 'block';
            }, 300);
          </script>
        </main>
        """
    )
    context, _events, _debug = _runtime_context()

    outcome = ApprovalWorkflowHandler().approval_pass(
        page,
        step={"action": "business_goal", "target": "审批通过", "intent": "approval_pass", "value": "按要求执行"},
        execution_context=context,
    )

    assert page.locator("#opinion").input_value() == "按要求执行"
    assert page.locator("#person").is_checked()
    assert page.evaluate("window.submitted") is True
    assert outcome["locator_strategy"] == "approval_pass"


def test_approval_handler_submits_legacy_bpm_form_with_link_submit(page: Page) -> None:
    page.set_content(
        """
        <main>
          <h1>员工休假申请流程</h1>
          <section>审批信息</section>
          <table>
            <tr><td>审批结果</td><td><label><input type="radio" name="result" checked /> 同意</label><label><input type="radio" name="result" /> 驳回</label></td></tr>
            <tr><td><label for="opinion">审批意见</label></td><td><textarea id="opinion" placeholder="请填写内容"></textarea></td></tr>
            <tr>
              <td>下一审批人</td>
              <td>
                <div id="loading">正在处理，请稍待...</div>
                <label id="candidate" style="display:none"><input id="person" type="checkbox" /> 张三</label>
              </td>
            </tr>
          </table>
          <a id="btnAudit" class="easyui-linkbutton" href="#" onclick="
            window.submitted = document.querySelector('#opinion').value;
            document.querySelector('main').insertAdjacentHTML('beforeend', '<div>审批成功</div>');
            return false;
          ">提交</a>
          <script>
            setTimeout(() => {
              document.querySelector('#loading').style.display = 'none';
              document.querySelector('#candidate').style.display = 'block';
            }, 200);
          </script>
        </main>
        """
    )
    context, _events, _debug = _runtime_context()

    outcome = ApprovalWorkflowHandler().approval_pass(
        page,
        step={"action": "business_goal", "target": "审批通过", "intent": "approval_pass", "value": "按要求执行"},
        execution_context=context,
    )

    assert page.locator("#opinion").input_value() == "按要求执行"
    assert page.locator("#person").is_checked()
    assert page.evaluate("window.submitted") == "按要求执行"
    assert outcome["locator_strategy"] == "approval_pass"


def test_approval_handler_submits_approval_form_inside_iframe(page: Page) -> None:
    page.set_content(
        """
        <iframe srcdoc="
          <main>
            <h1>员工休假申请流程</h1>
            <section>审批信息</section>
            <label for='opinion'>审批意见</label>
            <textarea id='opinion'></textarea>
            <div>下一审批人 <label><input id='person' type='checkbox' /> 张三</label></div>
            <a id='btnAudit' href='#' onclick=&quot;window.submitted = document.querySelector('#opinion').value; document.body.insertAdjacentHTML('beforeend', '<div>审批成功</div>'); return false;&quot;>提交</a>
          </main>
        "></iframe>
        """
    )
    context, _events, _debug = _runtime_context()

    outcome = ApprovalWorkflowHandler().approval_pass(
        page,
        step={"action": "business_goal", "target": "审批通过", "intent": "approval_pass", "value": "按要求执行"},
        execution_context=context,
    )

    frame = page.frames[1]
    assert frame.locator("#opinion").input_value() == "按要求执行"
    assert frame.locator("#person").is_checked()
    assert frame.evaluate("window.submitted") == "按要求执行"
    assert outcome["locator_strategy"] == "approval_pass"


def test_approval_handler_does_not_pass_when_submit_surface_remains(page: Page) -> None:
    page.set_content(
        """
        <main>
          <h2>流程审批</h2>
          <label for="opinion">审批意见</label>
          <textarea id="opinion"></textarea>
          <button onclick="window.clicked = true">提交</button>
        </main>
        """
    )
    context, _events, _debug = _runtime_context()

    with pytest.raises(RuntimeError, match="approval_submit_uncertain"):
        ApprovalWorkflowHandler().approval_pass(
            page,
            step=_approval_step_with_fast_result_policy(),
            execution_context=context,
        )

    assert page.evaluate("window.clicked") is True


def test_approval_handler_reports_business_submit_failure(page: Page) -> None:
    page.set_content(
        """
        <main>
          <h2>流程审批</h2>
          <label for="opinion">审批意见</label>
          <textarea id="opinion"></textarea>
          <div id="err" class="el-message" style="display:none">接口错误 保存失败</div>
          <button onclick="document.querySelector('#err').style.display = 'block'">提交</button>
        </main>
        """
    )
    context, _events, _debug = _runtime_context()

    with pytest.raises(RuntimeError, match="接口错误"):
        ApprovalWorkflowHandler().approval_pass(
            page,
            step=_approval_step_with_fast_result_policy(),
            execution_context=context,
        )


def test_approval_validation_messages_tolerate_empty_page_evaluate() -> None:
    class EmptyLocator:
        def count(self) -> int:
            return 0

    class EmptyPage:
        def evaluate(self, script: str):
            return None

        def get_by_text(self, text: str, exact: bool = False):
            return EmptyLocator()

    assert ApprovalWorkflowHandler()._visible_validation_messages(EmptyPage()) == []


def _approval_step_with_fast_result_policy() -> dict:
    rule = {
        "rule_code": "APPROVAL-PASS-v1",
        "rule_name": "审批通过",
        "rule_type": "approval_workflow",
        "actionConfig": {
            "formReadyTexts": ["流程审批", "审批意见"],
            "opinionSelectors": ["textarea"],
            "submitSelectors": ["button:has-text('提交')"],
            "submitLabels": ["提交"],
            "submissionResult": {
                "waitMs": 300,
                "pollMs": 100,
                "successTexts": ["审批成功"],
                "failureTexts": ["接口错误", "保存失败"],
                "requireFormClosed": True,
            },
        },
        "successCriteria": {"criteria": ["审批成功"]},
    }
    return {
        "action": "business_goal",
        "target": "审批通过",
        "operationIntent": {"intent": "approval_pass"},
        "abilityResolution": {"matchedRules": [rule], "selectedRules": [rule], "source": "test"},
    }


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
