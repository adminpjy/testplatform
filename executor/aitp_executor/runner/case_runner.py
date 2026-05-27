import os
import re
from datetime import datetime, timezone
from typing import Any, Callable

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from executor.aitp_executor.browser.provider_factory import create_sandbox_provider
from executor.aitp_executor.browser.sandbox_provider import SandboxProvider
from executor.aitp_executor.goal.goal_executor import GoalExecutor
from executor.aitp_executor.handlers import (
    AssertionHandler,
    DatePickerHandler,
    DialogSelectorHandler,
    DropdownHandler,
    FileUploadHandler,
    FormFillHandler,
    NavigationHandler,
    OrgSelectorHandler,
    PersonSelectorHandler,
    QueryHandler,
    TableHandler,
    TableRowActionHandler,
)
from executor.aitp_executor.locator.auto_form_filler import AutoFormFiller
from executor.aitp_executor.locator.element_locator import ElementLocator
from executor.aitp_executor.observer.auth_state_detector import AuthStateDetector, AuthStateResult
from executor.aitp_executor.reports.artifact_writer import ArtifactWriter
from executor.aitp_executor.reports.report_writer import ReportWriter
from executor.aitp_executor.runner.page_waiter import wait_for_page_ready


class CaseRunner:
    def __init__(
        self,
        provider: SandboxProvider | None = None,
        event_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.provider = provider or create_sandbox_provider()
        self.element_locator = ElementLocator()
        self.auto_form_filler = AutoFormFiller()
        self.goal_executor = GoalExecutor(locator=self.element_locator)
        self.table_handler = TableHandler(observer=self.element_locator.observer)
        self.dialog_selector_handler = DialogSelectorHandler()
        self.navigation_handler = NavigationHandler(
            locator=self.element_locator,
            menu_path_navigator=self.goal_executor.menu_path_navigator,
        )
        self.query_handler = QueryHandler(locator=self.element_locator, table_handler=self.table_handler)
        self.table_row_action_handler = TableRowActionHandler(
            table_handler=self.table_handler,
            dialog_handler=self.dialog_selector_handler,
        )
        self.form_fill_handler = FormFillHandler(locator=self.element_locator, form_filler=self.auto_form_filler)
        self.dropdown_handler = DropdownHandler(locator=self.element_locator)
        self.date_picker_handler = DatePickerHandler(locator=self.element_locator)
        self.org_selector_handler = OrgSelectorHandler(locator=self.element_locator, dialog_handler=self.dialog_selector_handler)
        self.person_selector_handler = PersonSelectorHandler(dialog_handler=self.dialog_selector_handler)
        self.file_upload_handler = FileUploadHandler(locator=self.element_locator)
        self.assertion_handler = AssertionHandler()
        self.auth_state_detector = AuthStateDetector()
        self.event_sink = event_sink

    def run(self, *, run_code: str, dsl: dict[str, Any]) -> dict[str, Any]:
        dsl = _normalize_runtime_dsl(dsl)
        writer = ArtifactWriter(run_code)
        report_writer = ReportWriter(writer)
        started_at = _utc_now()
        steps = dsl.get("steps") or []
        results: list[dict[str, Any]] = []
        status = "passed"
        error_summary = None
        session = None
        sandbox_screenshot_path = None

        self._emit_runtime(writer, "text", "understanding", "正在理解测试用例", "runner", {"run_code": run_code})
        self._emit_runtime(writer, "progress", "planning", "正在生成测试步骤", "runner", {"steps": len(steps)})

        try:
            sandbox_metadata = _sandbox_metadata(self.provider)
            self._emit_runtime(
                writer,
                "progress",
                "sandbox_starting",
                sandbox_metadata["starting_message"],
                "sandbox_provider",
                sandbox_metadata,
            )
            session = self.provider.start()
            page = session.page
            sandbox_screenshot_path = self._write_sandbox_screenshot(page, writer)
            self._emit_runtime(
                writer,
                "success",
                "sandbox_ready",
                sandbox_metadata["ready_message"],
                "sandbox_provider",
                {
                    **sandbox_metadata,
                    "sandbox_status": "ready",
                    "screenshot_path": sandbox_screenshot_path,
                },
            )
            base_url = dsl.get("baseUrl") or dsl.get("base_url")
            if base_url:
                writer.append_jsonl("execution-trace.jsonl", {"type": "base_url.open", "url": base_url})
                self._emit_runtime(writer, "progress", "open_system", "正在打开系统", "playwright", {"url": base_url})
                page.goto(base_url, wait_until="domcontentloaded")
                if self._continue_security_interstitial(page):
                    self._emit_runtime(
                        writer,
                        "warning",
                        "global_interruption",
                        "检测到证书安全提示，已按配置继续访问。",
                        "playwright",
                        {"interruption": "security_interstitial", "url": page.url},
                    )
                self._wait_for_page_ready(writer, page, step_number=None, reason="open_system")

            for index, step in enumerate(steps, start=1):
                result = self._run_step(page, writer, index, step, dsl)
                results.append(result)
                if result["status"] != "passed":
                    status = "failed"
                    error_summary = result.get("error_summary")
                    break
        except Exception as exc:
            status = "failed"
            error_summary = str(exc)
            self._emit_runtime(writer, "error", "failed", str(error_summary), "runner", {"run_code": run_code})
        finally:
            if session is not None:
                session.close()

        ended_at = _utc_now()
        summary = {
            "runCode": run_code,
            "caseName": dsl.get("caseName") or dsl.get("case_name") or "DSL Test Run",
            "baseUrl": dsl.get("baseUrl") or dsl.get("base_url") or "",
            "status": status,
            "totalSteps": len(steps),
            "executedSteps": len(results),
            "passedSteps": len([step for step in results if step.get("status") == "passed"]),
            "failedSteps": len([step for step in results if step.get("status") == "failed"]),
            "startedAt": started_at,
            "endedAt": ended_at,
            "durationMs": _duration_ms(started_at, ended_at),
            "errorSummary": error_summary,
        }
        summary_path = writer.write_json("summary.json", summary)
        self._emit_runtime(writer, "progress", "reporting", "正在生成报告", "report_writer", {"summary": summary_path})
        report_path = report_writer.write(summary, results)
        self._emit_runtime(
            writer,
            "success" if status == "passed" else "error",
            "completed" if status == "passed" else "failed",
            "测试执行通过" if status == "passed" else "测试执行失败",
            "runner",
            {"run_code": run_code, "report": report_path},
        )
        return {
            "status": status,
            "summary": summary,
            "steps": results,
            "artifacts": {
                "run_dir": writer.relative(writer.run_dir),
                "summary": summary_path,
                "report": report_path,
                "step_results": writer.relative(writer.path("step-result.jsonl")),
                "locator_debug": writer.relative(writer.path("locator-debug.jsonl")),
                "execution_trace": writer.relative(writer.path("execution-trace.jsonl")),
                "runtime_stream": writer.relative(writer.path("runtime-stream.jsonl")),
                "sandbox_screenshot": sandbox_screenshot_path,
            },
        }

    def _run_step(
        self,
        page: Any,
        writer: ArtifactWriter,
        step_number: int,
        step: dict[str, Any],
        dsl: dict[str, Any],
    ) -> dict[str, Any]:
        started_at = _utc_now()
        action = str(step.get("action") or "")
        target = str(step.get("target") or step.get("selector") or "")
        locatable_action = action in {"input", "click", "confirm_dialog", "navigate_menu", "select", "upload_file", "business_goal", "navigate_path"}
        vision_requested = bool((dsl.get("settings") or {}).get("visionFallbackEnabled"))
        self._emit_runtime(
            writer,
            "progress",
            "step",
            "步骤开始",
            "runner",
            {"step_number": step_number, "action": action, "target": target},
        )
        self._emit_ability_resolution(writer, step_number, step)
        writer.append_jsonl(
            "execution-trace.jsonl",
            {"type": "step.execute", "step_number": step_number, "step": _redact_step(step)},
        )
        self._wait_for_page_ready(writer, page, step_number=step_number, reason="before_step")
        auth_failure = self._auth_precondition_failure(page, writer, step_number, step, action, target)
        if auth_failure is not None:
            return auth_failure
        if action in {"business_goal", "navigate_path"}:
            self._emit_runtime(
                writer,
                "progress",
                "intent",
                "正在识别业务意图",
                "goal_executor",
                {"step_number": step_number, "target": target},
            )
        if locatable_action:
            self._emit_runtime(
                writer,
                "progress",
                "observe",
                "正在读取页面",
                "page_observer",
                {"step_number": step_number, "action": action, "target": target},
            )
            self._write_observation_debug(page, writer, step_number, action, target)
            self._emit_runtime(
                writer,
                "progress",
                "llm_resolver",
                "LLM 辅助定位已就绪，将在页面语义定位置信度不足时调用。",
                "llm_element_resolver",
                {"step_number": step_number, "action": action, "target": target},
            )
            self._emit_runtime(
                writer,
                "progress" if vision_requested else "text",
                "vision",
                "视觉兜底已开启，将在 DOM 和 LLM 无法确认时启用。" if vision_requested else "视觉兜底未开启，本步骤不会执行视觉识别。",
                "vision_resolver",
                {"step_number": step_number, "action": action, "target": target, "requested": vision_requested},
            )
            self._emit_runtime(
                writer,
                "progress",
                "locate",
                "正在分析候选元素",
                "element_locator",
                {"step_number": step_number, "action": action, "target": target},
            )
        if action in {"click", "confirm_dialog", "navigate_menu", "business_goal", "navigate_path"}:
            self._emit_runtime(
                writer,
                "progress",
                "action",
                "正在点击",
                "playwright",
                {"step_number": step_number, "target": target},
            )
        if action in {"wait_for_text", "assert_text_exists", "assert_text_not_exists", "assert_url_contains", "business_goal", "navigate_path"}:
            self._emit_runtime(
                writer,
                "progress",
                "verify",
                "正在验证",
                "action_verifier",
                {"step_number": step_number, "target": target},
            )

        status = "passed"
        error_summary = None
        locator_strategy = None
        element_ref = None
        confidence = 1.0
        reason = "executed"
        needs_vision_fallback = False
        fallback_reason = None
        failure_type = None
        failure_details: dict[str, Any] | None = None
        failure_analysis: dict[str, Any] | None = None
        candidates: list[dict[str, Any]] = []
        try:
            outcome = self._execute_action(page, step, dsl, writer=writer, step_number=step_number)
            page_ready = self._wait_for_page_ready(writer, page, step_number=step_number, reason="after_action")
            outcome["page_ready"] = page_ready
            if locatable_action:
                self._emit_locator_decision_runtime(writer, step_number, action, target, outcome, vision_requested)
            locator_strategy = outcome.get("locator_strategy")
            element_ref = outcome.get("element_ref")
            confidence = outcome.get("confidence", 1.0)
            reason = outcome.get("reason", "executed")
            needs_vision_fallback = outcome.get("needs_vision_fallback", False)
            fallback_reason = outcome.get("fallback_reason")
            failure_type = outcome.get("failure_type")
            candidates = outcome.get("candidates", [])
        except Exception as exc:
            status = "failed"
            error_summary = _error_summary(exc)
            failure_type = getattr(exc, "failure_type", None)
            failure_details = getattr(exc, "details", None)
            if isinstance(failure_details, dict):
                locator_strategy = failure_details.get("locator_strategy") or locator_strategy
                element_ref = failure_details.get("element_ref") or element_ref
                confidence = failure_details.get("confidence", confidence)
                reason = failure_details.get("reason") or reason
                candidates = failure_details.get("candidates", candidates)
            if failure_type:
                fallback_reason = str(failure_type)
            if "vision_fallback_not_configured" in error_summary:
                needs_vision_fallback = True
                fallback_reason = "vision_fallback_not_configured"
                self._emit_runtime(
                    writer,
                    "warning",
                    "llm_resolver",
                    "正在调用 LLM",
                    "llm_element_resolver",
                    {"step_number": step_number, "target": target, "configured": False},
                )
                self._emit_runtime(
                    writer,
                    "warning",
                    "vision",
                    "正在启用视觉兜底",
                    "vision_resolver",
                    {"step_number": step_number, "target": target, "status": fallback_reason},
                )
            failure_analysis = self.goal_executor.recovery_policy.analyze_failure(
                error_summary=error_summary,
                action=action,
                target=target,
                failure_type=failure_type,
                fallback_reason=fallback_reason,
                details=failure_details,
            )
            failure_type = failure_analysis.get("failureType") or failure_type
            fallback_reason = failure_type
            self._emit_failure_analysis_runtime(writer, step_number, action, target, failure_analysis)
        finally:
            screenshot_path = self._write_screenshot(page, writer, step_number)
            dom_snapshot_path = self._write_dom_snapshot(page, writer, step_number)
            accessibility_snapshot_path = self._write_accessibility_snapshot(page, writer, step_number)

        ended_at = _utc_now()
        result = {
            "step_number": step_number,
            "step_id": str(step.get("id") or step_number),
            "step_name": step.get("name") or target or action,
            "action": action,
            "target": target,
            "status": status,
            "locator_strategy": locator_strategy,
            "element_ref": element_ref,
            "confidence": confidence if status == "passed" else min(confidence, 0.25),
            "reason": reason if status == "passed" else "execution_failed",
            "needs_vision_fallback": needs_vision_fallback,
            "fallback_reason": fallback_reason,
            "failure_type": failure_type,
            "failure_details": failure_details,
            "failure_analysis": failure_analysis,
            "suggested_recovery": failure_analysis.get("suggestedRecovery") if failure_analysis else None,
            "screenshot_path": screenshot_path,
            "dom_snapshot_path": dom_snapshot_path,
            "accessibility_snapshot_path": accessibility_snapshot_path,
            "error_summary": error_summary,
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_ms": _duration_ms(started_at, ended_at),
        }
        writer.append_jsonl("step-result.jsonl", result)
        writer.append_jsonl(
            "locator-debug.jsonl",
            {
                "step_number": step_number,
                "action": action,
                "target": target,
                "locator_strategy": locator_strategy,
                "element_ref": element_ref,
                "status": status,
                "error_summary": error_summary,
                "confidence": confidence if status == "passed" else min(confidence, 0.25),
                "reason": reason,
                "needs_vision_fallback": needs_vision_fallback,
                "fallback_reason": fallback_reason,
                "failure_type": failure_type,
                "failure_details": failure_details,
                "failure_analysis": failure_analysis,
                "candidates": candidates,
            },
        )
        self._emit_runtime(
            writer,
            "success" if status == "passed" else "error",
            "step",
            "步骤执行成功" if status == "passed" else str(error_summary),
            "runner",
            {"step_number": step_number, "action": action, "target": target},
        )
        return result

    def _auth_precondition_failure(
        self,
        page: Any,
        writer: ArtifactWriter,
        step_number: int,
        step: dict[str, Any],
        action: str,
        target: str,
    ) -> dict[str, Any] | None:
        if not _step_requires_auth(step):
            return None

        started_at = _utc_now()
        auth_result = self.auth_state_detector.detect_auth_state(page)
        writer.append_jsonl(
            "locator-debug.jsonl",
            {
                "phase": "auth_state_detected",
                "stepId": step.get("id") or step.get("step_id") or step_number,
                "authState": auth_result.authState,
                "confidence": auth_result.confidence,
                "failureType": auth_result.failureType,
                "evidence": auth_result.evidence,
                "decision": _auth_decision(auth_result),
                "reason": auth_result.reason,
            },
        )

        if auth_result.authState == "login_success":
            self._emit_runtime(
                writer,
                "success",
                "auth_guard",
                "已确认当前处于登录后的系统页面，可以继续执行业务步骤。",
                "auth_state_detector",
                {"step_number": step_number, **auth_result.as_dict()},
            )
            return None

        if auth_result.authState not in {"login_failed", "login_page", "login_requires_manual_action"}:
            return None

        writer.append_jsonl(
            "locator-debug.jsonl",
            {
                "phase": "precondition_failed",
                "stepId": step.get("id") or step.get("step_id") or step_number,
                "action": action,
                "target": target,
                "requiredPrecondition": "auth_state_logged_in",
                "actualAuthState": auth_result.authState,
                "rootCause": auth_result.failureType or auth_result.authState,
                "decision": "skip_and_fail_run",
                "evidence": auth_result.evidence,
            },
        )

        error_summary = _auth_error_summary(auth_result)
        failure_type = _auth_failure_type(auth_result)
        failure_details = {
            "rootCause": failure_type,
            "precondition": "auth_state_logged_in",
            "auth_state": auth_result.as_dict(),
            "message": "当前仍停留在登录页，且检测到登录未成功，因此不执行后续业务步骤。",
        }
        failure_analysis = self.goal_executor.recovery_policy.analyze_failure(
            error_summary=error_summary,
            action=action,
            target=target,
            failure_type=failure_type,
            details=failure_details,
        )
        self._emit_runtime(
            writer,
            "error",
            "auth_guard",
            _auth_runtime_message(auth_result),
            "auth_state_detector",
            {"step_number": step_number, "action": action, "target": target, **auth_result.as_dict()},
        )
        self._emit_failure_analysis_runtime(writer, step_number, action, target, failure_analysis)

        screenshot_path = self._write_screenshot(page, writer, step_number)
        dom_snapshot_path = self._write_dom_snapshot(page, writer, step_number)
        accessibility_snapshot_path = self._write_accessibility_snapshot(page, writer, step_number)
        ended_at = _utc_now()
        result = {
            "step_number": step_number,
            "step_id": str(step.get("id") or step_number),
            "step_name": step.get("name") or target or action,
            "action": action,
            "target": target,
            "status": "failed",
            "locator_strategy": "auth_state_guard",
            "element_ref": None,
            "confidence": min(auth_result.confidence, 0.95),
            "reason": "auth_precondition_failed",
            "needs_vision_fallback": False,
            "fallback_reason": failure_analysis.get("failureType") or failure_type,
            "failure_type": failure_analysis.get("failureType") or failure_type,
            "failure_details": failure_details,
            "failure_analysis": failure_analysis,
            "suggested_recovery": failure_analysis.get("suggestedRecovery"),
            "screenshot_path": screenshot_path,
            "dom_snapshot_path": dom_snapshot_path,
            "accessibility_snapshot_path": accessibility_snapshot_path,
            "error_summary": error_summary,
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_ms": _duration_ms(started_at, ended_at),
        }
        writer.append_jsonl("step-result.jsonl", result)
        writer.append_jsonl(
            "locator-debug.jsonl",
            {
                "step_number": step_number,
                "action": action,
                "target": target,
                "locator_strategy": "auth_state_guard",
                "status": "failed",
                "error_summary": error_summary,
                "confidence": auth_result.confidence,
                "reason": "auth_precondition_failed",
                "failure_type": result["failure_type"],
                "failure_details": failure_details,
                "failure_analysis": failure_analysis,
            },
        )
        self._emit_runtime(
            writer,
            "error",
            "step",
            error_summary,
            "runner",
            {"step_number": step_number, "action": action, "target": target},
        )
        return result

    def _emit_failure_analysis_runtime(
        self,
        writer: ArtifactWriter,
        step_number: int,
        action: str,
        target: str,
        failure_analysis: dict[str, Any],
    ) -> None:
        strategies = failure_analysis.get("suggestedRecovery") or []
        self._emit_runtime(
            writer,
            "error",
            "failure_analysis",
            f"失败类型：{failure_analysis.get('failureType') or 'unknown_failure'}。{failure_analysis.get('summary') or ''}",
            "failure_analyzer",
            {
                "step_number": step_number,
                "action": action,
                "target": target,
                "failureType": failure_analysis.get("failureType"),
                "category": failure_analysis.get("category"),
                "attemptedStrategies": failure_analysis.get("attemptedStrategies") or [],
                "suggestedRecovery": strategies,
                "canIntervene": failure_analysis.get("canIntervene"),
                "canGenerateRuleDraft": failure_analysis.get("canGenerateRuleDraft"),
                "visionFallback": failure_analysis.get("visionFallback"),
            },
        )
        if strategies:
            labels = "；".join(str(item.get("label") or item.get("code")) for item in strategies[:4])
            self._emit_runtime(
                writer,
                "warning",
                "recovery_policy",
                f"下一步建议：{labels}。",
                "recovery_policy",
                {
                    "step_number": step_number,
                    "failureType": failure_analysis.get("failureType"),
                    "suggestedRecovery": strategies,
                    "canIntervene": failure_analysis.get("canIntervene"),
                    "canGenerateRuleDraft": failure_analysis.get("canGenerateRuleDraft"),
                },
            )

    def _wait_for_page_ready(
        self,
        writer: ArtifactWriter,
        page: Any,
        *,
        step_number: int | None,
        reason: str,
    ) -> dict[str, Any]:
        metadata = {"step_number": step_number, "reason": reason}
        self._emit_runtime(
            writer,
            "progress",
            "page_ready",
            "正在等待页面加载完成",
            "page_waiter",
            metadata,
        )
        state = wait_for_page_ready(page)
        payload = {**metadata, **state.as_dict()}
        writer.append_jsonl("execution-trace.jsonl", {"type": "page.ready", **payload})
        self._emit_runtime(
            writer,
            "success" if state.ready else "warning",
            "page_ready",
            "页面已加载完成" if state.ready else "页面加载等待超时，继续执行并保留证据。",
            "page_waiter",
            payload,
        )
        return state.as_dict()

    def _emit_locator_decision_runtime(
        self,
        writer: ArtifactWriter,
        step_number: int,
        action: str,
        target: str,
        outcome: dict[str, Any],
        vision_requested: bool,
    ) -> None:
        strategy = str(outcome.get("locator_strategy") or "")
        confidence = outcome.get("confidence")
        if strategy == "llm_resolver":
            self._emit_runtime(
                writer,
                "success",
                "llm_resolver",
                "LLM 已参与元素判断，并返回候选定位。",
                "llm_element_resolver",
                {"step_number": step_number, "action": action, "target": target, "strategy": strategy, "confidence": confidence},
            )
        else:
            self._emit_runtime(
                writer,
                "text",
                "llm_resolver",
                "LLM 未触发：当前步骤已通过确定性定位或页面语义定位完成。",
                "llm_element_resolver",
                {"step_number": step_number, "action": action, "target": target, "strategy": strategy, "confidence": confidence},
            )

        if outcome.get("needs_vision_fallback"):
            self._emit_runtime(
                writer,
                "warning",
                "vision",
                "视觉兜底已触发，正在记录兜底状态和截图证据。",
                "vision_resolver",
                {
                    "step_number": step_number,
                    "action": action,
                    "target": target,
                    "fallback_reason": outcome.get("fallback_reason"),
                    "requested": vision_requested,
                },
            )
        else:
            self._emit_runtime(
                writer,
                "text",
                "vision",
                "视觉兜底未触发：当前定位置信度足够。" if vision_requested else "视觉兜底未开启，本步骤未执行视觉识别。",
                "vision_resolver",
                {"step_number": step_number, "action": action, "target": target, "requested": vision_requested},
            )

    def _emit_runtime(
        self,
        writer: ArtifactWriter,
        message_type: str,
        phase: str,
        content: str,
        method: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        event = _runtime_event(message_type, phase, content, method, metadata or {})
        writer.append_jsonl("runtime-stream.jsonl", event)
        if self.event_sink:
            self.event_sink(event)

    def _write_observation_debug(
        self,
        page: Any,
        writer: ArtifactWriter,
        step_number: int,
        action: str,
        target: str,
    ) -> None:
        try:
            observation = self.element_locator.observer.observe(page)
            data = observation.as_dict()
            writer.append_jsonl(
                "locator-debug.jsonl",
                {
                    "step_number": step_number,
                    "phase": "page_observation",
                    "action": action,
                    "target": target,
                    "observation": _compact_observation(data),
                },
            )
        except Exception as exc:
            writer.append_jsonl(
                "locator-debug.jsonl",
                {
                    "step_number": step_number,
                    "phase": "page_observation",
                    "action": action,
                    "target": target,
                    "error": str(exc),
                },
            )

    def _execute_action(
        self,
        page: Any,
        step: dict[str, Any],
        dsl: dict[str, Any],
        *,
        writer: ArtifactWriter | None = None,
        step_number: int | None = None,
    ) -> dict[str, Any]:
        action = step.get("action")
        target = step.get("target") or step.get("selector") or ""
        execution_context = self._handler_execution_context(writer, step_number, step, dsl)
        operation_intent = str((step.get("operationIntent") or {}).get("intent") or "")

        if action == "open_url":
            url = step.get("url") or target
            page.goto(url, wait_until="domcontentloaded")
            self._continue_security_interstitial(page)
            return _outcome("url", str(url), 1.0, "url opened")

        if action == "input":
            if operation_intent in {"select_date", "select_date_range"}:
                return self.date_picker_handler.select_date(page, step=step, dsl=dsl, execution_context=execution_context)
            if operation_intent == "select_org":
                return self.org_selector_handler.select(page, step=step, dsl=dsl, execution_context=execution_context)
            if operation_intent == "select_person":
                return self.person_selector_handler.select(page, step=step, dsl=dsl, execution_context=execution_context)
            return self.form_fill_handler.fill_field(page, step=step, dsl=dsl, execution_context=execution_context)

        if action in {"click", "confirm_dialog"}:
            result = self.element_locator.locate(page, action="click", target=str(target), step=step)
            _require_locator(result).click()
            return _locator_outcome(result)

        if action == "navigate_menu":
            return self.navigation_handler.execute(page, step=step, dsl=dsl, execution_context=execution_context)

        if action in {"wait_for_text", "assert_text_exists"}:
            return self.assertion_handler.assert_step(page, step=step, dsl=dsl, execution_context=execution_context)

        if action == "assert_text_not_exists":
            return self.assertion_handler.assert_step(page, step=step, dsl=dsl, execution_context=execution_context)

        if action == "assert_url_contains":
            return self.assertion_handler.assert_step(page, step=step, dsl=dsl, execution_context=execution_context)

        if action == "select":
            return self.dropdown_handler.select(page, step=step, dsl=dsl, execution_context=execution_context)

        if action == "upload_file":
            return self.file_upload_handler.upload(page, step=step, dsl=dsl, execution_context=execution_context)

        if action == "wait":
            page.wait_for_timeout(int(step.get("ms") or step.get("timeoutMs") or 1000))
            return _outcome("timeout", str(step.get("ms") or step.get("timeoutMs") or 1000), 1.0, "waited")

        if action == "query_table":
            return self.query_handler.execute(page, step=step, dsl=dsl, execution_context=execution_context)

        if action == "query_table_count":
            return self.query_handler.count_rows(page, step=step, dsl=dsl, execution_context=execution_context)

        if action in {"for_each_table_row", "process_table_rows"}:
            return self.table_row_action_handler.process_rows(page, step=step, dsl=dsl, execution_context=execution_context)

        if action in {"open_row_link_or_detail", "open_table_row"}:
            return self.table_row_action_handler.open_first_row(page, step=step, dsl=dsl, execution_context=execution_context)

        if action == "wait_for_dialog":
            return self.dialog_selector_handler.wait_for_dialog(page, step=step, dsl=dsl, execution_context=execution_context)

        if action == "close_dialog_by_common_controls":
            return self.dialog_selector_handler.close_by_common_controls(page, step=step, dsl=dsl, execution_context=execution_context)

        if action == "continue_until_all_rows_processed":
            return _outcome("loop_checkpoint", "all_rows_processed", 0.8, "loop handled by for_each_table_row")

        if action in {"summary_assert", "assert_result"}:
            return self.assertion_handler.assert_step(page, step=step, dsl=dsl, execution_context=execution_context)

        if action in {"auto_fill_form", "fill_form"}:
            return self.form_fill_handler.fill_form(page, step=step, dsl=dsl, execution_context=execution_context)

        if action == "click_table_row_action":
            return self.table_row_action_handler.click_row_action(page, step=step, dsl=dsl, execution_context=execution_context)

        if action == "navigate_path":
            return self.navigation_handler.execute(page, step=step, dsl=dsl, execution_context=execution_context)

        if action == "business_goal":
            if step.get("pathSegments"):
                return self.navigation_handler.execute(page, step=step, dsl=dsl, execution_context=execution_context)
            goal_step = dict(step)
            credentials = dict(dsl.get("credentials") or {})
            credentials.update(dict(step.get("credentials") or {}))
            if credentials:
                goal_step["credentials"] = credentials
            return self.goal_executor.execute(page, target=str(target), step=goal_step, execution_context=execution_context)

        raise ValueError(f"Unsupported DSL action: {action}")

    def _execute_navigation_path(
        self,
        page: Any,
        step: dict[str, Any],
        dsl: dict[str, Any],
        *,
        writer: ArtifactWriter | None,
        step_number: int | None,
    ) -> dict[str, Any]:
        target = str(step.get("target") or "")
        segments = _runtime_path_segments(step.get("pathSegments") or target)
        if len(segments) < 2:
            raise RuntimeError("navigation_path_unresolved: pathSegments must contain at least two items.")
        return self.navigation_handler.execute(
            page,
            step={**step, "pathSegments": segments, "target": target or "/".join(segments)},
            dsl=dsl,
            execution_context=self._handler_execution_context(writer, step_number, step, dsl),
        )

    def _handler_execution_context(
        self,
        writer: ArtifactWriter | None,
        step_number: int | None,
        step: dict[str, Any],
        dsl: dict[str, Any],
    ) -> dict[str, Any]:
        execution_context: dict[str, Any] = {
            "step_number": step_number,
            "step_id": step.get("id") or step.get("step_id") or step_number,
            "vision_requested": bool((dsl.get("settings") or {}).get("visionFallbackEnabled")),
            "ability_resolution": step.get("abilityResolution") or {},
        }
        if writer is not None:
            execution_context["emit_runtime"] = (
                lambda message_type, phase, content, method, metadata: self._emit_runtime(
                    writer,
                    message_type,
                    phase,
                    content,
                    method,
                    {"step_number": step_number, **(metadata or {})},
                )
            )
            execution_context["append_debug"] = lambda event: writer.append_jsonl("locator-debug.jsonl", event)
        return execution_context

    def _emit_ability_resolution(self, writer: ArtifactWriter, step_number: int, step: dict[str, Any]) -> None:
        resolution = step.get("abilityResolution") or {}
        operation_intent = step.get("operationIntent") or {}
        matched_rules = resolution.get("matchedRules") or []
        selected_rules = resolution.get("selectedRules") or []
        matched_codes = [str(rule.get("rule_code")) for rule in matched_rules if rule.get("rule_code")]
        selected_codes = [str(rule.get("rule_code")) for rule in selected_rules if rule.get("rule_code")]
        debug_event = {
            "step_number": step_number,
            "stepId": step.get("id") or step.get("step_id") or step_number,
            "phase": "ability_resolve",
            "intent": operation_intent.get("intent"),
            "intentType": operation_intent.get("intentType"),
            "matchedRules": matched_codes,
            "selectedRules": selected_codes,
            "reason": resolution.get("reason") or operation_intent.get("reason") or "",
            "source": resolution.get("source"),
        }
        writer.append_jsonl("locator-debug.jsonl", debug_event)
        if not selected_rules:
            return
        for rule in selected_rules[:5]:
            message = rule.get("runtimeMessage") or f"命中规则 {rule.get('rule_code')}：将按{rule.get('rule_name')}处理。"
            self._emit_runtime(
                writer,
                "success",
                "ability_resolve",
                str(message),
                "ability_resolver",
                {
                    "step_number": step_number,
                    "intent": operation_intent.get("intent"),
                    "intentType": operation_intent.get("intentType"),
                    "rule_code": rule.get("rule_code"),
                    "rule_type": rule.get("rule_type"),
                    "rule_name": rule.get("rule_name"),
                    "score": rule.get("score"),
                    "source": resolution.get("source"),
                },
            )

    def _write_screenshot(self, page: Any, writer: ArtifactWriter, step_number: int) -> str | None:
        try:
            path = writer.screenshot_path(step_number)
            page.screenshot(path=str(path), full_page=True)
            return writer.relative(path)
        except PlaywrightError:
            return None

    def _write_sandbox_screenshot(self, page: Any, writer: ArtifactWriter) -> str | None:
        try:
            path = writer.path("screenshots", "sandbox-started.png")
            page.screenshot(path=str(path), full_page=True)
            return writer.relative(path)
        except PlaywrightError:
            return None

    def _continue_security_interstitial(self, page: Any) -> bool:
        if not _env_bool("PLAYWRIGHT_AUTO_CONTINUE_SECURITY_INTERSTITIAL", False):
            return False
        try:
            if page.locator("#details-button").count() > 0:
                page.locator("#details-button").first.click()
                page.wait_for_timeout(200)
            if page.locator("#proceed-link").count() > 0:
                page.locator("#proceed-link").first.click()
                page.wait_for_load_state("domcontentloaded", timeout=5_000)
                return True
            for text in ["高级", "继续访问", "继续前往", "接受风险并继续"]:
                candidate = page.get_by_text(text, exact=False)
                if candidate.count() > 0:
                    candidate.first.click()
                    page.wait_for_timeout(300)
                    if text != "高级":
                        return True
            if page.locator("#proceed-link").count() > 0:
                page.locator("#proceed-link").first.click()
                page.wait_for_load_state("domcontentloaded", timeout=5_000)
                return True
        except PlaywrightError:
            return False
        return False

    def _table_row_count(self, page: Any) -> int:
        rows = self._table_rows(page)
        count = rows.count()
        visible_rows = 0
        for index in range(count):
            try:
                row = rows.nth(index)
                text = row.inner_text(timeout=800).strip()
                if text:
                    visible_rows += 1
            except PlaywrightError:
                continue
        return visible_rows

    def _table_rows(self, page: Any) -> Any:
        selectors = [
            "table tbody tr",
            ".ant-table-tbody tr",
            ".el-table__body tbody tr",
            "[role='row']",
        ]
        best = page.locator(selectors[0])
        best_count = 0
        for selector in selectors:
            try:
                locator = page.locator(selector)
                count = locator.count()
                if count > best_count:
                    best = locator
                    best_count = count
            except PlaywrightError:
                continue
        return best

    def _for_each_table_row(self, page: Any, step: dict[str, Any]) -> dict[str, Any]:
        max_rows = int(step.get("maxRows") or step.get("max_rows") or 200)
        empty_strategy = str(step.get("emptyStrategy") or step.get("empty_strategy") or "pass")
        row_count = self._table_row_count(page)
        if row_count == 0:
            if empty_strategy == "pass":
                return {"row_count": 0, "processed_rows": 0, "status": "empty_pass"}
            raise AssertionError("Table has no rows.")

        processed = 0
        failures: list[dict[str, Any]] = []
        limit = min(row_count, max_rows)
        for index in range(limit):
            try:
                rows = self._table_rows(page)
                row = rows.nth(index)
                before_url = page.url
                self._click_row_entry(row)
                page.wait_for_timeout(500)
                dialog_opened = self._wait_for_dialog(page, timeout_ms=2_000)
                closed = False
                if dialog_opened:
                    closed = self._close_dialog_by_common_controls(page)
                elif page.url != before_url:
                    page.go_back(wait_until="domcontentloaded")
                    wait_for_page_ready(page)
                    closed = True
                processed += 1
                if dialog_opened and not closed:
                    failures.append({"row": index + 1, "error": "dialog_close_failed"})
            except Exception as exc:
                failures.append({"row": index + 1, "error": str(exc)})
        if failures:
            raise RuntimeError("table_row_loop_failed:" + _json_dumps({"processed_rows": processed, "failures": failures[:5]}))
        return {"row_count": row_count, "processed_rows": processed, "status": "processed"}

    def _open_first_table_row(self, page: Any) -> dict[str, Any]:
        rows = self._table_rows(page)
        if rows.count() == 0:
            return {"row_count": 0, "opened": False}
        self._click_row_entry(rows.first)
        page.wait_for_timeout(500)
        return {"row_count": rows.count(), "opened": True}

    def _click_row_entry(self, row: Any) -> None:
        selectors = [
            "a",
            "button",
            "[role='button']",
            ".ant-btn",
            ".el-button",
            "td a",
            "td button",
        ]
        for selector in selectors:
            try:
                candidate = row.locator(selector)
                count = candidate.count()
                if count > 0:
                    candidate.first.click()
                    return
            except PlaywrightError:
                continue
        try:
            row.dblclick()
            return
        except PlaywrightError as exc:
            raise RuntimeError("No clickable row entry was found.") from exc

    def _wait_for_dialog(self, page: Any, *, timeout_ms: int = 5_000) -> bool:
        selectors = [
            "[role='dialog']",
            "[aria-modal='true']",
            ".ant-modal",
            ".el-dialog",
            ".modal",
            ".drawer",
            ".ant-drawer",
            ".el-drawer",
        ]
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                if locator.count() > 0:
                    locator.wait_for(state="visible", timeout=timeout_ms)
                    return True
            except PlaywrightError:
                continue
        return False

    def _close_dialog_by_common_controls(self, page: Any) -> bool:
        for name in ["返回", "取消", "关闭", "确定", "我知道了"]:
            try:
                button = page.get_by_role("button", name=name, exact=True)
                if button.count() > 0:
                    button.first.click()
                    page.wait_for_timeout(300)
                    return True
                text = page.get_by_text(name, exact=True)
                if text.count() == 1:
                    text.click()
                    page.wait_for_timeout(300)
                    return True
            except PlaywrightError:
                continue
        for selector in [
            ".ant-modal-close",
            ".el-dialog__headerbtn",
            ".modal .close",
            "[aria-label='Close']",
            "[aria-label='关闭']",
            "[title='关闭']",
        ]:
            try:
                candidate = page.locator(selector)
                if candidate.count() > 0:
                    candidate.first.click()
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

    def _write_dom_snapshot(self, page: Any, writer: ArtifactWriter, step_number: int) -> str | None:
        try:
            path = writer.dom_snapshot_path(step_number)
            path.write_text(page.content(), encoding="utf-8")
            return writer.relative(path)
        except PlaywrightError:
            return None

    def _write_accessibility_snapshot(self, page: Any, writer: ArtifactWriter, step_number: int) -> str | None:
        try:
            path = writer.accessibility_snapshot_path(step_number)
            snapshot = page.accessibility.snapshot()
            path.write_text(_json_dumps(snapshot), encoding="utf-8")
            return writer.relative(path)
        except PlaywrightError:
            return None


def _require_locator(result: Any) -> Any:
    if result.locator is None:
        raise RuntimeError(result.fallback_reason or result.reason)
    return result.locator


AUTH_REQUIRED_ACTIONS = {
    "navigate_path",
    "navigate_menu",
    "query_table",
    "query_table_count",
    "open_table_row",
    "open_row_link_or_detail",
    "process_table_rows",
    "for_each_table_row",
    "click_table_row_action",
    "create_record",
    "update_record",
    "delete_record",
    "approval_pass",
    "approval_reject",
    "view_detail",
    "auto_fill_form",
    "fill_form",
    "select",
    "upload_file",
    "wait_for_dialog",
    "close_dialog_by_common_controls",
}

AUTH_REQUIRED_INTENTS = {
    "enter_page",
    "navigate_path",
    "query_list",
    "open_table_row",
    "process_table_rows",
    "click_table_row_action",
    "create_record",
    "update_record",
    "delete_record",
    "view_detail",
    "view_flow",
    "approval_pass",
    "approval_reject",
    "fill_form",
    "fill_field",
    "select_dropdown",
    "select_date",
    "select_date_range",
    "select_org",
    "select_person",
    "select_tree_node",
    "select_from_dialog",
    "upload_file",
    "assert_result",
}


def _step_requires_auth(step: dict[str, Any]) -> bool:
    preconditions = [str(item) for item in step.get("preconditions") or []]
    if "auth_state_logged_in" in preconditions:
        return True
    action = str(step.get("action") or "")
    target = str(step.get("target") or "")
    intent = str(step.get("intent") or (step.get("operationIntent") or {}).get("intent") or "")
    if action == "business_goal" and ("登录" in target or intent in {"login", "login_system", "username_password_login"}):
        return False
    if action in AUTH_REQUIRED_ACTIONS:
        return True
    if action == "business_goal" and intent not in {"", "login", "login_system", "username_password_login"}:
        return intent in AUTH_REQUIRED_INTENTS
    return intent in AUTH_REQUIRED_INTENTS


def _auth_decision(result: AuthStateResult) -> str:
    if result.authState == "login_success":
        return "continue_run"
    if result.authState in {"login_failed", "login_page", "login_requires_manual_action"}:
        return "skip_and_fail_run"
    return "continue_with_unknown_auth_state"


def _auth_failure_type(result: AuthStateResult) -> str:
    if result.authState == "login_failed":
        return "login_failed"
    if result.authState == "login_page":
        return "auth_not_logged_in"
    if result.authState == "login_requires_manual_action":
        return "login_requires_manual_action"
    return str(result.failureType or "precondition_auth_not_satisfied")


def _auth_error_summary(result: AuthStateResult) -> str:
    if result.authState == "login_failed":
        return (
            "login_failed: 检测到目标系统返回登录失败提示，当前仍停留在登录页面。"
            "后续业务步骤已停止。可能原因包括用户名或密码错误、账号被禁用、AD 账号未绑定或密码未同步。"
        )
    if result.authState == "login_page":
        return "auth_not_logged_in: 当前仍停留在登录页面，登录未完成，因此不执行后续业务步骤。"
    if result.authState == "login_requires_manual_action":
        return "login_requires_manual_action: 登录后需要人工处理，例如强制修改密码，因此不执行后续业务步骤。"
    return f"precondition_auth_not_satisfied: {result.reason}"


def _auth_runtime_message(result: AuthStateResult) -> str:
    if result.authState == "login_failed":
        return "当前仍停留在登录页面，且检测到登录失败提示，后续业务步骤不会继续执行。"
    if result.authState == "login_page":
        return "当前仍是登录页面，登录未完成，后续业务步骤不会继续执行。"
    if result.authState == "login_requires_manual_action":
        return "登录后需要人工处理，后续业务步骤已停止。"
    return "认证前置条件未满足，后续业务步骤已停止。"


def _locator_outcome(result: Any) -> dict[str, Any]:
    return {
        "locator_strategy": result.strategy,
        "element_ref": result.element_ref,
        "confidence": result.confidence,
        "reason": result.reason,
        "needs_vision_fallback": result.needs_vision_fallback,
        "fallback_reason": result.fallback_reason,
        "candidates": result.candidates,
    }


def _outcome(strategy: str, element_ref: str, confidence: float, reason: str) -> dict[str, Any]:
    return {
        "locator_strategy": strategy,
        "element_ref": element_ref,
        "confidence": confidence,
        "reason": reason,
        "needs_vision_fallback": False,
        "fallback_reason": None,
        "candidates": [],
    }


def _redact_step(step: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(step)
    target = str(redacted.get("target") or "").lower()
    if "password" in target or "密码" in target or redacted.get("secret_ref") or "password" in redacted:
        redacted["value"] = "***REDACTED***"
        redacted.pop("password", None)
    if isinstance(redacted.get("credentials"), dict):
        credentials = dict(redacted["credentials"])
        if "password" in credentials:
            credentials.pop("password")
            credentials["secret_ref"] = credentials.get("secret_ref", "redacted_password")
        redacted["credentials"] = credentials
    return redacted


def _normalize_runtime_dsl(dsl: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(dsl)
    steps = []
    for step in normalized.get("steps") or []:
        if not isinstance(step, dict):
            continue
        current = dict(step)
        action = str(current.get("action") or "")
        target = str(current.get("target") or "")
        segments = _runtime_path_segments(current.get("pathSegments") or target)
        if action == "navigate_path" and len(segments) >= 2:
            current["pathSegments"] = segments
            current["navigationType"] = current.get("navigationType") or "menu_path"
        elif action in {"business_goal", "navigate_menu", "click"} and len(segments) >= 2:
            current["originalAction"] = action
            current["originalTarget"] = target
            current["action"] = "navigate_path"
            current["pathSegments"] = segments
            current["navigationType"] = "menu_path"
            current["normalizedBy"] = "executor_runtime"
        if _step_requires_auth(current):
            preconditions = [str(item) for item in current.get("preconditions") or [] if str(item).strip()]
            if "auth_state_logged_in" not in preconditions:
                preconditions.append("auth_state_logged_in")
            current["preconditions"] = preconditions
        steps.append(current)
    normalized["steps"] = steps
    return normalized


def _runtime_path_segments(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_clean_runtime_segment(str(item), index) for index, item in enumerate(value) if _clean_runtime_segment(str(item), index)]
    text = str(value or "").strip()
    if not text or "://" in text or not re.search(r"[/>\-→\\]", text):
        return []
    return [
        cleaned
        for index, segment in enumerate(re.split(r"\s*(?:/|>|-|→|\\)\s*", text))
        if (cleaned := _clean_runtime_segment(segment, index))
    ]


def _clean_runtime_segment(segment: str, index: int) -> str:
    cleaned = segment.strip().strip("“”\"'，,。；;：:")
    if index == 0:
        cleaned = re.sub(r"^(进入|打开|点击|导航到|访问|前往|切换到|跳转到)", "", cleaned).strip()
    return cleaned


def _compact_observation(data: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {
        "url": data.get("url"),
        "title": data.get("title"),
        "pageType": data.get("pageType"),
        "visibleTexts": (data.get("visibleTexts") or [])[:30],
    }
    for key in [
        "menus",
        "buttons",
        "links",
        "inputs",
        "textareas",
        "selects",
        "comboboxes",
        "radios",
        "checkboxes",
        "datePickers",
        "treeSelectors",
        "orgSelectors",
        "personSelectors",
        "fileUploads",
        "tables",
        "dialogs",
        "drawers",
        "tabs",
        "breadcrumbs",
        "toasts",
        "loadingIndicators",
        "iframes",
    ]:
        compact[key] = _compact_items(data.get(key) or [], limit=12)
    return compact


def _compact_items(items: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    compacted = []
    for item in items[:limit]:
        compacted.append(
            {
                key: item.get(key)
                for key in [
                    "elementRef",
                    "text",
                    "label",
                    "controlType",
                    "dialogType",
                    "title",
                    "area",
                    "level",
                    "parentText",
                    "required",
                    "readonly",
                    "visible",
                    "enabled",
                    "headers",
                    "emptyState",
                    "frameIndex",
                    "src",
                    "accessible",
                    "selector",
                ]
                if key in item
            }
        )
    return compacted


def _error_summary(exc: Exception) -> str:
    if isinstance(exc, PlaywrightTimeoutError):
        return f"Playwright timeout: {exc}"
    return str(exc)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _duration_ms(started_at: str, ended_at: str) -> int:
    started = datetime.fromisoformat(started_at)
    ended = datetime.fromisoformat(ended_at)
    return int((ended - started).total_seconds() * 1000)


def _json_dumps(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _sandbox_metadata(provider: SandboxProvider) -> dict[str, Any]:
    mode = os.getenv("EXECUTOR_MODE", "local").strip().lower() or "local"
    cube_mock = _env_bool("CUBE_MOCK", True)
    local_browser = _env_bool("LOCAL_BROWSER", True)
    provider_name = provider.__class__.__name__
    is_cube = mode == "cube" or provider_name == "CubeSandboxProvider"
    if is_cube:
        mode_label = "Cube Sandbox"
        if cube_mock or local_browser:
            starting_message = "正在拉起 Cube Sandbox 执行环境，并使用本地浏览器承载本阶段运行。"
            ready_message = "Cube Sandbox 执行环境已就绪，已准备开始页面操作。"
        else:
            starting_message = "正在拉起 Cube Sandbox 执行环境。"
            ready_message = "Cube Sandbox 执行环境已就绪。"
    else:
        mode_label = "本地 Headless Chromium"
        starting_message = "正在启动本地 Headless Chromium 执行环境。"
        ready_message = "本地 Headless Chromium 执行环境已就绪。"
    return {
        "mode": mode,
        "mode_label": mode_label,
        "provider": provider_name,
        "cube_mock": cube_mock,
        "local_browser": local_browser,
        "cube_api_url": _safe_env_url("CUBE_API_URL"),
        "cube_cdp_port": os.getenv("CUBE_CDP_PORT", ""),
        "sandbox_status": "starting",
        "starting_message": starting_message,
        "ready_message": ready_message,
    }


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _safe_env_url(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    if not value:
        return None
    return value


def _runtime_event(
    message_type: str,
    phase: str,
    content: str,
    method: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "type": message_type,
        "phase": phase,
        "content": content,
        "method": method,
        "metadata": metadata or {},
    }
