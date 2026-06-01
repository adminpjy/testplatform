from urllib.parse import urlparse


def ensure_allowed_url(value: str | None, field_name: str = "url") -> None:
    if not value:
        return
    parsed = urlparse(str(value).strip())
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return
    raise ValueError(f"{field_name} must be a valid http:// or https:// URL.")


def ensure_allowed_urls(values: dict[str, str | None]) -> None:
    for field_name, value in values.items():
        ensure_allowed_url(value, field_name)
