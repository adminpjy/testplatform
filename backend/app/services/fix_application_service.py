from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import FailureAnalysis, FixApplication, HumanIntervention, RuleDraft, TestCase, TestCaseVersion
from app.schemas.cases import ApplySuggestionRequest, ApplySuggestionResponse, CaseRunCreate
from app.schemas.test_runs import TestCaseDSL
from app.services.dsl_post_processor import normalize_dsl
from app.services.test_run_execution import create_and_execute_case_run


def get_fix_application(db: Session, fix_id: int) -> FixApplication | None:
    return db.get(FixApplication, fix_id)


def apply_failure_analysis_suggestion(
    db: Session,
    analysis_id: int,
    payload: ApplySuggestionRequest,
) -> ApplySuggestionResponse:
    if not payload.confirm:
        raise ValueError("Confirmation is required before applying a suggestion.")
    analysis = db.get(FailureAnalysis, analysis_id)
    if analysis is None:
        raise ValueError("Failure analysis not found.")
    suggestion = _suggestion_at(analysis, payload.suggestionIndex)
    action = payload.action
    case = db.get(TestCase, analysis.case_id) if analysis.case_id else None

    if action == "apply_to_dsl":
        _require_case(case)
        fix = _apply_dsl_patch(db, analysis, case, suggestion)
    elif action == "create_rule_draft":
        fix = _create_rule_draft(db, analysis, suggestion)
    elif action == "modify_test_data":
        _require_case(case)
        fix = _merge_case_json_field(db, analysis, case, suggestion, "test_data_json", "suggestedTestData", "modify_test_data")
    elif action == "add_precondition":
        _require_case(case)
        fix = _merge_case_json_field(db, analysis, case, suggestion, "preconditions_json", "preconditions", "add_precondition")
    elif action == "modify_success_criteria":
        _require_case(case)
        fix = _merge_case_json_field(db, analysis, case, suggestion, "success_criteria_json", "successCriteria", "modify_success_criteria")
    elif action == "create_human_intervention":
        fix = _create_human_intervention(db, analysis, suggestion)
    elif action == "mark_environment_issue":
        fix = _record_simple_fix(db, analysis, "environment_issue", "applied", reason=suggestion.get("issue") or suggestion.get("suggestion"))
    elif action == "create_defect_candidate":
        fix = _record_simple_fix(
            db,
            analysis,
            "defect_candidate",
            "applied",
            reason=suggestion.get("defectTitle") or suggestion.get("reason"),
            defect_draft=suggestion,
        )
    else:
        raise ValueError(f"Unsupported action: {action}")
    db.commit()
    db.refresh(fix)
    return ApplySuggestionResponse(
        fixApplicationId=fix.id,
        status=fix.status,
        createdCaseVersionId=fix.created_case_version_id,
        createdRuleDraftId=fix.created_rule_draft_id,
        message="Repair suggestion applied.",
    )


def verify_fix_application(db: Session, fix_id: int):
    fix = db.get(FixApplication, fix_id)
    if fix is None:
        raise ValueError("Fix application not found.")
    if fix.case_id is None:
        raise ValueError("Fix application is not linked to a test case.")
    run = create_and_execute_case_run(db, fix.case_id, CaseRunCreate(runName=f"verify_fix:{fix.id}"))
    fix.verify_run_id = run.id
    fix.status = "verifying"
    db.add(fix)
    db.commit()
    db.refresh(fix)
    return run


def _apply_dsl_patch(db: Session, analysis: FailureAnalysis, case: TestCase, suggestion: dict[str, Any]) -> FixApplication:
    before = copy.deepcopy(case.dsl_json or {})
    patch = suggestion.get("dslPatch") if isinstance(suggestion.get("dslPatch"), dict) else {}
    after = normalize_dsl(_deep_merge(copy.deepcopy(before), patch))
    TestCaseDSL.model_validate(after)
    case.dsl_json = after
    version = _create_case_version(db, case, "repair_modify_dsl", suggestion.get("reason") or suggestion.get("description"))
    case.current_version_id = version.id
    db.add(case)
    fix = _base_fix(analysis, "modify_dsl", "applied", before, after)
    fix.created_case_version_id = version.id
    db.add(fix)
    return fix


