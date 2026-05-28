import re
from dataclasses import asdict, dataclass, field
from typing import Any

from app.services.dsl_post_processor import parse_menu_path


@dataclass
class OperationIntentResult:
    intent: str
    intentType: str
    confidence: float
    reason: str
    matchedExpressions: list[str] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


class OperationIntentClassifier:
    def classify(
        self,
        *,
        action: str | None = None,
        target: str | None = None,
        stepName: str | None = None,
        instruction: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> OperationIntentResult:
        action_text = str(action or "")
        target_text = str(target or "")
        context_text = _flatten(context or {})
        text = " ".join(part for part in [action_text, target_text, str(stepName or ""), str(instruction or ""), context_text] if part)

        if action_text == "navigate_path" or parse_menu_path(target_text):
            return _result("navigate_path", "navigation", 0.96, "目标包含菜单路径或 action=navigate_path。", [target_text])

        action_intent = _intent_from_action(action_text, target_text)
        if action_intent is not None:
            return action_intent

        expression_rules = [
            ("view_flow", "approval", 0.9, ["查看审批流程", "审批流程", "流程图", "审批记录"]),
            ("approval_pass", "approval", 0.9, ["审批通过", "审核通过", "同意", "批准"]),
            ("approval_reject", "approval", 0.88, ["驳回", "退回", "拒绝", "不通过"]),
            ("select_person", "form", 0.84, ["人员", "负责人", "经办人", "审批人", "申请人"]),
            ("select_org", "form", 0.84, ["组织", "机构", "部门", "单位"]),
            ("select_date_range", "form", 0.82, ["开始", "结束", "有效期", "日期范围", "时间范围"]),
            ("select_date", "form", 0.8, ["日期", "时间"]),
            ("select_dropdown", "form", 0.8, ["下拉", "选择状态", "选择类型"]),
            ("fill_form", "form", 0.78, ["填写", "录入", "输入"]),
            ("view_detail", "table", 0.82, ["查看详情", "打开单据", "详情"]),
            ("delete_record", "table", 0.86, ["删除", "移除"]),
            ("update_record", "form", 0.84, ["修改", "编辑", "变更"]),
            ("create_record", "form", 0.84, ["新增", "添加", "创建"]),
            ("query_list", "query", 0.82, ["查询", "搜索", "筛选"]),
            ("enter_page", "navigation", 0.78, ["进入", "打开", "跳转到", "导航到"]),
            ("assert_result", "assertion", 0.76, ["验证", "确认", "断言", "检查"]),
        ]
        for intent, intent_type, confidence, expressions in expression_rules:
            hits = [expr for expr in expressions if expr in text]
            if hits:
                return _result(intent, intent_type, confidence, "命中自然语言表达。", hits)

        return _result("unknown", "unknown", 0.2, "未识别到明确操作意图。", [])


def classify_operation_intent(payload: dict[str, Any]) -> dict[str, Any]:
    return OperationIntentClassifier().classify(
        action=payload.get("action"),
        target=payload.get("target"),
        stepName=payload.get("stepName") or payload.get("step_name") or payload.get("name"),
        instruction=payload.get("instruction"),
        context=payload.get("context"),
    ).model_dump()


def annotate_steps_with_operation_intents(dsl: dict[str, Any], *, instruction: str | None = None) -> dict[str, Any]:
    classifier = OperationIntentClassifier()
    annotated = dict(dsl)
    steps = []
    for step in annotated.get("steps") or []:
        if not isinstance(step, dict):
            continue
        current = dict(step)
        classification = classifier.classify(
            action=current.get("action"),
            target=current.get("target"),
            stepName=current.get("name") or current.get("step_name"),
            instruction=instruction,
            context=current,
        )
        current["operationIntent"] = classification.model_dump()
        steps.append(current)
    annotated["steps"] = steps
    return annotated


def _intent_from_action(action: str, target: str) -> OperationIntentResult | None:
    if action == "open_url":
        return _result("enter_page", "navigation", 0.9, "action 指向打开系统入口或页面。", [action])
    if action in {"query_table", "query_table_count"}:
        return _result("query_list", "query", 0.9, "action 指向列表查询或表格计数。", [action])
    if action in {"for_each_table_row", "process_table_rows"}:
        return _result("process_table_rows", "table", 0.92, "action 指向表格行循环处理。", [action])
    if action == "open_table_row":
        return _result("open_table_row", "table", 0.9, "action 指向打开一条表格记录。", [action])
    if action in {"click_table_row_action", "open_row_link_or_detail"}:
        return _result("click_table_row_action", "table", 0.9, "action 指向表格行操作。", [action])
    if action in {"auto_fill_form", "fill_form"}:
        return _result("fill_form", "form", 0.9, "action 指向自动填写表单。", [action])
    if action == "select":
        return _result("select_dropdown", "form", 0.82, "action 指向选择控件。", [action])
    if action == "upload_file":
        return _result("upload_file", "form", 0.9, "action 指向文件上传。", [action])
    if action in {"assert_text_exists", "assert_text_not_exists", "assert_url_contains", "summary_assert", "assert_result"}:
        return _result("assert_result", "assertion", 0.86, "action 指向结果断言。", [action])
    if action == "navigate_menu":
        return _result("enter_page", "navigation", 0.82, "action 指向菜单导航。", [action])
    if action == "input":
        if any(token in target for token in ["日期", "时间", "开始", "结束", "有效期"]):
            return _result("select_date", "form", 0.78, "输入目标是日期或时间字段。", [target])
        return _result("fill_field", "form", 0.78, "action 指向字段输入。", [action])
    return None


def _result(intent: str, intent_type: str, confidence: float, reason: str, expressions: list[str]) -> OperationIntentResult:
    return OperationIntentResult(
        intent=intent,
        intentType=intent_type,
        confidence=confidence,
        reason=reason,
        matchedExpressions=[item for item in expressions if item],
    )


def _flatten(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten(item) for item in value)
    if value is None:
        return ""
    text = str(value)
    return "" if re.search(r"(password|secret|token|密码|口令)", text, re.IGNORECASE) else text
