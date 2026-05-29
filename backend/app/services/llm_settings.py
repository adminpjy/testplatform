from __future__ import annotations

import json
import re
from typing import Any
from uuid import uuid4

from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.db.session import SessionLocal
from app.models import SystemSetting
from app.schemas.llm_settings import LLMProfileRead, LLMRuntimeConfig, LLMSettingsRead, LLMSettingsUpdate
from app.utils.secrets import decrypt_secret, encrypt_secret


SETTING_KEY = "llm_services"
MASKED_VALUE = "***REDACTED***"


def read_llm_settings(db: Session) -> LLMSettingsRead:
    value = _stored_or_default(db)
    profiles = [_public_profile(item) for item in value["profiles"]]
    active_id = str(value.get("activeProfileId") or profiles[0].id)
    effective = next((item for item in profiles if item.id == active_id), profiles[0] if profiles else None)
    return LLMSettingsRead(activeProfileId=active_id, profiles=profiles, effective=effective)


def update_llm_settings(db: Session, payload: LLMSettingsUpdate) -> LLMSettingsRead:
    current = _stored_or_default(db)
    current_by_id = {str(item.get("id")): item for item in current.get("profiles") or [] if isinstance(item, dict)}
    if payload.activeProfileId not in {profile.id for profile in payload.profiles}:
        raise ValueError("当前选中的 LLM 服务不存在。")

    profiles = []
    for profile in payload.profiles:
        previous = current_by_id.get(profile.id) or {}
        api_key = profile.apiKey
        if api_key and api_key != MASKED_VALUE and not api_key.startswith("***"):
            encrypted_key = encrypt_secret(api_key)
        else:
            encrypted_key = previous.get("apiKeyEncrypted")
        profiles.append(
            {
                "id": profile.id,
                "name": profile.name,
                "provider": profile.provider,
                "baseUrl": profile.baseUrl,
                "apiKeyEncrypted": encrypted_key,
                "model": profile.model,
                "stream": profile.stream,
                "verifySsl": profile.verifySsl,
                "timeoutSeconds": profile.timeoutSeconds,
                "maxTokens": profile.maxTokens,
                "temperature": profile.temperature,
                "topP": profile.topP,
                "caBundle": profile.caBundle,
            }
        )
    _save_settings(db, {"activeProfileId": payload.activeProfileId, "profiles": profiles})
    return read_llm_settings(db)


def get_active_llm_config() -> LLMRuntimeConfig:
    try:
        with SessionLocal() as db:
            value = _stored_or_default(db)
    except Exception:
        value = _default_settings_value(settings)
    return _runtime_config(value)


def llm_settings_metadata() -> dict[str, Any]:
    try:
        return get_active_llm_config().public_metadata()
    except Exception:
        return {
            "profileId": "env",
            "profileName": "环境变量配置",
            "provider": settings.llm_provider,
            "model": settings.test_llm_model,
            "endpoint": settings.test_llm_base_url,
            "stream": settings.test_llm_stream,
        }


def _stored_or_default(db: Session) -> dict[str, Any]:
    setting = db.scalars(select(SystemSetting).where(SystemSetting.key == SETTING_KEY)).first()
    if setting is None or not isinstance(setting.value_json, dict):
        value = _default_settings_value(settings)
        _save_settings(db, value)
        return value
    value = _normalize_settings_value(setting.value_json)
    if not value.get("profiles"):
        value = _default_settings_value(settings)
        _save_settings(db, value)
    return value


def _save_settings(db: Session, value: dict[str, Any]) -> None:
    setting = db.scalars(select(SystemSetting).where(SystemSetting.key == SETTING_KEY)).first()
    if setting is None:
        setting = SystemSetting(key=SETTING_KEY, description="Runtime LLM service profiles.")
        db.add(setting)
    setting.value_json = _normalize_settings_value(value)
    db.add(setting)
    db.commit()


def _default_settings_value(config: Settings) -> dict[str, Any]:
    profiles = _profiles_from_json(config.test_llm_profiles_json)
    if not profiles:
        profiles = [
            {
                "id": "env-default",
                "name": "环境变量默认 LLM",
                "provider": config.llm_provider,
                "baseUrl": config.test_llm_base_url,
                "apiKey": config.test_llm_api_key.get_secret_value() if isinstance(config.test_llm_api_key, SecretStr) else "",
                "model": config.test_llm_model,
                "stream": config.test_llm_stream,
                "verifySsl": config.test_llm_verify_ssl,
                "timeoutSeconds": config.test_llm_timeout_seconds,
                "maxTokens": config.test_llm_max_tokens,
                "temperature": config.test_llm_temperature,
                "topP": config.test_llm_top_p,
                "caBundle": config.test_llm_ca_bundle,
            }
        ]
    normalized = [_normalize_profile(_encrypt_plain_key(profile), index) for index, profile in enumerate(profiles)]
    return {"activeProfileId": normalized[0]["id"], "profiles": normalized}


