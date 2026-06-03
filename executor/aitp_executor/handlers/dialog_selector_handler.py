from typing import Any

from playwright.sync_api import Error as PlaywrightError

from executor.aitp_executor.handlers.base import CommonOperationHandler, handler_outcome


class DialogSelectorHandler(CommonOperationHandler):
    handler_name = "dialog_selector_handler"
    rule_types = ["dialog_selector", "global_interruption"]
    default_intent = "select_from_dialog"

    def wait_for_dialog(self, page: Any, *, step: dict[str, Any] | None = None, dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None, timeout_ms: int = 5_000) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        self.emit_rule_hits(ctx, self.resolve_rules(ctx, intent="select_from_dialog", rule_types=self.rule_types))
        self.emit(ctx, "progress", "dialog_selector", "正在等待弹窗出现。")
        if not self.dialog_visible(page, timeout_ms=timeout_ms):
            raise AssertionError("dialog_not_found: 未检测到弹窗。")
        return handler_outcome("dialog_visible", "dialog", 0.88, "dialog visible")

    def close_by_common_controls(self, page: Any, *, step: dict[str, Any] | None = None, dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        self.emit_rule_hits(ctx, self.resolve_rules(ctx, intent="handle_dialog", rule_types=["global_interruption", "dialog_handler", "dialog_selector"]))
        self.emit(ctx, "progress", "dialog_selector", "正在关闭当前弹窗。")
        if not self.close(page):
            raise AssertionError("dialog_not_found: 未找到可用的关闭按钮。")
        return handler_outcome("dialog_closed", "common_controls", 0.82, "dialog closed")

    def select_from_dialog(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        value = str(step.get("value") or step.get("target") or "")
        self.emit_rule_hits(ctx, self.resolve_rules(ctx, intent="select_from_dialog", rule_types=["dialog_selector"]))
        self.emit(ctx, "progress", "dialog_selector", f"正在弹窗中选择：{value}。")
        selector_button = page.get_by_role("button", name="选择", exact=False)
        if selector_button.count() > 0:
            selector_button.first.click()
        self.dialog_visible(page, timeout_ms=3_000)
        if value:
            row = page.get_by_text(value, exact=False)
            if row.count() > 0:
                row.first.click()
        self._confirm(page)
        return handler_outcome("dialog_selector", value, 0.76, "dialog selection completed")

    def dialog_visible(self, page: Any, *, timeout_ms: int = 5_000) -> bool:
        selectors = ["[role='dialog']", "[aria-modal='true']", ".ant-modal", ".el-dialog", ".modal", ".drawer", ".ant-drawer", ".el-drawer"]
        for selector in selectors:
            try:
                locator = page.locator(selector)
                if self._any_visible(locator, timeout_ms=timeout_ms):
                    return True
            except PlaywrightError:
                continue
        return False

    def close(self, page: Any) -> bool:
        for name in ["返回", "取消", "关闭", "确定", "我知道了"]:
            try:
                button = page.get_by_role("button", name=name, exact=True)
                if button.count() > 0:
                    button.first.click()
                    page.wait_for_timeout(300)
                    return True
                text = page.get_by_text(name, exact=True)
                if text.count() == 1:
                    text.first.click()
                    page.wait_for_timeout(300)
                    return True
            except PlaywrightError:
                continue
        for selector in [".ant-modal-close", ".el-dialog__headerbtn", ".modal .close", "[aria-label='Close']", "[aria-label='关闭']", "[title='关闭']"]:
            try:
                candidate = page.locator(selector)
                visible = self._first_visible(candidate, timeout_ms=300)
                if visible is not None:
                    visible.click()
                    page.wait_for_timeout(300)
                    return True
            except PlaywrightError:
                continue
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
            return True
        except PlaywrightError:
            return False

    def _confirm(self, page: Any) -> None:
        for name in ["确定", "确认", "提交"]:
            try:
                button = page.get_by_role("button", name=name, exact=True)
                if button.count() > 0:
                    button.first.click()
                    page.wait_for_timeout(300)
                    return
            except PlaywrightError:
                continue

    def _any_visible(self, locator: Any, *, timeout_ms: int, limit: int = 12) -> bool:
        return self._first_visible(locator, timeout_ms=timeout_ms, limit=limit) is not None

    def _first_visible(self, locator: Any, *, timeout_ms: int, limit: int = 12) -> Any | None:
        try:
            count = min(locator.count(), limit)
        except PlaywrightError:
            return None
        for index in range(count):
            try:
                item = locator.nth(index)
                if item.is_visible(timeout=timeout_ms):
                    return item
            except PlaywrightError:
                continue
        return None
