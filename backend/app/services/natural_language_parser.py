from typing import Any
import re
import time

from app.core.config import settings
from app.llm.json_utils import parse_json_model, parse_json_object, to_compact_json
from app.llm.provider import LLMProvider, LLMRequest, get_llm_provider
from app.schemas.test_runs import ALLOWED_DSL_ACTIONS, AnalyzeResult, NaturalLanguageTestRequest, TestCaseDSL
from app.services.dsl_post_processor import normalize_dsl
from app.services.llm_settings import get_active_llm_config
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
        explicit_criteria = self._extract_instruction_record_criteria(payload.instruction)
        if explicit_criteria:
            data["instructionExplicitData"] = explicit_criteria
            data["dataPrecedence"] = "自然语言测试目标中的显式数据优先；testData 仅作为未在目标中说明的补充数据。"
        return data

    def _stream_enabled(self, payload: NaturalLanguageTestRequest) -> bool:
        if payload.stream is not None:
            return payload.stream
        try:
            return get_active_llm_config().stream
        except Exception:
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
        if payload is not None:
            result = NaturalLanguageParser._apply_instruction_precedence_to_analysis(result, payload)
        return result

    def _repair_dsl(self, dsl_data: dict[str, Any], payload: NaturalLanguageTestRequest) -> dict[str, Any]:
        repaired = {
            "caseName": dsl_data.get("caseName") or "自然语言测试用例",
            "baseUrl": dsl_data.get("baseUrl") or payload.base_url or "",
            "credentials": self._sanitize_credentials(dsl_data.get("credentials") or payload.credentials or {}),
            "testData": dsl_data.get("testData") or payload.testData or {},
            "settings": dsl_data.get("settings") or payload.settings or {},
            "steps": dsl_data.get("steps") or [],
            "missingFields": dsl_data.get("missingFields") or [],
            "clarifyingQuestions": dsl_data.get("clarifyingQuestions") or [],
        }
        self._apply_instruction_precedence_to_dsl(repaired, payload)
        if self._is_todo_batch_approval(payload):
            self._ensure_todo_batch_approval_dsl(repaired, payload)
            self._apply_instruction_precedence_to_dsl(repaired, payload)
        if self._is_todo_dialog_exploration(payload):
            repaired.update(self._default_todo_dialog_dsl(payload, base=repaired))
            self._apply_instruction_precedence_to_dsl(repaired, payload)
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

    @classmethod
    def _apply_instruction_precedence_to_analysis(
        cls,
        result: AnalyzeResult,
        payload: NaturalLanguageTestRequest,
    ) -> AnalyzeResult:
        criteria = cls._extract_instruction_record_criteria(payload.instruction)
        conflicts = cls._conflicting_payload_values(criteria, payload.testData or {})
        if not criteria or not conflicts:
            return result
        criteria_text = "，".join(f"{key}={value}" for key, value in criteria.items())
        result.assumptions = [
            item
            for item in result.assumptions
            if not ("测试数据" in str(item) and "为准" in str(item))
        ]
        note = f"本次自然语言目标明确指定 {criteria_text}，与旧测试数据冲突时以本次目标为准。"
        result.assumptions = list(dict.fromkeys([*result.assumptions, note]))
        if result.normalizedInstruction and any(old in result.normalizedInstruction for old, _new in conflicts):
            result.normalizedInstruction = str(payload.instruction)
        if result.understoodGoal and any(old in result.understoodGoal for old, _new in conflicts):
            result.understoodGoal = str(payload.instruction)
        return result

    @classmethod
    def _apply_instruction_precedence_to_dsl(cls, repaired: dict[str, Any], payload: NaturalLanguageTestRequest) -> None:
        criteria = cls._extract_instruction_record_criteria(payload.instruction)
        if not criteria:
            return
        conflicts = cls._conflicting_payload_values(criteria, payload.testData or {})
        repaired["testData"] = cls._merge_test_data_with_instruction_precedence(repaired.get("testData"), criteria)
        steps = [dict(step) for step in repaired.get("steps") or [] if isinstance(step, dict)]
        for step in steps:
            cls._apply_criteria_to_existing_step(step, criteria, conflicts)
        repaired["steps"] = cls._ensure_record_target_steps(steps, criteria, payload.instruction)

    @staticmethod
    def _extract_instruction_record_criteria(instruction: str | None) -> dict[str, str]:
        text = str(instruction or "")
        criteria: dict[str, str] = {}
        fields = ["流程实例号", "实例号", "申请编号", "单据编号", "工单号", "单号", "编号"]
        for field in fields:
            match = re.search(
                rf"{field}\s*(?:为|是|=|:|：)?\s*[“\"']?\s*([A-Za-z0-9_-]{{3,}})\s*[”\"']?",
                text,
            )
            if match:
                criteria["实例号" if "实例号" in field else field] = match.group(1)
                return criteria
        approval_match = re.search(r"审批\s*[“\"']?\s*([A-Za-z0-9_-]{3,})\s*[”\"']?", text)
        if approval_match and any(token in text for token in ["待办", "流程", "单据", "实例"]):
            criteria["实例号"] = approval_match.group(1)
        return criteria

    @staticmethod
    def _merge_test_data_with_instruction_precedence(value: Any, criteria: dict[str, str]) -> dict[str, Any]:
        test_data = dict(value or {}) if isinstance(value, dict) else {}
        for field, field_value in criteria.items():
            canonical = "实例号" if "实例号" in field else field
            aliases = _record_field_aliases(canonical)
            replaced = False
            for alias in aliases:
                if alias in test_data:
                    test_data[alias] = field_value
                    replaced = True
            if not replaced:
                test_data[canonical] = field_value
        return test_data

    @classmethod
    def _apply_criteria_to_existing_step(
        cls,
        step: dict[str, Any],
        criteria: dict[str, str],
        conflicts: list[tuple[str, str]],
    ) -> None:
        action = str(step.get("action") or "")
        if action in {"query_table", "query_table_count"}:
            cls._merge_criteria_field(step, "queryConditions", criteria)
            cls._merge_criteria_field(step, "criteria", criteria)
        if action in {"open_table_row", "open_row_link_or_detail", "click_table_row_action"}:
            cls._merge_criteria_field(step, "rowCriteria", criteria)
        for key in [
            "queryConditions",
            "query_conditions",
            "criteria",
            "conditions",
            "rowCriteria",
            "row_criteria",
            "recordCondition",
            "record_condition",
            "targetRecord",
            "target_record",
        ]:
            if isinstance(step.get(key), dict):
                cls._merge_criteria_field(step, key, criteria)
        for key in ["target", "description", "name", "stepName", "step_name", "readableDescription"]:
            if isinstance(step.get(key), str):
                step[key] = cls._replace_conflicting_values(str(step[key]), conflicts)

    @staticmethod
    def _merge_criteria_field(step: dict[str, Any], key: str, criteria: dict[str, str]) -> None:
        current = dict(step.get(key) or {}) if isinstance(step.get(key), dict) else {}
        for field, value in criteria.items():
            aliases = _record_field_aliases(field)
            matched_alias = next((alias for alias in aliases if alias in current), field)
            current[matched_alias] = value
        step[key] = current

    @classmethod
    def _ensure_record_target_steps(
        cls,
        steps: list[dict[str, Any]],
        criteria: dict[str, str],
        instruction: str,
    ) -> list[dict[str, Any]]:
        if not criteria or "审批" not in instruction:
            return steps
        approval_index = cls._first_approval_step_index(steps)
        if approval_index is None:
            return steps
        before_approval = steps[:approval_index]
        inserts: list[dict[str, Any]] = []
        if not any(str(step.get("action") or "") in {"query_table", "query_table_count"} for step in before_approval):
            inserts.append(
                {
                    "action": "query_table",
                    "target": "我的待办列表",
                    "queryConditions": dict(criteria),
                    "criteria": dict(criteria),
                    "description": "按本次目标中的实例号查询待办列表。",
                }
            )
        if not any(str(step.get("action") or "") in {"open_table_row", "open_row_link_or_detail"} for step in before_approval):
            inserts.append(
                {
                    "action": "open_table_row",
                    "target": "我的待办列表",
                    "rowCriteria": dict(criteria),
                    "description": "打开匹配本次实例号的待办记录。",
                }
            )
        if not inserts:
            return steps
        return steps[:approval_index] + inserts + steps[approval_index:]

    @staticmethod
    def _first_approval_step_index(steps: list[dict[str, Any]]) -> int | None:
        for index, step in enumerate(steps):
            text = " ".join(
                str(step.get(key) or "")
                for key in ["action", "target", "intent", "description", "name", "stepName", "step_name"]
            )
            operation_intent = step.get("operationIntent") if isinstance(step.get("operationIntent"), dict) else {}
            if str(operation_intent.get("intent") or "") in {"approval_pass", "approval_reject"}:
                return index
            if "审批" in text and any(token in text for token in ["通过", "同意", "办理", "处理", "当前单据", "实例"]):
                return index
        return None

    @staticmethod
    def _conflicting_payload_values(criteria: dict[str, str], test_data: dict[str, Any]) -> list[tuple[str, str]]:
        conflicts: list[tuple[str, str]] = []
        if not isinstance(test_data, dict):
            return conflicts
        for field, value in criteria.items():
            aliases = _record_field_aliases(field)
            new_value = str(value)
            for alias in aliases:
                old_value = test_data.get(alias)
                if old_value not in (None, "") and str(old_value) != new_value:
                    conflicts.append((str(old_value), new_value))
        return conflicts

    @staticmethod
    def _replace_conflicting_values(value: str, conflicts: list[tuple[str, str]]) -> str:
        result = value
        for old, new in conflicts:
            if old and new:
                result = result.replace(old, new)
        return result

    @staticmethod
    def _is_todo_batch_approval(payload: NaturalLanguageTestRequest) -> bool:
        text = str(payload.instruction or "")
        compact = re.sub(r"\s+", "", text)
        if "待办" not in compact:
            return False
        if not any(token in compact for token in ["逐一", "逐条", "逐个", "每一条", "所有", "全部", "循环"]):
            return False
        if not any(token in compact for token in ["审批", "提交", "同意", "通过", "办理", "处理"]):
            return False
        return any(token in compact for token in ["意见", "填写", "填入", "输入"])

    @classmethod
    def _ensure_todo_batch_approval_dsl(cls, repaired: dict[str, Any], payload: NaturalLanguageTestRequest) -> None:
        opinion = cls._extract_approval_opinion(payload.instruction) or cls._opinion_from_mapping(repaired.get("testData") or {})
        if opinion:
            test_data = dict(repaired.get("testData") or {})
            for key in ["我的意见", "审批意见", "意见"]:
                test_data[key] = opinion
            repaired["testData"] = test_data

        steps = [dict(step) for step in repaired.get("steps") or [] if isinstance(step, dict)]
        cleaned: list[dict[str, Any]] = []
        process_inserted = False
        for step in steps:
            action = str(step.get("action") or "")
            if action == "process_table_rows":
                cleaned.append(cls._todo_batch_process_step(step, opinion=opinion))
                process_inserted = True
                continue
            if cls._is_todo_batch_row_body_step(step):
                continue
            cleaned.append(step)

        if not process_inserted:
            process_step = cls._todo_batch_process_step({"action": "process_table_rows", "target": "我的待办列表"}, opinion=opinion)
            cleaned.insert(cls._todo_process_insert_index(cleaned), process_step)
        if not any(str(step.get("action") or "") in {"query_table", "query_table_count"} and "待办" in _flatten(step) for step in cleaned):
            insert_at = max(0, cls._todo_process_insert_index(cleaned) - 1)
            cleaned.insert(
                insert_at,
                {
                    "action": "query_table_count",
                    "target": "我的待办列表",
                    "emptyStrategy": "pass",
                    "description": "读取待办列表数量；列表为空时正常结束。",
                },
            )
        repaired["steps"] = cleaned

    @staticmethod
    def _todo_batch_process_step(step: dict[str, Any], *, opinion: str | None) -> dict[str, Any]:
        current = dict(step)
        current["action"] = "process_table_rows"
        current.setdefault("target", "我的待办列表")
        row_step: dict[str, Any] = {
            "action": "business_goal",
            "target": "审批通过",
            "intent": "approval_pass",
            "readableDescription": "填写审批意见并提交。",
        }
        if opinion:
            row_step["value"] = opinion
            row_step["formData"] = {"我的意见": opinion, "审批意见": opinion, "意见": opinion}
        loop_policy = dict(current.get("loopPolicy") or current.get("loop_policy") or {})
        loop_policy.update(
            {
                "maxRows": int(current.get("maxRows") or loop_policy.get("maxRows") or loop_policy.get("max_rows") or 200),
                "emptyStrategy": current.get("emptyStrategy") or loop_policy.get("emptyStrategy") or loop_policy.get("empty_strategy") or "pass",
                "rowAction": "open_todo",
                "openMode": "new_page_or_same_page",
                "closeStrategy": "close_new_page_or_return_to_list",
                "rowEntryLabels": ["相关办理人处理", "办理人处理", "待办处理", "办理", "处理", "审批", "审核", "标题", "文号", "单号"],
                "rowSteps": [row_step],
            }
        )
        current["loopPolicy"] = loop_policy
        current["rowSteps"] = [row_step]
        current["readableDescription"] = "逐条打开待办，填写意见并提交审批。"
        return current

    @staticmethod
    def _todo_process_insert_index(steps: list[dict[str, Any]]) -> int:
        candidate = len(steps)
        for index, step in enumerate(steps):
            text = _flatten(step)
            action = str(step.get("action") or "")
            if action in {"query_table", "query_table_count"} and "待办" in text:
                candidate = index + 1
            elif action in {"navigate_path", "navigate_menu", "business_goal"} and "待办" in text:
                candidate = index + 1
        return candidate

    @staticmethod
    def _is_todo_batch_row_body_step(step: dict[str, Any]) -> bool:
        action = str(step.get("action") or "")
        intent = str((step.get("operationIntent") or {}).get("intent") or step.get("intent") or "")
        text = _flatten(step)
        if action in {"open_table_row", "open_row_link_or_detail", "click_table_row_action"}:
            return True
        if action == "wait" and any(token in text for token in ["页面稳定", "待办", "审批", "提交"]):
            return True
        if action in {"fill_form", "auto_fill_form"} and any(token in text for token in ["意见", "审批", "审核", "办理", "处理"]):
            return True
        if action in {"click", "confirm_dialog"} and any(token in text for token in ["第一行", "任意列", "待办", "提交", "审批", "审核", "同意", "通过", "办理", "处理"]):
            return True
        if action == "business_goal" and intent in {"approval_pass", "approval_reject"}:
            return True
        if action == "business_goal" and any(token in text for token in ["审批", "提交", "同意", "通过"]) and "登录" not in text:
            return True
        if action == "close_dialog_by_common_controls":
            return True
        return False

    @staticmethod
    def _extract_approval_opinion(instruction: str | None) -> str | None:
        text = str(instruction or "")
        patterns = [
            r"意见[为是填入填写输入：:\s]*[“\"']([^”\"']{1,200})[”\"']",
            r"填写意见[“\"']([^”\"']{1,200})[”\"']",
            r"输入意见[“\"']([^”\"']{1,200})[”\"']",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        return None

    @staticmethod
    def _opinion_from_mapping(mapping: dict[str, Any]) -> str | None:
        for key in ["我的意见", "审批意见", "审核意见", "处理意见", "办理意见", "意见", "opinion", "comment"]:
            value = mapping.get(key)
            if value not in (None, ""):
                return str(value)
        return None

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
                    "action": "process_table_rows",
                    "target": "我的待办列表",
                    "loopPolicy": {
                        "maxRows": 200,
                        "emptyStrategy": "pass",
                        "rowAction": "open_link_or_detail",
                        "closeStrategy": "common_dialog_controls",
                    },
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


def _flatten(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten(item) for item in value)
    if value is None:
        return ""
    return str(value)


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _record_field_aliases(field: str) -> list[str]:
    if "实例号" in field:
        return ["实例号", "流程实例号", "instanceNo", "instance_no", "processInstanceId", "process_instance_id"]
    if field in {"编号", "单据编号", "单号", "申请编号", "工单号"}:
        return [field, "编号", "单据编号", "单号", "申请编号", "工单号", "recordNo", "record_no"]
    return [field]
