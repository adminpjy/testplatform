import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class BusinessIntent:
    name: str
    normalized_target: str
    preferred_texts: list[str]
    negative_texts: list[str]
    preferred_roles: list[str]
    action_kind: str
    goal_type: str = "business_action"
    path_segments: list[str] = field(default_factory=list)
    leaf: str | None = None
    parents: list[str] = field(default_factory=list)


class BusinessIntentNormalizer:
    def normalize(self, *, action: str, target: str) -> BusinessIntent:
        text = target.strip()
        compact = text.replace(" ", "")
        lower_compact = compact.lower()
        path_segments = parse_navigation_path(action=action, target=text)
        if path_segments:
            return BusinessIntent(
                name="navigation_path",
                normalized_target=path_segments[-1],
                preferred_texts=[path_segments[-1], *path_segments[:-1]],
                negative_texts=[],
                preferred_roles=["button", "link", "menuitem", "tab"],
                action_kind="click",
                goal_type="navigation_path",
                path_segments=path_segments,
                leaf=path_segments[-1],
                parents=path_segments[:-1],
            )

        if _has_any(compact, ["审批通过", "审核通过", "同意申请", "批准"]):
            return BusinessIntent(
                name="approval_pass",
                normalized_target="审批",
                preferred_texts=["审批", "通过", "同意", "确定"],
                negative_texts=["查看审批流程", "审批流程", "流程图", "审批记录", "详情"],
                preferred_roles=["button"],
                action_kind="click",
            )
        if _has_any(compact, ["审批驳回", "驳回"]):
            return BusinessIntent(
                name="approval_reject",
                normalized_target="审批",
                preferred_texts=["审批", "驳回", "确定"],
                negative_texts=["查看审批流程", "审批流程", "流程图", "详情"],
                preferred_roles=["button", "radio"],
                action_kind="click",
            )
        if _has_any(compact, ["查看审批流程", "审批流程", "流程图"]):
            return BusinessIntent(
                name="approval_flow_view",
                normalized_target="查看审批流程",
                preferred_texts=["查看审批流程", "审批流程", "流程图", "审批记录"],
                negative_texts=["审批通过", "审核通过", "批准", "同意申请"],
                preferred_roles=["button", "link"],
                action_kind="click",
            )
        if _has_any(compact, ["工作台/我的待办", "我的待办", "待办事项"]):
            return BusinessIntent(
                name="enter_todo_list",
                normalized_target="我的待办",
                preferred_texts=["我的待办", "待办事项"],
                negative_texts=["待办数量"],
                preferred_roles=["button", "link"],
                action_kind="click",
            )
        if _has_any(compact, ["登录系统", "登录"]) or _has_any(lower_compact, ["login", "signin", "sign in"]):
            return BusinessIntent(
                name="login_system",
                normalized_target="登录",
                preferred_texts=["登录", "用户名", "密码"],
                negative_texts=["退出登录"],
                preferred_roles=["button", "textbox"],
                action_kind="click",
            )
        if _has_any(compact, ["查询记录", "查询", "搜索"]):
            return BusinessIntent(
                name="query_record",
                normalized_target="查询",
                preferred_texts=["查询", "搜索"],
                negative_texts=["重置"],
                preferred_roles=["button"],
                action_kind="click",
            )
        if _has_any(compact, ["新增记录", "新增", "新建"]):
            return BusinessIntent(
                name="create_record",
                normalized_target="新增",
                preferred_texts=["新增", "新建", "添加"],
                negative_texts=[],
                preferred_roles=["button"],
                action_kind="click",
            )
        if _has_any(compact, ["修改记录", "修改", "编辑"]):
            return BusinessIntent(
                name="update_record",
                normalized_target="修改",
                preferred_texts=["修改", "编辑", "保存修改"],
                negative_texts=[],
                preferred_roles=["button"],
                action_kind="click",
            )
        if _has_any(compact, ["删除记录", "删除", "作废"]):
            return BusinessIntent(
                name="delete_record",
                normalized_target="删除",
                preferred_texts=["删除", "作废", "确定"],
                negative_texts=["取消"],
                preferred_roles=["button"],
                action_kind="click",
            )
        if _has_any(compact, ["打开详情", "详情", "申请编号"]):
            return BusinessIntent(
                name="open_detail",
                normalized_target="详情",
                preferred_texts=["详情", "申请编号"],
                negative_texts=["查看审批流程"],
                preferred_roles=["button", "link"],
                action_kind="click",
            )

        kind = "input" if action in {"input", "select", "upload_file"} else "click"
        role = ["textbox", "combobox"] if kind == "input" else ["button", "link"]
        return BusinessIntent(
            name="generic",
            normalized_target=text,
            preferred_texts=[text],
            negative_texts=[],
            preferred_roles=role,
            action_kind=kind,
        )


def _has_any(text: str, options: list[str]) -> bool:
    return any(option in text for option in options)


def parse_navigation_path(*, action: str, target: str) -> list[str]:
    if action not in {"business_goal", "navigate_menu"}:
        return []
    text = target.strip()
    if not text or "://" in text:
        return []
    if not re.search(r"[/>\-→\\]", text):
        return []
    normalized = re.sub(r"\s*(?:/|>|-|→|\\)\s*", "/", text)
    segments = [segment.strip() for segment in normalized.split("/") if segment.strip()]
    return segments if len(segments) >= 2 else []