def _create_rule_draft(db: Session, analysis: FailureAnalysis, suggestion: dict[str, Any]) -> FixApplication:
    rule_draft = RuleDraft(
        source_type="failure_analysis",
        source_id=analysis.id,
        rule_type=str(suggestion.get("ruleType") or "recovery_policy"),
        rule_name=str(suggestion.get("ruleName") or suggestion.get("title") or "失败分析规则草案"),
        proposed_content_json=suggestion.get("ruleDraft") or suggestion.get("patch") or suggestion,
        reason=suggestion.get("reason"),
        status="pending_review",
    )
    db.add(rule_draft)
    db.flush()
    fix = _base_fix(analysis, str(suggestion.get("type") or "add_rule"), "applied", None, suggestion)
    fix.created_rule_draft_id = rule_draft.id
    db.add(fix)
    return fix


def _merge_case_json_field(
    db: Session,
    analysis: FailureAnalysis,
    case: TestCase,
    suggestion: dict[str, Any],
    field_name: str,
    suggestion_key: str,
    fix_type: str,
) -> FixApplication:
    before = copy.deepcopy(getattr(case, field_name) or {})
    incoming = suggestion.get(suggestion_key)
    if isinstance(incoming, list):
        incoming = {"items": incoming}
    if not isinstance(incoming, dict):
        incoming = {}
    after = _deep_merge(copy.deepcopy(before), incoming)
    setattr(case, field_name, after)
    version = _create_case_version(db, case, f"repair_{fix_type}", suggestion.get("reason"))
    case.current_version_id = version.id
    db.add(case)
    fix = _base_fix(analysis, fix_type, "applied", before, after)
    fix.created_case_version_id = version.id
    db.add(fix)
    return fix


def _create_human_intervention(db: Session, analysis: FailureAnalysis, suggestion: dict[str, Any]) -> FixApplication:
    intervention = HumanIntervention(
        run_id=analysis.run_id,
        step_id=None,
        user_instruction=suggestion.get("instructionTemplate") or suggestion.get("reason") or "请人工确认当前失败并给出处理步骤。",
        llm_plan_json=None,
        execution_result_json=None,
        status="submitted",
    )
    db.add(intervention)
    fix = _record_simple_fix(db, analysis, "human_intervention", "applied", reason=intervention.user_instruction)
    return fix


def _record_simple_fix(
    db: Session,
    analysis: FailureAnalysis,
    fix_type: str,
    status: str,
    *,
    reason: Any = None,
    defect_draft: dict[str, Any] | None = None,
) -> FixApplication:
    fix = _base_fix(analysis, fix_type, status, None, None)
    fix.reason = str(reason or "")
    fix.defect_draft_json = defect_draft
    db.add(fix)
    return fix


def _base_fix(
    analysis: FailureAnalysis,
    fix_type: str,
    status: str,
    before: Any,
    after: Any,
) -> FixApplication:
    return FixApplication(
        project_id=analysis.project_id,
        case_id=analysis.case_id,
        run_id=analysis.run_id,
        failure_analysis_id=analysis.id,
        fix_type=fix_type,
        status=status,
        before_snapshot_json=before if isinstance(before, dict) else {"value": before} if before is not None else None,
        after_snapshot_json=after if isinstance(after, dict) else {"value": after} if after is not None else None,
        applied_at=datetime.now(timezone.utc),
    )


def _create_case_version(db: Session, case: TestCase, change_type: str, change_summary: str | None) -> TestCaseVersion:
    version_no = max((version.version_no for version in case.versions), default=0) + 1
    version = TestCaseVersion(
        case_id=case.id,
        version_no=version_no,
        natural_language_goal=case.natural_language_goal,
        dsl_json=copy.deepcopy(case.dsl_json or {}),
        test_data_json=copy.deepcopy(case.test_data_json or {}),
        preconditions_json=copy.deepcopy(case.preconditions_json or {}),
        success_criteria_json=copy.deepcopy(case.success_criteria_json or {}),
        settings_json=copy.deepcopy(case.settings_json or {}),
        change_type=change_type,
        change_summary=change_summary,
    )
    db.add(version)
    db.flush()
    return version


def _suggestion_at(analysis: FailureAnalysis, index: int) -> dict[str, Any]:
    items = (analysis.suggestions_json or {}).get("items") if isinstance(analysis.suggestions_json, dict) else []
    if not isinstance(items, list) or index < 0 or index >= len(items):
        raise ValueError("Suggestion not found.")
    suggestion = items[index]
    if not isinstance(suggestion, dict):
        raise ValueError("Suggestion is not actionable.")
    return suggestion


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(dict(base[key]), value)
        else:
            base[key] = value
    return base


def _require_case(case: TestCase | None) -> None:
    if case is None:
        raise ValueError("Failure analysis is not linked to a test case.")
