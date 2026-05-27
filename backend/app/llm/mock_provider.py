import json
import re
from collections.abc import Iterator
from typing import Any

from app.llm.json_utils import parse_json_object
from app.llm.provider import LLMRequest


class MockLLMProvider:
    def complete(self, request: LLMRequest) -> str:
        text = json.dumps(_mock_response(request), ensure_ascii=False)
        if request.stream:
            return _as_data_stream(text)
        return text

    def stream_complete(self, request: LLMRequest) -> Iterator[str]:
        text = json.dumps(_mock_response(request), ensure_ascii=False)
        for index in range(0, len(text), 32):
            yield text[index : index + 32]


def _mock_response(request: LLMRequest) -> dict[str, Any]:
    payload = _extract_input_payload(request.user_prompt)
    if "TASK: plan" in request.user_prompt:
        return _mock_plan(payload)
    return _mock_analyze(payload)


def _extract_input_payload(prompt: str) -> dict[str, Any]:
    marker = "INPUT_JSON:"
    if marker not in prompt:
        return {}
    return parse_json_object(prompt.split(marker, 1)[1])


def _mock_analyze(payload: dict[str, Any]) -> dict[str, Any]:
    instruction = str(payload.get("instruction") or "")
    base_url = str(payload.get("base_url") or _extract_url(instruction) or "")
    credentials = payload.get("credentials") or {}

    missing_fields: list[str] = []
    clarifying_questions: list[str] = []
    if not instruction.strip():
        missing_fields.append("instruction")
        clarifying_questions.append("请说明要测试的业务目标和期望结果。")
    if not base_url:
        missing_fields.append("baseUrl")
        clarifying_questions.append("请提供被测 MIS 系统的入口地址。")
    if _mentions_login(instruction) and not _has_credentials(instruction, credentials):
        missing_fields.append("credentials")
        clarifying_questions.append("请提供可用于测试的账号引用，或确认使用项目默认测试账号。")
    if not _has_verifiable_goal(instruction):
        missing_fields.append("expectedResult")
        clarifying_questions.append("请说明需要验证的页面文本、状态变化或业务结果。")

    ready = len(missing_fields) == 0
    return {
        "readyToExecute": ready,
        "confidence": 0.86 if ready else 0.42,
        "understoodGoal": _understood_goal(instruction),
        "missingFields": missing_fields,
        "clarifyingQuestions": clarifying_questions,
        "assumptions": _assumptions(instruction, base_url),
        "riskLevel": _risk_level(instruction),
        "normalizedInstruction": _normalize_instruction(instruction, base_url),
    }


