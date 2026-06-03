from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import PlatformUser
from app.services.auth import user_id_from_token
from app.services.permissions import require_admin


def get_current_user(
    authorization: str | None = Header(default=None),
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> PlatformUser:
    raw_token = _extract_token(authorization) or token
    user_id = user_id_from_token(raw_token or "") if raw_token else None
    user = db.get(PlatformUser, user_id) if user_id else None
    if user is None or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录后再使用系统。")
    return user


def get_admin_user(current_user: PlatformUser = Depends(get_current_user)) -> PlatformUser:
    require_admin(current_user)
    return current_user


def _extract_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()
