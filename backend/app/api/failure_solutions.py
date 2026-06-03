from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_admin_user, get_current_user
from app.models import PlatformUser
from app.schemas.failure_workflow import (
    FailureSolutionRead,
    FailureSolutionUpdate,
    MaintenanceResponseRead,
    PublishSolutionRuleResponse,
    RuleValidationRead,
    RuleValidationRequest,
)
from app.schemas.test_runs import RuleDraftRead
from app.services.failure_workflow import (
    create_maintenance_response,
    create_rule_draft_from_solution,
    get_failure_solution,
    publish_solution_rule,
    update_failure_solution,
    validate_solution_rule,
)

router = APIRouter()


@router.get("/{solution_id}", response_model=FailureSolutionRead)
def read_failure_solution(
    solution_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_user),
) -> FailureSolutionRead:
    solution = get_failure_solution(db, solution_id)
    if solution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Failure solution not found.")
    return solution


@router.put("/{solution_id}", response_model=FailureSolutionRead)
def update_solution(
    solution_id: int,
    payload: FailureSolutionUpdate,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_admin_user),
) -> FailureSolutionRead:
    try:
        return update_failure_solution(db, solution_id, payload, actor=current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{solution_id}/rule-draft", response_model=RuleDraftRead)
def create_solution_rule_draft(
    solution_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_admin_user),
) -> RuleDraftRead:
    try:
        return create_rule_draft_from_solution(db, solution_id, actor=current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{solution_id}/validate", response_model=RuleValidationRead)
def validate_solution(
    solution_id: int,
    payload: RuleValidationRequest | None = None,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_admin_user),
) -> RuleValidationRead:
    try:
        return validate_solution_rule(
            db,
            solution_id,
            payload or RuleValidationRequest(),
            actor=current_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{solution_id}/publish", response_model=PublishSolutionRuleResponse)
def publish_solution(
    solution_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_admin_user),
) -> PublishSolutionRuleResponse:
    try:
        rule = publish_solution_rule(db, solution_id, actor=current_user)
        solution = get_failure_solution(db, solution_id)
        return PublishSolutionRuleResponse(
            abilityRuleId=rule.id,
            ruleDraftId=solution.rule_draft_id if solution and solution.rule_draft_id else 0,
            status=rule.status,
            message="规则已发布到能力规则库，后续执行会自动参与匹配。",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{solution_id}/response", response_model=MaintenanceResponseRead)
def create_solution_response(
    solution_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_admin_user),
) -> MaintenanceResponseRead:
    try:
        return create_maintenance_response(db, solution_id, actor=current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