def _mock_plan(payload: dict[str, Any]) -> dict[str, Any]:
    instruction = str(payload.get("instruction") or "")
    base_url = str(payload.get("base_url") or _extract_url(instruction) or "")
    credentials = payload.get("credentials") or {}
    test_data = dict(payload.get("testData") or {})
    test_data.update(_extract_test_data(instruction))
    missing_fields: list[str] = []
    clarifying_questions: list[str] = []
    steps: list[dict[str, Any]] = []

    if base_url:
        steps.append({"action": "open_url", "target": base_url, "description": "打开被测系统入口"})

    if _mentions_login(instruction):
        username = _extract_username(instruction) or credentials.get("username")
        if username:
            credentials = {"username": username, "secret_ref": credentials.get("secret_ref", "provided_or_default")}
        else:
            credentials = {"secret_ref": credentials.get("secret_ref", "project_default_account")}
        steps.extend(
            [
                {"action": "input", "target": "用户名", "value": username or "${TEST_USERNAME}"},
                {"action": "input", "target": "密码", "value": "${TEST_PASSWORD_SECRET}"},
                {"action": "click", "target": "登录"},
            ]
        )
    else:
        credentials = credentials if isinstance(credentials, dict) else {}

    menu_path = _extract_menu_path(instruction)
    if menu_path:
        steps.append(
            {
                "action": "navigate_path",
                "target": "/".join(menu_path),
                "pathSegments": menu_path,
                "navigationType": "menu_path",
                "successCriteria": [
                    f"页面出现{menu_path[-1]}",
                    f"菜单项{menu_path[-1]}高亮",
                    "出现目标列表或目标功能区",
                    f"面包屑包含{'/'.join(menu_path)}",
                ],
                "fallbackStrategies": [
                    "expand_parent_menu",
                    "try_left_menu",
                    "try_top_nav",
                    "try_dashboard_card",
                    "try_menu_search",
                    "try_iframe",
                    "llm_disambiguation",
                    "vision_fallback_optional",
                ],
            }
        )
    elif any(word in instruction for word in ["我的待办", "待办事项"]):
        steps.append({"action": "navigate_menu", "target": "我的待办"})

    if _is_delete_without_target(instruction, test_data):
        missing_fields.append("删除目标记录")
        clarifying_questions.append("请补充删除操作的目标记录条件，例如用户名、编号或唯一标识。")
    elif any(word in instruction for word in ["审批通过", "审核通过", "同意申请", "批准"]):
        steps.append({"action": "business_goal", "intent": "approval_pass", "target": "审批通过", "ruleHint": "APPROVAL-PASS-v1"})
        steps.append({"action": "assert_result", "target": "审批成功"})
    elif "审批流程" in instruction or "流程图" in instruction:
        steps.append({"action": "business_goal", "intent": "approval_flow_view", "target": "查看审批流程", "ruleHint": "APPROVAL-FLOW-VIEW-v1"})
        steps.append({"action": "assert_result", "target": "审批流程"})
    elif _mentions_create(instruction):
        steps.append(
            {
                "action": "business_goal",
                "intent": "create_record",
                "target": _create_target(instruction),
                "formData": test_data,
            }
        )
        if test_data:
            steps.append({"action": "fill_form", "target": "新增表单", "formData": test_data})
        steps.append({"action": "assert_result", "target": "新增成功"})
    elif _mentions_update(instruction):
        steps.append({"action": "query_table", "target": "目标列表", "queryConditions": _query_conditions(test_data)})
        steps.append({"action": "click_table_row_action", "target": "编辑", "button": "编辑", "queryConditions": _query_conditions(test_data)})
        steps.append({"action": "fill_form", "target": "编辑表单", "formData": test_data})
        steps.append({"action": "assert_result", "target": "修改成功"})
    elif _mentions_process_all(instruction):
        steps.append({"action": "query_table_count", "target": "我的待办列表", "emptyStrategy": "pass"})
        steps.append(
            {
                "action": "process_table_rows",
                "target": "我的待办列表",
                "loopPolicy": {
                    "maxRows": 200,
                    "emptyStrategy": "pass",
                    "rowAction": "open_link_or_detail",
                    "closeStrategy": "common_dialog_controls",
                },
            }
        )
        steps.append({"action": "summary_assert", "target": "所有可见待办行均已尝试处理。"})
    elif _mentions_open_one_todo(instruction):
        steps.append({"action": "query_table", "target": "我的待办列表"})
        steps.append({"action": "open_table_row", "target": "我的待办列表", "rowAction": "open_link_or_detail"})
    elif any(word in instruction for word in ["查询", "搜索", "筛选"]):
        steps.append({"action": "query_table", "target": "查询结果表格", "queryConditions": _query_conditions(test_data)})
        steps.append({"action": "assert_result", "target": _expected_text(instruction)})
    else:
        steps.append({"action": "assert_text_exists", "target": _expected_text(instruction)})

    for field in _critical_missing_fields(instruction, test_data, steps):
        if field not in missing_fields:
            missing_fields.append(field)
            clarifying_questions.append(_question_for_missing_field(field))

    return {
        "caseName": _case_name(instruction),
        "baseUrl": base_url,
        "credentials": credentials,
        "testData": test_data,
        "settings": {
            "timeoutMs": 30000,
            "stream": bool(payload.get("stream", True)),
            "riskLevel": _risk_level(instruction),
        },
        "steps": steps,
        "missingFields": missing_fields,
        "clarifyingQuestions": clarifying_questions,
    }


def _as_data_stream(text: str) -> str:
    chunks = [text[index : index + 32] for index in range(0, len(text), 32)]
    return "\n".join([f"data: {chunk}" for chunk in chunks] + ["data: [DONE]"])


def _extract_url(text: str) -> str | None:
    match = re.search(r"https?://[^\s，,。；;]+", text)
    return match.group(0) if match else None


def _extract_menu_path(text: str) -> list[str]:
    match = re.search(r"[\u4e00-\u9fffA-Za-z0-9_]+(?:\s*(?:/|>|-|→|\\)\s*[\u4e00-\u9fffA-Za-z0-9_]+)+", text)
    if not match:
        return []
    candidate = match.group(0)
    if "://" in candidate:
        return []
    return [segment.strip() for segment in re.split(r"\s*(?:/|>|-|→|\\)\s*", candidate) if segment.strip()]


def _mentions_login(text: str) -> bool:
    return any(word in text for word in ["登录", "账号", "密码"])


def _has_credentials(text: str, credentials: dict[str, Any]) -> bool:
    if credentials.get("secret_ref") or credentials.get("password_provided"):
        return True
    return bool(_extract_username(text) and re.search(r"(密码|口令)\s*[:：]?\s*\S+", text))


def _extract_username(text: str) -> str | None:
    match = re.search(r"(账号|用户名|用户)\s*[:：]?\s*([A-Za-z0-9_.@-]+)", text)
    return match.group(2) if match else None


def _has_verifiable_goal(text: str) -> bool:
    return any(
        word in text
        for word in [
            "确认",
            "验证",
            "断言",
            "看到",
            "存在",
            "出现",
            "成功",
            "状态",
            "待办",
            "审批通过",
            "审批流程",
        ]
    )


