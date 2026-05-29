from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.llm.json_utils import parse_json_object, to_compact_json
from app.llm.provider import LLMRequest, get_llm_provider
from app.models import FailureAnalysis, FailureSample, TestCase, TestCaseVersion, TestProject, TestRun, TestStepRun
from app.services.llm_call_logs import log_llm_call
from app.services.prompt_manager import get_prompt_manager


MAX_TEXT_CHARS = 12000


class FailureAnalysisService:
    def analyze_failure(self, db: Session, failure_sample_id: int) -> FailureAnalysis:
        sample = db.get(FailureSample, failure_sample_id)
        if sample is None:
            raise ValueError("Failure sample not found.")
        package = self._build_evidence_package(db, sample)
        rendered = get_prompt_manager().render_prompt(
            "failure_analysis",
            {
                "failure_sample": to_compact_json(package["failureSample"]),
                "runtime_messages": package.get("runtimeStream") or "",
                "locator_debug": package.get("locatorDebug") or "",
                "evidence_package": to_compact_json(package),
            },
        )
        request = LLMRequest(
            system_prompt=rendered.system,
            user_prompt=rendered.user,
            stream=settings.test_llm_stream,
            temperature=rendered.metadata.get("temperature"),
            max_tokens=rendered.metadata.get("max_tokens"),
            prompt_key=rendered.prompt_key,
            prompt_version=rendered.prompt_version,
        )
        started = time.monotonic()
        raw = ""
        success = False
        error_summary = None
        try:
            raw = get_llm_provider().complete(request)
            result = self._normalize_llm_result(raw, package)
            success = True
        except Exception as exc:
            error_summary = str(exc)
            result = self._fallback_result(package, error_summary)
        finally:
            log_llm_call(
                run_id=sample.run_id,
                step_id=sample.step_id,
                prompt_key=request.prompt_key,
                prompt_version=request.prompt_version,
                provider=settings.llm_provider,
                model=settings.test_llm_model,
                success=success,
                elapsed_ms=_elapsed_ms(started),
                error_summary=error_summary,
            )

        run = db.get(TestRun, sample.run_id)
        analysis = FailureAnalysis(
            project_id=sample.project_id or (run.project_id if run else None),
            case_id=sample.case_id or (run.case_id if run else None),
            case_version_id=sample.case_version_id or (run.case_version_id if run else None),
            run_id=sample.run_id,
            failure_sample_id=sample.id,
            analysis_status="completed" if success else "fallback",
            failure_category=str(result.get("failureCategory") or result.get("failure_category") or sample.failure_type or "unknown"),
            root_cause=str(result.get("rootCause") or result.get("root_cause") or sample.failure_summary or "unknown"),
            confidence=_float_or_none(result.get("confidence")),
            evidence_json={"items": result.get("evidence") or [], "packageSummary": _package_summary(package)},
            suggestions_json={"items": _normalize_suggestions(result.get("suggestions") or [], package)},
            recommended_actions_json={"items": result.get("recommendedActions") or result.get("recommended_actions") or []},
            risk_level=str(result.get("riskLevel") or result.get("risk_level") or "medium"),
            requires_human_review=bool(result.get("requiresHumanReview", True)),
            llm_prompt_key=request.prompt_key,
            llm_prompt_version=request.prompt_version,
            llm_model=settings.test_llm_model,
            llm_provider=settings.llm_provider,
            elapsed_ms=_elapsed_ms(started),
            error_summary=error_summary,
        )
        db.add(analysis)
        sample.status = "analyzed"
        sample.ai_analysis_json = {
            **(sample.ai_analysis_json or {}),
            "failureAnalysisId": None,
            "llmFailureAnalysis": {
                "failureCategory": analysis.failure_category,
                "rootCause": analysis.root_cause,
                "confidence": analysis.confidence,
                "riskLevel": analysis.risk_level,
            },
        }
        db.add(sample)
        db.flush()
        sample.ai_analysis_json = {
            **(sample.ai_analysis_json or {}),
            "failureAnalysisId": analysis.id,
        }
        db.add(sample)
        db.commit()
        db.refresh(analysis)
        return analysis

    def _build_evidence_package(self, db: Session, sample: FailureSample) -> dict[str, Any]:
        run = db.get(TestRun, sample.run_id)
        step = db.get(TestStepRun, sample.step_id) if sample.step_id else None
        project = db.get(TestProject, sample.project_id or (run.project_id if run else None)) if (sample.project_id or (run.project_id if run else None)) else None
        case = db.get(TestCase, sample.case_id or (run.case_id if run else None)) if (sample.case_id or (run.case_id if run else None)) else None
        version = db.get(TestCaseVersion, sample.case_version_id or (run.case_version_id if run else None)) if (sample.case_version_id or (run.case_version_id if run else None)) else None
        return {
            "project": _project_payload(project),
            "case": _case_payload(case),
            "caseVersion": _version_payload(version),
            "run": _run_payload(run),
            "failedStep": _step_payload(step),
            "failureSample": {
                "id": sample.id,
                "failureType": sample.failure_type,
                "failureSummary": sample.failure_summary,
                "status": sample.status,
                "evidence": sample.evidence_json,
                "aiAnalysis": sample.ai_analysis_json,
                "paths": {
                    "screenshot": sample.screenshot_path,
                    "domSnapshot": sample.dom_snapshot_path,
                    "accessibilitySnapshot": sample.accessibility_snapshot_path,
                    "locatorDebug": sample.locator_debug_path,
                    "runtimeStream": sample.runtime_stream_path,
                    "executionTrace": sample.execution_trace_path,
                    "report": sample.report_path,
                },
            },
            "dslSnapshot": _safe_json(run.dsl_snapshot if run else None),
            "testDataSnapshot": _safe_json(run.test_data_snapshot if run else None),
            "settingsSnapshot": _safe_json(run.settings_snapshot if run else None),
            "accountSnapshot": _safe_json(run.account_snapshot if run else None),
            "domSnapshot": _read_text(sample.dom_snapshot_path),
            "accessibilitySnapshot": _read_text(sample.accessibility_snapshot_path),
            "runtimeStream": _read_text(sample.runtime_stream_path),
            "locatorDebug": _read_text(sample.locator_debug_path),
            "executionTrace": _read_text(sample.execution_trace_path),
            "playwrightTracePath": _trace_path_for_run(run),
            "history": {
                "caseRunCount": case.run_count if case else None,
                "casePassCount": case.pass_count if case else None,
                "caseFailCount": case.fail_count if case else None,
            },
        }

    def _normalize_llm_result(self, raw: str, package: dict[str, Any]) -> dict[str, Any]:
        try:
            result = parse_json_object(raw)
        except Exception:
            result = {}
        if not result.get("failureCategory") and not result.get("rootCause"):
            return self._fallback_result(package, None)
        result.setdefault("suggestions", [])
        result.setdefault("recommendedActions", [])
        result.setdefault("evidence", [])
        result.setdefault("requiresHumanReview", True)
        return result

    def _fallback_result(self, package: dict[str, Any], error_summary: str | None) -> dict[str, Any]:
        sample = package.get("failureSample") or {}
        failure_type = str(sample.get("failureType") or "unknown_failure")
        root_cause = str(sample.get("failureSummary") or error_summary or "未能从证据中确定根因。")
        return {
            "failureCategory": failure_type,
            "rootCause": root_cause,
            "confidence": 0.55,
            "evidence": _fallback_evidence(package),
            "impact": "当前用例执行失败，需要处理后再稳定运行。",
            "suggestions": [_fallback_suggestion(failure_type, root_cause)],
            "recommendedActions": ["查看截图、Runtime Stream 和 locator-debug 后确认修复方案。"],
            "riskLevel": "medium",
            "requiresHumanReview": True,
        }


