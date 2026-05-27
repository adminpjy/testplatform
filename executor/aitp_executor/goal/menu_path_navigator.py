import re
from dataclasses import dataclass, field
from typing import Any, Callable

from playwright.sync_api import Error as PlaywrightError

from executor.aitp_executor.locator.llm_element_resolver import LLMElementResolver
from executor.aitp_executor.locator.vision_resolver import VisionResolver
from executor.aitp_executor.observer.page_observer import PageObserver
from executor.aitp_executor.runner.page_waiter import wait_for_page_ready


RuntimeEmitter = Callable[[str, str, str, str, dict[str, Any]], None]
DebugWriter = Callable[[dict[str, Any]], None]


@dataclass
class NavigationResult:
    status: str
    pathSegments: list[str]
    attemptedStrategies: list[dict[str, Any]] = field(default_factory=list)
    clickedElements: list[dict[str, Any]] = field(default_factory=list)
    successEvidence: list[str] = field(default_factory=list)
    failureType: str | None = None
    reason: str = ""
    visionFallback: str | None = None

    def as_outcome(self) -> dict[str, Any]:
        return {
            "locator_strategy": "navigation_path",
            "element_ref": self.pathSegments[-1] if self.pathSegments else None,
            "confidence": 0.92 if self.status == "passed" else 0.25,
            "reason": self.reason,
            "needs_vision_fallback": False,
            "fallback_reason": self.failureType,
            "failure_type": self.failureType,
            "candidates": self.attemptedStrategies,
            "navigation_result": {
                "status": self.status,
                "pathSegments": self.pathSegments,
                "attemptedStrategies": self.attemptedStrategies,
                "clickedElements": self.clickedElements,
                "successEvidence": self.successEvidence,
                "failureType": self.failureType,
                "reason": self.reason,
                "visionFallback": self.visionFallback,
            },
        }


class NavigationPathError(RuntimeError):
    def __init__(self, result: NavigationResult) -> None:
        super().__init__(f"{result.failureType or 'navigation_path_unresolved'}: {result.reason}")
        self.failure_type = result.failureType or "navigation_path_unresolved"
        self.fallback_reason = self.failure_type
        self.details = result.as_outcome()


