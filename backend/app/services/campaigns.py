from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TestCampaign, TestCampaignCase, TestCase, TestProject, TestRun
from app.schemas.cases import CaseRunCreate
from app.schemas.enterprise import CampaignCreateRequest, CampaignReportSummary, CampaignStartRequest, TestCampaignRead
from app.services.test_run_execution import create_and_execute_case_run, get_run


TERMINAL_STATUSES = {"passed", "failed", "stopped", "cancelled", "aborted"}


def create_campaign(db: Session, project_id: int, payload: CampaignCreateRequest) -> TestCampaignRead:
    project = db.get(TestProject, project_id)
    if project is None or project.deleted_at is not None or project.status == "deleted":
        raise ValueError("Project not found.")
    cases = _selected_cases(db, project_id, payload.caseIds)
    if not cases:
        raise ValueError("No executable cases found for campaign.")
    campaign = TestCampaign(
        project_id=project_id,
        campaign_code=_campaign_code(),
        name=payload.name,
        description=payload.description,
        status="created",
        case_ids_json={"items": [case.id for case in cases]},
        settings_json=payload.settings,
        total_count=len(cases),
        queued_count=len(cases),
        running_count=0,
        passed_count=0,
        failed_count=0,
        blocked_count=0,
        summary_json={"message": "批次已创建，尚未开始执行。"},
    )
    db.add(campaign)
    db.flush()
    for index, case in enumerate(cases, start=1):
        db.add(
            TestCampaignCase(
                campaign_id=campaign.id,
                project_id=project_id,
                case_id=case.id,
                case_version_id=case.current_version_id,
                order_index=index,
                status="queued",
            )
        )
    db.commit()
    return get_campaign(db, campaign.id)


def list_project_campaigns(db: Session, project_id: int) -> list[TestCampaignRead]:
    campaigns = list(
        db.scalars(select(TestCampaign).where(TestCampaign.project_id == project_id).order_by(TestCampaign.id.desc())).all()
    )
    return [get_campaign(db, campaign.id) for campaign in campaigns]


def get_campaign(db: Session, campaign_id: int) -> TestCampaignRead:
    campaign = db.get(TestCampaign, campaign_id)
    if campaign is None:
        raise ValueError("Campaign not found.")
    _refresh_campaign_status(db, campaign)
    cases = _campaign_cases(db, campaign.id)
    payload = TestCampaignRead.model_validate(campaign)
    payload.cases = cases
    return payload


def start_campaign(db: Session, campaign_id: int, payload: CampaignStartRequest) -> TestCampaignRead:
    campaign = db.get(TestCampaign, campaign_id)
    if campaign is None:
        raise ValueError("Campaign not found.")
    items = _campaign_case_models(db, campaign.id)
    selected = [item for item in items if item.status in {"queued", "blocked"}]
    if payload.maxCases:
        selected = selected[: payload.maxCases]
    campaign.status = "running"
    campaign.started_at = campaign.started_at or _utc_now()
    db.add(campaign)
    db.commit()

    for item in selected:
        try:
            run = create_and_execute_case_run(
                db,
                item.case_id,
                CaseRunCreate(
                    accountId=payload.accountId,
                    settingsOverride=payload.settingsOverride,
                    runName=f"campaign:{campaign.campaign_code}:case:{item.case_id}",
                ),
            )
            item.run_id = run.id
            item.status = "running"
            item.failure_summary = None
            item.result_json = {"runCode": run.run_code}
        except Exception as exc:
            item.status = "blocked"
            item.failure_summary = str(exc)
            item.result_json = {"error": str(exc)}
        db.add(item)
        db.commit()

    return get_campaign(db, campaign_id)


