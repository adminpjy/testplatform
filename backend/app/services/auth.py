from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import PlatformUser

TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60
PASSWORD_ITERATIONS = 120_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PASSWORD_ITERATIONS,
        _b64encode(salt),
        _b64encode(digest),
    )


def verify_password(password: str, stored_hash: str | None) -> bool:
    if not stored_hash:
        return False
    try:
        scheme, iterations, salt, digest = stored_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        expected = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            _b64decode(salt),
            int(iterations),
        )
        return hmac.compare_digest(expected, _b64decode(digest))
    except Exception:
        return False


def authenticate_user(db: Session, username: str, password: str) -> PlatformUser | None:
    clean_username = (username or "").strip()
    if not clean_username or not password:
        return None
    user = db.scalars(select(PlatformUser).where(PlatformUser.username == clean_username)).first()
    if user is None or user.status != "active":
        return None
    if verify_password(password, user.password_hash):
        return user
    if not user.password_hash and password == clean_username:
        user.password_hash = hash_password(password)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    return None


def create_access_token(user: PlatformUser, ttl_seconds: int = TOKEN_TTL_SECONDS) -> str:
    now = int(time.time())
    payload = {
        "sub": user.id,
        "username": user.username,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    encoded_payload = _b64encode(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    signature = _sign(encoded_payload)
    return f"{encoded_payload}.{signature}"


def user_id_from_token(token: str) -> int | None:
    try:
        encoded_payload, signature = token.split(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(signature, _sign(encoded_payload)):
        return None
    try:
        payload = json.loads(_b64decode(encoded_payload).decode("utf-8"))
    except Exception:
        return None
    if int(payload.get("exp") or 0) < int(time.time()):
        return None
    try:
        return int(payload["sub"])
    except Exception:
        return None


def ensure_default_admin(db: Session) -> PlatformUser:
    user = db.scalars(select(PlatformUser).where(PlatformUser.username == "admin")).first()
    if user is None:
        user = PlatformUser(
            username="admin",
            display_name="系统管理员",
            role="admin",
            status="active",
            password_hash=hash_password("admin"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    changed = False
    if user.role != "admin":
        user.role = "admin"
        changed = True
    if user.status != "active":
        user.status = "active"
        changed = True
    if not user.password_hash:
        user.password_hash = hash_password("admin")
        changed = True
    if changed:
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def normalize_user_role(role: str | None) -> str:
    value = str(role or "testuser").strip().lower()
    if value in {"admin", "owner", "testuser"}:
        return value
    if value in {"tester", "member", "user"}:
        return "testuser"
    return "testuser"


def current_user_payload(user: PlatformUser) -> dict[str, Any]:
    role = normalize_user_role(user.role)
    navigation = [
        "projects",
        "project-wizard",
        "test-run",
        "ability-center",
        "enterprise-center",
        "failure-samples",
        "reports",
        "settings",
    ]
    if role != "admin":
        navigation = ["projects", "project-wizard", "test-run"]
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": role,
        "status": user.status,
        "permissions": {"admin": role == "admin"},
        "navigation": navigation,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


def _sign(value: str) -> str:
    secret = settings.local_secret_key.get_secret_value()
    digest = hmac.new(secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).digest()
    return _b64encode(digest)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
