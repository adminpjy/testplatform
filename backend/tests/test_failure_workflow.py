from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.base import Base
from app.models import FailureAnalysis, FailureSample, PlatformUser, TestRun as OrmTestRun
from app.schemas.failure_workflow import RuleValidationRequest
from app.schemas.projects import TestProjectCreate as ProjectCreateSchema
from app.services import failure_workflow
from app.services.auth import hash_password
from app.services.projects import create_project, get_project_model


def test_failure_workflow_generates_validates_publishes_and_replies() -> None:
    session = _session()
    admin = _admin(session)
    project = _project(session, admin)
    run = _run(session, project.id, "RUN-WORKFLOW-001", "failed", admin.id)
    sample = _failure_sample(session, project.id, run.id)
    _analysis(session, project.id, run.id, sample.id)

    solution = failure_workflow.generate_failure_solution(session, sample.id, actor=admin)
    draft = failure_workflow.create_rule_draft_from_solution(session, solution.id, actor=admin)
    validation = failure_workflow.validate_solution_rule(
        session,
        solution.id,
        RuleValidationRequest(sampleIds=[sample.id]),
        actor=admin,
    )
    rule = failure_workflow.publish_solution_rule(session, solution.id, actor=admin)
    response = failure_workflow.create_maintenance_response(session, solution.id, actor=admin)

    assert solution.context_snapshot_json["opsContext"]["projectName"] == "企业平台项目"
    assert draft.rule_type == "approval_workflow"
    assert validation.status == "passed"
    assert rule.production_enabled is True
    assert response.handled_by_user_id == admin.id
    assert "项目" in (response.user_reply or "")


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return Session(bind=engine)


def _admin(session: Session) -> PlatformUser:
    user = PlatformUser(username="admin", display_name="管理员", role="admin", password_hash=hash_password("admin"))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _project(session: Session, admin: PlatformUser):
    payload = ProjectCreateSchema(project_name="企业平台项目", base_url="https://oa.example.test/")
    created = create_project(session, payload, admin)
    project = get_project_model(session, int(created["id"]))
    assert project is not None
    return project


def _run(session: Session, project_id: int, run_code: str, status: str, user_id: int) -> OrmTestRun:
    run = OrmTestRun(
        run_code=run_code,
        project_id=project_id,
        status=status,
        current_phase=status,
        created_by_user_id=user_id,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def _failure_sample(session: Session, project_id: int, run_id: int) -> FailureSample:
    sample = FailureSample(
        project_id=project_id,
        run_id=run_id,
        failure_type="approval_submit_failed",
        failure_summary="未找到审批提交按钮",
        screenshot_path="artifacts/test.png",
    )
    session.add(sample)
    session.commit()
    session.refresh(sample)
    return sample


def _analysis(session: Session, project_id: int, run_id: int, sample_id: int) -> FailureAnalysis:
    analysis = FailureAnalysis(
        project_id=project_id,
        run_id=run_id,
        failure_sample_id=sample_id,
        analysis_status="completed",
        failure_category="approval_submit_failed",
        root_cause="审批页面提交按钮文案和图标不固定，原规则只识别单一按钮。",
        confidence=0.9,
        evidence_json={"items": ["失败截图", "运行消息"]},
        suggestions_json={"items": []},
        recommended_actions_json={"items": ["补充审批提交规则"]},
        generalized_pattern_json={"patternName": "审批提交控件识别失败", "description": "同类审批页面按钮文案不固定。"},
        solution_json={"summary": "补充提交、同意、审批等按钮的组合识别规则。"},
        rule_draft_json={
            "ruleType": "approval_workflow",
            "ruleName": "审批提交按钮自适应规则",
            "reason": "当前审批按钮识别过窄。",
            "content": {
                "rule_code_suggestion": "FAILURE-APPROVAL-SUBMIT-v1",
                "match_config": {"failureTypes": ["approval_submit_failed"]},
                "action_config": {"strategy": "adaptive_approval_submit", "buttonText": ["提交", "同意", "审批"]},
                "success_criteria": ["提交后页面状态变化", "不再出现审批提交失败"],
            },
        },
        validation_plan_json={"type": "evidence_static_precheck"},
        user_reply="项目：企业平台项目\n问题原因：审批按钮识别过窄\n处理方案：补充审批提交规则",
        risk_level="medium",
        requires_human_review=True,
    )
    session.add(analysis)
    session.commit()
    session.refresh(analysis)
    return analysis
