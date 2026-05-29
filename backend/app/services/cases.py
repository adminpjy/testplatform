from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    FailureAnalysis,
    FailureSample,
    FixApplication,
    TestCase,
    TestCaseVersion,
    TestProject,
    TestRun,
)
from app.schemas.cases import (
    CaseAnalyzeRequest,
    FunctionalTestCaseCreate,
    FunctionalTestCaseUpdate,
    SaveGeneratedDslRequest,
    TestCaseVersionCreate,
)
from app.schemas.test_runs import NaturalLanguageTestRequest, TestCaseDSL
from app.services.dsl_post_processor import normalize_dsl
from app.services.natural_language_parser import NaturalLanguageParser


VERSIONED_FIELDS = {
    "dsl_json",
    "test_data_json",
    "preconditions_json",
    "success_criteria_json",
    "settings_json",
    "natural_language_goal",
}


def list_project_cases(db: Session, project_id: int) -> list[TestCase]:
    return list(
        db.scalars(
            select(TestCase)
            .where(
                TestCase.project_id == project_id,
                TestCase.deleted_at.is_(None),
                TestCase.status != "deleted",
            )
            .order_by(TestCase.id.desc())
        ).all()
    )


def get_case(db: Session, case_id: int) -> TestCase | None:
    case = db.get(TestCase, case_id)
    if case is None or case.deleted_at is not None or case.status == "deleted":
        return None
    return case


def create_case(db: Session, project: TestProject, payload: FunctionalTestCaseCreate) -> TestCase:
    data = payload.model_dump(exclude_unset=True)
    dsl_json = _normalize_optional_dsl(data.get("dsl_json"))
    case = TestCase(
        project_id=project.id,
        case_code=data.get("case_code") or _case_code(),
        case_name=data["case_name"],
        description=data.get("description"),
        source_type=data.get("source_type") or "manual",
        instruction=data.get("natural_language_goal"),
        natural_language_goal=data.get("natural_language_goal"),
        menu_path=data.get("menu_path"),
        business_intent=data.get("business_intent"),
        inherit_project_account=bool(data.get("inherit_project_account", True)),
        account_id=data.get("account_id"),
        test_data_json=data.get("test_data_json") or {},
        preconditions_json=data.get("preconditions_json") or {},
        success_criteria_json=data.get("success_criteria_json") or {},
        settings_json=data.get("settings_json") or {},
        dsl_json=dsl_json,
        risk_level=data.get("risk_level") or "low",
        status=data.get("status") or "draft",
    )
    db.add(case)
    db.flush()
    version = _create_version_from_case(db, case, change_type="initial", change_summary="Initial version")
    case.current_version_id = version.id
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def update_case(db: Session, case: TestCase, payload: FunctionalTestCaseUpdate) -> TestCase:
    data = payload.model_dump(exclude_unset=True)
    versioned_changed = any(field in data and _json_value(getattr(case, field), field) != _json_value(data[field], field) for field in VERSIONED_FIELDS)
    if "dsl_json" in data:
        data["dsl_json"] = _normalize_optional_dsl(data["dsl_json"])
    for field_name, value in data.items():
        setattr(case, field_name, value)
    if "natural_language_goal" in data:
        case.instruction = data["natural_language_goal"]
    db.add(case)
    db.flush()
    if versioned_changed:
        version = _create_version_from_case(db, case, change_type="manual_edit", change_summary="Case content updated")
        case.current_version_id = version.id
        db.add(case)
    db.commit()
    db.refresh(case)
    return case


def soft_delete_case(db: Session, case: TestCase) -> None:
    case.status = "deleted"
    case.deleted_at = datetime.now(timezone.utc)
    db.add(case)
    db.commit()


def set_case_status(db: Session, case: TestCase, status: str) -> TestCase:
    case.status = status
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def copy_case(db: Session, case: TestCase) -> TestCase:
    copied = TestCase(
        project_id=case.project_id,
        case_code=_case_code(),
        case_name=f"{case.case_name} 副本",
        description=case.description,
        source_type=case.source_type,
        instruction=case.instruction,
        natural_language_goal=case.natural_language_goal,
        menu_path=case.menu_path,
        business_intent=case.business_intent,
        inherit_project_account=case.inherit_project_account,
        account_id=case.account_id,
        test_data_json=copy.deepcopy(case.test_data_json or {}),
        preconditions_json=copy.deepcopy(case.preconditions_json or {}),
        success_criteria_json=copy.deepcopy(case.success_criteria_json or {}),
        settings_json=copy.deepcopy(case.settings_json or {}),
        risk_level=case.risk_level,
        dsl_json=copy.deepcopy(case.dsl_json or {}),
        status="draft",
    )
    db.add(copied)
    db.flush()
    version = _create_version_from_case(db, copied, change_type="copied", change_summary=f"Copied from {case.case_code or case.id}")
    copied.current_version_id = version.id
    db.add(copied)
    db.commit()
    db.refresh(copied)
    return copied


def list_versions(db: Session, case_id: int) -> list[TestCaseVersion]:
    return list(
        db.scalars(
            select(TestCaseVersion).where(TestCaseVersion.case_id == case_id).order_by(TestCaseVersion.version_no.desc())
        ).all()
    )


def get_version(db: Session, case_id: int, version_id: int) -> TestCaseVersion | None:
    return db.scalars(
        select(TestCaseVersion).where(TestCaseVersion.id == version_id, TestCaseVersion.case_id == case_id)
    ).first()


