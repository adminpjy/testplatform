import re
from typing import Any, Callable, TypeVar

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

T = TypeVar("T")


def _strategy(code: str, label: str, *, automatic: bool = True) -> dict[str, Any]:
    return {"code": code, "label": label, "automatic": automatic}


class RecoveryPolicy:
    strategy_catalog: dict[str, list[dict[str, Any]]] = {
        "menu_parent_not_found": [
            _strategy("reobserve_page", "重新读取页面菜单结构"),
            _strategy("try_top_nav", "尝试顶部导航"),
            _strategy("try_dashboard_card", "尝试首页卡片或快捷入口"),
            _strategy("try_menu_search", "尝试菜单搜索"),
            _strategy("try_iframe", "尝试 iframe 内菜单"),
            _strategy("ask_human", "请求人工教学", automatic=False),
        ],
        "menu_child_not_found": [
            _strategy("expand_parent_menu", "重新展开父菜单"),
            _strategy("try_top_nav", "尝试顶部导航"),
            _strategy("try_dashboard_card", "尝试首页卡片"),
            _strategy("try_menu_search", "尝试菜单搜索"),
            _strategy("try_iframe", "尝试 iframe"),
            _strategy("ask_human", "请求人工教学", automatic=False),
        ],
        "menu_expand_failed": [
            _strategy("retry_expand_parent_menu", "重新展开父菜单"),
            _strategy("try_keyboard_expand", "尝试键盘展开"),
            _strategy("try_menu_search", "尝试菜单搜索"),
            _strategy("ask_human", "请求人工介入", automatic=False),
        ],
        "navigation_goal_not_reached": [
            _strategy("wait_and_reobserve", "等待页面加载后重新观察"),
            _strategy("try_alternate_navigation", "尝试备用导航入口"),
            _strategy("check_global_interruption", "检查弹窗或中断页"),
            _strategy("ask_human", "请求人工确认目标页面特征", automatic=False),
        ],
        "navigation_path_unresolved": [
            _strategy("try_menu_search", "尝试菜单搜索"),
            _strategy("try_dashboard_card", "尝试首页卡片"),
            _strategy("try_iframe", "尝试 iframe"),
            _strategy("ask_human", "请求人工教学", automatic=False),
        ],
        "table_not_found": [
            _strategy("wait_for_page_ready", "等待页面加载完成"),
            _strategy("reobserve_page", "重新读取页面"),
            _strategy("try_grid_role", "尝试 grid 结构"),
            _strategy("ask_human", "请求人工标注表格区域", automatic=False),
        ],
        "table_no_data_rows": [
            _strategy("check_empty_state", "检查是否为空状态"),
            _strategy("refresh_table", "刷新列表"),
            _strategy("adjust_query_conditions", "调整查询条件", automatic=False),
        ],
        "table_target_row_not_found": [
            _strategy("relax_row_match", "放宽行匹配条件"),
            _strategy("try_pagination", "尝试分页查找"),
            _strategy("ask_human", "请求补充目标记录条件", automatic=False),
        ],
        "table_no_action_found": [
            _strategy("try_more_actions", "尝试更多菜单"),
            _strategy("try_id_link", "尝试编号链接"),
            _strategy("try_detail_button", "尝试详情按钮"),
            _strategy("skip_non_processable_row", "跳过不可处理行"),
            _strategy("ask_human", "请求人工标注行内操作", automatic=False),
        ],
        "table_row_loop_failed": [
            _strategy("continue_next_row", "继续下一行"),
            _strategy("summarize_failed_rows", "汇总失败行"),
            _strategy("ask_human", "请求人工处理失败行", automatic=False),
        ],
        "form_required_field_missing": [
            _strategy("use_default_data_rules", "使用默认测试数据规则"),
            _strategy("request_test_data", "请求补充必填字段", automatic=False),
        ],
        "form_field_not_found": [
            _strategy("nearby_label_match", "尝试邻近标签匹配"),
            _strategy("page_semantic_extract", "重新提取表单语义"),
            _strategy("ask_human", "请求人工标注字段", automatic=False),
        ],
        "form_validation_error": [
            _strategy("read_validation_message", "读取校验错误"),
            _strategy("refill_invalid_fields", "重填校验失败字段"),
            _strategy("request_test_data", "请求补充合法字段值", automatic=False),
        ],
        "dropdown_not_found": [
            _strategy("nearby_label_match", "按标签邻近区域查找"),
            _strategy("try_combobox_role", "尝试 combobox 角色"),
            _strategy("ask_human", "请求人工标注下拉框", automatic=False),
        ],
        "dropdown_option_not_found": [
            _strategy("search_option_text", "尝试搜索选项"),
            _strategy("scroll_options", "滚动下拉选项"),
            _strategy("semantic_match_option", "尝试语义匹配"),
            _strategy("request_option_value", "请求人工补充选项值", automatic=False),
        ],
        "dropdown_popup_not_opened": [
            _strategy("retry_open_dropdown", "重新打开下拉框"),
            _strategy("keyboard_arrow_down", "尝试键盘展开"),
            _strategy("ask_human", "请求人工介入", automatic=False),
        ],
        "date_picker_not_found": [
            _strategy("direct_input_date", "尝试直接输入日期"),
            _strategy("nearby_label_match", "按标签重新定位日期控件"),
            _strategy("ask_human", "请求人工标注日期控件", automatic=False),
        ],
        "date_not_selectable": [
            _strategy("choose_next_enabled_date", "选择下一个可用日期"),
            _strategy("direct_input_date", "尝试直接输入日期"),
            _strategy("request_date_value", "请求补充可用日期", automatic=False),
        ],
        "org_selector_not_found": [
            _strategy("try_tree_select", "尝试组织树"),
            _strategy("try_modal_selector", "尝试弹窗选择机构"),
            _strategy("ask_human", "请求人工标注机构选择器", automatic=False),
        ],
        "org_value_missing": [
            _strategy("request_org_value", "提示用户补充组织机构", automatic=False),
        ],
        "org_node_not_found": [
            _strategy("search_org", "搜索机构"),
            _strategy("expand_org_tree", "展开组织树"),
            _strategy("request_org_value", "请求确认机构名称", automatic=False),
        ],
        "person_selector_not_found": [
            _strategy("try_person_dialog", "尝试人员选择弹窗"),
            _strategy("try_department_tree", "尝试部门人员树"),
            _strategy("ask_human", "请求人工标注人员选择器", automatic=False),
        ],
        "person_value_missing": [
            _strategy("request_person_value", "提示用户补充人员", automatic=False),
        ],
        "person_not_found": [
            _strategy("search_person", "搜索人员"),
            _strategy("request_person_value", "请求确认人员姓名或工号", automatic=False),
        ],
        "dialog_not_found": [
            _strategy("wait_and_retry", "等待后重试"),
            _strategy("check_click_effect", "检查上一步点击是否生效"),
            _strategy("ask_human", "请求人工介入", automatic=False),
        ],
        "confirm_dialog_not_found": [
            _strategy("try_common_confirm_buttons", "查找通用确认按钮"),
            _strategy("ask_human", "请求人工确认弹窗", automatic=False),
        ],
        "blocking_dialog_unhandled": [
            _strategy("handle_low_risk_continue", "处理低风险继续按钮"),
            _strategy("ask_human", "请求人工判断弹窗风险", automatic=False),
        ],
        "approval_entry_not_found": [
            _strategy("try_row_actions", "查找行内审批入口"),
            _strategy("try_more_actions", "尝试更多菜单"),
            _strategy("ask_human", "请求人工标注审批入口", automatic=False),
        ],
        "approval_result_option_not_found": [
            _strategy("find_radio_option", "查找通过/驳回单选项"),
            _strategy("find_select_option", "查找审批结果下拉框"),
            _strategy("fill_opinion_and_submit", "填写审批意见后提交"),
            _strategy("ask_human", "请求人工介入", automatic=False),
        ],
        "approval_submit_failed": [
            _strategy("read_validation_message", "读取审批提交校验错误"),
            _strategy("retry_submit_once", "重试提交一次"),
            _strategy("ask_human", "请求人工介入", automatic=False),
        ],
        "approval_status_not_changed": [
            _strategy("wait_and_reobserve", "等待后重新验证状态"),
            _strategy("refresh_table", "刷新列表"),
            _strategy("ask_human", "请求人工确认审批状态", automatic=False),
        ],
        "vision_fallback_not_configured": [
            _strategy("continue_dom_llm_flow", "继续使用 DOM 与语义定位"),
            _strategy("configure_vision_model", "配置视觉兜底模型", automatic=False),
        ],
    }

    def retry_once(self, operation: Callable[[], T]) -> T:
        try:
            return operation()
        except PlaywrightTimeoutError:
            return operation()

    def analyze_failure(
        self,
        *,
        error_summary: str | None = None,
        action: str | None = None,
        target: str | None = None,
        failure_type: str | None = None,
        fallback_reason: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized = self.normalize_failure_type(
            error_summary=error_summary,
            action=action,
            target=target,
            failure_type=failure_type,
            fallback_reason=fallback_reason,
            details=details,
        )
        strategies = self.strategies_for(normalized)
        return {
            "failureType": normalized,
            "category": _category(normalized),
            "summary": _summary(normalized, target=target, error_summary=error_summary),
            "suggestedRecovery": strategies,
            "attemptedStrategies": _attempted_strategies(details),
            "canIntervene": True,
            "canGenerateRuleDraft": normalized not in {"org_value_missing", "person_value_missing"},
            "visionFallback": _vision_fallback_status(failure_type, fallback_reason, details),
        }

    def normalize_failure_type(
        self,
        *,
        error_summary: str | None = None,
        action: str | None = None,
        target: str | None = None,
        failure_type: str | None = None,
        fallback_reason: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> str:
        explicit = _clean_failure_type(failure_type)
        fallback = _clean_failure_type(fallback_reason)
        text = " ".join(str(item or "") for item in [error_summary, action, target, explicit, fallback, details])
        detected = _detect_from_text(text)
        if explicit and explicit != "vision_fallback_not_configured":
            return _canonicalize(explicit, text)
        if detected and detected != "vision_fallback_not_configured":
            return detected
        if fallback and fallback != "vision_fallback_not_configured":
            return _canonicalize(fallback, text)
        if explicit == "vision_fallback_not_configured" or fallback == "vision_fallback_not_configured":
            if str(action or "") in {"navigate_path", "navigate_menu", "business_goal"}:
                return "navigation_path_unresolved"
            if str(action or "").startswith("query"):
                return "table_not_found"
            return "vision_fallback_not_configured"
        return _infer_from_action(str(action or ""), text)

    def strategies_for(self, failure_type: str) -> list[dict[str, Any]]:
        return list(self.strategy_catalog.get(failure_type) or [_strategy("ask_human", "请求人工介入", automatic=False)])

def _clean_failure_type(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    if ":" in text:
        text = text.split(":", 1)[0].strip()
    text = text.strip().lower()
    return text or None


def _detect_from_text(text: str) -> str | None:
    lower = text.lower()
    patterns = [
        ("menu_parent_not_found", ["menu_parent_not_found", "未找到一级菜单"]),
        ("menu_child_not_found", ["menu_child_not_found", "未找到二级菜单", "但未找到"]),
        ("menu_expand_failed", ["menu_expand_failed", "展开失败"]),
        ("navigation_goal_not_reached", ["navigation_goal_not_reached", "没有检测到目标页面证据"]),
        ("table_not_found", ["table_not_found", "未识别到可见表格", "table not found"]),
        ("table_no_data_rows", ["table_no_data_rows", "table has no rows", "没有可处理数据行"]),
        ("table_target_row_not_found", ["table_target_row_not_found"]),
        ("table_no_action_found", ["table_no_action_found", "no clickable row entry", "没有可点击入口"]),
        ("table_row_loop_failed", ["table_row_loop_failed"]),
        ("form_required_field_missing", ["form_required_field_missing", "required field"]),
        ("form_field_not_found", ["form_field_not_found", "control_not_found", "field not found"]),
        ("form_validation_error", ["form_validation_error", "不能为空", "必填", "校验"]),
        ("dropdown_not_found", ["dropdown_not_found"]),
        ("dropdown_option_not_found", ["dropdown_option_not_found", "option not found"]),
        ("dropdown_popup_not_opened", ["dropdown_popup_not_opened"]),
        ("date_picker_not_found", ["date_picker_not_found"]),
        ("date_not_selectable", ["date_not_selectable"]),
        ("org_value_missing", ["needs_clarification:组织机构", "org_value_missing", "组织机构", "所属机构"]),
        ("org_selector_not_found", ["org_selector_not_found"]),
        ("org_node_not_found", ["org_node_not_found"]),
        ("person_value_missing", ["needs_clarification:审批人", "needs_clarification:负责人", "person_value_missing"]),
        ("person_selector_not_found", ["person_selector_not_found"]),
        ("person_not_found", ["person_not_found"]),
        ("dialog_not_found", ["dialog_not_found", "dialog did not appear"]),
        ("confirm_dialog_not_found", ["confirm_dialog_not_found"]),
        ("blocking_dialog_unhandled", ["blocking_dialog_unhandled"]),
        ("approval_entry_not_found", ["approval_entry_not_found"]),
        ("approval_result_option_not_found", ["approval_result_option_not_found"]),
        ("approval_submit_failed", ["approval_submit_failed"]),
        ("approval_status_not_changed", ["approval_status_not_changed"]),
        ("vision_fallback_not_configured", ["vision_fallback_not_configured"]),
    ]
    for failure_type, tokens in patterns:
        if any(token.lower() in lower for token in tokens):
            return failure_type
    return None


def _canonicalize(value: str, text: str) -> str:
    if value == "needs_clarification":
        if any(token in text for token in ["组织机构", "所属机构", "部门", "单位"]):
            return "org_value_missing"
        if any(token in text for token in ["审批人", "负责人", "经办人", "人员"]):
            return "person_value_missing"
        return "form_required_field_missing"
    if value == "needs_vision_fallback":
        return "vision_fallback_not_configured"
    return value


def _infer_from_action(action: str, text: str) -> str:
    if action in {"navigate_path", "navigate_menu"}:
        return "navigation_path_unresolved"
    if action in {"query_table", "query_table_count"}:
        return "table_not_found"
    if action in {"process_table_rows", "for_each_table_row"}:
        return "table_row_loop_failed"
    if action in {"open_table_row", "open_row_link_or_detail", "click_table_row_action"}:
        return "table_no_action_found"
    if action in {"auto_fill_form", "fill_form", "input"}:
        if any(token in text for token in ["组织机构", "部门", "单位"]):
            return "org_value_missing"
        if any(token in text for token in ["审批人", "负责人", "人员"]):
            return "person_value_missing"
        return "form_field_not_found"
    if action == "select":
        return "dropdown_option_not_found"
    if action == "wait_for_dialog":
        return "dialog_not_found"
    if action == "business_goal" and "审批" in text:
        return "approval_entry_not_found"
    return f"{action}_failed" if action else "unknown_failure"


def _category(failure_type: str) -> str:
    if failure_type.startswith(("menu_", "navigation_")):
        return "navigation"
    if failure_type.startswith("table_"):
        return "table"
    if failure_type.startswith("form_"):
        return "form"
    if failure_type.startswith("dropdown_"):
        return "dropdown"
    if failure_type.startswith("date_"):
        return "date_picker"
    if failure_type.startswith("org_"):
        return "org_selector"
    if failure_type.startswith("person_"):
        return "person_selector"
    if failure_type.startswith(("dialog_", "confirm_", "blocking_")):
        return "dialog"
    if failure_type.startswith("approval_"):
        return "approval"
    if failure_type.startswith("vision_"):
        return "vision"
    return "unknown"


def _summary(failure_type: str, *, target: str | None, error_summary: str | None) -> str:
    labels = {
        "menu_child_not_found": "未找到目标子菜单。",
        "menu_parent_not_found": "未找到目标父菜单。",
        "navigation_goal_not_reached": "已尝试导航，但未达到目标页面。",
        "table_no_action_found": "未找到可执行的行内操作。",
        "table_no_data_rows": "表格没有可处理的数据行。",
        "org_value_missing": "组织机构是关键字段，需要用户补充。",
        "person_value_missing": "人员字段需要用户补充。",
        "dropdown_option_not_found": "下拉选项不存在或不可见。",
        "approval_result_option_not_found": "未找到审批结果选项。",
    }
    base = labels.get(failure_type) or (error_summary or "步骤执行失败。")
    return f"{base} 目标：{target}" if target else base


def _attempted_strategies(details: dict[str, Any] | None) -> list[Any]:
    if not isinstance(details, dict):
        return []
    navigation = details.get("navigation_result")
    if isinstance(navigation, dict):
        return list(navigation.get("attemptedStrategies") or [])
    return list(details.get("attemptedStrategies") or details.get("candidates") or [])


def _vision_fallback_status(failure_type: str | None, fallback_reason: str | None, details: dict[str, Any] | None) -> str | None:
    if failure_type == "vision_fallback_not_configured" or fallback_reason == "vision_fallback_not_configured":
        return "not_configured"
    if isinstance(details, dict):
        navigation = details.get("navigation_result")
        if isinstance(navigation, dict):
            return navigation.get("visionFallback")
        if details.get("visionFallback"):
            return str(details["visionFallback"])
    return None
