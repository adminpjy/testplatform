from typing import Any
import re

from app.core.config import settings
from app.llm.json_utils import parse_json_model, parse_json_object, to_compact_json
from app.llm.provider import LLMProvider, LLMRequest, get_llm_provider
from app.schemas.test_runs import ALLOWED_DSL_ACTIONS, AnalyzeResult, NaturalLanguageTestRequest, TestCaseDSL


SYSTEM_PROMPT = (
    "You analyze natural-language functional testing goals for existing enterprise MIS systems. "
    "Return strict JSON only. Do not reveal, transform, or invent API keys or tokens. "
    "Do not include plaintext passwords in the output; use a secret_ref instead."
)


class NaturalLanguageParser:
    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider or get_llm_provider()

    def analyze(self, payload: NaturalLanguageTestRequest) -> AnalyzeResult:
        raw = self.provider.complete(self.build_analyze_request(payload))
        return self.parse_analysis(raw)

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

    def parse_analysis(self, raw: str) -> AnalyzeResult:
        return self._normalize_analysis(parse_json_model(raw, AnalyzeResult))

    def parse_plan(self, raw: str, payload: NaturalLanguageTestRequest) -> TestCaseDSL:
        dsl_data = parse_json_object(raw)
        return TestCaseDSL.model_validate(self._repair_dsl(dsl_data, payload))

    def sanitized_input_payload(self, payload: NaturalLanguageTestRequest) -> dict[str, Any]:
        return self._input_payload(payload)

    def _build_analyze_prompt(self, payload: NaturalLanguageTestRequest) -> str:
        return (
            "TASK: analyze\n"
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
    def _normalize_analysis(result: AnalyzeResult) -> AnalyzeResult:
        result.missingFields = list(dict.fromkeys(result.missingFields))
        result.clarifyingQuestions = list(dict.fromkeys(result.clarifyingQuestions))
        result.assumptions = list(dict.fromkeys(result.assumptions))
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
