import re
from typing import Any

from playwright.sync_api import Error as PlaywrightError

from executor.aitp_executor.handlers.base import CommonOperationHandler, handler_outcome
from executor.aitp_executor.handlers.dropdown_handler import DropdownHandler
from executor.aitp_executor.handlers.list_page_evidence import assert_target_list_page_ready_for_empty_result
from executor.aitp_executor.handlers.table_handler import TableHandler
from executor.aitp_executor.locator.element_locator import ElementLocator
from executor.aitp_executor.runner.page_waiter import wait_for_page_ready


class QueryHandler(CommonOperationHandler):
    handler_name = "query_handler"
    rule_types = ["query", "table_detection"]
    default_intent = "query_list"

    def __init__(self, *, locator: ElementLocator | None = None, table_handler: TableHandler | None = None) -> None:
        super().__init__()
        self.locator = locator or ElementLocator()
        self.table_handler = table_handler or TableHandler()
        self.dropdown_handler = DropdownHandler(locator=self.locator)

    def execute(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        resolution = self.resolve_rules(ctx, intent="query_list", rule_types=["query", "table_detection"])
        self.emit_rule_hits(ctx, resolution)
        self.emit(ctx, "progress", "query", "正在处理查询条件并刷新列表。")
        criteria = _extract_query_criteria(step)
        filled_fields: list[dict[str, Any]] = []
        missing_fields: list[str] = []
        for label, value in criteria.items():
            if value in (None, ""):
                continue
            fill_result = self._fill_query_field(page, str(label), value)
            if fill_result:
                filled_fields.append(fill_result)
            else:
                missing_fields.append(f"{label}={value}")
        if missing_fields:
            raise RuntimeError(
                "query_field_not_found: 未找到查询条件输入控件，无法执行目标查询："
                + "，".join(missing_fields)
                + "。"
            )
        clicked = self._click_query_button(page)
        wait_for_page_ready(page)
        table_outcome = self.table_handler.wait_for_table(page, step=step, dsl=dsl, execution_context=execution_context)
        row_count = self.table_handler.row_count(page)
        empty_strategy = str(step.get("emptyStrategy") or step.get("empty_strategy") or "pass")
        if row_count == 0:
            assert_target_list_page_ready_for_empty_result(page, step)
        if row_count == 0 and empty_strategy != "pass":
            raise AssertionError("table_no_data_rows: 查询结果没有数据行。")
        matched_rows = self._matched_row_count(page, criteria)
        if criteria and matched_rows == 0:
            raise AssertionError(
                "table_query_target_not_found: 查询后列表中未找到目标数据行："
                + _format_criteria(criteria)
                + "。"
            )
        self.debug(
            ctx,
            {
                "strategy": "query_list",
                "criteriaKeys": list(criteria),
                "filledFields": filled_fields,
                "queryButtonClicked": clicked,
                "rowCount": row_count,
                "matchedRows": matched_rows,
            },
        )
        return handler_outcome(
            "query_handler",
            "table",
            0.88,
            {
                "query_button_clicked": clicked,
                "row_count": row_count,
                "matched_rows": matched_rows,
                "criteria": criteria,
                "filled_fields": filled_fields,
                "table": table_outcome.get("reason"),
            },
        )

    def count_rows(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        resolution = self.resolve_rules(ctx, intent="query_list", rule_types=["query", "table_detection"])
        self.emit_rule_hits(ctx, resolution)
        row_count = self.table_handler.row_count(page)
        empty_strategy = str(step.get("emptyStrategy") or step.get("empty_strategy") or "pass")
        if row_count == 0:
            assert_target_list_page_ready_for_empty_result(page, step)
        if row_count == 0 and empty_strategy != "pass":
            raise AssertionError("table_no_data_rows: 查询结果没有数据行。")
        self.debug(ctx, {"strategy": "query_table_count", "rowCount": row_count, "emptyStrategy": empty_strategy})
        return handler_outcome("table_count", row_count, 0.92, {"row_count": row_count, "empty_strategy": empty_strategy})

    def _fill_query_field(self, page: Any, label: str, value: Any) -> dict[str, Any] | None:
        try:
            field = page.get_by_label(label, exact=True)
            if self._fill_first(field, value):
                return {"label": label, "value": str(value), "strategy": "playwright_label_exact"}
        except PlaywrightError:
            pass
        try:
            field = page.get_by_placeholder(label, exact=False)
            if self._fill_first(field, value):
                return {"label": label, "value": str(value), "strategy": "playwright_placeholder"}
        except PlaywrightError:
            pass
        observed = self._fill_observed_control(page, label, value)
        if observed:
            return observed
        return self._fill_nearby_form_control(page, label, value)

    def _fill_first(self, locator: Any, value: Any) -> bool:
        try:
            for index in range(min(locator.count(), 6)):
                item = locator.nth(index)
                if item.is_visible(timeout=500) and item.is_enabled(timeout=500):
                    item.fill(str(value))
                    return True
        except PlaywrightError:
            return False
        return False

    def _fill_observed_control(self, page: Any, label: str, value: Any) -> dict[str, Any] | None:
        try:
            observation = self.locator.observer.observe(page)
        except Exception:
            return None
        controls = (
            observation.inputs
            + observation.textareas
            + observation.datePickers
            + observation.comboboxes
            + observation.personSelectors
            + observation.orgSelectors
            + observation.treeSelectors
        )
        for control in controls:
            if not control.get("visible") or not control.get("enabled"):
                continue
            haystack = [
                control.get("text"),
                control.get("label"),
                control.get("placeholder"),
                control.get("ariaLabel"),
                control.get("title"),
                control.get("name"),
                *(control.get("nearbyText") or []),
            ]
            if not _matches_label(label, haystack):
                continue
            selector = str(control.get("selector") or "")
            if not selector:
                continue
            try:
                locator = page.locator(selector)
                if self._fill_first(locator, value):
                    return {
                        "label": label,
                        "value": str(value),
                        "strategy": "page_observer_control",
                        "selector": selector,
                        "elementRef": control.get("elementRef"),
                    }
            except PlaywrightError:
                continue
        return None

    def _fill_nearby_form_control(self, page: Any, label: str, value: Any) -> dict[str, Any] | None:
        containers = [
            ".el-form-item",
            ".ant-form-item",
            ".form-item",
            ".form-group",
            "[class*='form-item']",
            "[class*='formItem']",
        ]
        for container in containers:
            try:
                candidates = page.locator(container).filter(has_text=re.compile(re.escape(label)))
                for index in range(min(candidates.count(), 8)):
                    field = candidates.nth(index).locator(
                        "input:not([type='hidden']):not([type='button']):not([type='submit']), textarea"
                    )
                    if self._fill_first(field, value):
                        return {"label": label, "value": str(value), "strategy": "nearby_form_control"}
            except PlaywrightError:
                continue
        return None

    def _matched_row_count(self, page: Any, criteria: dict[str, Any]) -> int | None:
        values = [str(value).strip() for value in criteria.values() if value not in (None, "")]
        if not values:
            return None
        matched = 0
        for row in self.table_handler.data_rows(page, max_rows=100):
            try:
                row_text = _compact_text(row.inner_text(timeout=800))
            except PlaywrightError:
                continue
            if all(_compact_text(value) in row_text for value in values):
                matched += 1
        return matched

    def _click_query_button(self, page: Any) -> bool:
        for name in ["查询", "搜索", "筛选"]:
            try:
                button = page.get_by_role("button", name=name, exact=True)
                if button.count() > 0 and button.first.is_visible(timeout=500):
                    button.first.click()
                    return True
            except PlaywrightError:
                continue
        return False


def _extract_query_criteria(step: dict[str, Any]) -> dict[str, Any]:
    criteria: dict[str, Any] = {}
    for key in [
        "criteria",
        "query",
        "queryConditions",
        "query_conditions",
        "conditions",
        "filters",
        "filterConditions",
        "filter_conditions",
        "search",
    ]:
        value = step.get(key)
        if isinstance(value, dict):
            for field, field_value in value.items():
                if field_value not in (None, ""):
                    criteria[str(field)] = field_value
    if not criteria:
        criteria.update(_criteria_from_text(" ".join(str(step.get(key) or "") for key in ["target", "name", "description", "readableDescription"])))
    return criteria


def _criteria_from_text(text: str) -> dict[str, str]:
    criteria: dict[str, str] = {}
    for field in ["实例号", "流程实例号", "编号", "单号", "申请编号"]:
        match = re.search(rf"{field}\s*[“\"']?([A-Za-z0-9_-]{{3,}})[”\"']?", text)
        if match:
            criteria[field] = match.group(1)
            return criteria
    quoted = re.search(r"[“\"']([A-Za-z0-9_-]{3,})[”\"']", text)
    if quoted and re.search(r"查询|搜索|筛选|查找", text):
        criteria["关键字"] = quoted.group(1)
    return criteria


def _matches_label(label: str, values: list[Any]) -> bool:
    target = _compact_text(label)
    if not target:
        return False
    for value in values:
        current = _compact_text(str(value or ""))
        if current and (target == current or target in current or current in target):
            return True
    return False


def _compact_text(value: Any) -> str:
    return re.sub(r"[\s：:，,。]+", "", str(value or ""))


def _format_criteria(criteria: dict[str, Any]) -> str:
    return "，".join(f"{key}={value}" for key, value in criteria.items() if value not in (None, ""))
