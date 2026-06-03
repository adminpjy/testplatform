from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditEvent, PlatformUser


def log_audit(
    db: Session,
    user: PlatformUser | None,
    action: str,
    *,
    target_type: str | None = None,
    target_id: int | None = None,
    project_id: int | None = None,
    case_id: int | None = None,
    run_id: int | None = None,
    campaign_id: int | None = None,
    result: str = "success",
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    detail: dict[str, Any] | None = None,
    commit: bool = True,
) -> AuditEvent:
    event = AuditEvent(
        project_id=project_id,
        actor_user_id=user.id if user else None,
        actor=user.username if user else "system",
        action=action,
        target_type=target_type,
        target_id=target_id,
        case_id=case_id,
        run_id=run_id,
        campaign_id=campaign_id,
        result=result,
        before_json=before,
        after_json=after,
        detail_json=detail or {},
    )
    db.add(event)
    if commit:
        db.commit()
        db.refresh(event)
    return event