def _understood_goal(instruction: str) -> str:
    if "审批通过" in instruction or "审核通过" in instruction:
        return "完成审批通过并验证结果"
    if "审批流程" in instruction or "流程图" in instruction:
        return "查看审批流程并验证流程信息"
    if "我的待办" in instruction or "待办事项" in instruction:
        return "进入我的待办并验证页面内容"
    return instruction.strip()


def _assumptions(instruction: str, base_url: str) -> list[str]:
    assumptions = []
    if base_url:
        assumptions.append("使用提供的入口地址作为测试 baseUrl。")
    if _mentions_login(instruction):
        assumptions.append("登录凭据通过 secret_ref 或运行时安全输入提供。")
    return assumptions


def _risk_level(instruction: str) -> str:
    if any(word in instruction for word in ["删除", "作废", "审批通过", "批准", "付款", "金额"]):
        return "high"
    if any(word in instruction for word in ["新增", "修改", "编辑", "提交"]):
        return "medium"
    return "low"


def _normalize_instruction(instruction: str, base_url: str) -> str:
    normalized = " ".join(instruction.split())
    if base_url and base_url not in normalized:
        normalized = f"{normalized} baseUrl={base_url}".strip()
    return normalized


def _case_name(instruction: str) -> str:
    goal = _understood_goal(instruction)
    return goal[:60] or "自然语言测试用例"


def _expected_text(instruction: str) -> str:
    quoted = re.findall(r"[“\"]([^”\"]+)[”\"]", instruction)
    if quoted:
        return quoted[-1]
    if "我的待办" in instruction:
        return "我的待办"
    if "成功" in instruction:
        return "成功"
    return "目标内容"


def _mentions_open_one_todo(text: str) -> bool:
    compact = text.replace(" ", "")
    return "待办" in compact and any(token in compact for token in ["打开一条", "处理一条", "找一条", "一条待办"])


def _mentions_process_all(text: str) -> bool:
    compact = text.replace(" ", "")
    return "待办" in compact and any(token in compact for token in ["处理所有", "遍历所有", "每一条", "所有行", "逐行", "循环"])


def _mentions_create(text: str) -> bool:
    return any(token in text for token in ["新增", "添加", "创建"])


def _mentions_update(text: str) -> bool:
    return any(token in text for token in ["修改", "编辑", "变更"])


def _is_delete_without_target(text: str, test_data: dict[str, Any]) -> bool:
    if not any(token in text for token in ["删除", "移除"]):
        return False
    if any(test_data.get(key) for key in ["用户名", "姓名", "编号", "申请编号", "手机号"]):
        return False
    return not re.search(r"(用户名|用户|姓名|编号|申请编号|手机号|账号)\s*(?:为|是|=|:|：)\s*[\u4e00-\u9fffA-Za-z0-9_.@-]+", text)


def _extract_test_data(text: str) -> dict[str, Any]:
    fields = [
        "组织机构",
        "所属机构",
        "部门",
        "负责人",
        "审批人",
        "用户名",
        "姓名",
        "手机号",
        "邮箱",
        "开始日期",
        "结束日期",
        "标题",
        "编号",
    ]
    data: dict[str, Any] = {}
    for field in fields:
        match = re.search(rf"{field}\s*(?:选择|为|是|=|:|：)?\s*([\u4e00-\u9fffA-Za-z0-9_.@/-]+)", text)
        if match:
            value = match.group(1).strip("，,。；; ")
            if value and value not in {"选择", "为", "是"}:
                data[field] = value
    return data


def _critical_missing_fields(instruction: str, test_data: dict[str, Any], steps: list[dict[str, Any]]) -> list[str]:
    missing: list[str] = []
    if any(token in instruction for token in ["组织机构", "所属机构", "部门"]) and not any(test_data.get(key) for key in ["组织机构", "所属机构", "部门"]):
        missing.append("组织机构")
    if "审批人" in instruction and not test_data.get("审批人"):
        missing.append("审批人")
    if any(token in instruction for token in ["上传", "附件", "文件"]) and not any(step.get("file_path") or step.get("filePath") for step in steps):
        missing.append("上传文件")
    return missing


def _question_for_missing_field(field: str) -> str:
    return {
        "组织机构": "请补充需要选择的组织机构、部门或单位。",
        "审批人": "请补充审批人。",
        "上传文件": "请提供需要上传的文件路径或附件引用。",
        "删除目标记录": "请补充删除操作的目标记录条件，例如用户名、编号或唯一标识。",
    }.get(field, f"请补充{field}。")


def _create_target(text: str) -> str:
    if "用户" in text:
        return "新增用户"
    return "新增记录"


def _query_conditions(test_data: dict[str, Any]) -> dict[str, Any]:
    preferred = ["用户名", "姓名", "编号", "申请编号", "手机号"]
    return {key: test_data[key] for key in preferred if test_data.get(key)}