def get_failure_analysis(db: Session, analysis_id: int) -> FailureAnalysis | None:
    return db.get(FailureAnalysis, analysis_id)


def _project_payload(project: TestProject | None) -> dict[str, Any] | None:
    if project is None:
        return None
    return {
        "id": project.id,
        "projectCode": project.project_code,
        "projectName": project.project_name or project.name,
        "systemName": project.system_name,
        "baseUrl": project.base_url,
        "loginUrl": project.login_url,
        "homeUrl": project.home_url,
        "authType": project.auth_type,
    }


def _case_payload(case: TestCase | None) -> dict[str, Any] | None:
    if case is None:
        return None
    return {
        "id": case.id,
        "caseCode": case.case_code,
        "caseName": case.case_name,
        "naturalLanguageGoal": case.natural_language_goal,
        "menuPath": case.menu_path,
        "businessIntent": case.business_intent,
        "status": case.status,
    }


def _version_payload(version: TestCaseVersion | None) -> dict[str, Any] | None:
    if version is None:
        return None
    return {
        "id": version.id,
        "versionNo": version.version_no,
        "changeType": version.change_type,
        "createdAt": str(version.created_at),
    }


def _run_payload(run: TestRun | None) -> dict[str, Any] | None:
    if run is None:
        return None
    return {
        "id": run.id,
        "runCode": run.run_code,
        "status": run.status,
        "currentPhase": run.current_phase,
        "errorSummary": run.error_summary,
        "durationMs": run.duration_ms,
        "baseUrlSnapshot": run.base_url_snapshot,
        "createdAt": str(run.created_at),
    }