class MenuPathNavigator:
    def __init__(
        self,
        *,
        observer: PageObserver | None = None,
        llm_resolver: LLMElementResolver | None = None,
        vision_resolver: VisionResolver | None = None,
    ) -> None:
        self.observer = observer or PageObserver()
        self.llm_resolver = llm_resolver or LLMElementResolver()
        self.vision_resolver = vision_resolver or VisionResolver(configured=False)

    def navigate_path(
        self,
        page: Any,
        target: str,
        path_segments: list[str],
        execution_context: dict[str, Any] | None = None,
    ) -> NavigationResult:
        context = execution_context or {}
        emit = context.get("emit_runtime") or _noop_emit
        debug = context.get("append_debug") or _noop_debug
        step_id = context.get("step_id")
        vision_requested = bool(context.get("vision_requested"))
        parent = path_segments[0] if path_segments else ""
        leaf = path_segments[-1] if path_segments else target

        emit(
            "progress",
            "navigation_path",
            f"检测到目标“{target}”是菜单路径。",
            "menu_path_navigator",
            {"step_id": step_id, "target": target, "pathSegments": path_segments},
        )
        emit(
            "progress",
            "navigation_path",
            f"已拆分路径：{' → '.join(path_segments)}。",
            "menu_path_navigator",
            {"step_id": step_id, "target": target, "pathSegments": path_segments, "parent": parent, "leaf": leaf},
        )
        debug(
            {
                "stepId": step_id,
                "phase": "navigation_path_detected",
                "target": target,
                "pathSegments": path_segments,
            }
        )

        result = NavigationResult(status="failed", pathSegments=path_segments)
        wait_for_page_ready(page)

        if self._already_on_target_page(page, path_segments, result, emit, debug, step_id):
            return self._pass(result, "already_on_target_page", "当前页面已经是目标页面。", emit, step_id)

        for strategy in [
            self._left_menu_path,
            self._top_nav_path,
            self._dashboard_card,
            self._menu_search,
            self._iframe_menu,
            self._llm_disambiguation,
        ]:
            strategy_name = strategy.__name__.lstrip("_")
            if strategy(page, path_segments, result, emit, debug, step_id):
                if self._verify_goal(page, path_segments, result):
                    return self._pass(result, strategy_name, "菜单路径导航完成。", emit, step_id)
                result.failureType = "navigation_goal_not_reached"
                result.reason = f"已点击“{leaf}”，但没有检测到目标页面证据。"
                debug(
                    {
                        "stepId": step_id,
                        "phase": "navigation_failure",
                        "failureType": result.failureType,
                        "strategy": strategy_name,
                        "visionFallback": result.visionFallback,
                    }
                )
                return self._fail(result, emit, step_id)

        if vision_requested:
            vision = self.vision_resolver.resolve(page=page, target=target, action="navigate_menu")
            result.visionFallback = "not_configured" if vision.status == "vision_fallback_not_configured" else vision.status
            result.attemptedStrategies.append(
                {
                    "strategy": "vision_fallback_optional",
                    "status": vision.status,
                    "overlayScreenshotPath": vision.overlay_screenshot_path,
                }
            )
            emit(
                "warning",
                "navigation_path",
                "视觉兜底未完成，但这不是菜单路径导航的主失败原因。",
                "menu_path_navigator",
                {
                    "step_id": step_id,
                    "target": target,
                    "visionFallback": result.visionFallback,
                    "overlayScreenshotPath": vision.overlay_screenshot_path,
                },
            )
        else:
            result.visionFallback = "not_requested"

        result.failureType = _prefer_failure_type(result)
        result.reason = result.reason or "无法完成菜单路径导航。"
        debug(
            {
                "stepId": step_id,
                "phase": "navigation_failure",
                "failureType": result.failureType,
                "visionFallback": result.visionFallback,
            }
        )
        return self._fail(result, emit, step_id)

    def _already_on_target_page(
        self,
        page: Any,
        path_segments: list[str],
        result: NavigationResult,
        emit: RuntimeEmitter,
        debug: DebugWriter,
        step_id: Any,
    ) -> bool:
        leaf = path_segments[-1]
        emit(
            "progress",
            "navigation_path",
            f"正在检查当前页面是否已经是“{leaf}”。",
            "menu_path_navigator",
            {"step_id": step_id, "leaf": leaf},
        )
        evidence = _target_evidence(page, path_segments)
        result.attemptedStrategies.append({"strategy": "already_on_target_page", "evidence": evidence})
        debug({"stepId": step_id, "phase": "menu_path_attempt", "strategy": "already_on_target_page", "evidence": evidence})
        if evidence:
            result.successEvidence.extend(evidence)
            return True
        return False

    def _left_menu_path(
        self,
        page: Any,
        path_segments: list[str],
        result: NavigationResult,
        emit: RuntimeEmitter,
        debug: DebugWriter,
        step_id: Any,
    ) -> bool:
        parent, leaf = path_segments[0], path_segments[-1]
        emit("progress", "navigation_path", f"正在查找一级菜单“{parent}”。", "menu_path_navigator", {"step_id": step_id})
        scope = _first_visible(page, ["aside", ".sidebar", ".side-menu", ".ant-layout-sider", ".el-aside", "[role='menu']", ".ant-menu", ".el-menu"])
        attempt = {"strategy": "left_menu_path", "parent": parent, "child": leaf, "parentFound": False, "expanded": False, "childFound": False}
        if scope is None:
            result.attemptedStrategies.append(attempt)
            debug({"stepId": step_id, "phase": "menu_path_attempt", **attempt})
            return False

        parent_locator = _find_text(scope, parent)
        if parent_locator is None:
            result.failureType = result.failureType or "menu_parent_not_found"
            result.reason = result.reason or f"未找到一级菜单“{parent}”。"
            result.attemptedStrategies.append(attempt)
            debug({"stepId": step_id, "phase": "menu_path_attempt", **attempt})
            return False
        attempt["parentFound"] = True
        emit("success", "navigation_path", f"已找到“{parent}”，正在展开。", "menu_path_navigator", {"step_id": step_id})
        child_locator = _find_text(scope, leaf)
        if child_locator is None:
            if not _click(parent_locator):
                result.failureType = "menu_expand_failed"
                result.reason = f"找到一级菜单“{parent}”，但展开失败。"
                result.attemptedStrategies.append(attempt)
                debug({"stepId": step_id, "phase": "menu_path_attempt", **attempt})
                return False
            attempt["expanded"] = True
            result.clickedElements.append({"strategy": "left_menu_path", "text": parent, "role": "parent"})
            wait_for_page_ready(page, settle_ms=300)
            child_locator = _find_text(scope, leaf)
        else:
            attempt["expanded"] = True

        emit("progress", "navigation_path", f"正在查找二级菜单“{leaf}”。", "menu_path_navigator", {"step_id": step_id})
        if child_locator is None:
            result.failureType = result.failureType or "menu_child_not_found"
            result.reason = result.reason or f"找到“{parent}”，但未找到“{leaf}”。"
            result.attemptedStrategies.append(attempt)
            debug({"stepId": step_id, "phase": "menu_path_attempt", **attempt})
            return False
        attempt["childFound"] = True
        result.attemptedStrategies.append(attempt)
        debug({"stepId": step_id, "phase": "menu_path_attempt", **attempt})
        emit("progress", "navigation_path", f"正在点击“{leaf}”。", "menu_path_navigator", {"step_id": step_id})
        before = _page_fingerprint(page)
        if not _click(child_locator):
            result.failureType = "menu_click_no_effect"
            result.reason = f"找到“{leaf}”，但点击失败。"
            return False
        result.clickedElements.append({"strategy": "left_menu_path", "text": leaf, "role": "child"})
        wait_for_page_ready(page)
        if before == _page_fingerprint(page) and not _target_evidence(page, path_segments):
            result.failureType = "menu_click_no_effect"
            result.reason = f"点击“{leaf}”后页面没有明显变化。"
            return False
        return True

    def _top_nav_path(self, page: Any, path_segments: list[str], result: NavigationResult, emit: RuntimeEmitter, debug: DebugWriter, step_id: Any) -> bool:
        parent, leaf = path_segments[0], path_segments[-1]
        scope = _first_visible(page, ["header", ".top-nav", ".navbar", "nav", ".ant-menu-horizontal"])
        attempt = {"strategy": "top_nav_path", "parent": parent, "child": leaf, "parentFound": False, "childFound": False}
        if scope is None:
            result.attemptedStrategies.append(attempt)
            return False
        parent_locator = _find_text(scope, parent)
        if parent_locator is None:
            result.attemptedStrategies.append(attempt)
            debug({"stepId": step_id, "phase": "menu_path_attempt", **attempt})
            return False
        attempt["parentFound"] = True
        emit("progress", "navigation_path", f"正在从顶部导航打开“{parent}”。", "menu_path_navigator", {"step_id": step_id})
        _click(parent_locator)
        wait_for_page_ready(page, settle_ms=300)
        child_locator = _find_text(page.locator("body"), leaf)
        if child_locator is None:
            result.attemptedStrategies.append(attempt)
            debug({"stepId": step_id, "phase": "menu_path_attempt", **attempt})
            return False
        attempt["childFound"] = True
        result.attemptedStrategies.append(attempt)
        debug({"stepId": step_id, "phase": "menu_path_attempt", **attempt})
        _click(child_locator)
        wait_for_page_ready(page)
        result.clickedElements.append({"strategy": "top_nav_path", "text": leaf, "role": "child"})
        return True

    def _dashboard_card(self, page: Any, path_segments: list[str], result: NavigationResult, emit: RuntimeEmitter, debug: DebugWriter, step_id: Any) -> bool:
        leaf = path_segments[-1]
        emit("progress", "navigation_path", f"正在查找“{leaf}”首页卡片或快捷入口。", "menu_path_navigator", {"step_id": step_id})
        scope = _first_visible(page, ["main", ".dashboard", ".workbench", ".content", ".ant-layout-content", ".el-main", "body"])
        attempt = {"strategy": "dashboard_card", "leaf": leaf, "found": False}
        if scope is None:
            result.attemptedStrategies.append(attempt)
            return False
        locator = _find_text(scope, leaf)
        if locator is None:
            result.attemptedStrategies.append(attempt)
            debug({"stepId": step_id, "phase": "menu_path_attempt", **attempt})
            return False
        attempt["found"] = True
        result.attemptedStrategies.append(attempt)
        debug({"stepId": step_id, "phase": "menu_path_attempt", **attempt})
        _click(locator)
        wait_for_page_ready(page)
        result.clickedElements.append({"strategy": "dashboard_card", "text": leaf})
        return True

    def _menu_search(self, page: Any, path_segments: list[str], result: NavigationResult, emit: RuntimeEmitter, debug: DebugWriter, step_id: Any) -> bool:
        leaf = path_segments[-1]
        attempt = {"strategy": "menu_search", "leaf": leaf, "searchFound": False, "resultFound": False}
        search = _first_visible(
            page,
            [
                "input[placeholder*='菜单']",
                "input[placeholder*='搜索']",
                "input[aria-label*='菜单']",
                "input[aria-label*='搜索']",
                ".menu-search input",
                ".ant-select-selection-search-input",
            ],
        )
        if search is None:
            result.attemptedStrategies.append(attempt)
            return False
        attempt["searchFound"] = True
        emit("progress", "navigation_path", f"正在通过菜单搜索查找“{leaf}”。", "menu_path_navigator", {"step_id": step_id})
        try:
            search.fill(leaf)
        except PlaywrightError:
            try:
                search.click()
                search.type(leaf)
            except PlaywrightError:
                result.attemptedStrategies.append(attempt)
                return False
        wait_for_page_ready(page, settle_ms=500)
        result_locator = _find_text(page.locator("body"), leaf)
        if result_locator is None:
            result.attemptedStrategies.append(attempt)
            debug({"stepId": step_id, "phase": "menu_path_attempt", **attempt})
            return False
        attempt["resultFound"] = True
        result.attemptedStrategies.append(attempt)
        debug({"stepId": step_id, "phase": "menu_path_attempt", **attempt})
        _click(result_locator)
        wait_for_page_ready(page)
        result.clickedElements.append({"strategy": "menu_search", "text": leaf})
        return True

    def _iframe_menu(self, page: Any, path_segments: list[str], result: NavigationResult, emit: RuntimeEmitter, debug: DebugWriter, step_id: Any) -> bool:
        parent, leaf = path_segments[0], path_segments[-1]
        for frame_index, frame in enumerate(page.frames):
            if frame == page.main_frame:
                continue
            attempt = {"strategy": "iframe_menu", "frameIndex": frame_index, "parent": parent, "child": leaf, "parentFound": False, "childFound": False}
            try:
                scope = _first_visible(frame, ["aside", ".sidebar", "[role='menu']", ".ant-menu", ".el-menu", "body"])
                if scope is None:
                    result.attemptedStrategies.append(attempt)
                    continue
                parent_locator = _find_text(scope, parent)
                if parent_locator is None:
                    result.attemptedStrategies.append(attempt)
                    continue
                attempt["parentFound"] = True
                _click(parent_locator)
                wait_for_page_ready(page, settle_ms=300)
                child_locator = _find_text(scope, leaf)
                if child_locator is None:
                    result.attemptedStrategies.append(attempt)
                    debug({"stepId": step_id, "phase": "menu_path_attempt", **attempt})
                    continue
                attempt["childFound"] = True
                result.attemptedStrategies.append(attempt)
                debug({"stepId": step_id, "phase": "menu_path_attempt", **attempt})
                _click(child_locator)
                wait_for_page_ready(page)
                result.clickedElements.append({"strategy": "iframe_menu", "text": leaf, "frameIndex": frame_index})
                return True
            except PlaywrightError:
                result.attemptedStrategies.append(attempt)
        return False

    def _llm_disambiguation(self, page: Any, path_segments: list[str], result: NavigationResult, emit: RuntimeEmitter, debug: DebugWriter, step_id: Any) -> bool:
        leaf = path_segments[-1]
        observation = self.observer.observe(page)
        candidates = [
            {
                "selector": item.get("selector"),
                "text": item.get("text"),
                "area": item.get("area"),
                "parentText": item.get("parentText"),
            }
            for item in observation.menus
            if _similar_menu_text(str(item.get("text") or ""), leaf)
        ][:8]
        attempt = {"strategy": "llm_disambiguation", "leaf": leaf, "candidateCount": len(candidates), "selected": None}
        if len(candidates) < 2:
            result.attemptedStrategies.append(attempt)
            return False
        emit("progress", "navigation_path", "存在多个相似菜单，正在结合上下文判断。", "menu_path_navigator", {"step_id": step_id, "leaf": leaf})
        llm_result = self.llm_resolver.resolve(
            page_context={
                "url": observation.url,
                "title": observation.title,
                "visible_text": observation.visible_text[:1800],
                "candidates": candidates,
            },
            target=leaf,
            action="navigate_menu",
        )
        attempt["selected"] = llm_result.selector
        attempt["status"] = llm_result.status
        result.attemptedStrategies.append(attempt)
        debug({"stepId": step_id, "phase": "menu_path_attempt", **attempt})
        if not llm_result.selector:
            return False
        locator = page.locator(llm_result.selector)
        if locator.count() == 0:
            return False
        _click(locator.first)
        wait_for_page_ready(page)
        result.clickedElements.append({"strategy": "llm_disambiguation", "selector": llm_result.selector})
        return True

    def _verify_goal(self, page: Any, path_segments: list[str], result: NavigationResult) -> bool:
        evidence = _target_evidence(page, path_segments)
        if evidence:
            result.successEvidence.extend(item for item in evidence if item not in result.successEvidence)
            return True
        return False

    def _pass(self, result: NavigationResult, strategy: str, reason: str, emit: RuntimeEmitter, step_id: Any) -> NavigationResult:
        result.status = "passed"
        result.failureType = None
        result.reason = reason
        result.attemptedStrategies.append({"strategy": strategy, "status": "passed", "successEvidence": result.successEvidence})
        emit(
            "success",
            "navigation_path",
            "菜单路径导航完成。",
            "menu_path_navigator",
            {"step_id": step_id, "pathSegments": result.pathSegments, "successEvidence": result.successEvidence},
        )
        return result

    def _fail(self, result: NavigationResult, emit: RuntimeEmitter, step_id: Any) -> NavigationResult:
        result.status = "failed"
        result.failureType = result.failureType or "navigation_path_unresolved"
        emit(
            "error",
            "navigation_path",
            result.reason or "无法完成菜单路径导航。",
            "menu_path_navigator",
            {"step_id": step_id, "failureType": result.failureType, "visionFallback": result.visionFallback},
        )
        return result