def _profiles_from_json(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(value, dict):
        value = value.get("profiles") or []
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _encrypt_plain_key(profile: dict[str, Any]) -> dict[str, Any]:
    next_profile = dict(profile)
    api_key = next_profile.pop("apiKey", None) or next_profile.pop("api_key", None)
    if api_key and not next_profile.get("apiKeyEncrypted"):
        next_profile["apiKeyEncrypted"] = encrypt_secret(str(api_key))
    return next_profile


def _normalize_settings_value(value: dict[str, Any]) -> dict[str, Any]:
    profiles = [_normalize_profile(item, index) for index, item in enumerate(value.get("profiles") or []) if isinstance(item, dict)]
    active_id = str(value.get("activeProfileId") or (profiles[0]["id"] if profiles else ""))
    if profiles and active_id not in {profile["id"] for profile in profiles}:
        active_id = profiles[0]["id"]
    return {"activeProfileId": active_id, "profiles": profiles}


def _normalize_profile(profile: dict[str, Any], index: int) -> dict[str, Any]:
    profile_id = str(profile.get("id") or _slug(str(profile.get("name") or "")) or f"llm-{index + 1}")
    return {
        "id": profile_id,
        "name": str(profile.get("name") or profile_id),
        "provider": str(profile.get("provider") or settings.llm_provider or "openai_compatible"),
        "baseUrl": str(profile.get("baseUrl") or profile.get("base_url") or ""),
        "apiKeyEncrypted": profile.get("apiKeyEncrypted") or profile.get("api_key_encrypted"),
        "model": str(profile.get("model") or settings.test_llm_model),
        "stream": bool(profile.get("stream", settings.test_llm_stream)),
        "verifySsl": bool(profile.get("verifySsl", profile.get("verify_ssl", settings.test_llm_verify_ssl))),
        "timeoutSeconds": _int_value(profile.get("timeoutSeconds", profile.get("timeout_seconds")), settings.test_llm_timeout_seconds),
        "maxTokens": _int_value(profile.get("maxTokens", profile.get("max_tokens")), settings.test_llm_max_tokens),
        "temperature": _float_value(profile.get("temperature"), settings.test_llm_temperature),
        "topP": _float_value(profile.get("topP", profile.get("top_p")), settings.test_llm_top_p),
        "caBundle": str(profile.get("caBundle") or profile.get("ca_bundle") or ""),
    }


def _public_profile(profile: dict[str, Any]) -> LLMProfileRead:
    has_key = bool(profile.get("apiKeyEncrypted"))
    return LLMProfileRead(
        id=str(profile["id"]),
        name=str(profile["name"]),
        provider=str(profile["provider"]),
        baseUrl=str(profile["baseUrl"]),
        model=str(profile["model"]),
        stream=bool(profile["stream"]),
        verifySsl=bool(profile["verifySsl"]),
        timeoutSeconds=int(profile["timeoutSeconds"]),
        maxTokens=int(profile["maxTokens"]),
        temperature=float(profile["temperature"]),
        topP=float(profile["topP"]),
        caBundle=str(profile.get("caBundle") or ""),
        hasApiKey=has_key,
        apiKeyMasked=_mask_profile_key(profile) if has_key else None,
    )


def _runtime_config(value: dict[str, Any]) -> LLMRuntimeConfig:
    normalized = _normalize_settings_value(value)
    profiles = normalized["profiles"] or _default_settings_value(settings)["profiles"]
    profile = next((item for item in profiles if item["id"] == normalized["activeProfileId"]), profiles[0])
    api_key = decrypt_secret(profile.get("apiKeyEncrypted")) or ""
    return LLMRuntimeConfig(
        profile_id=str(profile["id"]),
        profile_name=str(profile["name"]),
        provider=str(profile["provider"]),
        base_url=str(profile["baseUrl"]),
        api_key=api_key,
        model=str(profile["model"]),
        stream=bool(profile["stream"]),
        timeout_seconds=int(profile["timeoutSeconds"]),
        max_tokens=int(profile["maxTokens"]),
        temperature=float(profile["temperature"]),
        top_p=float(profile["topP"]),
        verify_ssl=bool(profile["verifySsl"]),
        ca_bundle=str(profile.get("caBundle") or ""),
    )


def _mask_profile_key(profile: dict[str, Any]) -> str:
    clear = decrypt_secret(profile.get("apiKeyEncrypted")) or ""
    if len(clear) <= 8:
        return MASKED_VALUE
    return f"{clear[:4]}...{clear[-4:]}"


def _slug(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    return text or uuid4().hex[:8]


def _int_value(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float_value(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
