from typing import Any
import re
import time

from app.core.config import settings
from app.llm.json_utils import parse_json_model, parse_json_object, to_compact_json
from app.llm.provider import LLMProvider, LLMRequest, get_llm_provider
from app.schemas.test_runs import ALLOWED_DSL_ACTIONS, AnalyzeResult, NaturalLanguageTestRequest, TestCaseDSL
from app.services.dsl_post_processor import normalize_dsl
from app.services.llm_call_logs import log_llm_call
from app.services.operation_intent_classifier import annotate_steps_with_operation_intents
from app.services.prompt_manager import get_prompt_manager


class NaturalLanguageParser:
    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider or get_llm_provider()

    def analyze(self, payload: NaturalLanguageTestRequest) -> AnalyzeResult:
        request = self.build_analyze_request(payload)
        started = time.monotonic()
        try:
            raw = self.provider.complete(request)
            log_llm_call(
                prompt_key=request.prompt_key,
                prompt_version=request.prompt_version,
                success=True,
                elapsed_ms=_elapsed_ms(started),
            )
            return self.parse_analysis(raw, payload)
        except Exception as exc:
            log_llm_call(
                prompt_key=request.prompt_key,
                prompt_version=request.prompt_version,
                success=False,
                elapsed_ms=_elapsed_ms(started),
                error_summary=str(exc),
            )
            raise

    def plan(self, payload: NaturalLanguageTestRequest) -> TestCaseDSL:
        request = self.build_plan_request(payload)
        started = time.monotonic()
        try:
            raw = self.provider.complete(request)
            log_llm_call(
                prompt_key=request.prompt_key,
                prompt_version=request.prompt_version,
                success=True,
                elapsed_ms=_elapsed_ms(started),
            )
            return self.parse_plan(raw, payload)
        except Exception as exc:
            log_llm_call(
                prompt_key=request.prompt_key,
                prompt_version=request.prompt_version,
                success=False,
                elapsed_ms=_elapsed_ms(started),
                error_summary=str(exc),
            )
            raise

    def build_analyze_request(self, payload: NaturalLanguageTestRequest) -> LLMRequest:
        rendered = get_prompt_manager().render_prompt(
            "test_instruction_analysis",
            {
                "instruction": self._redact_sensitive_text(payload.instruction),
                "context": {},
                "known_systems": [],
                "test_data": self._sanitize_mapping(payload.testData or {}),
                "input_json": to_compact_json(self._input_payload(payload)),
            },
        )
        return LLMRequest(
            system_prompt=rendered.system,
            user_prompt=rendered.user,
            stream=self._stream_enabled(payload),
            temperature=rendered.metadata.get("temperature"),
            max_tokens=rendered.metadata.get("max_tokens"),
            prompt_key=rendered.prompt_key,
            prompt_version=rendered.prompt_version,
        )

    def build_plan_request(self, payload: NaturalLanguageTestRequest) -> LLMRequest:
        rendered = get_prompt_manager().render_prompt(
            "test_dsl_generation",
            {
                "instruction": self._redact_sensitive_text(payload.instruction),
                "allowed_actions": ", ".join(sorted(ALLOWED_DSL_ACTIONS)),
                "input_json": to_compact_json(self._input_payload(payload)),
            },
        )
        return LLMRequest(
            system_prompt=rendered.system,
            user_prompt=rendered.user,
            stream=self._stream_enabled(payload),
            temperature=rendered.metadata.get("temperature"),
            max_tokens=rendered.metadata.get("max_tokens"),
            prompt_key=rendered.prompt_key,
            prompt_version=rendered.prompt_version,
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
        normalized = normalize_dsl(self._repair_dsl(dsl_data, payload))
        return TestCaseDSL.model_validate(annotate_steps_with_operation_intents(normalized, instruction=payload.instruction))

    def sanitized_input_payload(self, payload: NaturalLanguageTestRequest) -> dict[str, Any]:
        return self._input_payload(payload)

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
        if payload is not None and (
            NaturalLanguageParser._is_connectivity_goal(payload)
            or NaturalLanguageParser._looks_like_low_risk_connectivity_check(result, payload)
        ):
            result = NaturalLanguageParser._accept_connectivity_goal(result, payload)
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
        return normalize_dsl(repaired)

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

    @staticmethod
    def _is_connectivity_goal(payload: NaturalLanguageTestRequest) -> bool:
        text = str(payload.instruction or "")
        if not NaturalLanguageParser._has_base_url(payload) or any(token in text for token in ["登录", "账号", "密码"]):
            return False
        return any(token in text for token in ["可访问", "连通", "打开", "入口"]) and any(
            token in text for token in ["确认", "验证", "检查"]
        )

    @staticmethod
    def _looks_like_low_risk_connectivity_check(result: AnalyzeResult, payload: NaturalLanguageTestRequest) -> bool:
        if not NaturalLanguageParser._has_base_url(payload):
            return False
        text = str(payload.instruction or "")
        if any(token in text for token in ["登录", "账号", "密码", "查询", "搜索", "新增", "修改", "删除", "审批", "上传", "填写", "选择"]):
            return False
        return result.riskLevel == "low" and set(result.missingFields).issubset({"expectedResult"})

    @staticmethod
    def _accept_connectivity_goal(result: AnalyzeResult, payload: NaturalLanguageTestRequest) -> AnalyzeResult:
        non_blocking_fields = {"expectedResult", "credentials"}
        result.missingFields = [item for item in result.missingFields if item not in non_blocking_fields]
        result.clarifyingQuestions = [
            item
            for item in result.clarifyingQuestions
            if not any(token in str(item) for token in ["账号", "验证的页面文本", "业务结果"])
        ]
        result.assumptions = list(
            dict.fromkeys([*result.assumptions, "该任务只验证入口地址可访问，不执行登录或写操作。"])
        )
        result.understoodGoal = result.understoodGoal or "验证被测系统入口可访问"
        result.normalizedInstruction = result.normalizedInstruction or NaturalLanguageParser._normalize_instruction(
            payload.instruction,
            str(payload.base_url or NaturalLanguageParser._extract_url(payload.instruction) or ""),
        )
        if not result.missingFields:
            result.readyToExecute = True
            result.confidence = max(result.confidence, 0.82)
        return result

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
                {
                    "action": "navigate_path",
                    "target": "工作台/我的待办",
                    "pathSegments": ["工作台", "我的待办"],
                    "navigationType": "menu_path",
                    "description": "进入工作台下的我的待办列表。",
                },
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


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
