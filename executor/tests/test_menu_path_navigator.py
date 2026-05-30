from collections.abc import Iterator
from pathlib import Path
import sys

import pytest
from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from executor.aitp_executor.goal.menu_path_navigator import MenuPathNavigator
from executor.aitp_executor.locator.business_intent_normalizer import BusinessIntentNormalizer


@pytest.fixture(scope="module")
def page() -> Iterator[Page]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        yield page
        context.close()
        browser.close()


def test_business_intent_recognizes_navigation_path() -> None:
    intent = BusinessIntentNormalizer().normalize(action="business_goal", target="工作台/我的待办")
    assert intent.goal_type == "navigation_path"
    assert intent.path_segments == ["工作台", "我的待办"]
    assert intent.parents == ["工作台"]
    assert intent.leaf == "我的待办"
    assert BusinessIntentNormalizer().normalize(action="business_goal", target="工作台 > 我的待办").path_segments == ["工作台", "我的待办"]
    assert BusinessIntentNormalizer().normalize(action="navigate_menu", target="工作台 → 我的待办").path_segments == ["工作台", "我的待办"]
    assert BusinessIntentNormalizer().normalize(action="business_goal", target="工作台 - 我的待办").path_segments == ["工作台", "我的待办"]
    assert BusinessIntentNormalizer().normalize(
        action="business_goal",
        target="系统导航-办公自动化-燕山业务流程管理系统-BPM",
    ).path_segments == ["系统导航", "办公自动化", "燕山业务流程管理系统-BPM"]


def test_left_menu_path_success(page: Page) -> None:
    page.set_content(
        """
        <aside>
          <button>工作台</button>
          <button onclick="document.querySelector('main').innerHTML='<h1>我的待办</h1><table><tr><th>申请编号</th><th>操作</th></tr></table>'">我的待办</button>
        </aside>
        <main><h1>首页</h1></main>
        """
    )
    result = MenuPathNavigator().navigate_path(page, "工作台/我的待办", ["工作台", "我的待办"])
    assert result.status == "passed"
    assert any(item["strategy"] == "left_menu_path" for item in result.attemptedStrategies)


def test_already_on_target_page_success(page: Page) -> None:
    page.set_content(
        """
        <aside><button>工作台</button><button class="active">我的待办</button></aside>
        <main><h1>我的待办</h1><table><tr><th>申请编号</th><th>操作</th></tr></table></main>
        """
    )
    result = MenuPathNavigator().navigate_path(page, "工作台/我的待办", ["工作台", "我的待办"])
    assert result.status == "passed"
    assert "page_heading_contains_leaf" in result.successEvidence


def test_collapsed_left_menu_expands_then_clicks(page: Page) -> None:
    page.set_content(
        """
        <aside>
          <button onclick="document.querySelector('#children').hidden=false">工作台</button>
          <div id="children" hidden>
            <button onclick="document.querySelector('main').innerHTML='<h1>我的待办</h1><p>待办列表</p>'">我的待办</button>
          </div>
        </aside>
        <main><h1>首页</h1></main>
        """
    )
    result = MenuPathNavigator().navigate_path(page, "工作台/我的待办", ["工作台", "我的待办"])
    assert result.status == "passed"
    left_attempt = next(item for item in result.attemptedStrategies if item["strategy"] == "left_menu_path")
    assert left_attempt["expanded"] is True
    assert left_attempt["childFound"] is True


def test_dashboard_card_fallback_success(page: Page) -> None:
    page.set_content(
        """
        <main class="dashboard">
          <button class="card" onclick="document.querySelector('main').innerHTML='<h1>我的待办</h1><p>待办任务表格</p>'">我的待办</button>
        </main>
        """
    )
    result = MenuPathNavigator().navigate_path(page, "工作台/我的待办", ["工作台", "我的待办"])
    assert result.status == "passed"
    assert any(item["strategy"] == "dashboard_card" and item["found"] for item in result.attemptedStrategies)


