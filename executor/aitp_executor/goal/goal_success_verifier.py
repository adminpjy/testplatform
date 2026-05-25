from typing import Any


class GoalSuccessVerifier:
    def verify(self, page: Any, intent_name: str) -> tuple[bool, str]:
        if intent_name == "enter_todo_list":
            ok = "/todo" in page.url or page.get_by_text("待办表格", exact=False).count() > 0
            return ok, "todo_page_verified" if ok else "todo_page_not_verified"
        if intent_name == "approval_pass":
            ok = page.get_by_text("审批成功", exact=False).count() > 0 or page.get_by_text("通过", exact=True).count() > 0
            return ok, "approval_pass_verified" if ok else "approval_pass_not_verified"
        if intent_name == "approval_flow_view":
            ok = page.get_by_text("审批流程", exact=False).count() > 0 or "flow=true" in page.url
            return ok, "approval_flow_verified" if ok else "approval_flow_not_verified"
        return True, "verification_not_required"
