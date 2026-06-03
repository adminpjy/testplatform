import re
from typing import Any


NON_HYPHEN_PATH_SEPARATORS_PATTERN = r"\s*(?:/|>|→|\\)\s*"
PORTAL_ROOTS = {"系统导航"}
PORTAL_CATEGORY_HINTS = {
    "我的应用",
    "办公自动化",
    "财务",
    "财务管理",
    "生产",
    "生产经营",
    "设备",
    "设备管理",
    "采购",
    "采购管理",
    "销售",
    "销售管理",
    "安环",
    "安全环保",
    "综合",
    "综合管理",
    "人力资源",
    "信息化",
}


class DslPostProcessor:
    def normalize_dsl(self, dsl: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(dsl)
        normalized["testData"] = dict(normalized.get("testData") or {})
        normalized_steps = [self.normalize_step(step) for step in normalized.get("steps") or [] if isinstance(step, dict)]
        folded_steps = _fold_table_row_substeps(
            _relax_brittle_login_success_assertions(normalized_steps),
            normalized["testData"],
        )
        normalized["steps"] = _ensure_todo_list_navigation(_normalize_query_row_context(folded_steps))
        for step in normalized["steps"]:
            _merge_step_test_data(normalized["testData"], step)
        missing_fields = list(normalized.get("missingFields") or [])
        missing_fields.extend(_collect_missing_fields(normalized))
        normalized["missingFields"] = list(dict.fromkeys(str(item) for item in missing_fields if str(item).strip()))
        if normalized["missingFields"]:
            questions = list(normalized.get("clarifyingQuestions") or [])
            questions.extend(_question_for_missing_field(item) for item in normalized["missingFields"])
            normalized["clarifyingQuestions"] = list(dict.fromkeys(question for question in questions if question))
        return normalized

    def normalize_step(self, step: dict[str, Any]) -> dict[str, Any]:
        current = dict(step)
        action = str(current.get("action") or "")
        target = str(current.get("target") or "")

        if action == "open_url":
            _remove_auth_precondition(current)
            return current

        if _is_login_transition_wait(current):
            _remove_auth_precondition(current)
            return current

        if action == "for_each_table_row":
            _remember_original(current, action, target, "for_each_table_row is normalized to process_table_rows")
            current["action"] = "process_table_rows"
            current.setdefault("loopPolicy", _loop_policy_from_step(current))
            current.setdefault("readableDescription", "处理表格中的所有数据行")
            action = "process_table_rows"

        if action == "process_table_rows":
            current.setdefault("loopPolicy", _loop_policy_from_step(current))
            _normalize_existing_row_steps(current)

        if action in {"click", "confirm_dialog", "click_table_row_action"} and _is_approval_pass_target(target):
            _remember_original(current, action, target, "approval pass click is normalized to business goal")
            current["action"] = "business_goal"
            current["intent"] = "approval_pass"
            current["target"] = "审批通过"
            current.setdefault("readableDescription", "审批通过")
            _ensure_auth_precondition(current)
            return current

        if _is_approval_flow_target(target):
            if action != "business_goal" or current.get("intent") != "approval_flow_view":
                _remember_original(current, action, target, "approval flow view is normalized to business goal")
            current["action"] = "business_goal"
            current["intent"] = "approval_flow_view"
            current["target"] = "查看审批流程"
            current.setdefault("readableDescription", "查看审批流程")
            _ensure_auth_precondition(current)
            return current

        if action == "navigate_path":
            segments = _path_segments(current.get("pathSegments") or current.get("path_segments") or target)
            if len(segments) >= 2:
                current["pathSegments"] = segments
                current["navigationType"] = current.get("navigationType") or _navigation_type_for_segments(segments)
                _ensure_navigation_defaults(current, segments)
            _ensure_auth_precondition(current)
            return current

        if action in {"business_goal", "navigate_menu", "click"}:
            segments = _path_segments(target)
            if len(segments) >= 2:
                _remember_original(current, action, target, "target contains menu path separator")
                current["action"] = "navigate_path"
                current["pathSegments"] = segments
                current["navigationType"] = _navigation_type_for_segments(segments)
                current["readableDescription"] = f"菜单路径导航：{' → '.join(segments)}"
                _ensure_navigation_defaults(current, segments)
        _ensure_auth_precondition(current)
        return current


def normalize_dsl(dsl: dict[str, Any]) -> dict[str, Any]:
    return DslPostProcessor().normalize_dsl(dsl)


def _normalize_query_row_context(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    last_query_criteria: dict[str, Any] = {}
    for step in steps:
        current = dict(step)
        action = str(current.get("action") or "")
        intent = str((current.get("operationIntent") or {}).get("intent") or current.get("intent") or "")
        criteria = _extract_query_criteria(current)
        if criteria and action in {"query_table", "query_table_count"} and not isinstance(current.get("criteria"), dict):
            current["criteria"] = dict(criteria)
        if (
            last_query_criteria
            and action in {"open_table_row", "open_row_link_or_detail", "click_table_row_action"}
            and not isinstance(current.get("rowCriteria"), dict)
            and not isinstance(current.get("row_criteria"), dict)
        ):
            current["rowCriteria"] = dict(last_query_criteria)
        if criteria and (action in {"query_table", "query_table_count"} or intent == "query_list"):
            last_query_criteria = dict(criteria)
        normalized.append(current)
    return normalized


def _ensure_todo_list_navigation(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    todo_navigation_seen = False
    inserted = False
    for index, step in enumerate(steps):
        current = dict(step)
        if _is_todo_navigation_step(current):
            todo_navigation_seen = True
        if (_is_todo_list_action(current) or _is_query_before_todo_list_action(steps, index)) and not todo_navigation_seen and not inserted:
            nav_step = {
                "action": "navigate_path",
                "target": "工作台/我的待办",
                "pathSegments": ["工作台", "我的待办"],
                "navigationType": "menu_path",
                "readableDescription": "进入我的待办列表",
                "normalizedBy": "DslPostProcessor",
                "normalizationReason": "todo list operation requires entering 工作台/我的待办 first",
            }
            _ensure_navigation_defaults(nav_step, nav_step["pathSegments"])
            _ensure_auth_precondition(nav_step)
            normalized.append(nav_step)
            todo_navigation_seen = True
            inserted = True
        normalized.append(current)
    return normalized


def _is_todo_navigation_step(step: dict[str, Any]) -> bool:
    action = str(step.get("action") or "")
    target = _flatten(
        {
            "target": step.get("target"),
            "pathSegments": step.get("pathSegments") or step.get("path_segments"),
            "description": step.get("description"),
            "readableDescription": step.get("readableDescription"),
        }
    )
    return action in {"navigate_path", "navigate_menu", "business_goal", "click"} and "待办" in target


def _is_todo_list_action(step: dict[str, Any]) -> bool:
    action = str(step.get("action") or "")
    intent = str((step.get("operationIntent") or {}).get("intent") or step.get("intent") or "")
    if action not in {"query_table", "query_table_count", "process_table_rows", "open_table_row", "open_row_link_or_detail", "click_table_row_action"}:
        return False
    if intent and intent not in {"query_list", "process_table_rows", "open_table_row", "click_table_row_action"}:
        return False
    return "待办" in _flatten(step)


def _is_query_before_todo_list_action(steps: list[dict[str, Any]], index: int) -> bool:
    step = steps[index]
    if str(step.get("action") or "") not in {"query_table", "query_table_count"}:
        return False
    if "待办" in _flatten(step):
        return False
    for next_step in steps[index + 1 :]:
        next_action = str(next_step.get("action") or "")
        if _is_todo_navigation_step(next_step):
            return False
        if _is_todo_list_action(next_step):
            return True
        if next_action in {"query_table", "query_table_count", "business_goal", "navigate_path", "navigate_menu"}:
            return False
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
    return criteria


def _fold_table_row_substeps(steps: list[dict[str, Any]], test_data: dict[str, Any]) -> list[dict[str, Any]]:
    folded: list[dict[str, Any]] = []
    index = 0
    while index < len(steps):
        current = dict(steps[index])
        if str(current.get("action") or "") != "process_table_rows":
            folded.append(current)
            index += 1
            continue

        body_steps: list[dict[str, Any]] = []
        scan = index + 1
        while scan < len(steps) and _is_table_loop_approval_body_step(steps[scan]):
            body_steps.append(dict(steps[scan]))
            scan += 1

        if body_steps or _has_approval_row_steps(current):
            opinion = _opinion_from_steps_or_test_data(body_steps, test_data)
            _configure_table_loop_for_approval(current, opinion=opinion)
            current.setdefault("normalizationReason", "table row follow-up approval steps folded into rowSteps")
            current["normalizedBy"] = "DslPostProcessor"
            folded.append(current)
            index = scan
            continue

        folded.append(current)
        index += 1
    return folded


def _is_table_loop_approval_body_step(step: dict[str, Any]) -> bool:
    action = str(step.get("action") or "")
    intent = str((step.get("operationIntent") or {}).get("intent") or step.get("intent") or "")
    text = _flatten(
        {
            "target": step.get("target"),
            "description": step.get("description"),
            "readableDescription": step.get("readableDescription"),
            "name": step.get("name"),
            "stepName": step.get("stepName") or step.get("step_name"),
            "formData": step.get("formData"),
        }
    )
    if action == "wait":
        return True
    if action in {"open_table_row", "open_row_link_or_detail", "click_table_row_action"}:
        return True
    if action in {"fill_form", "auto_fill_form"} and any(token in text for token in ["意见", "审批", "审核", "办理", "处理"]):
        return True
    if action in {"click", "confirm_dialog"} and any(token in text for token in ["第一行", "任意列", "待办", "提交", "审批", "审核", "同意", "通过", "办理", "处理"]):
        return True
    if action == "business_goal" and intent in {"approval_pass", "approval_reject"}:
        return True
    if action == "business_goal" and any(token in text for token in ["审批", "审核", "同意", "通过", "提交"]):
        return True
    if action == "close_dialog_by_common_controls":
        return True
    return False


def _has_approval_row_steps(step: dict[str, Any]) -> bool:
    loop_policy = step.get("loopPolicy") if isinstance(step.get("loopPolicy"), dict) else {}
    for key in ["rowSteps", "row_steps", "subSteps", "sub_steps", "bodySteps", "body_steps"]:
        value = step.get(key) or loop_policy.get(key)
        if not isinstance(value, list):
            continue
        if any(_is_table_loop_approval_body_step(item) for item in value if isinstance(item, dict)):
            return True
    return False


def _opinion_from_steps_or_test_data(body_steps: list[dict[str, Any]], test_data: dict[str, Any]) -> str | None:
    for step in body_steps:
        for key in ["value", "opinion", "opinionText", "approvalOpinion", "comment", "commentText"]:
            value = step.get(key)
            if value not in (None, ""):
                return str(value)
        for mapping_key in ["formData", "testData"]:
            mapping = step.get(mapping_key)
            if isinstance(mapping, dict):
                value = _opinion_from_mapping(mapping)
                if value:
                    return value
    return _opinion_from_mapping(test_data)


def _opinion_from_mapping(mapping: dict[str, Any]) -> str | None:
    for key in ["我的意见", "审批意见", "审核意见", "处理意见", "办理意见", "意见", "opinion", "comment"]:
        value = mapping.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _configure_table_loop_for_approval(step: dict[str, Any], *, opinion: str | None) -> None:
    loop_policy = dict(step.get("loopPolicy") or step.get("loop_policy") or {})
    loop_policy.setdefault("maxRows", int(step.get("maxRows") or step.get("max_rows") or 30))
    loop_policy.setdefault("emptyStrategy", step.get("emptyStrategy") or step.get("empty_strategy") or "pass")
    loop_policy.setdefault("rowAction", "open_todo")
    loop_policy.setdefault("openMode", "new_page_or_same_page")
    loop_policy.setdefault("closeStrategy", "close_new_page_or_return_to_list")
    loop_policy.setdefault("maxDurationMs", 600_000)
    loop_policy.setdefault("rowProbeTimeoutMs", 250)
    loop_policy.setdefault("maxConsecutiveFailures", 3)
    loop_policy.setdefault("continueOnRowFailure", True)
    loop_policy.setdefault("stopAfterInitialRows", True)
    loop_policy.setdefault("followNewRows", False)
    loop_policy.setdefault(
        "rowEntryLabels",
        ["相关办理人处理", "办理人处理", "待办处理", "办理", "处理", "审批", "审核", "标题", "文号", "单号"],
    )
    row_step = _approval_row_step(opinion)
    loop_policy["rowSteps"] = [row_step]
    step["loopPolicy"] = loop_policy
    step["rowSteps"] = [row_step]
    step.setdefault("target", "我的待办列表")
    step.setdefault("readableDescription", "逐条打开待办并提交审批意见")


def _approval_row_step(opinion: str | None) -> dict[str, Any]:
    form_data = {}
    if opinion:
        form_data = {"我的意见": opinion, "审批意见": opinion, "意见": opinion}
    row_step: dict[str, Any] = {
        "action": "business_goal",
        "target": "审批通过",
        "intent": "approval_pass",
        "readableDescription": "填写审批意见并提交",
    }
    if opinion:
        row_step["value"] = opinion
        row_step["formData"] = form_data
    return row_step


def _normalize_existing_row_steps(step: dict[str, Any]) -> None:
    loop_policy = dict(step.get("loopPolicy") or step.get("loop_policy") or {})
    for key in ["rowSteps", "row_steps", "subSteps", "sub_steps", "bodySteps", "body_steps"]:
        value = step.get(key) if isinstance(step.get(key), list) else loop_policy.get(key)
        if not isinstance(value, list):
            continue
        normalized = []
        for item in value:
            if not isinstance(item, dict):
                continue
            current = dict(item)
            action = str(current.get("action") or "")
            target = str(current.get("target") or "")
            if action in {"click", "confirm_dialog", "click_table_row_action"} and _is_approval_pass_target(target):
                current["action"] = "business_goal"
                current["intent"] = "approval_pass"
                current["target"] = "审批通过"
            normalized.append(current)
        step[key] = normalized
        loop_policy[key] = normalized
    if loop_policy:
        step["loopPolicy"] = loop_policy


def parse_menu_path(target: str) -> list[str]:
    return _path_segments(target)


def _path_segments(value: Any) -> list[str]:
    if isinstance(value, list):
        cleaned_items = [_clean_segment(str(item), index) for index, item in enumerate(value) if _clean_segment(str(item), index)]
        if len(cleaned_items) == 1:
            return _path_segments_from_text(cleaned_items[0]) or cleaned_items
        flattened: list[str] = []
        for item in cleaned_items:
            nested = _path_segments_from_text(item)
            flattened.extend(nested or [item])
        return _normalize_portal_segments(flattened)
    return _path_segments_from_text(str(value or ""))


def _path_segments_from_text(value: str) -> list[str]:
    text = str(value or "").strip()
    if not text or "://" in text:
        return []
    if not re.search(r"[/>\-→\\]", text):
        return []
    if re.search(r"[/>\u2192\\]", text):
        return _normalize_portal_segments(
            [
                cleaned
                for index, segment in enumerate(re.split(NON_HYPHEN_PATH_SEPARATORS_PATTERN, text))
                if (cleaned := _clean_segment(segment, index))
            ]
        )
    if "-" in text:
        return _split_hyphen_path(text)
    return []


def _split_hyphen_path(text: str) -> list[str]:
    parts = [
        cleaned
        for index, segment in enumerate(re.split(r"\s*-\s*", text))
        if (cleaned := _clean_segment(segment, index))
    ]
    if len(parts) < 2:
        return []
    return _normalize_portal_segments(parts)


def _normalize_portal_segments(segments: list[str]) -> list[str]:
    if len(segments) < 3 or segments[0] not in PORTAL_ROOTS:
        return segments
    category_index = 1
    for index, segment in enumerate(segments[1:4], start=1):
        if _segment_base(segment) in PORTAL_CATEGORY_HINTS:
            category_index = index
            break
    root = segments[0]
    category = segments[category_index]
    app_name = "-".join(segments[category_index + 1 :]).strip()
    if not app_name:
        return segments
    return [root, category, app_name]


def _segment_base(segment: str) -> str:
    return re.sub(r"\s*[（(]\d+[）)]\s*$", "", segment).strip()


def _navigation_type_for_segments(segments: list[str]) -> str:
    if len(segments) >= 3 and segments[0] in PORTAL_ROOTS:
        return "portal_app_path"
    return "menu_path"


def _clean_segment(segment: str, index: int) -> str:
    cleaned = segment.strip().strip("“”\"'，,。；;：:")
    if index == 0:
        cleaned = re.sub(r"^(进入|打开|点击|导航到|访问|前往|切换到|跳转到)", "", cleaned).strip()
    return cleaned


def _ensure_navigation_defaults(step: dict[str, Any], segments: list[str]) -> None:
    leaf = segments[-1]
    full_path = "/".join(segments)
    step.setdefault(
        "successCriteria",
        [
            f"页面出现{leaf}",
            f"菜单项{leaf}高亮",
            "出现目标列表或目标功能区",
            f"面包屑包含{full_path}",
        ],
    )
    step.setdefault(
        "fallbackStrategies",
        [
            "expand_parent_menu",
            "try_left_menu",
            "try_top_nav",
            "try_dashboard_card",
            "try_menu_search",
            "try_iframe",
            "llm_disambiguation",
            "vision_fallback_optional",
        ],
    )


def _relax_brittle_login_success_assertions(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    relaxed: list[dict[str, Any]] = []
    recently_login_step = False
    for step in steps:
        current = dict(step)
        if _is_login_step(current):
            relaxed.append(current)
            recently_login_step = True
            continue
        if _is_brittle_login_success_assertion(current, recently_login_step):
            relaxed.append(_login_success_stabilization_wait(current))
            recently_login_step = False
            continue
        relaxed.append(current)
        if str(current.get("action") or "") not in {"wait", "wait_for_text", "assert_text_exists"}:
            recently_login_step = False
    return relaxed


def _is_login_step(step: dict[str, Any]) -> bool:
    action = str(step.get("action") or "").lower()
    target = str(step.get("target") or "")
    intent = str(step.get("intent") or (step.get("operationIntent") or {}).get("intent") or "").lower()
    description = str(step.get("description") or step.get("readableDescription") or "")
    combined = f"{target} {description}".lower()
    if any(token in target for token in ["退出登录", "注销登录", "登出"]):
        return False
    if intent in {"login", "login_system", "username_password_login"}:
        return True
    if "登录" in combined or "登陆" in combined or "login" in combined or "sign in" in combined:
        return action in {"business_goal", "click", "submit", "fill_form", "auto_fill_form"}
    return False


def _is_login_transition_wait(step: dict[str, Any]) -> bool:
    if str(step.get("action") or "") != "wait":
        return False
    context_text = _flatten(
        {
            "target": step.get("target"),
            "description": step.get("description"),
            "readableDescription": step.get("readableDescription"),
            "stepName": step.get("stepName") or step.get("step_name") or step.get("name"),
        }
    )
    compact = re.sub(r"\s+", "", context_text)
    return any(token in compact for token in ["登录后页面稳定", "登陆后页面稳定", "登录后", "登陆后", "登录完成", "登陆完成"])


def _is_brittle_login_success_assertion(step: dict[str, Any], recently_login_step: bool) -> bool:
    action = str(step.get("action") or "")
    if action not in {"wait_for_text", "assert_text_exists"}:
        return False
    visible_text = _assertion_visible_text(step)
    context_text = _flatten(
        {
            "target": step.get("target"),
            "text": step.get("text"),
            "description": step.get("description"),
            "readableDescription": step.get("readableDescription"),
            "stepName": step.get("stepName") or step.get("step_name") or step.get("name"),
        }
    )
    if _mentions_login_success(context_text) and (_is_generic_login_home_marker(visible_text) or str(step.get("target") or "") in {"登录成功标识", "登录成功"}):
        return True
    return recently_login_step and _is_generic_login_home_marker(visible_text)


def _assertion_visible_text(step: dict[str, Any]) -> str:
    text = str(step.get("text") or "").strip()
    if text:
        return text
    return str(step.get("target") or "").strip()


def _mentions_login_success(value: str) -> bool:
    return any(token in value for token in ["登录成功", "登陆成功", "登录成功标识", "登陆成功标识", "登录后", "登陆后", "登录完成"])


def _is_generic_login_home_marker(value: str) -> bool:
    normalized = re.sub(r"[\s，,。；;：:\"'“”‘’]+", "", str(value or ""))
    if not normalized:
        return False
    return normalized in {"工作台", "首页", "主页", "门户", "门户首页", "系统首页", "后台首页", "Home", "home"}


def _login_success_stabilization_wait(step: dict[str, Any]) -> dict[str, Any]:
    next_step = dict(step)
    next_step["action"] = "wait"
    next_step["target"] = "登录后页面稳定"
    next_step["ms"] = _coerce_wait_ms(step.get("ms"), default=1500)
    next_step["description"] = "登录成功后可能进入门户首页、业务首页或中间页，不固定等待“工作台”等页面文字。"
    next_step.setdefault("originalAction", step.get("action"))
    next_step.setdefault("originalTarget", step.get("target"))
    next_step["normalizedBy"] = "DslPostProcessor"
    next_step["normalizationReason"] = "generic login success text assertion is relaxed to a stabilization wait"
    next_step.pop("text", None)
    next_step.pop("selector", None)
    return next_step


def _coerce_wait_ms(value: Any, *, default: int) -> int:
    try:
        wait_ms = int(float(str(value or default).strip()))
    except (TypeError, ValueError):
        wait_ms = default
    return max(100, min(wait_ms, 60000))


AUTH_REQUIRED_ACTIONS = {
    "navigate_path",
    "navigate_menu",
    "query_table",
    "query_table_count",
    "open_table_row",
    "open_row_link_or_detail",
    "process_table_rows",
    "for_each_table_row",
    "click_table_row_action",
    "auto_fill_form",
    "fill_form",
    "select",
    "upload_file",
    "wait_for_dialog",
    "close_dialog_by_common_controls",
    "assert_result",
    "summary_assert",
}

AUTH_REQUIRED_INTENTS = {
    "enter_page",
    "navigate_path",
    "query_list",
    "open_table_row",
    "process_table_rows",
    "click_table_row_action",
    "create_record",
    "update_record",
    "delete_record",
    "view_detail",
    "view_flow",
    "approval_pass",
    "approval_reject",
    "approval_flow_view",
    "fill_form",
    "fill_field",
    "select_dropdown",
    "select_date",
    "select_date_range",
    "select_org",
    "select_person",
    "upload_file",
    "assert_result",
}


def _ensure_auth_precondition(step: dict[str, Any]) -> None:
    if not _requires_auth(step):
        return
    current = step.get("preconditions")
    if isinstance(current, dict):
        current["authState"] = "logged_in"
        step["preconditions"] = current
        return
    step["preconditions"] = {"authState": "logged_in"}


def _remove_auth_precondition(step: dict[str, Any]) -> None:
    current = step.get("preconditions")
    if isinstance(current, dict):
        cleaned = dict(current)
        if cleaned.get("authState") == "logged_in":
            cleaned.pop("authState", None)
        if cleaned:
            step["preconditions"] = cleaned
        else:
            step.pop("preconditions", None)
        return
    if isinstance(current, list):
        cleaned = [item for item in current if str(item) != "auth_state_logged_in"]
        if cleaned:
            step["preconditions"] = cleaned
        else:
            step.pop("preconditions", None)


def _requires_auth(step: dict[str, Any]) -> bool:
    action = str(step.get("action") or "")
    target = str(step.get("target") or "")
    intent = str(step.get("intent") or (step.get("operationIntent") or {}).get("intent") or "")
    if action == "open_url":
        return False
    if _is_login_transition_wait(step):
        return False
    if _is_login_step(step):
        return False
    if action == "business_goal" and ("登录" in target or intent in {"login", "login_system", "username_password_login"}):
        return False
    if action in AUTH_REQUIRED_ACTIONS:
        return True
    if action == "business_goal":
        return intent in AUTH_REQUIRED_INTENTS or bool(intent)
    return intent in AUTH_REQUIRED_INTENTS


def _remember_original(step: dict[str, Any], action: str, target: str, reason: str) -> None:
    step.setdefault("originalAction", action)
    step.setdefault("originalTarget", target)
    step["normalizedBy"] = "DslPostProcessor"
    step["normalizationReason"] = reason


def _loop_policy_from_step(step: dict[str, Any]) -> dict[str, Any]:
    return {
        "maxRows": int(step.get("maxRows") or step.get("max_rows") or 30),
        "emptyStrategy": step.get("emptyStrategy") or step.get("empty_strategy") or "pass",
        "rowAction": step.get("rowAction") or step.get("row_action") or "open_link_or_detail",
        "closeStrategy": step.get("closeStrategy") or step.get("close_strategy") or "common_dialog_controls",
        "maxDurationMs": int(step.get("maxDurationMs") or step.get("timeoutMs") or 600_000),
        "rowProbeTimeoutMs": int(step.get("rowProbeTimeoutMs") or step.get("candidateTimeoutMs") or 250),
        "maxConsecutiveFailures": int(step.get("maxConsecutiveFailures") or 2),
    }


def _merge_step_test_data(test_data: dict[str, Any], step: dict[str, Any]) -> None:
    for key in ["formData", "testData"]:
        value = step.get(key)
        if isinstance(value, dict):
            for field, field_value in value.items():
                if field_value not in (None, ""):
                    test_data.setdefault(str(field), field_value)


def _collect_missing_fields(dsl: dict[str, Any]) -> list[str]:
    steps = [step for step in dsl.get("steps") or [] if isinstance(step, dict)]
    text = _flatten({"steps": steps})
    missing: list[str] = []
    if _mentions_any(text, ["组织机构", "所属机构", "部门", "所属部门", "单位"]) and not _has_any_value(
        dsl,
        ["组织机构", "所属机构", "部门", "所属部门", "单位"],
    ):
        missing.append("组织机构")
    if _mentions_any(text, ["审批人", "审核人"]) and not _has_any_value(dsl, ["审批人", "审核人"]):
        missing.append("审批人")
    if _mentions_any(text, ["上传", "附件", "文件"]) and not _has_file_value(steps):
        missing.append("上传文件")
    for step in steps:
        if _is_delete_step(step) and not _has_delete_target(step, dsl):
            missing.append("删除目标记录")
    return missing


def _is_delete_step(step: dict[str, Any]) -> bool:
    action = str(step.get("action") or "")
    target = str(step.get("target") or "")
    intent = str(step.get("intent") or "")
    return action == "delete" or intent == "delete_record" or ("删除" in target and action in {"business_goal", "click"})


def _has_delete_target(step: dict[str, Any], dsl: dict[str, Any]) -> bool:
    for key in ["rowText", "row_text", "recordId", "record_id", "recordCondition", "targetRecord"]:
        if step.get(key):
            return True
    for key in ["queryConditions", "conditions", "criteria"]:
        value = step.get(key)
        if isinstance(value, dict) and any(item not in (None, "") for item in value.values()):
            return True
    target = str(step.get("target") or "")
    if re.search(r"(删除用户|删除记录|删除数据|删除单据)$", target):
        return False
    return bool((dsl.get("testData") or {}).get("用户名") or (dsl.get("testData") or {}).get("编号"))


def _has_any_value(dsl: dict[str, Any], fields: list[str]) -> bool:
    test_data = dsl.get("testData") or {}
    for field in fields:
        if test_data.get(field) not in (None, ""):
            return True
    for step in dsl.get("steps") or []:
        if not isinstance(step, dict):
            continue
        for key in ["formData", "testData", "queryConditions", "criteria"]:
            value = step.get(key)
            if isinstance(value, dict):
                for field in fields:
                    if value.get(field) not in (None, ""):
                        return True
        if str(step.get("target") or "") in fields and step.get("value") not in (None, ""):
            return True
    return False


def _has_file_value(steps: list[dict[str, Any]]) -> bool:
    for step in steps:
        if step.get("file_path") or step.get("filePath"):
            return True
        if step.get("action") == "upload_file" and step.get("value"):
            return True
    return False


def _question_for_missing_field(field: str) -> str:
    mapping = {
        "组织机构": "请补充需要选择的组织机构、部门或单位。",
        "审批人": "请补充审批人或审核人。",
        "上传文件": "请提供需要上传的文件路径或附件引用。",
        "删除目标记录": "请补充删除操作的目标记录条件，例如用户名、编号或唯一标识。",
    }
    return mapping.get(field, f"请补充{field}。")


def _is_approval_pass_target(target: str) -> bool:
    return any(token in target for token in ["审批通过", "审核通过", "同意", "批准"]) and not _is_approval_flow_target(target)


def _is_approval_flow_target(target: str) -> bool:
    return any(token in target for token in ["查看审批流程", "审批流程", "流程图", "审批记录"])


def _mentions_any(text: str, tokens: list[str]) -> bool:
    return any(token in text for token in tokens)


def _flatten(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten(item) for item in value)
    if value is None:
        return ""
    return str(value)
