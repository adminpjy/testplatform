from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.base import Base
from app.schemas.llm_settings import LLMSettingsUpdate
from app.services.llm_settings import get_active_llm_config, read_llm_settings, update_llm_settings
import app.services.llm_settings as llm_settings_service


def test_update_llm_settings_masks_and_preserves_api_key(monkeypatch) -> None:
    session = _session()
    monkeypatch.setattr(llm_settings_service, "SessionLocal", lambda: session)
    saved = update_llm_settings(
        session,
        LLMSettingsUpdate.model_validate(
            {
                "activeProfileId": "deepseek-a",
                "profiles": [
                    {
                        "id": "deepseek-a",
                        "name": "DeepSeek A",
                        "baseUrl": "http://llm-a.example.test/v1",
                        "apiKey": "secret-key-a",
                        "model": "DeepSeek",
                        "stream": False,
                        "verifySsl": False,
                    }
                ],
            }
        ),
    )

    assert saved.effective is not None
    assert saved.effective.apiKeyMasked == "secr...ey-a"
    assert "secret-key-a" not in saved.model_dump_json()

    saved_again = update_llm_settings(
        session,
        LLMSettingsUpdate.model_validate(
            {
                "activeProfileId": "deepseek-a",
                "profiles": [
                    {
                        "id": "deepseek-a",
                        "name": "DeepSeek A Renamed",
                        "baseUrl": "http://llm-a.example.test/v1",
                        "apiKey": "",
                        "model": "DeepSeek",
                        "stream": False,
                        "verifySsl": False,
                    }
                ],
            }
        ),
    )
    runtime = get_active_llm_config()

    assert saved_again.effective is not None
    assert saved_again.effective.name == "DeepSeek A Renamed"
    assert runtime.api_key == "secret-key-a"


def test_read_llm_settings_initializes_from_default(monkeypatch) -> None:
    session = _session()
    monkeypatch.setattr(llm_settings_service, "SessionLocal", lambda: session)

    result = read_llm_settings(session)

    assert result.profiles
    assert result.activeProfileId == result.profiles[0].id


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return Session(bind=engine)
