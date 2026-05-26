from typing import Any
import re

from app.core.config import settings
from app.llm.json_utils import parse_json_model, parse_json_object, to_compact_json
from app.llm.provider import LLMProvider, LLMRequest, get_llm_provider
from app.schemas.test_runs import ALLOWED_DSL_ACTIONS, AnalyzeResult, NaturalLanguageTestRequest, TestCaseDSL


SYSTEM_PROMPT = (
    "You analyze natural-language functional testing goals for existing enterprise MIS systems. "
    "Return strict JSON only. Do not reveal, transform, or invent API keys or tokens. "
    "Do not include plaintext passwords in the output; use a secret_ref instead. "
    "Do not ask clarifying questions for non-blocking exploratory test behavior. "
    "If a list may be empty, assume the run records count=0 and ends the loop. "
    "If dialog close controls are not specified, assume common controls such as return, cancel, close, X, and Escape. "
    "If dialog content checks are not specified, assume only open/close behavior is verified."
)


class NaturalLanguageParser:
    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider or get_llm_provider()

    def analyze(self, payload: NaturalLanguageTestRequest) -> AnalyzeResult:
        raw = self.provider.complete(self.build_analyze_request(payload))
        return self.parse_analysis(raw, payload)

    def plan(self, payload: NaturalLanguageTestRequest) -> TestCaseDSL:
        raw = self.provider.complete(self.build_plan_request(payload))
        return self.parse_plan(raw, payload)

    def build_analyze_request(self, payload: NaturalLanguageTestRequest) -> LLMRequest:
        return LLMRequest(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=self._build_analyze_prompt(payload),
            stream=self._stream_enabled(payload),
        )

    def build_plan_request(self, payload: NaturalLanguageTestRequest) -> LLMRequest:
        return LLMRequest(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=self._build_plan_prompt(payload),
            stream=self._stream_enabled(payload),
        )

    def parse_analysis(self, raw: str, payload: NaturalLanguageTestRequest | None = None) -> AnalyzeResult:
        return self._normalize_analysis(parse_json_model(raw, AnalyzeResult), payload)

    def parse_plan(self, raw: str, payload: NaturalLanguageTestRequest) -> TestCaseDSL:
        try:
            dsl_data = parse_json_object(raw)
        except Exception:
            if self._is_todo_dialog_exploration(payload):
                dsl_data = self._default_todo_dialog_dsl(payload)
            else:
                raise
        return TestCaseDSL.model_validate(self._repair_dsl(dsl_data, payload))

    def sanitized_input_payload(self, payload: NaturalLanguageTestRequest) -> dict[str, Any]:
        return self._input_payload(payload)

    def _build_analyze_prompt(self, payload: NaturalLanguageTestRequest) -> str:
        return (
            "TASK: analyze\n"
            "Decision rules:\n"
            "- Only block execution for missing base URL, missing usable credentials when login is required, unsafe write/approval/delete confirmation, or absent business goal.\n"
            "- Do not block for empty table handling; default to count=0 and finish the loop.\n"
            "- Do not block for unspecified dialog close button; default to common close controls.\n"
            "- Do not block for unspecified dialog content assertion; default to verifying the dialog opens and closes.\n"
            "- Put these defaults in assumptions, not missingFields.\n"
            "Return JSON matching this schema exactly:\n"
            "{"
            '"readyToExecute":false,'
            '"confidence":0.0,'
            '"understoodGoal":"",'
            '"missingFields":[],'
            '"clarifyingQuestions":[],'
            '"assumptions":[],'
            '"riskLevel":"low",'
            '"normalizedInstruction":""'
            "}\n"
            "INPUT_JSON:\n"
            f"{to_compact_json(self._input_payload(payload))}"
        )

    def _build_plan_prompt(self, payload: NaturalLanguageTestRequest) -> str:
        return (
            "TASK: plan\n"
            "Create a TestCaseDSL for the natural-language testing goal. "
            "For exploratory todo-list and dialog-loop goals, generate executable high-level DSL steps instead of asking for selectors. "
            "Use query_table_count and for_each_table_row when the goal asks to count rows and iterate table links. "
            "Use close_dialog_by_common_controls when the user says return/cancel/close or does not provide a precise dialog close selector. "
            "Use only these actions: "
            f"{', '.join(sorted(ALLOWED_DSL_ACTIONS))}. "
            "Return JSON matching this schema exactly: "
            "{"
            '"caseName":"",'
            '"baseUrl":"",'
            '"credentials":{},'
            '"testData":{},'
            '"settings":{},'
            '"steps":[]'
            "}\n"
            "INPUT_JSON:\n"
            f"{to_compact_json(self._input_payload(payload))}"
        )

    def _input_payload(self, payload: NaturalLanguageTestRequest) -> dict[str, Any]:
        data = payload.model_dump()
        data["stream"] = self._stream_enabled(payload)
        data["instruction"] = self._redact_sensitive_text(str(data.get("instruction") or ""))
        data["credentials"] = self._sanitize_credentials(data.get("credentials") or {})
        data["testData"] = self._sanitize_mapping(data.get("testData") or {})
        return data

    def _stream_enabled(self, payload: NaturalLanguageTestRequest) -> bool:
        if payload.stream is not None:
            return payload.stream
        return settings.test_llm_stream

    @staticmethod
    def _sanitize_credentials(credentials: dict[str, Any]) -> dict[str, Any]:
        sanitized = dict(credentials)
        if "password" in sanitized:
            sanitized.pop("password")
            sanitized["secret_ref"] = sanitized.get("secret_ref", "provided_password_redacted")
            sanitized["password_provided"] = True
        return sanitized

    @classmethod
    def _sanitize_mapping(cls, value: Any) -> Any:
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            for key, item in value.items():
                key_text = str(key)
                if cls._is_sensitive_key(key_text):
                    result[key_text] = "***REDACTED***"
                else:
                    result[key_text] = cls._sanitize_mapping(item)
            return result
        if isinstance(value, list):
            return [cls._sanitize_mapping(item) for item in value]
        if isinstance(value, str):
            return cls._redact_sensitive_text(value)
        return value

    @staticmethod
    def _is_sensitive_key(key: str) -> bool:
        return any(token in key.lower() for token in ["password", "secret", "token", "api_key", "apikey", "key", "密码", "口令", "密钥"])

    @staticmethod
    def _redact_sensitive_text(value: str) -> str:
        patterns = [
            r"((?:密码|口令)\s*[:：=]?\s*)([^\s,，;；。]+)",
            r"((?:password|secret|token|api[_-]?key)\s*[:：=]\s*)([^\s,，;；。]+)",
        ]
        redacted = value
        for pattern in patterns:
            redacted = re.sub(pattern, r"\1***REDACTED***", redacted, flags=re.IGNORECASE)
        return redacted

    @staticmethod
    def _normalize_analysis(result: AnalyzeResult, payload: NaturalLanguageTestRequest | None = None) -> AnalyzeResult:
        result.missingFields = list(dict.fromkeys(result.missingFields))
        result.clarifyingQuestions = list(dict.fromkeys(result.clarifyingQuestions))
        result.assumptions = list(dict.fromkeys(result.assumptions))
        if payload is not None and NaturalLanguageParser._is_todo_dialog_exploration(payload):
            result = NaturalLanguageParser._downgrade_exploratory_questions(result, payload)
        if result.readyToExecute and result.missingFields:
            result.readyToExecute = False
        if not result.readyToExecute and not result.clarifyingQuestions:
            result.clarifyingQuestions = ["请补充被测地址、业务目标和期望结果。"]
        return result

    def _repair_dsl(self, dsl_data: dict[str, Any], payload: NaturalLanguageTestRequest) -> dict[str, Any]:
        repaired = {
            "caseName": dsl_data.get("caseName") or "自然语言测试用例",
            "baseUrl": dsl_data.get("baseUrl") or payload.base_url or "",
            "credentials": self._sanitize_credentials(dsl_data.get("credentials") or payload.credentials or {}),
            "testData": dsl_data.get("testData") or payload.testData or {},
            "settings": dsl_data.get("settings") or payload.settings or {},
            "steps": dsl_data.get("steps") or [],
        }
        if self._is_todo_dialog_exploration(payload):
            repaired.update(self._default_todo_dialog_dsl(payload, base=repaired))
        repaired_steps = []
        for step in repaired["steps"]:
            if not isinstance(step, dict):
                continue
            action = step.get("action")
            if action not in ALLOWED_DSL_ACTIONS:
                step = dict(step)
                step["original_action"] = action
                step["action"] = "business_goal"
            repaired_steps.append(step)
        repaired["steps"] = repaired_steps
        return repaired

    @staticmethod
    def _is_todo_dialog_exploration(payload: NaturalLanguageTestRequest) -> bool:
        text = str(payload.instruction or "")
        compact = text.replace(" ", "")
        return all(token in compact for token in ["我的待办", "列表"]) and any(
            token in compact for token in ["循环", "反复", "所有行", "逐行"]
        ) and any(token in compact for token in ["对话框", "弹窗", "关闭", "返回", "取消"])

    @staticmethod
    def _downgrade_exploratory_questions(result: AnalyzeResult, payload: NaturalLanguageTestRequest) -> AnalyzeResult:
        non_blocking_patterns = [
            "待办列表.*无数据",
            "待办列表.*为空",
            "列表为空",
            "数量为0",
            "对话框.*关闭",
            "弹窗.*关闭",
            "关闭按钮",
            "选择器",
            "具体文本",
            "对话框内容",
            "弹窗内容",
            "是否需要验证",
            "仅执行打开",
            "循环中是否",
        ]

        def is_non_blocking(value: str) -> bool:
            return any(re.search(pattern, value) for pattern in non_blocking_patterns)

        result.missingFields = [item for item in result.missingFields if not is_non_blocking(str(item))]
        result.clarifyingQuestions = [item for item in result.clarifyingQuestions if not is_non_blocking(str(item))]
        defaults = [
            "待办列表为空时记录数量为0，并正常结束循环。",
            "弹窗关闭使用通用返回、取消、关闭、X、Esc 策略。",
            "未指定弹窗内容校验时，仅验证弹窗可打开并可关闭。",
        ]
        result.assumptions = list(dict.fromkeys([*result.assumptions, *defaults]))
        if not result.normalizedInstruction:
            result.normalizedInstruction = NaturalLanguageParser._normalize_instruction(
                payload.instruction,
                str(payload.base_url or ""),
            )
        if not result.understoodGoal:
            result.understoodGoal = "登录系统，进入我的待办并逐行打开、关闭待办对话框"
        if not result.missingFields and NaturalLanguageParser._has_base_url(payload):
            result.readyToExecute = True
            result.confidence = max(result.confidence, 0.82)
        return result

    @staticmethod
    def _has_base_url(payload: NaturalLanguageTestRequest) -> bool:
        return bool(payload.base_url or re.search(r"https?://[^\s，,。；;]+", payload.instruction or ""))

    def _default_todo_dialog_dsl(
        self,
        payload: NaturalLanguageTestRequest,
        *,
        base: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        base = base or {}
        base_url = str(base.get("baseUrl") or payload.base_url or self._extract_url(payload.instruction) or "")
        credentials = self._sanitize_credentials(base.get("credentials") or payload.credentials or {})
        username = credentials.get("username") or (payload.credentials or {}).get("username")
        login_step: dict[str, Any] = {
            "action": "business_goal",
            "target": "登录系统",
            "description": "使用配置的测试账号登录系统。",
            "credentials": credentials,
        }
        if username:
            login_step["username"] = username
        steps: list[dict[str, Any]] = []
        if base_url:
            steps.append({"action": "open_url", "target": base_url, "description": "打开被测系统入口。"})
        steps.extend(
            [
                login_step,
                {"action": "business_goal", "target": "工作台/我的待办", "description": "进入工作台下的我的待办列表。"},
                {
                    "action": "query_table_count",
                    "target": "我的待办列表",
                    "emptyStrategy": "pass",
                    "description": "获取待办列表数量；如果数量为0，记录并结束循环。",
                },
                {
                    "action": "for_each_table_row",
                    "target": "我的待办列表",
                    "rowAction": "open_link_or_detail",
                    "closeStrategy": "common_dialog_controls",
                    "emptyStrategy": "pass",
                    "description": "逐行点击待办链接，验证弹窗可打开，并用返回/取消/关闭/X/Esc 关闭。",
                },
                {
                    "action": "summary_assert",
                    "target": "所有可见待办行均已尝试打开并关闭。",
                    "description": "汇总执行结果；空列表视为正常结束。",
                },
            ]
        )
        return {
            "caseName": base.get("caseName") or "我的待办列表逐行打开关闭验证",
            "baseUrl": base_url,
            "credentials": credentials,
            "testData": base.get("testData") or payload.testData or {},
            "settings": {
                **dict(base.get("settings") or payload.settings or {}),
                "exploratoryDefaults": {
                    "emptyTable": "pass",
                    "dialogClose": ["返回", "取消", "关闭", "X", "Esc"],
                    "dialogContentAssertion": "open_close_only",
                },
            },
            "steps": steps,
        }

    @staticmethod
    def _extract_url(text: str) -> str | None:
        match = re.search(r"https?://[^\s，,。；;]+", text)
        return match.group(0) if match else None
