from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.utils.url_policy import ensure_allowed_url


def test_url_policy_allows_any_http_url_even_when_prefix_env_is_set(monkeypatch) -> None:
    monkeypatch.setenv("ALLOWED_BASE_URL_PREFIXES", "https://only.example.test")

    ensure_allowed_url("https://menhu.bypc.com.cn/", "base_url")
    ensure_allowed_url("http://172.21.4.88/v1", "base_url")


def test_url_policy_rejects_non_http_url() -> None:
    with pytest.raises(ValueError, match="valid http:// or https:// URL"):
        ensure_allowed_url("file:///etc/passwd", "base_url")
