import json
import re
from typing import Any

from app.llm.json_utils import parse_json_object
from app.llm.provider import LLMRequest


class MockLLMProvider:
    def complete(self, request: LLMRequest) -> str:
        payload = _extract_input_payload(request.user_prompt)
        if "TASK: plan" in request.user_prompt:
            response = _mock_plan(payload)
        else:
            response = _mock_analyze(payload)

        text = json.dumps(response, ensure_ascii=False)
        if request.stream:
            return _as_data_stream(text)
        return text


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

    if any(word in instruction for word in ["我的待办", "待办事项", "工作台/我的待办"]):
        steps.append({"action": "navigate_menu", "target": "我的待办"})
    if any(word in instruction for word in ["审批通过", "审核通过", "同意申请", "批准"]):
        steps.append({"action": "business_goal", "target": "审批通过", "ruleHint": "APPROVAL-PASS-v1"})
        steps.append({"action": "assert_text_exists", "target": "审批成功"})
    elif "审批流程" in instruction or "流程图" in instruction:
        steps.append({"action": "business_goal", "target": "查看审批流程", "ruleHint": "APPROVAL-FLOW-VIEW-v1"})
        steps.append({"action": "assert_text_exists", "target": "审批流程"})
    elif any(word in instruction for word in ["查询", "搜索", "筛选"]):
        steps.append({"action": "query_table", "target": "查询结果表格"})
        steps.append({"action": "assert_text_exists", "target": _expected_text(instruction)})
    else:
        steps.append({"action": "assert_text_exists", "target": _expected_text(instruction)})

    return {
        "caseName": _case_name(instruction),
        "baseUrl": base_url,
        "credentials": credentials,
        "testData": payload.get("testData") or {},
        "settings": {
            "timeoutMs": 30000,
            "stream": bool(payload.get("stream", True)),
            "riskLevel": _risk_level(instruction),
        },
        "steps": steps,
    }


def _as_data_stream(text: str) -> str:
    chunks = [text[index : index + 32] for index in range(0, len(text), 32)]
    return "\n".join([f"data: {chunk}" for chunk in chunks] + ["data: [DONE]"])


def _extract_url(text: str) -> str | None:
    match = re.search(r"https?://[^\s，,。；;]+", text)
    return match.group(0) if match else None


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