def create_version(db: Session, case: TestCase, payload: TestCaseVersionCreate) -> TestCaseVersion:
    data = payload.model_dump(exclude_unset=True)
    version = TestCaseVersion(
        case_id=case.id,
        version_no=_next_version_no(db, case.id),
        version_label=data.get("version_label"),
        natural_language_goal=data.get("natural_language_goal", case.natural_language_goal),
        dsl_json=_normalize_optional_dsl(data.get("dsl_json", case.dsl_json)),
        test_data_json=data.get("test_data_json", case.test_data_json or {}),
        preconditions_json=data.get("preconditions_json", case.preconditions_json or {}),
        success_criteria_json=data.get("success_criteria_json", case.success_criteria_json or {}),
        settings_json=data.get("settings_json", case.settings_json or {}),
        change_type=data.get("change_type") or "manual_edit",
        change_summary=data.get("change_summary"),
        source_analysis_id=data.get("source_analysis_id"),
        source_run_id=data.get("source_run_id"),
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


def activate_version(db: Session, case: TestCase, version: TestCaseVersion) -> TestCase:
    case.current_version_id = version.id
    case.natural_language_goal = version.natural_language_goal
    case.instruction = version.natural_language_goal
    case.dsl_json = copy.deepcopy(version.dsl_json or {})
    case.test_data_json = copy.deepcopy(version.test_data_json or {})
    case.preconditions_json = copy.deepcopy(version.preconditions_json or {})
    case.success_criteria_json = copy.deepcopy(version.success_criteria_json or {})
    case.settings_json = copy.deepcopy(version.settings_json or {})
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def validate_dsl(dsl_json: dict[str, Any]) -> dict[str, Any]:
    try:
        normalized = normalize_dsl(dsl_json)
        TestCaseDSL.model_validate(normalized)
        return {"valid": True, "errors": [], "dsl_json": normalized}
    except Exception as exc:
        return {"valid": False, "errors": [str(exc)], "dsl_json": dsl_json}


def format_dsl(dsl_json: dict[str, Any]) -> dict[str, Any]:
    return normalize_dsl(dsl_json)


def update_case_dsl(db: Session, case: TestCase, dsl_json: dict[str, Any], change_summary: str | None, change_type: str = "manual_edit") -> TestCase:
    case.dsl_json = normalize_dsl(dsl_json)
    version = _create_version_from_case(db, case, change_type=change_type, change_summary=change_summary or "DSL updated")
    case.current_version_id = version.id
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def analyze_case(db: Session, case: TestCase, payload: CaseAnalyzeRequest):
    parser = NaturalLanguageParser()
    request = _nl_request(db, case, payload)
    return parser.analyze(request)


def generate_case_dsl(db: Session, case: TestCase, payload: CaseAnalyzeRequest) -> dict[str, Any]:
    parser = NaturalLanguageParser()
    request = _nl_request(db, case, payload)
    return parser.plan(request).model_dump()


def save_generated_dsl(db: Session, case: TestCase, payload: SaveGeneratedDslRequest) -> TestCase:
    if payload.test_data_json:
        merged = dict(case.test_data_json or {})
        merged.update(payload.test_data_json)
        case.test_data_json = merged
    case.dsl_json = normalize_dsl(payload.dsl_json)
    version = _create_version_from_case(
        db,
        case,
        change_type="llm_generated",
        change_summary=payload.change_summary or "Saved generated DSL",
    )
    case.current_version_id = version.id
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def list_case_runs(db: Session, case_id: int) -> list[TestRun]:
    return list(db.scalars(select(TestRun).where(TestRun.case_id == case_id).order_by(TestRun.id.desc())).all())


def list_case_failure_samples(db: Session, case_id: int) -> list[FailureSample]:
    return list(
        db.scalars(select(FailureSample).where(FailureSample.case_id == case_id).order_by(FailureSample.id.desc())).all()
    )


def list_case_failure_analyses(db: Session, case_id: int) -> list[FailureAnalysis]:
    return list(
        db.scalars(select(FailureAnalysis).where(FailureAnalysis.case_id == case_id).order_by(FailureAnalysis.id.desc())).all()
    )


def list_case_fix_applications(db: Session, case_id: int) -> list[FixApplication]:
    return list(
        db.scalars(select(FixApplication).where(FixApplication.case_id == case_id).order_by(FixApplication.id.desc())).all()
    )


def _create_version_from_case(
    db: Session,
    case: TestCase,
    *,
    change_type: str,
    change_summary: str | None = None,
) -> TestCaseVersion:
    version = TestCaseVersion(
        case_id=case.id,
        version_no=_next_version_no(db, case.id),
        version_label=None,
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


def _next_version_no(db: Session, case_id: int) -> int:
    current = db.scalar(select(func.max(TestCaseVersion.version_no)).where(TestCaseVersion.case_id == case_id))
    return int(current or 0) + 1


def _case_code() -> str:
    return f"CASE-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6].upper()}"


def _normalize_optional_dsl(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("dsl_json must be a JSON object.")
    return normalize_dsl(value)


def _json_value(value: Any, field: str) -> Any:
    if field == "dsl_json" and isinstance(value, dict):
        return normalize_dsl(value)
    return value


def _nl_request(db: Session, case: TestCase, payload: CaseAnalyzeRequest) -> NaturalLanguageTestRequest:
    project = db.get(TestProject, case.project_id)
    instruction = payload.instruction or case.natural_language_goal or case.instruction or case.case_name
    test_data = dict(case.test_data_json or {})
    if payload.testData:
        test_data.update(payload.testData)
    return NaturalLanguageTestRequest(
        project_id=case.project_id,
        system_id=project.system_id if project else None,
        instruction=instruction,
        base_url=project.base_url if project else None,
        credentials={},
        testData=test_data,
        settings=case.settings_json or {},
        stream=payload.stream,
    )
