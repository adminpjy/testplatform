from typing import Any

from executor.aitp_executor.goal.menu_path_navigator import MenuPathNavigator, NavigationPathError
from executor.aitp_executor.handlers.base import CommonOperationHandler, handler_outcome, locator_outcome, path_segments, require_locator
from executor.aitp_executor.locator.element_locator import ElementLocator
from executor.aitp_executor.runner.page_waiter import wait_for_page_ready


class NavigationHandler(CommonOperationHandler):
    handler_name = "navigation_handler"
    rule_types = ["navigation"]
    default_intent = "navigate_path"

    def __init__(self, *, locator: ElementLocator | None = None, menu_path_navigator: MenuPathNavigator | None = None) -> None:
        super().__init__()
        self.locator = locator or ElementLocator()
        self.menu_path_navigator = menu_path_navigator or MenuPathNavigator()

    def execute(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        target = str(step.get("target") or "")
        segments = path_segments(step.get("pathSegments") or target)
        intent = "navigate_path" if segments else "enter_page"
        resolution = self.resolve_rules(ctx, intent=intent, rule_types=["navigation"])
        self.emit_rule_hits(ctx, resolution)
        self.emit(ctx, "progress", "navigation", "正在执行菜单导航。" if segments else "正在进入目标页面。")
        if segments:
            result = self.menu_path_navigator.navigate_path(page, target or "/".join(segments), segments, execution_context=execution_context)
            if result.status != "passed":
                raise NavigationPathError(result)
            self.debug(ctx, {"strategy": "menu_path", "target": target, "pathSegments": segments, "result": result.as_outcome().get("navigation_result")})
            return result.as_outcome()
        result = self.locator.locate(page, action="navigate_menu", target=target, step=step)
        require_locator(result).click()
        wait_for_page_ready(page)
        self.debug(ctx, {"strategy": "navigate_menu_locator", "target": target, "locatorStrategy": result.strategy})
        return locator_outcome(result)

    def dashboard_card(self, page: Any, *, target: str, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        self.emit(ctx, "progress", "navigation", f"正在查找快捷入口：{target}。")
        locator = page.get_by_text(target, exact=True)
        if locator.count() == 0:
            raise RuntimeError(f"navigation_path_unresolved: 未找到快捷入口“{target}”。")
        locator.first.click()
        wait_for_page_ready(page)
        return handler_outcome("dashboard_card", target, 0.82, "dashboard card clicked")