def _target_evidence(page: Any, path_segments: list[str]) -> list[str]:
    leaf = path_segments[-1]
    parents = path_segments[:-1]
    evidence: list[str] = []
    try:
        title = page.title()
        if leaf and leaf in title:
            evidence.append("title_contains_leaf")
    except PlaywrightError:
        pass
    for selector, label in [
        ("h1, h2, h3, .page-title, .header-title, .ant-page-header-heading-title, .el-page-header__content", "page_heading_contains_leaf"),
        (".ant-breadcrumb, .el-breadcrumb, .breadcrumb, [aria-label*='breadcrumb' i]", "breadcrumb_contains_path"),
        (".ant-menu-item-selected, .el-menu-item.is-active, .active, [aria-current='page']", "active_menu_contains_leaf"),
    ]:
        try:
            locator = page.locator(selector)
            for index in range(min(locator.count(), 8)):
                text = locator.nth(index).inner_text(timeout=800)
                if leaf in text and (label != "breadcrumb_contains_path" or all(parent in text for parent in parents)):
                    evidence.append(label)
                    break
        except PlaywrightError:
            continue
    try:
        body_text = page.locator("body").inner_text(timeout=1000)
        if leaf in body_text and any(signal in body_text for signal in ["待办列表", "待办任务", "待办事项", "申请编号", "操作"]):
            evidence.append("todo_list_signal")
    except PlaywrightError:
        pass
    try:
        url = page.url.lower()
        if any(token in url for token in ["todo", "task", "workbench", "pending"]):
            evidence.append("url_auxiliary_signal")
    except PlaywrightError:
        pass
    strong = [item for item in evidence if item != "url_auxiliary_signal"]
    if strong:
        return evidence
    return evidence if len(evidence) >= 2 else []


