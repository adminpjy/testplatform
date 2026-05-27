import re
from typing import Any


PATH_SEPARATORS_PATTERN = r"\s*(?:/|>|-|→|\\)\s*"


class DslPostProcessor:
    def normalize_dsl(self, dsl: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(dsl)
        normalized["testData"] = dict(normalized.get("testData") or {})
        normalized["steps"] = [self.normalize_step(step) for step in normalized.get("steps") or [] if isinstance(step, dict)]
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

        if action == "for_each_table_row":
            _remember_original(current, action, target, "for_each_table_row is normalized to process_table_rows")
            current["action"] = "process_table_rows"
            current.setdefault("loopPolicy", _loop_policy_from_step(current))
            current.setdefault("readableDescription", "处理表格中的所有数据行")
            action = "process_table_rows"

        if action in {"click", "confirm_dialog", "click_table_row_action"} and _is_approval_pass_target(target):
            _remember_original(current, action, target, "approval pass click is normalized to business goal")
            current["action"] = "business_goal"
            current["intent"] = "approval_pass"
            current["target"] = "审批通过"
            current.setdefault("readableDescription", "审批通过")
            return current

        if _is_approval_flow_target(target):
            if action != "business_goal" or current.get("intent") != "approval_flow_view":
                _remember_original(current, action, target, "approval flow view is normalized to business goal")
            current["action"] = "business_goal"
            current["intent"] = "approval_flow_view"
            current["target"] = "查看审批流程"
            current.setdefault("readableDescription", "查看审批流程")
            return current

        if action == "navigate_path":
            segments = _path_segments(current.get("pathSegments") or current.get("path_segments") or target)
            if len(segments) >= 2:
                current["pathSegments"] = segments
                current["navigationType"] = current.get("navigationType") or "menu_path"
                _ensure_navigation_defaults(current, segments)
            return current

        if action in {"business_goal", "navigate_menu", "click"}:
            segments = _path_segments(target)
            if len(segments) >= 2:
                _remember_original(current, action, target, "target contains menu path separator")
                current["action"] = "navigate_path"
                current["pathSegments"] = segments
                current["navigationType"] = "menu_path"
                current["readableDescription"] = f"菜单路径导航：{' → '.join(segments)}"
                _ensure_navigation_defaults(current, segments)
        return current


def normalize_dsl(dsl: dict[str, Any]) -> dict[str, Any]:
    return DslPostProcessor().normalize_dsl(dsl)


def parse_menu_path(target: str) -> list[str]:
    return _path_segments(target)


def _path_segments(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_clean_segment(str(item), index) for index, item in enumerate(value) if _clean_segment(str(item), index)]
    text = str(value or "").strip()
    if not text or "://" in text:
        return []
    if not re.search(r"[/>\-→\\]", text):
        return []
    return [
        cleaned
        for index, segment in enumerate(re.split(PATH_SEPARATORS_PATTERN, text))
        if (cleaned := _clean_segment(segment, index))
    ]


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


def _remember_original(step: dict[str, Any], action: str, target: str, reason: str) -> None:
    step.setdefault("originalAction", action)
    step.setdefault("originalTarget", target)
    step["normalizedBy"] = "DslPostProcessor"
    step["normalizationReason"] = reason


def _loop_policy_from_step(step: dict[str, Any]) -> dict[str, Any]:
    return {
        "maxRows": int(step.get("maxRows") or step.get("max_rows") or 200),
        "emptyStrategy": step.get("emptyStrategy") or step.get("empty_strategy") or "pass",
        "rowAction": step.get("rowAction") or step.get("row_action") or "open_link_or_detail",
        "closeStrategy": step.get("closeStrategy") or step.get("close_strategy") or "common_dialog_controls",
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
