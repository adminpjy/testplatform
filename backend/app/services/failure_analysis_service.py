from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.llm.json_utils import parse_json_object, to_compact_json
from app.llm.provider import LLMRequest, get_llm_provider
from app.models import (
    FailureAnalysis,
    FailureSample,
    PlatformUser,
    RuntimeMessage,
    TestArtifact,
    TestCampaign,
    TestCase,
    TestCaseVersion,
    TestProject,
    TestRun,
    TestStepRun,
)
from app.services.llm_call_logs import log_llm_call
from app.services.llm_settings import get_active_llm_config
from app.services.prompt_manager import get_prompt_manager


MAX_TEXT_CHARS = 12000


class FailureAnalysisService:
    def analyze_failure(self, db: Session, failure_sample_id: int) -> FailureAnalysis:
        sample = db.get(FailureSample, failure_sample_id)
        if sample is None:
            raise ValueError("Failure sample not found.")
        package = self.build_evidence_package(db, sample)
        rendered = get_prompt_manager().render_prompt(
            "failure_analysis",
            {
                "failure_sample": to_compact_json(package["failureSample"]),
                "runtime_messages": package.get("runtimeStream") or "",
                "locator_debug": package.get("locatorDebug") or "",
                "evidence_package": to_compact_json(package),
            },
        )
        llm_config = get_active_llm_config()
        request = LLMRequest(
            system_prompt=rendered.system,
            user_prompt=rendered.user,
            stream=llm_config.stream,
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
                provider=llm_config.provider,
                model=llm_config.model,
                success=success,
                elapsed_ms=_elapsed_ms(started),
                error_summary=error_summary,
            )

        run = db.get(TestRun, sample.run_id)
        generalized_pattern = _normalize_pattern(result, package)
        solution = _normalize_solution(result, package)
        rule_draft = _normalize_rule_draft(result, package)
        validation_plan = _normalize_validation_plan(result, package)
        user_reply = _string_or_none(result.get("userReply") or result.get("user_reply")) or _default_user_reply(
            package,
            str(result.get("rootCause") or result.get("root_cause") or sample.failure_summary or "未能确定根因。"),
            solution.get("summary"),
        )
        internal_notes = _string_or_none(result.get("internalNotes") or result.get("internal_notes"))
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
            evidence_json={
                "items": result.get("evidence") or [],
                "packageSummary": _package_summary(package),
                "opsContext": package.get("opsContext"),
            },
            suggestions_json={"items": _normalize_suggestions(result.get("suggestions") or [], package)},
            recommended_actions_json={"items": result.get("recommendedActions") or result.get("recommended_actions") or []},
            generalized_pattern_json=generalized_pattern,
            solution_json=solution,
            rule_draft_json=rule_draft,
            validation_plan_json=validation_plan,
            user_reply=user_reply,
            internal_notes=internal_notes,
            llm_raw_response_json=result,
            risk_level=str(result.get("riskLevel") or result.get("risk_level") or "medium"),
            requires_human_review=bool(result.get("requiresHumanReview", True)),
            llm_prompt_key=request.prompt_key,
            llm_prompt_version=request.prompt_version,
            llm_model=llm_config.model,
            llm_provider=llm_config.provider,
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
                "generalizedPattern": generalized_pattern,
                "solution": solution,
                "validationPlan": validation_plan,
            },
        }
        if rule_draft:
            sample.suggested_rule_json = rule_draft
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

    def build_evidence_package(self, db: Session, sample: FailureSample) -> dict[str, Any]:
        return self._build_evidence_package(db, sample)

    def _build_evidence_package(self, db: Session, sample: FailureSample) -> dict[str, Any]:
        run = db.get(TestRun, sample.run_id)
        step = db.get(TestStepRun, sample.step_id) if sample.step_id else None
        project = db.get(TestProject, sample.project_id or (run.project_id if run else None)) if (sample.project_id or (run.project_id if run else None)) else None
        case = db.get(TestCase, sample.case_id or (run.case_id if run else None)) if (sample.case_id or (run.case_id if run else None)) else None
        version = db.get(TestCaseVersion, sample.case_version_id or (run.case_version_id if run else None)) if (sample.case_version_id or (run.case_version_id if run else None)) else None
        operator = db.get(PlatformUser, run.created_by_user_id) if run and run.created_by_user_id else None
        campaign = db.get(TestCampaign, run.campaign_id) if run and run.campaign_id else None
        artifacts = _artifacts_payload(db, run.id) if run else []
        runtime_messages = _runtime_messages_payload(db, run.id) if run else []
        run_payload = _run_payload(run)
        project_payload = _project_payload(project)
        case_payload = _case_payload(case)
        operator_payload = _operator_payload(operator)
        campaign_payload = _campaign_payload(campaign)
        return {
            "project": project_payload,
            "case": case_payload,
            "caseVersion": _version_payload(version),
            "run": run_payload,
            "campaign": campaign_payload,
            "operator": operator_payload,
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
            "runtimeMessages": runtime_messages,
            "locatorDebug": _read_text(sample.locator_debug_path),
            "executionTrace": _read_text(sample.execution_trace_path),
            "artifacts": artifacts,
            "playwrightTracePath": _trace_path_for_run(run),
            "opsContext": _ops_context(
                project_payload,
                case_payload,
                run_payload,
                operator_payload,
                campaign_payload,
                sample,
                step,
            ),
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
        pattern = _normalize_pattern({"failureCategory": failure_type}, package)
        solution = _normalize_solution({"failureCategory": failure_type, "rootCause": root_cause}, package)
        rule_draft = _normalize_rule_draft({"failureCategory": failure_type, "rootCause": root_cause}, package)
        validation_plan = _normalize_validation_plan({}, package)
        return {
            "failureCategory": failure_type,
            "rootCause": root_cause,
            "confidence": 0.55,
            "evidence": _fallback_evidence(package),
            "impact": "当前用例执行失败，需要处理后再稳定运行。",
            "suggestions": [_fallback_suggestion(failure_type, root_cause)],
            "recommendedActions": ["查看截图、Runtime Stream 和 locator-debug 后确认修复方案。"],
            "generalizedPattern": pattern,
            "solution": solution,
            "ruleDraft": rule_draft,
            "validationPlan": validation_plan,
            "userReply": _default_user_reply(package, root_cause, solution.get("summary")),
            "internalNotes": error_summary,
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


def _campaign_payload(campaign: TestCampaign | None) -> dict[str, Any] | None:
    if campaign is None:
        return None
    return {
        "id": campaign.id,
        "campaignCode": campaign.campaign_code,
        "name": campaign.name,
        "status": campaign.status,
        "totalCount": campaign.total_count,
        "passedCount": campaign.passed_count,
        "failedCount": campaign.failed_count,
        "blockedCount": campaign.blocked_count,
        "startedAt": str(campaign.started_at) if campaign.started_at else None,
        "endedAt": str(campaign.ended_at) if campaign.ended_at else None,
        "createdAt": str(campaign.created_at),
    }


def _operator_payload(user: PlatformUser | None) -> dict[str, Any] | None:
    if user is None:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "displayName": user.display_name,
        "role": user.role,
    }


def _run_payload(run: TestRun | None) -> dict[str, Any] | None:
    if run is None:
        return None
    return {
        "id": run.id,
        "runCode": run.run_code,
        "projectId": run.project_id,
        "caseId": run.case_id,
        "caseVersionId": run.case_version_id,
        "campaignId": run.campaign_id,
        "createdByUserId": run.created_by_user_id,
        "status": run.status,
        "currentPhase": run.current_phase,
        "errorSummary": run.error_summary,
        "durationMs": run.duration_ms,
        "baseUrlSnapshot": run.base_url_snapshot,
        "loginUrlSnapshot": run.login_url_snapshot,
        "homeUrlSnapshot": run.home_url_snapshot,
        "startedAt": str(run.started_at) if run.started_at else None,
        "endedAt": str(run.ended_at) if run.ended_at else None,
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
        "screenshotPath": step.screenshot_path,
        "startedAt": str(step.started_at) if step.started_at else None,
        "endedAt": str(step.ended_at) if step.ended_at else None,
    }


def _runtime_messages_payload(db: Session, run_id: int) -> list[dict[str, Any]]:
    rows = list(
        db.scalars(
            select(RuntimeMessage)
            .where(RuntimeMessage.run_id == run_id)
            .order_by(RuntimeMessage.id.desc())
            .limit(120)
        ).all()
    )
    rows.reverse()
    return [
        {
            "id": item.id,
            "type": item.type,
            "phase": item.phase,
            "content": item.content,
            "method": item.method,
            "metadata": _safe_json(item.metadata_json or {}),
            "createdAt": str(item.created_at),
        }
        for item in rows
    ]


def _artifacts_payload(db: Session, run_id: int) -> list[dict[str, Any]]:
    rows = list(
        db.scalars(
            select(TestArtifact)
            .where(TestArtifact.run_id == run_id)
            .order_by(TestArtifact.id.desc())
            .limit(80)
        ).all()
    )
    rows.reverse()
    return [
        {
            "id": item.id,
            "stepId": item.step_id,
            "artifactType": item.artifact_type,
            "filePath": item.file_path,
            "metadata": _safe_json(item.metadata_json or {}),
            "createdAt": str(item.created_at),
        }
        for item in rows
    ]


def _ops_context(
    project: dict[str, Any] | None,
    case: dict[str, Any] | None,
    run: dict[str, Any] | None,
    operator: dict[str, Any] | None,
    campaign: dict[str, Any] | None,
    sample: FailureSample,
    step: TestStepRun | None,
) -> dict[str, Any]:
    return {
        "projectName": (project or {}).get("projectName") or (project or {}).get("projectCode"),
        "caseName": (case or {}).get("caseName"),
        "caseCode": (case or {}).get("caseCode"),
        "runCode": (run or {}).get("runCode"),
        "runStatus": (run or {}).get("status"),
        "campaignName": (campaign or {}).get("name"),
        "campaignCode": (campaign or {}).get("campaignCode"),
        "operator": (operator or {}).get("displayName") or (operator or {}).get("username"),
        "executedAt": (run or {}).get("startedAt") or (run or {}).get("createdAt"),
        "endedAt": (run or {}).get("endedAt"),
        "failureSampleId": sample.id,
        "failureType": sample.failure_type,
        "failureSummary": sample.failure_summary,
        "failedStepName": step.step_name if step else None,
        "failedStepAction": step.action if step else None,
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


def _normalize_pattern(result: dict[str, Any], package: dict[str, Any]) -> dict[str, Any]:
    pattern = result.get("generalizedPattern") or result.get("generalized_pattern")
    if isinstance(pattern, dict):
        return _safe_json(pattern)
    sample = package.get("failureSample") or {}
    failure_type = str(sample.get("failureType") or result.get("failureCategory") or "unknown_failure")
    return {
        "patternName": _fallback_pattern_name(failure_type),
        "failureType": failure_type,
        "description": "同类页面或控件在目标识别、状态判断或提交验证上缺少稳定证据时，可能出现同类失败。",
        "applicability": {
            "failureTypes": [failure_type],
            "pageSignals": _page_signals(package),
            "businessActions": _business_actions(package),
        },
        "exclusions": ["真实业务权限不足", "账号密码错误", "被测系统服务不可用"],
        "evidenceSchema": ["失败截图", "失败步骤", "运行消息", "定位调试", "页面结构快照"],
    }


def _normalize_solution(result: dict[str, Any], package: dict[str, Any]) -> dict[str, Any]:
    solution = result.get("solution") or result.get("solutionPlan") or result.get("solution_plan")
    if isinstance(solution, dict):
        normalized = _safe_json(solution)
    else:
        sample = package.get("failureSample") or {}
        failure_type = str(sample.get("failureType") or result.get("failureCategory") or "unknown_failure")
        normalized = {
            "summary": _fallback_solution_summary(failure_type),
            "steps": [
                "用失败证据识别同类页面/控件特征。",
                "生成低风险规则草案，先在失败样本证据上预验证。",
                "管理员确认后发布为生产规则，并回归失败用例。",
            ],
            "riskControls": ["默认需要管理员确认", "不自动执行高风险写入/删除/审批动作", "保留原始证据和规则验证记录"],
        }
    normalized.setdefault("summary", result.get("impact") or "已生成可审核的修复方案。")
    normalized.setdefault("scope", "同类失败样本和同类页面交互。")
    return normalized


def _normalize_rule_draft(result: dict[str, Any], package: dict[str, Any]) -> dict[str, Any]:
    incoming = result.get("ruleDraft") or result.get("rule_draft")
    if isinstance(incoming, dict):
        incoming = _safe_json(incoming)
    else:
        incoming = {}

    sample = package.get("failureSample") or {}
    failure_type = str(sample.get("failureType") or result.get("failureCategory") or "unknown_failure")
    rule_type = str(incoming.get("ruleType") or incoming.get("rule_type") or _infer_rule_type(failure_type))
    rule_name = str(incoming.get("ruleName") or incoming.get("rule_name") or _fallback_rule_name(failure_type))
    content = incoming.get("content") if isinstance(incoming.get("content"), dict) else incoming
    match_config = content.get("match_config") if isinstance(content, dict) and isinstance(content.get("match_config"), dict) else {}
    action_config = content.get("action_config") if isinstance(content, dict) and isinstance(content.get("action_config"), dict) else {}
    success_criteria = content.get("success_criteria") if isinstance(content, dict) else []
    failure_patterns = content.get("failure_patterns") if isinstance(content, dict) and isinstance(content.get("failure_patterns"), dict) else {}
    recovery_strategies = content.get("recovery_strategies") if isinstance(content, dict) and isinstance(content.get("recovery_strategies"), dict) else {}

    if not match_config:
        match_config = {
            "failureTypes": [failure_type],
            "targetKeywords": _business_actions(package),
            "pageSignals": _page_signals(package),
            "minimumConfidence": 0.7,
        }
    if not action_config:
        action_config = {
            "strategy": _fallback_strategy_code(failure_type),
            "requiresHumanReview": True,
            "useEvidenceBeforeAction": True,
        }
    if not success_criteria:
        success_criteria = ["失败类型不再出现", "目标页面证据可识别", "同类用例可继续执行"]
    if not failure_patterns:
        failure_patterns = {"failureSignals": [failure_type], "negativeTextHints": []}
    if not recovery_strategies:
        recovery_strategies = {"strategies": [{"code": _fallback_strategy_code(failure_type), "label": _fallback_solution_summary(failure_type)}]}

    return {
        "ruleType": rule_type,
        "ruleName": rule_name,
        "reason": incoming.get("reason") or result.get("rootCause") or result.get("root_cause") or sample.get("failureSummary"),
        "content": {
            "rule_code_suggestion": str(
                content.get("rule_code_suggestion")
                if isinstance(content, dict) and content.get("rule_code_suggestion")
                else f"FAILURE-{failure_type.upper().replace('-', '_')}-{sample.get('id')}-v1"
            )[:64],
            "match_config": _safe_json(match_config),
            "action_config": _safe_json(action_config),
            "success_criteria": _safe_json(success_criteria),
            "failure_patterns": _safe_json(failure_patterns),
            "recovery_strategies": _safe_json(recovery_strategies),
        },
    }


def _normalize_validation_plan(result: dict[str, Any], package: dict[str, Any]) -> dict[str, Any]:
    plan = result.get("validationPlan") or result.get("validation_plan")
    if isinstance(plan, dict):
        normalized = _safe_json(plan)
    else:
        normalized = {
            "type": "evidence_static_precheck",
            "checks": [
                "规则草案必须包含匹配条件、执行策略和成功标准。",
                "匹配条件必须覆盖当前失败类型或失败摘要。",
                "失败样本必须包含截图、运行消息、定位调试或页面快照中的至少一种证据。",
                "发布前必须由管理员确认风险等级。",
            ],
        }
    normalized.setdefault("type", "evidence_static_precheck")
    normalized.setdefault("sampleIds", [(package.get("failureSample") or {}).get("id")])
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


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _default_user_reply(package: dict[str, Any], root_cause: str, solution_summary: Any) -> str:
    ops = package.get("opsContext") or {}
    project = ops.get("projectName") or "未知项目"
    case_name = ops.get("caseName") or "未关联用例"
    run_code = ops.get("runCode") or f"运行 #{(package.get('run') or {}).get('id') or '-'}"
    operator = ops.get("operator") or "未知执行人"
    executed_at = ops.get("executedAt") or "未知时间"
    fix_summary = str(solution_summary or "已生成失败分析和规则草案，待管理员预验证后发布。")
    return (
        f"项目：{project}\n"
        f"用例：{case_name}\n"
        f"运行记录：{run_code}\n"
        f"执行人：{operator}\n"
        f"执行时间：{executed_at}\n"
        f"问题原因：{root_cause}\n"
        f"处理方案：{fix_summary}\n"
        "后续动作：请在能力中心完成规则预验证和发布后重新执行相关用例。"
    )


def _fallback_pattern_name(failure_type: str) -> str:
    mapping = {
        "login_failed": "统一身份认证登录失败",
        "auth_state_not_logged_in": "登录后状态未确认",
        "login_form_fields_not_found": "登录表单控件识别不完整",
        "navigation_goal_not_reached": "菜单导航目标未到达",
        "approval_submit_failed": "审批提交控件识别失败",
    }
    return mapping.get(failure_type, f"{failure_type} 同类失败")


def _fallback_solution_summary(failure_type: str) -> str:
    if "login" in failure_type or "auth" in failure_type:
        return "补充统一身份认证页面的字段识别、提交按钮和登录成功判定规则。"
    if "navigation" in failure_type or "menu" in failure_type:
        return "补充菜单路径拆解、选中态和右侧列表变化等导航证据规则。"
    if "approval" in failure_type:
        return "补充审批意见区、下一步处理人和提交/同意按钮的识别与验证规则。"
    if "table" in failure_type or "row" in failure_type:
        return "补充表格识别、分页遍历、行打开和新页面切换的处理规则。"
    if "form" in failure_type or "locator" in failure_type:
        return "补充字段标签、占位符、邻近文本和可编辑状态的复合定位规则。"
    return "补充同类失败的页面证据识别和恢复策略规则。"


def _fallback_rule_name(failure_type: str) -> str:
    if "login" in failure_type or "auth" in failure_type:
        return "统一身份认证自适应登录规则"
    if "navigation" in failure_type or "menu" in failure_type:
        return "门户菜单路径自适应导航规则"
    if "approval" in failure_type:
        return "审批表单提交自适应规则"
    if "table" in failure_type or "row" in failure_type:
        return "列表行逐条处理自适应规则"
    return "失败恢复自适应规则"


def _fallback_strategy_code(failure_type: str) -> str:
    if "login" in failure_type or "auth" in failure_type:
        return "adaptive_login"
    if "navigation" in failure_type or "menu" in failure_type:
        return "adaptive_navigation"
    if "approval" in failure_type:
        return "adaptive_approval_submit"
    if "table" in failure_type or "row" in failure_type:
        return "adaptive_table_row_processing"
    if "form" in failure_type:
        return "adaptive_form_fill"
    return "adaptive_recovery"


def _infer_rule_type(failure_type: str) -> str:
    if "login" in failure_type or "auth" in failure_type:
        return "login"
    if "navigation" in failure_type or "menu" in failure_type or "path" in failure_type:
        return "navigation"
    if "approval" in failure_type:
        return "approval_workflow"
    if "table" in failure_type or "row" in failure_type:
        return "table_row_action"
    if "form" in failure_type or "input" in failure_type:
        return "form_fill"
    if "assert" in failure_type or "success" in failure_type:
        return "assertion"
    return "recovery_policy"


def _page_signals(package: dict[str, Any]) -> list[str]:
    signals: list[str] = []
    step = package.get("failedStep") or {}
    for key in ["stepName", "target", "action"]:
        value = step.get(key)
        if value:
            signals.append(str(value))
    sample = package.get("failureSample") or {}
    if sample.get("failureSummary"):
        signals.append(str(sample["failureSummary"])[:200])
    return signals[:8]


def _business_actions(package: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    case = package.get("case") or {}
    for key in ["businessIntent", "menuPath", "naturalLanguageGoal", "caseName"]:
        value = case.get(key)
        if value:
            actions.append(str(value)[:200])
    step = package.get("failedStep") or {}
    if step.get("target"):
        actions.append(str(step["target"])[:200])
    return actions[:8]


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
