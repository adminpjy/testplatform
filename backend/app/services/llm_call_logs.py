from app.core.config import settings
from app.db.session import SessionLocal
from app.models import LLMCallLog


def log_llm_call(
    *,
    prompt_key: str | None,
    prompt_version: str | None,
    success: bool,
    elapsed_ms: int | None,
    error_summary: str | None = None,
    run_id: int | None = None,
    step_id: str | None = None,
) -> None:
    try:
        with SessionLocal() as db:
            db.add(
                LLMCallLog(
                    run_id=run_id,
                    step_id=step_id,
                    prompt_key=prompt_key,
                    prompt_version=prompt_version,
                    provider=settings.llm_provider,
                    model=settings.test_llm_model,
                    success=success,
                    elapsed_ms=elapsed_ms,
                    error_summary=_compact_error(error_summary),
                )
            )
            db.commit()
    except Exception:
        return


def _compact_error(value: str | None) -> str | None:
    if not value:
        return None
    return value[:1000]
