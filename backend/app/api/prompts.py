from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.prompt_manager import PromptError, get_prompt_manager

router = APIRouter()


class PromptPreviewRequest(BaseModel):
    variables: dict[str, Any] = Field(default_factory=dict)


@router.get("")
def list_prompts():
    return get_prompt_manager().list_prompts()


@router.post("/reload")
def reload_prompts():
    return get_prompt_manager().reload()


@router.get("/{prompt_key}")
def read_prompt(prompt_key: str):
    try:
        return get_prompt_manager().get_prompt(prompt_key)
    except PromptError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{prompt_key}/preview")
def preview_prompt(prompt_key: str, payload: PromptPreviewRequest):
    try:
        rendered = get_prompt_manager().render_prompt(prompt_key, payload.variables)
    except PromptError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {
        "prompt_key": rendered.prompt_key,
        "prompt_version": rendered.prompt_version,
        "system": rendered.system,
        "user": rendered.user,
    }
