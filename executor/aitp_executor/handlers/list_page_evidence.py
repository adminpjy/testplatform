import re
from typing import Any

from playwright.sync_api import Error as PlaywrightError


TODO_PAGE_MARKERS = ["我的待办", "待办", "todo", "to-do"]
TODO_TABLE_HEADER_MARKERS = [
    "实例号",
    "流程实例号",
    "流程标题",
    "流程名称",
    "申请编号",
    "当前环节",
    "当前处理人",
    "办理人",
    "申请时间",
    "接收时间",
    "到达时间",
    "操作",
]
EMPTY_LIST_MARKERS = ["暂无数据", "无数据", "没有可显示", "没有显示的记录", "共0条", "共0 条", "0条"]
LIST_SURFACE_SELECTORS = [
    "table",
    ".ant-table",
    ".el-table",
    ".vxe-table",
    "[role='table']",
    ".ant-empty",
    ".el-empty",
    ".el-table__empty-block",
    ".vxe-table--empty-content",
]


def assert_target_list_page_ready_for_empty_result(
    page: Any,
    step: dict[str, Any],
    *,
    loop_policy: dict[str, Any] | None = None,
) -> None:
    if not is_todo_list_target(step, loop_policy=loop_policy):
        return
    if is_todo_list_page_ready(page):
        return
    target = str(step.get("target") or "我的待办列表").strip() or "我的待办列表"
    raise AssertionError(
        "target_list_page_not_reached: 当前页面未进入"
        f"“{target}”，不能按空列表通过。请先进入“工作台/我的待办”，再读取或处理待办列表。"
    )


def is_todo_list_target(step: dict[str, Any], *, loop_policy: dict[str, Any] | None = None) -> bool:
    text = _flatten({"step": step, "loopPolicy": loop_policy or {}})
    compact = _compact(text).lower()
    return any(marker in compact for marker in TODO_PAGE_MARKERS)


def is_todo_list_page_ready(page: Any) -> bool:
    text = _visible_body_text(page)
    compact = _compact(text).lower()
    if not any(marker.lower() in compact for marker in TODO_PAGE_MARKERS):
        return False
    if any(marker in compact for marker in [_compact(item).lower() for item in EMPTY_LIST_MARKERS]):
        return True
    if _table_header_hit_count(compact) >= 2:
        return True
    return _has_visible_todo_list_surface(page)


def _has_visible_todo_list_surface(page: Any) -> bool:
    for selector in LIST_SURFACE_SELECTORS:
        try:
            locator = page.locator(selector)
            for index in range(min(locator.count(), 5)):
                item = locator.nth(index)
                if not item.is_visible(timeout=300):
                    continue
                surface_text = _compact(item.inner_text(timeout=500)).lower()
                if any(marker in surface_text for marker in [_compact(item).lower() for item in EMPTY_LIST_MARKERS]):
                    return True
                if _table_header_hit_count(surface_text) >= 1:
                    return True
        except PlaywrightError:
            continue
    return False


def _table_header_hit_count(compact_text: str) -> int:
    return sum(1 for marker in TODO_TABLE_HEADER_MARKERS if _compact(marker).lower() in compact_text)


def _visible_body_text(page: Any) -> str:
    try:
        return page.locator("body").inner_text(timeout=1_000)
    except PlaywrightError:
        return ""


def _compact(value: Any) -> str:
    return re.sub(r"[\s：:，,。；;、/\\|_-]+", "", str(value or ""))


def _flatten(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten(item) for item in value)
    if value is None:
        return ""
    return str(value)
