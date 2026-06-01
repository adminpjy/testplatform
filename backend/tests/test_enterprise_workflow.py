from pathlib import Path
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.base import Base
from app.models import FailureSample, RuleDraft, TestCase as OrmTestCase, TestRun as OrmTestRun
from app.schemas.cases import FunctionalTestCaseCreate
from app.schemas.enterprise import (
    CampaignCreateRequest,
    ImportBootstrapCasesRequest,
    MaintenanceFeedbackCreate,
    PrescanRequest,
    ProjectWizardBootstrapRequest,
)
from app.schemas.projects import TestProjectCreate as ProjectCreateSchema
from app.services.campaigns import campaign_report_summary, create_campaign
from app.services.cases import create_case
from app.services.maintenance_feedback import create_maintenance_feedback
from app.services.prescan import run_project_prescan
from app.services.project_wizard import bootstrap_project, import_bootstrap_cases
from app.services.projects import create_project, get_project_model


def test_project_wizard_generates_and_imports_cases(tmp_path, monkeypatch) -> None:
    session = _session()
    monkeypatch.setattr("app.services.project_wizard.settings.data_dir", str(tmp_path))

    result = bootstrap_project(
        session,
        ProjectWizardBootstrapRequest.model_validate(
            {
                "project": {
                    "project_name": "OA 测试项目",
                    "base_url": "https://oa.example.test/",
                    "login_url": "https://oa.example.test/login",
                    "enable_vision_fallback_default": True,
                },
                "files": [
                    {"file_name": "old.txt", "role": "baseline", "content": "菜单：工作台/我的待办\n"},
                    {"file_name": "new.txt", "role": "current", "content": "审批待办列表，填写意见“按要求执行”，点击提交\n"},
                ],
            }
        ),
    )

    assert result["drafts"]
    assert result["package"].status == "draft_generated"

    imported = import_bootstrap_cases(
        session,
        result["package"].id,
        ImportBootstrapCasesRequest(draftIndexes=[result["drafts"][0].index]),
    )

    assert len(imported.importedCaseIds) == 1
    case_id = imported.importedCaseIds[0]
    case = session.get(OrmTestCase, case_id)
    assert case is not None
    assert case.dsl_json["steps"][0]["action"] == "business_goal"


def test_prescan_creates_rule_drafts_for_navigation_and_approval() -> None:
    session = _session()
    project = _project(session)
    case = create_case(
        session,
        project,
        FunctionalTestCaseCreate(
            case_name="审批待办",
            natural_language_goal="打开工作台/我的待办，逐一点开待办，填写意见按要求执行，点击提交",
            menu_path="工作台/我的待办",
            dsl_json={
                "caseName": "审批待办",
                "baseUrl": "https://oa.example.test/",
                "credentials": {},
                "testData": {},
                "settings": {},
                "steps": [{"action": "navigate_path", "target": "工作台/我的待办"}],
            },
        ),
    )

    result = run_project_prescan(session, project.id, PrescanRequest(caseIds=[case.id], dryRun=True))
    rule_types = {
        item.rule_type
        for item in session.scalars(select(RuleDraft).where(RuleDraft.id.in_(result.ruleDraftIds))).all()
    }

    assert "navigation_rule" in rule_types
    assert "approval_rule" in rule_types
    assert result.summary["dryRun"] is True


def test_campaign_summary_counts_cases() -> None:
    session = _session()
    project = _project(session)
    case = create_case(
        session,
        project,
        FunctionalTestCaseCreate(
            case_name="查询待办",
            natural_language_goal="登录系统，查询待办列表",
            dsl_json={
                "caseName": "查询待办",
                "baseUrl": "https://oa.example.test/",
                "credentials": {},
                "testData": {},
                "settings": {},
                "steps": [{"action": "business_goal", "target": "查询待办列表"}],
            },
        ),
    )

    campaign = create_campaign(session, project.id, CampaignCreateRequest(name="回归批次", caseIds=[case.id]))
    summary = campaign_report_summary(session, campaign.id)

    assert summary.totals["total"] == 1
    assert summary.totals["queued"] == 1
    assert summary.status == "created"


def test_maintenance_feedback_redacts_sensitive_values() -> None:
    session = _session()
    project = _project(session)
    run = OrmTestRun(
        run_code="RUN-TEST-FEEDBACK",
        project_id=project.id,
        status="failed",
        current_phase="failed",
        dsl_snapshot={"credentials": {"username": "tester", "password": "secret-pass"}},
        test_data_snapshot={"token": "secret-token", "实例号": "26058"},
        settings_snapshot={"safe": True},
        account_snapshot={"username": "tester", "has_password": True},
        error_summary="locator failed",
    )
    session.add(run)
    session.flush()
    sample = FailureSample(
        project_id=project.id,
        run_id=run.id,
        failure_type="locator_failed",
        failure_summary="未找到提交按钮",
        status="new",
    )
    session.add(sample)
    session.commit()

    feedback = create_maintenance_feedback(session, MaintenanceFeedbackCreate(failureSampleId=sample.id))
    serialized = str(feedback.evidence_package_json)

    assert "secret-pass" not in serialized
    assert "secret-token" not in serialized
    assert "***REDACTED***" in serialized
    assert feedback.feedback_code.startswith("FB-")


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return Session(bind=engine)


def _project(session: Session):
    payload = ProjectCreateSchema(project_name="OA 项目", base_url="https://oa.example.test/")
    created = create_project(session, payload)
    project = get_project_model(session, int(created["id"]))
    assert project is not None
    return project
