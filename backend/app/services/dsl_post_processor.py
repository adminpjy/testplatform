import re
from typing import Any


PATH_SEPARATORS_PATTERN = r"\s*(?:/|>|-|→|\\)\s*"


class DslPostProcessor:
    def normalize_dsl(self, dsl: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(dsl)
        normalized["steps"] = [self.normalize_step(step) for step in normalized.get("steps") or [] if isinstance(step, dict)]
        return normalized

    def normalize_step(self, step: dict[str, Any]) -> dict[str, Any]:
        current = dict(step)
        action = str(current.get("action") or "")
        target = str(current.get("target") or "")

        if action == "navigate_path":
            segments = _path_segments(current.get("pathSegments") or current.get("path_segments") or target)
            if len(segments) >= 2:
                current["pathSegments"] = segments
                current["navigationType"] = current.get("navigationType") or "menu_path"
                _ensure_navigation_defaults(current, segments)
            return current

        if action in {"business_goal", "navigate_menu", "click"}:
            segments = _path_segments(target)
            if len(segments) >= 2:
                current["originalAction"] = action
                current["originalTarget"] = target
                current["action"] = "navigate_path"
                current["pathSegments"] = segments
                current["navigationType"] = "menu_path"
                current["normalizedBy"] = "DslPostProcessor"
                current["normalizationReason"] = "target contains menu path separator"
                current["readableDescription"] = f"菜单路径导航：{' → '.join(segments)}"
                _ensure_navigation_defaults(current, segments)
        return current


def normalize_dsl(dsl: dict[str, Any]) -> dict[str, Any]:
    return DslPostProcessor().normalize_dsl(dsl)


def parse_menu_path(target: str) -> list[str]:
    return _path_segments(target)


def _path_segments(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_clean_segment(str(item), index) for index, item in enumerate(value) if _clean_segment(str(item), index)]
    text = str(value or "").strip()
    if not text or "://" in text:
        return []
    if not re.search(r"[/>\-→\\]", text):
        return []
    return [
        cleaned
        for index, segment in enumerate(re.split(PATH_SEPARATORS_PATTERN, text))
        if (cleaned := _clean_segment(segment, index))
    ]


def _clean_segment(segment: str, index: int) -> str:
    cleaned = segment.strip().strip("“”\"'，,。；;：:")
    if index == 0:
        cleaned = re.sub(r"^(进入|打开|点击|导航到|访问|前往|切换到|跳转到)", "", cleaned).strip()
    return cleaned


def _ensure_navigation_defaults(step: dict[str, Any], segments: list[str]) -> None:
    leaf = segments[-1]
    full_path = "/".join(segments)
    step.setdefault(
        "successCriteria",
        [
            f"页面出现{leaf}",
            f"菜单项{leaf}高亮",
            "出现目标列表或目标功能区",
            f"面包屑包含{full_path}",
        ],
    )
    step.setdefault(
        "fallbackStrategies",
        [
            "expand_parent_menu",
            "try_left_menu",
            "try_top_nav",
            "try_dashboard_card",
            "try_menu_search",
            "try_iframe",
            "llm_disambiguation",
            "vision_fallback_optional",
        ],
    )
