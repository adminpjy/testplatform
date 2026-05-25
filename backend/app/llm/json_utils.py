import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


class JSONParseError(ValueError):
    pass


def parse_json_object(text: str) -> dict[str, Any]:
    cleaned = _strip_transport_noise(text)
    for candidate in (cleaned, _repair_json_text(cleaned), _extract_json_text(cleaned)):
        if not candidate:
            continue
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise JSONParseError("Unable to extract a JSON object from LLM response.")


def parse_json_model(text: str, model_type: type[ModelT]) -> ModelT:
    return model_type.model_validate(parse_json_object(text))


def to_compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _strip_transport_noise(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped, flags=re.IGNORECASE).strip()
        stripped = re.sub(r"```$", "", stripped).strip()

    lines = stripped.splitlines()
    data_lines: list[str] = []
    has_data_prefix = False
    for line in lines:
        left = line.lstrip()
        if not left.startswith("data:"):
            continue
        has_data_prefix = True
        content = left[5:]
        if content.startswith(" "):
            content = content[1:]
        if content.strip() == "[DONE]":
            continue
        data_lines.append(content)

    if has_data_prefix:
        return "".join(data_lines).strip()
    return stripped


def _extract_json_text(text: str) -> str | None:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            _, end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        return text[index : index + end]
    return None


def _repair_json_text(text: str) -> str:
    repaired = _extract_json_text(text) or text
    repaired = repaired.strip()
    repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
    repaired = repaired.replace("：", ":")
    repaired = repaired.replace("，", ",")
    repaired = repaired.replace("“", '"').replace("”", '"')
    repaired = repaired.replace("‘", "'").replace("’", "'")
    repaired = re.sub(r"\bNone\b", "null", repaired)
    repaired = re.sub(r"\bTrue\b", "true", repaired)
    repaired = re.sub(r"\bFalse\b", "false", repaired)
    return repaired