def _step_payload(step: TestStepRun | None) -> dict[str, Any] | None:
    if step is None:
        return None
    return {
        "id": step.id,
        "stepId": step.step_id,
        "stepName": step.step_name,
        "action": step.action,
        "target": step.target,
        "status": step.status,
        "locatorStrategy": step.locator_strategy,
        "confidence": step.confidence,
        "reason": step.reason,
        "errorSummary": step.error_summary,
    }


def _read_text(file_path: str | None) -> str | None:
    if not file_path:
        return None
    try:
        from executor.aitp_executor.utils.file_paths import resolve_project_path

        path = resolve_project_path(file_path)
    except Exception:
        path = Path(file_path)
    if not path.exists() or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:MAX_TEXT_CHARS]
    except Exception:
        return None


def _trace_path_for_run(run: TestRun | None) -> str | None:
    if run is None:
        return None
    try:
        from executor.aitp_executor.utils.file_paths import runs_root, safe_name

        path = runs_root() / safe_name(run.run_code) / "traces" / "trace.zip"
        return str(path.as_posix()) if path.exists() else None
    except Exception:
        return None


def _safe_json(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            if any(token in str(key).lower() for token in ["password", "token", "secret", "密码"]):
                sanitized[key] = "***REDACTED***"
            else:
                sanitized[key] = _safe_json(item)
        return sanitized
    if isinstance(value, list):
        return [_safe_json(item) for item in value]
    return value


def _package_summary(package: dict[str, Any]) -> dict[str, Any]:
    sample = package.get("failureSample") or {}
    return {
        "failureType": sample.get("failureType"),
        "hasDomSnapshot": bool(package.get("domSnapshot")),
        "hasAccessibilitySnapshot": bool(package.get("accessibilitySnapshot")),
        "hasRuntimeStream": bool(package.get("runtimeStream")),
        "hasLocatorDebug": bool(package.get("locatorDebug")),
        "hasExecutionTrace": bool(package.get("executionTrace")),
        "playwrightTracePath": package.get("playwrightTracePath"),
    }


def _normalize_suggestions(suggestions: Any, package: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(suggestions, list) or not suggestions:
        sample = package.get("failureSample") or {}
        return [_fallback_suggestion(str(sample.get("failureType") or "unknown_failure"), str(sample.get("failureSummary") or ""))]
    normalized = []
    for item in suggestions:
        if isinstance(item, dict):
            normalized.append(item)
        else:
            normalized.append({"type": "human_intervention", "instructionTemplate": str(item), "reason": "LLM suggestion"})
    return normalized


def _fallback_suggestion(failure_type: str, reason: str) -> dict[str, Any]:
    if failure_type in {"login_failed", "auth_state_not_logged_in"}:
        return {
            "type": "modify_account",
            "issue": "登录未成功",
            "suggestion": "检查测试账号、密码、账号状态和角色权限。",
            "requiredRole": "",
            "reason": reason,
        }
    if "menu" in failure_type or "navigation" in failure_type:
        return {
            "type": "add_rule",
            "ruleType": "navigation",
            "ruleName": "菜单路径导航失败恢复规则",
            "ruleDraft": {},
            "reason": reason,
            "requiresReview": True,
        }
    return {
        "type": "human_intervention",
        "instructionTemplate": "请人工确认当前页面状态，并说明下一步应点击或填写的控件。",
        "reason": reason,
    }


def _fallback_evidence(package: dict[str, Any]) -> list[str]:
    evidence = []
    sample = package.get("failureSample") or {}
    if sample.get("failureType"):
        evidence.append(f"failureType={sample['failureType']}")
    if sample.get("failureSummary"):
        evidence.append(str(sample["failureSummary"]))
    if package.get("failedStep"):
        evidence.append(f"failedStep={to_compact_json(package['failedStep'])}")
    return evidence


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
