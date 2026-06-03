from pathlib import Path
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.base import Base
from app.models import AuditEvent, DefectCandidate, FailureSample, PlatformPlugin, TestCase as OrmTestCase, TestRun as OrmTestRun
from app.schemas.maturity import AssetCreate, AssetUpdate, GenerateCasesRequest, LearningItemCreate, PluginCreate
from app.schemas.projects import TestProjectCreate as ProjectCreateSchema
from app.services import maturity
from app.services.projects import create_project, get_project_model


def test_asset_version_publish_and_rollback() -> None:
    session = _session()

    asset = maturity.create_asset(
        session,
        AssetCreate(
            assetName="审批提交按钮规则",
            assetType="rule_template",
            module="审批",
            riskLevel="low",
            content={"selector": "button:has-text('提交')"},
        ),
    )
    first_version_id = asset.current_version_id

    updated = maturity.update_asset(
        session,
        asset.id,
        AssetUpdate(content={"selector": "button:has-text('提交'),button:has-text('同意')"}, changeSummary="补充同意按钮"),
    )
    assert updated.current_version_id != first_version_id
    assert len(maturity.asset_versions(session, asset.id)) == 2

    published = maturity.publish_asset(session, asset.id)
    assert published.status == "published"
    assert published.latest_published_version_id == published.current_version_id

    rolled_back = maturity.rollback_asset(session, asset.id, int(first_version_id))
    assert rolled_back.status == "draft"
    assert rolled_back.content_json == {"selector": "button:has-text('提交')"}
    assert len(maturity.asset_versions(session, asset.id)) == 3


def test_high_risk_asset_publish_requires_review() -> None:
    session = _session()
    asset = maturity.create_asset(
        session,
        AssetCreate(assetName="删除规则", assetType="rule_template", riskLevel="high", content={"action": "delete"}),
    )

    published = maturity.publish_asset(session, asset.id)
    audits = session.scalars(select(AuditEvent).where(AuditEvent.target_id == asset.id)).all()

    assert published.status == "pending_review"
    assert any(item.action == "request_high_risk_asset_review" for item in audits)


def test_case_generation_covers_positive_negative_boundary_and_permission() -> None:
    result = maturity.generate_cases(
        GenerateCasesRequest(
            sourceText="工作台/我的待办：查询待办列表\n审批中心/待办审批：审批并提交实例",
            includeNegative=True,
            includeBoundary=True,
            includePermission=True,
        )
    )
    scenario_types = {item.scenarioType for item in result.items}

    assert {"positive", "negative", "boundary", "permission"}.issubset(scenario_types)
    assert result.coverage["missingScenarioTypes"] == []


def test_defect_candidate_can_be_generated_from_failure_sample() -> None:
    session = _session()
    project = _project(session)
    run = _run(session, project.id, "RUN-MATURITY-DEFECT", "failed")
    sample = _failure_sample(session, project.id, run.id, "approval_submit_failed", "未找到审批提交按钮")

    defect = maturity.defect_from_failure(session, sample.id)

    assert defect.failure_sample_id == sample.id
    assert defect.defect_type == "system_defect"
    assert defect.severity == "high"
    assert defect.evidence_json["runtimeStream"] is None


def test_quality_overview_aggregates_runs_failures_and_defects() -> None:
    session = _session()
    project = _project(session)
    session.add(OrmTestCase(project_id=project.id, case_name="待办查询", business_intent="工作台"))
    _run(session, project.id, "RUN-MATURITY-PASSED", "passed")
    failed_run = _run(session, project.id, "RUN-MATURITY-FAILED", "failed")
    sample = _failure_sample(session, project.id, failed_run.id, "locator_failed", "未找到元素")
    session.add(
        DefectCandidate(
            defect_code="DEF-TEST",
            project_id=project.id,
            failure_sample_id=sample.id,
            title="定位失败",
            severity="medium",
            priority="normal",
            defect_type="automation_issue",
        )
    )
    session.commit()

    overview = maturity.quality_overview(session, project.id)

    assert overview.totals["cases"] == 1
    assert overview.totals["runs"] == 2
    assert overview.totals["passRate"] == 50.0
    assert overview.failures == [{"type": "locator_failed", "count": 1}]
    assert overview.totals["defects"] == 1


def test_learning_item_high_risk_transition_is_gated() -> None:
    session = _session()
    item = maturity.create_learning_item(
        session,
        LearningItemCreate(itemType="rule_candidate", title="高风险删除规则", riskLevel="high", proposal={"action": "delete"}),
    )

    transitioned = maturity.transition_learning_item(session, item.id, "active")

    assert transitioned.status == "pending_review"
    assert transitioned.audit_json["blocked"] == "high risk learning item requires review"


def test_plugin_registry_and_health_check() -> None:
    session = _session()
    plugin = maturity.register_plugin(
        session,
        PluginCreate(pluginName="企业 UI 适配器", pluginType="ui_adapter", config={"framework": "ant-design"}),
    )

    checked = maturity.plugin_health_check(session, plugin.id)
    plugins = session.scalars(select(PlatformPlugin)).all()

    assert len(plugins) == 1
    assert checked.health_json["status"] == "healthy"


def test_failure_solution_returns_user_readable_recovery_action() -> None:
    session = _session()
    project = _project(session)
    run = _run(session, project.id, "RUN-MATURITY-SOLUTION", "failed")
    sample = _failure_sample(session, project.id, run.id, "login_form_fields_not_found", "登录表单识别不完整")

    solution = maturity.failure_solution(session, sample.id)

    assert solution["recommendedAction"] == "modify_account_or_login_rule"
    assert solution["verificationPlan"]["type"] == "dry_run"


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return Session(bind=engine)


def _project(session: Session):
    payload = ProjectCreateSchema(project_name="企业平台项目", base_url="https://oa.example.test/")
    created = create_project(session, payload)
    project = get_project_model(session, int(created["id"]))
    assert project is not None
    return project


def _run(session: Session, project_id: int, run_code: str, status: str) -> OrmTestRun:
    run = OrmTestRun(run_code=run_code, project_id=project_id, status=status, current_phase=status)
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def _failure_sample(session: Session, project_id: int, run_id: int, failure_type: str, summary: str) -> FailureSample:
    sample = FailureSample(project_id=project_id, run_id=run_id, failure_type=failure_type, failure_summary=summary)
    session.add(sample)
    session.commit()
    session.refresh(sample)
    return sample
