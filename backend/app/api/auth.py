from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models import PlatformUser
from app.schemas.auth import CurrentUserRead, LoginRequest, LoginResponse
from app.services.audit import log_audit
from app.services.auth import authenticate_user, create_access_token, current_user_payload

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = authenticate_user(db, payload.username, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码不正确。")
    token = create_access_token(user)
    log_audit(
        db,
        user,
        "user_login",
        target_type="platform_user",
        target_id=user.id,
        detail={"username": user.username},
    )
    return LoginResponse(token=token, user=CurrentUserRead.model_validate(current_user_payload(user)))


@router.get("/me", response_model=CurrentUserRead)
def read_current_user(current_user: PlatformUser = Depends(get_current_user)) -> CurrentUserRead:
    return CurrentUserRead.model_validate(current_user_payload(current_user))


@router.post("/logout")
def logout(current_user: PlatformUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    log_audit(db, current_user, "user_logout", target_type="platform_user", target_id=current_user.id)
    return {"status": "ok"}
