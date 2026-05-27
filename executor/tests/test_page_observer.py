from collections.abc import Iterator
from pathlib import Path
import sys

import pytest
from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from executor.aitp_executor.observer.page_observer import PageObserver


@pytest.fixture(scope="module")
def page() -> Iterator[Page]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        yield page
        context.close()
        browser.close()


def test_page_observer_extracts_mis_page_structures(page: Page) -> None:
    page.set_content(
        """
        <header class="top-nav"><nav><button>系统管理</button></nav></header>
        <aside class="sidebar">
          <ul class="ant-menu">
            <li class="ant-menu-submenu"><div class="ant-menu-submenu-title" aria-expanded="true">工作台</div>
              <ul><li class="ant-menu-item">我的待办</li></ul>
            </li>
          </ul>
        </aside>
        <main class="workbench">
          <div class="ant-breadcrumb"><a>工作台</a><a>我的待办</a></div>
          <button class="card">快捷入口</button>
          <section class="ant-card">
            <h2>查询条件</h2>
            <label for="kw">关键字</label><input id="kw" placeholder="请输入关键字" required />
            <label>备注<textarea placeholder="请输入备注"></textarea></label>
            <label>状态<select><option>启用</option></select></label>
            <div class="ant-select" role="combobox" aria-label="选择类型">类型</div>
            <label>是否<input type="radio" name="yesno" /></label>
            <label>勾选<input type="checkbox" /></label>
            <label>开始日期<input class="ant-picker-input" placeholder="开始日期" /></label>
            <label>所属机构<input class="ant-tree-select" placeholder="组织机构" /></label>
            <label>审批人<input class="person-selector" placeholder="选择人员" /></label>
            <label>附件<input type="file" /></label>
          </section>
          <div class="ant-table-wrapper">
            <table class="ant-table">
              <thead><tr><th>申请编号</th><th>申请人</th><th>操作</th></tr></thead>
              <tbody>
                <tr><td><a>A001</a></td><td>张三</td><td><button>审批</button><button>查看审批流程</button></td></tr>
                <tr class="summary"><td>合计</td><td></td><td></td></tr>
              </tbody>
            </table>
            <div class="ant-pagination">下一页</div>
          </div>
          <div class="ant-modal" role="dialog" aria-modal="true">
            <div class="ant-modal-title">审批处理</div>
            <textarea aria-label="审批意见"></textarea>
            <button>通过</button><button>取消</button>
          </div>
          <div class="ant-drawer"><div class="ant-drawer-title">详情</div></div>
          <div class="ant-message">保存成功</div>
          <div class="ant-spin">加载中</div>
          <iframe title="内嵌菜单" srcdoc="<aside><button>审批管理</button><button>待审批</button></aside>"></iframe>
        </main>
        """
    )
    page.wait_for_timeout(300)

    observation = PageObserver().observe(page)

    assert observation.menus
    assert any(item["text"] == "工作台" and item["area"] == "left_menu" for item in observation.menus)
    assert any(item["text"] == "我的待办" for item in observation.menus)
    assert observation.breadcrumbs
    assert observation.tabs == []
    assert observation.tables
    table = observation.tables[0]
    assert "申请编号" in table["headers"]
    assert any(row["rowType"] == "data_row" and row["actions"] for row in table["rows"])
    assert any(row["rowType"] == "summary_row" for row in table["rows"])
    assert table["pagination"]["visible"] is True
    assert observation.inputs
    assert observation.textareas
    assert observation.selects
    assert observation.comboboxes
    assert observation.radios
    assert observation.checkboxes
    assert observation.datePickers
    assert observation.orgSelectors
    assert observation.personSelectors
    assert observation.fileUploads
    assert observation.dialogs
    assert observation.dialogs[0]["dialogType"] == "approval"
    assert observation.drawers
    assert observation.toasts
    assert observation.loadingIndicators
    assert observation.iframes
    assert any(item.get("accessible") is True for item in observation.iframes)
    assert observation.elements
