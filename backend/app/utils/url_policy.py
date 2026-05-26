from app.core.config import settings


def ensure_allowed_url(value: str | None, field_name: str = "url") -> None:
    if settings.is_allowed_url(value):
        return
    raise ValueError(f"{field_name} is not in ALLOWED_BASE_URL_PREFIXES.")


def ensure_allowed_urls(values: dict[str, str | None]) -> None:
    for field_name, value in values.items():
        ensure_allowed_url(value, field_name)