def _first_visible(root: Any, selectors: list[str]) -> Any | None:
    for selector in selectors:
        try:
            locator = root.locator(selector)
            count = locator.count()
            for index in range(min(count, 8)):
                item = locator.nth(index)
                if item.is_visible(timeout=500):
                    return item
        except PlaywrightError:
            continue
    return None


def _find_text(scope: Any, text: str) -> Any | None:
    escaped = re.escape(text)
    patterns = [
        lambda: scope.get_by_role("menuitem", name=re.compile(f"^{escaped}$")),
        lambda: scope.get_by_role("button", name=re.compile(f"^{escaped}$")),
        lambda: scope.get_by_role("link", name=re.compile(f"^{escaped}$")),
        lambda: scope.get_by_role("tab", name=re.compile(f"^{escaped}$")),
        lambda: scope.get_by_text(text, exact=True),
        lambda: scope.get_by_text(text, exact=False),
    ]
    for factory in patterns:
        try:
            locator = factory()
            count = locator.count()
            for index in range(min(count, 8)):
                item = locator.nth(index)
                if item.is_visible(timeout=500):
                    return item
        except PlaywrightError:
            continue
    return None


def _click(locator: Any) -> bool:
    try:
        locator.click(timeout=3_000)
        return True
    except PlaywrightError:
        try:
            locator.click(timeout=3_000, force=True)
            return True
        except PlaywrightError:
            return False


def _page_fingerprint(page: Any) -> str:
    try:
        body = page.locator("body").inner_text(timeout=1000)[:500]
    except PlaywrightError:
        body = ""
    return f"{page.url}|{body}"


def _prefer_failure_type(result: NavigationResult) -> str:
    for item in result.attemptedStrategies:
        if item.get("strategy") == "left_menu_path" and item.get("parentFound") and not item.get("childFound"):
            return "menu_child_not_found"
    for item in result.attemptedStrategies:
        if item.get("strategy") == "left_menu_path" and not item.get("parentFound"):
            return "menu_parent_not_found"
    return result.failureType or "navigation_path_unresolved"


def _similar_menu_text(text: str, leaf: str) -> bool:
    if not text or not leaf:
        return False
    return leaf in text or text in leaf or any(token and token in text for token in re.split(r"\s+", leaf))


def _noop_emit(_message_type: str, _phase: str, _content: str, _method: str, _metadata: dict[str, Any]) -> None:
    return None


def _noop_debug(_event: dict[str, Any]) -> None:
    return None
