from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models import PlatformUser
from app.schemas.enterprise import CampaignCreateRequest, CampaignReportSummary, CampaignStartRequest, TestCampaignRead
from app.services.audit import log_audit
from app.services.campaigns import campaign_report_summary, create_campaign, get_campaign, list_project_campaigns, start_campaign
from app.services.permissions import require_project_permission

router = APIRouter()


@router.post("/api/projects/{project_id}/campaigns", response_model=TestCampaignRead, status_code=status.HTTP_201_CREATED)
def create_project_campaign(
    project_id: int,
    payload: CampaignCreateRequest,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> TestCampaignRead:
    require_project_permission(db, current_user, project_id, "run_campaign")
    try:
        campaign = create_campaign(db, project_id, payload, actor_user_id=current_user.id)
        log_audit(
            db,
            current_user,
            "campaign_create",
            target_type="test_campaign",
            target_id=campaign.id,
            project_id=project_id,
            campaign_id=campaign.id,
            after={"name": campaign.name, "caseCount": campaign.total_count},
        )
        return campaign
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/api/projects/{project_id}/campaigns", response_model=list[TestCampaignRead])
def read_project_campaigns(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> list[TestCampaignRead]:
    require_project_permission(db, current_user, project_id, "view_reports")
    return list_project_campaigns(db, project_id)


@router.get("/api/campaigns/{campaign_id}", response_model=TestCampaignRead)
def read_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> TestCampaignRead:
    try:
        campaign = get_campaign(db, campaign_id)
        require_project_permission(db, current_user, campaign.project_id, "view_reports")
        return campaign
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/api/campaigns/{campaign_id}/start", response_model=TestCampaignRead)
def start_existing_campaign(
    campaign_id: int,
    payload: CampaignStartRequest,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> TestCampaignRead:
    try:
        campaign = get_campaign(db, campaign_id)
        require_project_permission(db, current_user, campaign.project_id, "run_campaign")
        started = start_campaign(db, campaign_id, payload, actor_user_id=current_user.id)
        log_audit(
            db,
            current_user,
            "campaign_start",
            target_type="test_campaign",
            target_id=campaign_id,
            project_id=started.project_id,
            campaign_id=campaign_id,
            detail={"maxCases": payload.maxCases, "accountId": payload.accountId},
        )
        return started
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/api/campaigns/{campaign_id}/report-summary", response_model=CampaignReportSummary)
def read_campaign_report_summary(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> CampaignReportSummary:
    try:
        campaign = get_campaign(db, campaign_id)
        require_project_permission(db, current_user, campaign.project_id, "view_reports")
        return campaign_report_summary(db, campaign_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
