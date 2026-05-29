from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.llm_settings import LLMSettingsRead, LLMSettingsUpdate
from app.services.llm_settings import read_llm_settings, update_llm_settings


router = APIRouter()


@router.get("", response_model=LLMSettingsRead)
def read_settings(db: Session = Depends(get_db)) -> LLMSettingsRead:
    return read_llm_settings(db)


@router.put("", response_model=LLMSettingsRead)
def update_settings(payload: LLMSettingsUpdate, db: Session = Depends(get_db)) -> LLMSettingsRead:
    try:
        return update_llm_settings(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