def campaign_report_summary(db: Session, campaign_id: int) -> CampaignReportSummary:
    campaign_read = get_campaign(db, campaign_id)
    failures: list[dict[str, Any]] = []
    runs: list[dict[str, Any]] = []
    for item in campaign_read.cases:
        if item.run_id:
            run = db.get(TestRun, item.run_id)
            runs.append(
                {
                    "caseId": item.case_id,
                    "runId": item.run_id,
                    "runCode": run.run_code if run else None,
                    "status": item.status,
                    "durationMs": run.duration_ms if run else None,
                }
            )
        if item.status in {"failed", "blocked", "aborted", "stopped"}:
            failures.append({"caseId": item.case_id, "runId": item.run_id, "status": item.status, "summary": item.failure_summary})
    return CampaignReportSummary(
        campaignId=campaign_read.id,
        campaignCode=campaign_read.campaign_code,
        projectId=campaign_read.project_id,
        name=campaign_read.name,
        status=campaign_read.status,
        totals={
            "total": campaign_read.total_count,
            "queued": campaign_read.queued_count,
            "running": campaign_read.running_count,
            "passed": campaign_read.passed_count,
            "failed": campaign_read.failed_count,
            "blocked": campaign_read.blocked_count,
        },
        failures=failures,
        runs=runs,
        recommendations=_recommendations(campaign_read, failures),
    )


def _selected_cases(db: Session, project_id: int, case_ids: list[int] | None) -> list[TestCase]:
    query = select(TestCase).where(
        TestCase.project_id == project_id,
        TestCase.deleted_at.is_(None),
        TestCase.status.in_(["active", "draft"]),
    )
    if case_ids:
        query = query.where(TestCase.id.in_(case_ids))
    return list(db.scalars(query.order_by(TestCase.id)).all())


def _campaign_case_models(db: Session, campaign_id: int) -> list[TestCampaignCase]:
    return list(
        db.scalars(select(TestCampaignCase).where(TestCampaignCase.campaign_id == campaign_id).order_by(TestCampaignCase.order_index)).all()
    )


def _campaign_cases(db: Session, campaign_id: int):
    return _campaign_case_models(db, campaign_id)


def _refresh_campaign_status(db: Session, campaign: TestCampaign) -> None:
    items = _campaign_case_models(db, campaign.id)
    changed = False
    for item in items:
        if not item.run_id:
            continue
        run = get_run(db, item.run_id)
        if run is None:
            continue
        next_status = run.status if run.status in TERMINAL_STATUSES else "running"
        if item.status != next_status:
            item.status = next_status
            item.failure_summary = run.error_summary if next_status == "failed" else item.failure_summary
            item.result_json = {
                **(item.result_json or {}),
                "runCode": run.run_code,
                "runStatus": run.status,
                "durationMs": run.duration_ms,
            }
            db.add(item)
            changed = True
    counts = _status_counts(items)
    campaign.total_count = len(items)
    campaign.queued_count = counts.get("queued", 0)
    campaign.running_count = counts.get("running", 0)
    campaign.passed_count = counts.get("passed", 0)
    campaign.failed_count = counts.get("failed", 0)
    campaign.blocked_count = counts.get("blocked", 0)
    if campaign.running_count > 0:
        campaign.status = "running"
    elif campaign.queued_count > 0 and campaign.status == "running":
        campaign.status = "running"
    elif campaign.failed_count > 0 or campaign.blocked_count > 0:
        campaign.status = "completed_with_failures"
        campaign.ended_at = campaign.ended_at or _utc_now()
    elif campaign.passed_count == campaign.total_count and campaign.total_count:
        campaign.status = "passed"
        campaign.ended_at = campaign.ended_at or _utc_now()
    campaign.summary_json = {
        "total": campaign.total_count,
        "queued": campaign.queued_count,
        "running": campaign.running_count,
        "passed": campaign.passed_count,
        "failed": campaign.failed_count,
        "blocked": campaign.blocked_count,
    }
    db.add(campaign)
    if changed or True:
        db.commit()
        db.refresh(campaign)


def _status_counts(items: list[TestCampaignCase]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1
    return counts


def _recommendations(campaign: TestCampaignRead, failures: list[dict[str, Any]]) -> list[str]:
    recommendations = []
    if failures:
        recommendations.append("优先处理失败样本中的定位失败、登录失败和高风险提交失败，并生成规则草案。")
        recommendations.append("对无法自动修复的问题使用一键反馈，提交完整运行证据给维护人员。")
    if campaign.queued_count:
        recommendations.append("仍有未执行用例，可继续启动批次执行。")
    if not recommendations:
        recommendations.append("当前批次未发现阻塞问题，可导出报告并归档。")
    return recommendations


def _campaign_code() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"CAMP-{stamp}-{uuid4().hex[:6].upper()}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)

