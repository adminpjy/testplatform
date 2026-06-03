import json
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.services.default_prompts import DEFAULT_PROMPTS


class PromptError(RuntimeError):
    pass


@dataclass(frozen=True)
class RenderedPrompt:
    prompt_key: str
    prompt_version: str
    system: str
    user: str
    metadata: dict[str, Any]


class PromptManager:
    def __init__(self, *, root: Path | None = None) -> None:
        self.root = root or Path("config/prompts")
        self.registry_path = self.root / "prompt-registry.yaml"
        self._prompts: dict[str, dict[str, Any]] = {}
        self._last_error: str | None = None
        self.load_all()

    def load_all(self) -> None:
        try:
            prompts = self._load_from_files()
            self._prompts = prompts
            self._last_error = None
        except Exception as exc:
            self._last_error = str(exc)
            if not self._prompts:
                self._prompts = self._fallback_prompts()

    def reload(self) -> dict[str, Any]:
        before = dict(self._prompts)
        self.load_all()
        if self._last_error and before:
            self._prompts = before
        return {"loaded": len(self._prompts), "last_error": self._last_error}

    def disable_prompt(self, prompt_key: str) -> dict[str, Any]:
        if not self.registry_path.exists():
            raise PromptError("当前使用内置 Prompt，不能删除；请先在 config/prompts/prompt-registry.yaml 中注册可维护 Prompt。")
        registry_doc = yaml.safe_load(self.registry_path.read_text(encoding="utf-8")) or {}
        registry = registry_doc.get("registry") or {}
        entry = registry.get(prompt_key)
        if entry is None:
            raise PromptError(f"Prompt is built-in or not registered, cannot delete: {prompt_key}")
        entry["enabled"] = False
        registry_doc["registry"] = registry
        self.registry_path.write_text(yaml.safe_dump(registry_doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
        self.reload()
        return {"prompt_key": prompt_key, "status": "disabled"}

    def get_prompt(self, prompt_key: str) -> dict[str, Any]:
        prompt = self._prompts.get(prompt_key) or self._fallback_prompts().get(prompt_key)
        if prompt is None:
            raise PromptError(f"Prompt not found: {prompt_key}")
        if not prompt.get("enabled", True):
            raise PromptError(f"Prompt is disabled: {prompt_key}")
        return deepcopy(prompt)

    def render_prompt(self, prompt_key: str, variables: dict[str, Any]) -> RenderedPrompt:
        prompt = self.get_prompt(prompt_key)
        self.validate_prompt(prompt_key)
        declared = set(prompt.get("variables") or [])
        required = set(_template_variables(str(prompt.get("system") or ""))) | set(_template_variables(str(prompt.get("user") or "")))
        missing = sorted((required | declared) - set(variables.keys()))
        if missing:
            raise PromptError(f"Missing prompt variables for {prompt_key}: {', '.join(missing)}")
        rendered_system = _render_template(str(prompt.get("system") or ""), variables)
        rendered_user = _render_template(str(prompt.get("user") or ""), variables)
        return RenderedPrompt(
            prompt_key=prompt_key,
            prompt_version=str(prompt["version"]),
            system=rendered_system,
            user=rendered_user,
            metadata=self._public_prompt(prompt),
        )

    def list_prompts(self) -> list[dict[str, Any]]:
        return [self._public_prompt(prompt) for prompt in sorted(self._prompts.values(), key=lambda item: item["key"])]

    def validate_prompt(self, prompt_key: str) -> None:
        prompt = self.get_prompt(prompt_key)
        for field in ["key", "name", "version", "enabled", "variables", "system", "user"]:
            if field not in prompt:
                raise PromptError(f"Prompt {prompt_key} missing required field: {field}")
        if not isinstance(prompt["variables"], list):
            raise PromptError(f"Prompt {prompt_key} variables must be a list.")
        if str(prompt.get("output_format") or "json") not in {"json", "text"}:
            raise PromptError(f"Prompt {prompt_key} output_format must be json or text.")

    def _load_from_files(self) -> dict[str, dict[str, Any]]:
        if not self.registry_path.exists():
            return self._fallback_prompts()
        registry_doc = yaml.safe_load(self.registry_path.read_text(encoding="utf-8")) or {}
        registry = registry_doc.get("registry") or {}
        prompts: dict[str, dict[str, Any]] = {}
        disabled_keys: set[str] = set()
        for registry_key, entry in registry.items():
            if not entry.get("enabled", True):
                disabled_keys.add(str(registry_key))
                continue
            file_path = self.root / str(entry["file"])
            doc = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
            candidates = {item.get("key"): item for item in doc.get("prompts") or []}
            prompt = candidates.get(entry.get("key"))
            if prompt is None:
                raise PromptError(f"Prompt {entry.get('key')} not found in {entry.get('file')}")
            prompt = dict(prompt)
            prompt["file"] = str(entry["file"])
            prompt["enabled"] = bool(prompt.get("enabled", True) and entry.get("enabled", True))
            prompt["version"] = str(prompt.get("version") or entry.get("version") or "")
            if not prompt["version"]:
                raise PromptError(f"Prompt {registry_key} version is required.")
            prompts[str(registry_key)] = prompt
        for key, fallback in self._fallback_prompts().items():
            if key not in disabled_keys:
                prompts.setdefault(key, fallback)
        return prompts

    def _fallback_prompts(self) -> dict[str, dict[str, Any]]:
        return {key: dict(value) for key, value in DEFAULT_PROMPTS.items()}

    def _public_prompt(self, prompt: dict[str, Any]) -> dict[str, Any]:
        return {
            "key": prompt.get("key"),
            "name": prompt.get("name"),
            "version": prompt.get("version"),
            "enabled": bool(prompt.get("enabled", True)),
            "model_profile": prompt.get("model_profile", "default"),
            "temperature": prompt.get("temperature"),
            "max_tokens": prompt.get("max_tokens"),
            "output_format": prompt.get("output_format", "json"),
            "description": prompt.get("description"),
            "variables": prompt.get("variables") or [],
            "file": prompt.get("file"),
            "system": prompt.get("system"),
            "user": prompt.get("user"),
            "examples": prompt.get("examples") or [],
        }


_PROMPT_MANAGER: PromptManager | None = None


def get_prompt_manager() -> PromptManager:
    global _PROMPT_MANAGER
    if _PROMPT_MANAGER is None:
        _PROMPT_MANAGER = PromptManager()
    return _PROMPT_MANAGER


def render_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _template_variables(template: str) -> list[str]:
    return [match.strip() for match in re.findall(r"{{\s*([a-zA-Z0-9_]+)\s*}}", template)]


def _render_template(template: str, variables: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        value = variables[key]
        return value if isinstance(value, str) else render_json(value)

    return re.sub(r"{{\s*([a-zA-Z0-9_]+)\s*}}", replace, template)
