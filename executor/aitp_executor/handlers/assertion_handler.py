from typing import Any

from executor.aitp_executor.handlers.base import CommonOperationHandler, handler_outcome


class AssertionHandler(CommonOperationHandler):
    handler_name = "assertion_handler"
    rule_types = ["assertion"]
    default_intent = "assert_result"

    def assert_step(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        self.emit_rule_hits(ctx, self.resolve_rules(ctx, intent="assert_result", rule_types=self.rule_types))
        action = str(step.get("action") or "")
        target = str(step.get("target") or "")
        assertion_text = str(step.get("text") or target)
        self.emit(ctx, "progress", "assertion", "正在验证执行结果。", metadata={"action": action, "target": target, "text": assertion_text})
        if action in {"wait_for_text", "assert_text_exists"}:
            page.get_by_text(assertion_text, exact=False).wait_for(state="visible")
            return handler_outcome("text_visible", assertion_text, 1.0, "text visible")
        if action == "assert_text_not_exists":
            count = page.get_by_text(target, exact=False).count()
            if count > 0:
                raise AssertionError(f"assertion_not_met: 文本不应存在：{target}")
            return handler_outcome("text_absent", target, 1.0, "text absent")
        if action == "assert_url_contains":
            current_url = page.url
            if target not in current_url:
                raise AssertionError(f"assertion_not_met: URL 不包含 {target}: {current_url}")
            return handler_outcome("url_contains", target, 1.0, "url contains target")
        return handler_outcome("summary_assert", target or "summary", 0.9, "summary assertion recorded")
