from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.enterprise import CampaignCreateRequest, CampaignReportSummary, CampaignStartRequest, TestCampaignRead
from app.services.campaigns import campaign_report_summary, create_campaign, get_campaign, list_project_campaigns, start_campaign

router = APIRouter()


@router.post("/api/projects/{project_id}/campaigns", response_model=TestCampaignRead, status_code=status.HTTP_201_CREATED)
def create_project_campaign(
    project_id: int,
    payload: CampaignCreateRequest,
    db: Session = Depends(get_db),
) -> TestCampaignRead:
    try:
        return create_campaign(db, project_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/api/projects/{project_id}/campaigns", response_model=list[TestCampaignRead])
def read_project_campaigns(project_id: int, db: Session = Depends(get_db)) -> list[TestCampaignRead]:
    return list_project_campaigns(db, project_id)


@router.get("/api/campaigns/{campaign_id}", response_model=TestCampaignRead)
def read_campaign(campaign_id: int, db: Session = Depends(get_db)) -> TestCampaignRead:
    try:
        return get_campaign(db, campaign_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/api/campaigns/{campaign_id}/start", response_model=TestCampaignRead)
def start_existing_campaign(
    campaign_id: int,
    payload: CampaignStartRequest,
    db: Session = Depends(get_db),
) -> TestCampaignRead:
    try:
        return start_campaign(db, campaign_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/api/campaigns/{campaign_id}/report-summary", response_model=CampaignReportSummary)
def read_campaign_report_summary(campaign_id: int, db: Session = Depends(get_db)) -> CampaignReportSummary:
    try:
        return campaign_report_summary(db, campaign_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

