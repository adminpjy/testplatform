from typing import Any

from executor.aitp_executor.handlers.base import CommonOperationHandler, handler_outcome
from executor.aitp_executor.runner.page_waiter import wait_for_page_ready


class RecoveryHandler(CommonOperationHandler):
    handler_name = "recovery_handler"
    rule_types = ["recovery_policy"]
    default_intent = "handle_dialog"

    def wait_and_retry(self, page: Any, *, step: dict[str, Any] | None = None, dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None, timeout_ms: int = 1000) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        self.emit_rule_hits(ctx, self.resolve_rules(ctx, intent="handle_dialog", rule_types=self.rule_types))
        self.emit(ctx, "progress", "recovery", "正在等待页面稳定后重试。")
        page.wait_for_timeout(timeout_ms)
        wait_for_page_ready(page)
        return handler_outcome("recovery_wait_and_retry", timeout_ms, 0.7, "waited before retry")

    def reload_page(self, page: Any, *, step: dict[str, Any] | None = None, dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        self.emit_rule_hits(ctx, self.resolve_rules(ctx, intent="handle_dialog", rule_types=self.rule_types))
        self.emit(ctx, "progress", "recovery", "正在重新加载页面。")
        page.reload(wait_until="domcontentloaded")
        wait_for_page_ready(page)
        return handler_outcome("recovery_reload_page", page.url, 0.72, "page reloaded")
