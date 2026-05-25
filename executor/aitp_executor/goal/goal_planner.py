from typing import Any

from executor.aitp_executor.locator.business_intent_normalizer import BusinessIntentNormalizer


class GoalPlanner:
    def __init__(self) -> None:
        self.normalizer = BusinessIntentNormalizer()

    def plan(self, goal: str, step: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        step = step or {}
        intent = self.normalizer.normalize(action="business_goal", target=goal)
        if intent.name == "login_system":
            return [
                {"action": "input", "target": "用户名", "value": step.get("username", "admin")},
                {"action": "input", "target": "密码", "value": step.get("password", "123456")},
                {"action": "click", "target": "登录"},
            ]
        if intent.name == "enter_todo_list":
            return [{"action": "navigate_menu", "target": "工作台/我的待办"}]
        return [{"action": "business_goal", "target": goal}]
