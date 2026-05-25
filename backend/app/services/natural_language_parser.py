from typing import Any

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
        raw = self.provider.complete(
            LLMRequest(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=self._build_analyze_prompt(payload),
                stream=self._stream_enabled(payload),
            )
        )
        result = parse_json_model(raw, AnalyzeResult)
        return self._normalize_analysis(result)

    def plan(self, payload: NaturalLanguageTestRequest) -> TestCaseDSL:
        raw = self.provider.complete(
            LLMRequest(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=self._build_plan_prompt(payload),
                stream=self._stream_enabled(payload),
            )
        )
        dsl_data = parse_json_object(raw)
        return TestCaseDSL.model_validate(self._repair_dsl(dsl_data, payload))

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
            '"settings":{},'
            '"steps":[]'
            "}\n"
            "INPUT_JSON:\n"
            f"{to_compact_json(self._input_payload(payload))}"
        )

    def _input_payload(self, payload: NaturalLanguageTestRequest) -> dict[str, Any]:
        data = payload.model_dump()
        data["stream"] = self._stream_enabled(payload)
        data["credentials"] = self._sanitize_credentials(data.get("credentials") or {})
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
