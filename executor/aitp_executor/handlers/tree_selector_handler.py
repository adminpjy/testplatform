from typing import Any

from playwright.sync_api import Error as PlaywrightError

from executor.aitp_executor.handlers.base import CommonOperationHandler, handler_outcome


class TreeSelectorHandler(CommonOperationHandler):
    handler_name = "tree_selector_handler"
    rule_types = ["tree_selector"]
    default_intent = "select_tree_node"

    def select_node(self, page: Any, *, step: dict[str, Any], dsl: dict[str, Any] | None = None, execution_context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self.context(step, dsl, execution_context)
        self.emit_rule_hits(ctx, self.resolve_rules(ctx, intent="select_tree_node", rule_types=self.rule_types))
        value = str(step.get("value") or step.get("target") or "")
        if not value:
            raise RuntimeError("needs_clarification:树节点名称")
        self.emit(ctx, "progress", "tree_selector", f"正在选择树节点：{value}。")
        for selector in [".ant-tree", ".el-tree", "[role='tree']", "body"]:
            try:
                scope = page.locator(selector).first
                if scope.count() == 0:
                    continue
                node = scope.get_by_text(value, exact=False)
                if node.count() > 0:
                    node.first.click()
                    return handler_outcome("tree_selector", value, 0.76, "tree node selected")
            except PlaywrightError:
                continue
        raise RuntimeError(f"tree_node_not_found: {value}")
