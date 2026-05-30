import re
import time
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
    pageTransitions: list[dict[str, Any]] = field(default_factory=list)
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
                "pageTransitions": self.pageTransitions,
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
            self._adaptive_segment_path,
            self._left_menu_path,
            self._top_nav_path,
            self._dashboard_card,
            self._menu_search,
            self._iframe_menu,
            self._llm_disambiguation,
        ]:
            strategy_name = strategy.__name__.lstrip("_")
            if strategy(page, path_segments, result, emit, debug, step_id, context):
                active_page = _active_page(context, page)
                if self._verify_goal(active_page, path_segments, result):
                    return self._pass(result, strategy_name, "菜单路径导航完成。", emit, step_id)
                result.failureType = "navigation_target_not_verified" if result.pageTransitions else "navigation_goal_not_reached"
                result.reason = _target_not_verified_reason(active_page, leaf, result)
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

    def _adaptive_segment_path(
        self,
        page: Any,
        path_segments: list[str],
        result: NavigationResult,
        emit: RuntimeEmitter,
        debug: DebugWriter,
        step_id: Any,
        context: dict[str, Any],
    ) -> bool:
        if len(path_segments) < 3:
            return False

        leaf = path_segments[-1]
        attempt: dict[str, Any] = {"strategy": "adaptive_segment_path", "segments": path_segments, "segmentResults": []}
        result.attemptedStrategies.append(attempt)
        emit(
            "progress",
            "navigation_path",
            f"正在按路径逐级导航：{' → '.join(path_segments)}。",
            "menu_path_navigator",
            {"step_id": step_id, "pathSegments": path_segments},
        )

        for index, segment in enumerate(path_segments):
            next_segment = path_segments[index + 1] if index + 1 < len(path_segments) else ""
            is_leaf = index == len(path_segments) - 1
            if not is_leaf:
                ready_evidence = _segment_transition_evidence(page, segment, next_segment)
                if _segment_transition_reached(ready_evidence, page_changed=False):
                    attempt["segmentResults"].append(
                        {"index": index, "segment": segment, "status": "already_ready", "evidence": ready_evidence}
                    )
                    result.successEvidence.extend(item for item in ready_evidence if item not in result.successEvidence)
                    continue

            locator = _find_text(page.locator("body"), segment)
            if locator is None:
                failure_type = "menu_leaf_not_found" if is_leaf else "menu_segment_not_found"
                result.failureType = result.failureType or failure_type
                result.reason = result.reason or f"未找到路径第 {index + 1} 段“{segment}”。请确认页面是否已进入正确入口，或菜单名称是否有别名。"
                attempt["segmentResults"].append({"index": index, "segment": segment, "status": "not_found"})
                debug({"stepId": step_id, "phase": "menu_path_attempt", **attempt})
                return False

            emit(
                "progress",
                "navigation_path",
                f"正在点击路径第 {index + 1} 段“{segment}”。",
                "menu_path_navigator",
                {"step_id": step_id, "segment": segment, "index": index},
            )
            before = _page_fingerprint(page)
            pages_before = _context_pages(page)
            if not _click(locator):
                failure_type = "menu_leaf_click_failed" if is_leaf else "menu_segment_click_failed"
                result.failureType = failure_type
                result.reason = f"找到路径第 {index + 1} 段“{segment}”，但点击失败。"
                attempt["segmentResults"].append({"index": index, "segment": segment, "status": "click_failed"})
                debug({"stepId": step_id, "phase": "menu_path_attempt", **attempt})
                return False

            result.clickedElements.append({"strategy": "adaptive_segment_path", "text": segment, "index": index, "role": "leaf" if is_leaf else "segment"})
            wait_for_page_ready(page, settle_ms=500)
            after = _page_fingerprint(page)
            page_changed = before != after
            new_page = _new_page_after_click(page, pages_before)

            if is_leaf:
                active_page = _prepare_navigation_target_page(new_page, page, path_segments, result, context, emit, step_id)
                evidence = _target_evidence(active_page, path_segments)
                if new_page is not None:
                    evidence.append("new_page_opened_after_leaf_click")
                if page_changed:
                    evidence.append("page_changed_after_leaf_click")
                target_verified = bool([item for item in evidence if item not in {"new_page_opened_after_leaf_click", "page_changed_after_leaf_click"}])
                if target_verified:
                    result.successEvidence.extend(item for item in evidence if item not in result.successEvidence)
                    attempt["segmentResults"].append({"index": index, "segment": segment, "status": "clicked", "evidence": evidence})
                    debug({"stepId": step_id, "phase": "menu_path_attempt", **attempt})
                    return True
                result.successEvidence.extend(item for item in evidence if item not in result.successEvidence)
                result.failureType = "navigation_target_not_verified" if new_page is not None else "navigation_goal_not_reached"
                result.reason = _target_not_verified_reason(active_page, leaf, result)
                attempt["segmentResults"].append({"index": index, "segment": segment, "status": "clicked_without_goal_evidence"})
                debug({"stepId": step_id, "phase": "menu_path_attempt", **attempt})
                return False

            transition_evidence = _segment_transition_evidence(page, segment, next_segment)
            if _segment_transition_reached(transition_evidence, page_changed=page_changed):
                evidence = transition_evidence or ["page_changed_after_segment_click"]
                result.successEvidence.extend(item for item in evidence if item not in result.successEvidence)
                attempt["segmentResults"].append({"index": index, "segment": segment, "status": "clicked", "evidence": evidence})
                continue

            result.failureType = "menu_segment_not_reached"
            result.reason = f"已点击路径第 {index + 1} 段“{segment}”，但未看到下一段“{next_segment}”，页面也没有明显变化。"
            attempt["segmentResults"].append({"index": index, "segment": segment, "status": "clicked_without_transition", "nextSegment": next_segment})
            debug({"stepId": step_id, "phase": "menu_path_attempt", **attempt})
            return False

        return False

    def _left_menu_path(
        self,
        page: Any,
        path_segments: list[str],
        result: NavigationResult,
        emit: RuntimeEmitter,
        debug: DebugWriter,
        step_id: Any,
        context: dict[str, Any],
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
        pages_before = _context_pages(page)
        if not _click(child_locator):
            result.failureType = "menu_click_no_effect"
            result.reason = f"找到“{leaf}”，但点击失败。"
            return False
        result.clickedElements.append({"strategy": "left_menu_path", "text": leaf, "role": "child"})
        wait_for_page_ready(page)
        new_page = _new_page_after_click(page, pages_before)
        active_page = _prepare_navigation_target_page(new_page, page, path_segments, result, context, emit, step_id)
        if new_page is None and before == _page_fingerprint(page) and not _target_evidence(active_page, path_segments):
            result.failureType = "menu_click_no_effect"
            result.reason = f"点击“{leaf}”后页面没有明显变化。"
            return False
        return True

    def _top_nav_path(
        self,
        page: Any,
        path_segments: list[str],
        result: NavigationResult,
        emit: RuntimeEmitter,
        debug: DebugWriter,
        step_id: Any,
        context: dict[str, Any],
    ) -> bool:
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
        pages_before = _context_pages(page)
        _click(child_locator)
        wait_for_page_ready(page)
        _prepare_navigation_target_page(_new_page_after_click(page, pages_before), page, path_segments, result, context, emit, step_id)
        result.clickedElements.append({"strategy": "top_nav_path", "text": leaf, "role": "child"})
        return True

    def _dashboard_card(
        self,
        page: Any,
        path_segments: list[str],
        result: NavigationResult,
        emit: RuntimeEmitter,
        debug: DebugWriter,
        step_id: Any,
        context: dict[str, Any],
    ) -> bool:
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
        pages_before = _context_pages(page)
        _click(locator)
        wait_for_page_ready(page)
        _prepare_navigation_target_page(_new_page_after_click(page, pages_before), page, path_segments, result, context, emit, step_id)
        result.clickedElements.append({"strategy": "dashboard_card", "text": leaf})
        return True

    def _menu_search(
        self,
        page: Any,
        path_segments: list[str],
        result: NavigationResult,
        emit: RuntimeEmitter,
        debug: DebugWriter,
        step_id: Any,
        context: dict[str, Any],
    ) -> bool:
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
        pages_before = _context_pages(page)
        _click(result_locator)
        wait_for_page_ready(page)
        _prepare_navigation_target_page(_new_page_after_click(page, pages_before), page, path_segments, result, context, emit, step_id)
        result.clickedElements.append({"strategy": "menu_search", "text": leaf})
        return True

    def _iframe_menu(
        self,
        page: Any,
        path_segments: list[str],
        result: NavigationResult,
        emit: RuntimeEmitter,
        debug: DebugWriter,
        step_id: Any,
        context: dict[str, Any],
    ) -> bool:
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
                pages_before = _context_pages(page)
                _click(child_locator)
                wait_for_page_ready(page)
                _prepare_navigation_target_page(_new_page_after_click(page, pages_before), page, path_segments, result, context, emit, step_id)
                result.clickedElements.append({"strategy": "iframe_menu", "text": leaf, "frameIndex": frame_index})
                return True
            except PlaywrightError:
                result.attemptedStrategies.append(attempt)
        return False

    def _llm_disambiguation(
        self,
        page: Any,
        path_segments: list[str],
        result: NavigationResult,
        emit: RuntimeEmitter,
        debug: DebugWriter,
        step_id: Any,
        context: dict[str, Any],
    ) -> bool:
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
        pages_before = _context_pages(page)
        _click(locator.first)
        wait_for_page_ready(page)
        _prepare_navigation_target_page(_new_page_after_click(page, pages_before), page, path_segments, result, context, emit, step_id)
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
    leaf_aliases = _leaf_aliases(leaf)
    evidence: list[str] = []
    try:
        title = page.title()
        if any(alias and alias in title for alias in leaf_aliases):
            evidence.append("title_contains_leaf")
    except PlaywrightError:
        pass
    for selector, label in [
        ("h1, h2, h3, .page-title, .header-title, .ant-page-header-heading-title, .el-page-header__content", "page_heading_contains_leaf"),
        (".ant-breadcrumb, .el-breadcrumb, .breadcrumb, [aria-label*='breadcrumb' i]", "breadcrumb_contains_path"),
        (
            "[role='tab'][aria-selected='true'], [aria-selected='true'], .ant-tabs-tab-active, .ant-menu-item-selected, .el-menu-item.is-active, .active, .selected, [aria-current='page']",
            "active_menu_contains_leaf",
        ),
    ]:
        try:
            locator = page.locator(selector)
            for index in range(min(locator.count(), 12)):
                text = locator.nth(index).inner_text(timeout=800)
                leaf_matches = any(_text_matches_segment(text, alias) for alias in leaf_aliases)
                parent_matches = all(parent in text or _text_matches_segment(text, parent) for parent in parents)
                if leaf_matches and (label != "breadcrumb_contains_path" or parent_matches):
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


def _prepare_navigation_target_page(
    new_page: Any | None,
    source_page: Any,
    path_segments: list[str],
    result: NavigationResult,
    context: dict[str, Any],
    emit: RuntimeEmitter,
    step_id: Any,
) -> Any:
    if new_page is None:
        return source_page

    leaf = path_segments[-1] if path_segments else ""
    transition: dict[str, Any] = {
        "type": "new_page",
        "reason": "leaf_click_opened_new_page",
        "target": leaf,
        "sourcePage": _page_snapshot(source_page),
        "targetPageBeforeWait": _page_snapshot(new_page),
    }
    try:
        new_page.bring_to_front()
    except PlaywrightError:
        transition["bringToFrontFailed"] = True

    security_handler = context.get("handle_security_interstitial")
    if callable(security_handler):
        try:
            if security_handler(new_page):
                transition["securityInterstitialContinued"] = True
        except Exception as exc:
            transition["securityInterstitialError"] = str(exc)

    try:
        wait_for_page_ready(new_page, settle_ms=500)
    except PlaywrightError as exc:
        transition["waitError"] = str(exc)

    transition["targetPage"] = _page_snapshot(new_page)
    transition["targetEvidence"] = _target_evidence(new_page, path_segments)
    result.pageTransitions.append(transition)
    _set_active_page(context, new_page, transition)
    emit(
        "success" if transition["targetEvidence"] else "warning",
        "navigation_page",
        "检测到目标系统打开了新页面，已切换到新页面继续验证。"
        if transition["targetEvidence"]
        else "检测到目标系统打开了新页面，但尚未确认新页面已进入目标系统。",
        "menu_path_navigator",
        {"step_id": step_id, "pageTransition": transition},
    )
    return new_page


def _active_page(context: dict[str, Any], fallback: Any) -> Any:
    getter = context.get("get_active_page")
    if callable(getter):
        try:
            page = getter()
            if page is not None:
                return page
        except Exception:
            return fallback
    return fallback


def _set_active_page(context: dict[str, Any], page: Any, transition: dict[str, Any]) -> None:
    setter = context.get("set_active_page")
    if callable(setter):
        try:
            setter(page, transition)
        except Exception:
            return


def _target_not_verified_reason(page: Any, leaf: str, result: NavigationResult) -> str:
    snapshot = _page_snapshot(page)
    page_hint = f"当前页标题：{snapshot.get('title') or '-'}，URL：{snapshot.get('url') or '-'}。"
    if result.pageTransitions:
        return f"已点击最终目标“{leaf}”并检测到新页面，但新页面未出现目标系统证据。{page_hint}"
    return f"已点击最终目标“{leaf}”，但没有检测到目标页面证据。{page_hint}"


def _context_pages(page: Any) -> list[Any]:
    try:
        return list(page.context.pages)
    except Exception:
        return []


def _new_page_after_click(page: Any, pages_before: list[Any], *, timeout_ms: int = 2_500) -> Any | None:
    deadline = time.monotonic() + max(timeout_ms, 0) / 1000
    before_ids = {id(item) for item in pages_before}
    while True:
        try:
            for candidate in reversed(list(page.context.pages)):
                if id(candidate) in before_ids:
                    continue
                try:
                    if candidate.is_closed():
                        continue
                except PlaywrightError:
                    continue
                return candidate
        except Exception:
            return None
        if time.monotonic() >= deadline:
            return None
        try:
            page.wait_for_timeout(100)
        except PlaywrightError:
            return None
    return None


def _page_snapshot(page: Any) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    try:
        snapshot["url"] = page.url
    except PlaywrightError:
        snapshot["url"] = ""
    try:
        snapshot["title"] = page.title()
    except PlaywrightError:
        snapshot["title"] = ""
    try:
        snapshot["textLength"] = len(page.locator("body").inner_text(timeout=800))
    except PlaywrightError:
        snapshot["textLength"] = 0
    return snapshot


def _segment_transition_evidence(page: Any, segment: str, next_segment: str) -> list[str]:
    evidence: list[str] = []
    selected = _selected_segment_evidence(page, segment)
    if selected:
        evidence.append(selected)
    if next_segment and _text_visible(page, next_segment):
        evidence.append(f"next_segment_visible:{next_segment}")
    return evidence


def _segment_transition_reached(evidence: list[str], *, page_changed: bool) -> bool:
    return page_changed or any(item.startswith("next_segment_visible:") for item in evidence)


def _selected_segment_evidence(page: Any, segment: str) -> str | None:
    selectors = [
        "[role='tab'][aria-selected='true']",
        "[aria-selected='true']",
        ".ant-tabs-tab-active",
        ".ant-menu-item-selected",
        ".el-menu-item.is-active",
        "[aria-current='page']",
        ".active",
        ".selected",
    ]
    for selector in selectors:
        try:
            locator = page.locator(selector)
            for index in range(min(locator.count(), 20)):
                text = locator.nth(index).inner_text(timeout=500)
                if _text_matches_segment(text, segment):
                    return f"segment_selected:{segment}"
        except PlaywrightError:
            continue
    return None


def _text_visible(page: Any, text: str) -> bool:
    return _find_text(page.locator("body"), text) is not None


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
    normalized = _normalize_label(text)
    normalized_escaped = re.escape(normalized)
    exact_with_count = re.compile(rf"^\s*{normalized_escaped}\s*(?:[（(]\d+[）)])?\s*$")
    patterns = [
        lambda: scope.get_by_role("menuitem", name=re.compile(f"^{escaped}$")),
        lambda: scope.get_by_role("menuitem", name=exact_with_count),
        lambda: scope.get_by_role("button", name=re.compile(f"^{escaped}$")),
        lambda: scope.get_by_role("button", name=exact_with_count),
        lambda: scope.get_by_role("link", name=re.compile(f"^{escaped}$")),
        lambda: scope.get_by_role("link", name=exact_with_count),
        lambda: scope.get_by_role("tab", name=re.compile(f"^{escaped}$")),
        lambda: scope.get_by_role("tab", name=exact_with_count),
        lambda: scope.get_by_text(text, exact=True),
        lambda: scope.get_by_text(exact_with_count),
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
        body = re.sub(r"\s+", " ", page.locator("body").inner_text(timeout=1000))[:4000]
    except PlaywrightError:
        body = ""
    return f"{page.url}|{body}"


def _page_count(page: Any) -> int:
    try:
        return len(page.context.pages)
    except Exception:
        return 1


def _leaf_aliases(leaf: str) -> list[str]:
    normalized = _normalize_label(leaf)
    aliases = [leaf, normalized]
    for prefix in ["中国石化", "中石化", "燕山石化", "燕山"]:
        if normalized.startswith(prefix):
            aliases.append(normalized.removeprefix(prefix))
    return [item for item in dict.fromkeys(aliases) if item]


def _normalize_label(value: str) -> str:
    text = re.sub(r"\s+", "", str(value or ""))
    return re.sub(r"[（(]\d+[）)]$", "", text)


def _text_matches_segment(candidate: str, segment: str) -> bool:
    normalized_candidate = _normalize_label(candidate)
    normalized_segment = _normalize_label(segment)
    if not normalized_candidate or not normalized_segment:
        return False
    return (
        normalized_candidate == normalized_segment
        or normalized_candidate.startswith(normalized_segment)
        or normalized_segment in normalized_candidate
    )


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