def test_adaptive_portal_path_clicks_category_then_app(page: Page) -> None:
    page.set_content(
        """
        <header>
          <button onclick="document.querySelector('#categories').hidden=false">系统导航</button>
        </header>
        <main>
          <aside id="categories" hidden>
            <button
              role="tab"
              onclick="this.setAttribute('aria-selected', 'true'); document.querySelector('#apps').innerHTML='<button class=app-card onclick=&quot;document.querySelector(\\'main\\').innerHTML=\\'<h1>中国石化公文管理系统</h1><p>操作</p>\\'&quot;>中国石化公文管理系统</button>'"
            >办公自动化(14)</button>
          </aside>
          <section id="apps"></section>
        </main>
        """
    )
    result = MenuPathNavigator().navigate_path(
        page,
        "系统导航-办公自动化-中国石化公文管理系统",
        ["系统导航", "办公自动化", "中国石化公文管理系统"],
    )
    assert result.status == "passed"
    assert any(item["strategy"] == "adaptive_segment_path" and item.get("status") == "passed" for item in result.attemptedStrategies)
    assert any(item["text"] == "办公自动化" for item in result.clickedElements)
    assert any(item["text"] == "中国石化公文管理系统" for item in result.clickedElements)


def test_adaptive_portal_path_switches_to_popup_target_page(page: Page) -> None:
    page.set_content(
        """
        <header>
          <button>系统导航</button>
        </header>
        <main>
          <button role="tab" aria-selected="true">办公自动化(14)</button>
          <button onclick="const w=window.open('about:blank', '_blank'); w.document.write('<!doctype html><title>中国石化公文管理系统</title><h1>中国石化公文管理系统</h1><main>业务首页 操作</main>'); w.document.close();">中国石化公文管理系统</button>
        </main>
        """
    )
    holder = {"page": page}

    try:
        result = MenuPathNavigator().navigate_path(
            page,
            "系统导航/办公自动化/中国石化公文管理系统",
            ["系统导航", "办公自动化", "中国石化公文管理系统"],
            {
                "get_active_page": lambda: holder["page"],
                "set_active_page": lambda new_page, _metadata: holder.__setitem__("page", new_page),
            },
        )
        assert result.status == "passed"
        assert holder["page"] is not page
        assert result.pageTransitions
        assert "new_page_opened_after_leaf_click" in result.successEvidence
        assert any(item in result.successEvidence for item in ["title_contains_leaf", "page_heading_contains_leaf"])
        assert holder["page"].locator("h1").inner_text() == "中国石化公文管理系统"
    finally:
        if holder["page"] is not page:
            holder["page"].close()


def test_adaptive_portal_path_fails_when_popup_target_is_not_verified(page: Page) -> None:
    page.set_content(
        """
        <header>
          <button>系统导航</button>
        </header>
        <main>
          <button role="tab" aria-selected="true">办公自动化(14)</button>
          <button onclick="const w=window.open('about:blank', '_blank'); w.document.write('<!doctype html><title>空白页</title><h1>加载中</h1>'); w.document.close();">中国石化公文管理系统</button>
        </main>
        """
    )
    holder = {"page": page}

    try:
        result = MenuPathNavigator().navigate_path(
            page,
            "系统导航/办公自动化/中国石化公文管理系统",
            ["系统导航", "办公自动化", "中国石化公文管理系统"],
            {
                "get_active_page": lambda: holder["page"],
                "set_active_page": lambda new_page, _metadata: holder.__setitem__("page", new_page),
            },
        )
        assert result.status == "failed"
        assert result.failureType == "navigation_target_not_verified"
        assert holder["page"] is not page
        assert result.pageTransitions
    finally:
        if holder["page"] is not page:
            holder["page"].close()


def test_missing_child_does_not_fail_as_vision_not_configured(page: Page) -> None:
    page.set_content(
        """
        <aside><button>工作台</button><button>其他事项</button></aside>
        <main><h1>首页</h1></main>
        """
    )
    result = MenuPathNavigator().navigate_path(
        page,
        "工作台/我的待办",
        ["工作台", "我的待办"],
        {"vision_requested": True},
    )
    assert result.status == "failed"
    assert result.failureType in {"menu_child_not_found", "navigation_path_unresolved"}
    assert result.failureType != "vision_fallback_not_configured"
    assert result.visionFallback == "not_configured"
