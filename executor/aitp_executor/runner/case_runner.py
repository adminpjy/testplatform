from datetime import datetime, timezone
from typing import Any, Callable

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from executor.aitp_executor.browser.provider_factory import create_sandbox_provider
from executor.aitp_executor.browser.sandbox_provider import SandboxProvider
from executor.aitp_executor.goal.goal_executor import GoalExecutor
from executor.aitp_executor.locator.auto_form_filler import AutoFormFiller
from executor.aitp_executor.locator.element_locator import ElementLocator
from executor.aitp_executor.reports.artifact_writer import ArtifactWriter
from executor.aitp_executor.reports.report_writer import ReportWriter


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
        self.event_sink = event_sink

    def run(self, *, run_code: str, dsl: dict[str, Any]) -> dict[str, Any]:
        writer = ArtifactWriter(run_code)
        report_writer = ReportWriter(writer)
        started_at = _utc_now()
        steps = dsl.get("steps") or []
        results: list[dict[str, Any]] = []
        status = "passed"
        error_summary = None

        self._emit_runtime(writer, "text", "understanding", "正在理解测试用例", "runner", {"run_code": run_code})
        self._emit_runtime(writer, "progress", "planning", "正在生成测试步骤", "runner", {"steps": len(steps)})
        self._emit_runtime(writer, "progress", "browser", "正在启动浏览器", "playwright", {"headless": True})

        session = self.provider.start()
        try:
            page = session.page
            base_url = dsl.get("baseUrl") or dsl.get("base_url")
            if base_url:
                writer.append_jsonl("execution-trace.jsonl", {"type": "base_url.open", "url": base_url})
                self._emit_runtime(writer, "progress", "open_system", "正在打开系统", "playwright", {"url": base_url})
                page.goto(base_url, wait_until="domcontentloaded")

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
        self._emit_runtime(
            writer,
            "progress",
            "step",
            "步骤开始",
            "runner",
            {"step_number": step_number, "action": action, "target": target},
        )
        if action == "business_goal":
            self._emit_runtime(
                writer,
                "progress",
                "intent",
                "正在识别业务意图",
                "goal_executor",
                {"step_number": step_number, "target": target},
            )
        if action in {"input", "click", "confirm_dialog", "navigate_menu", "select", "upload_file", "business_goal"}:
            self._emit_runtime(
                writer,
                "progress",
                "observe",
                "正在读取页面",
                "page_observer",
                {"step_number": step_number, "action": action, "target": target},
            )
            self._emit_runtime(
                writer,
                "progress",
                "locate",
                "正在分析候选元素",
                "element_locator",
                {"step_number": step_number, "action": action, "target": target},
            )
        if action in {"click", "confirm_dialog", "navigate_menu", "business_goal"}:
            self._emit_runtime(
                writer,
                "progress",
                "action",
                "正在点击",
                "playwright",
                {"step_number": step_number, "target": target},
            )
        if action in {"wait_for_text", "assert_text_exists", "assert_text_not_exists", "assert_url_contains", "business_goal"}:
            self._emit_runtime(
                writer,
                "progress",
                "verify",
                "正在验证",
                "action_verifier",
                {"step_number": step_number, "target": target},
            )
        writer.append_jsonl(
            "execution-trace.jsonl",
            {"type": "step.execute", "step_number": step_number, "step": _redact_step(step)},
        )

        status = "passed"
        error_summary = None
        locator_strategy = None
        element_ref = None
        confidence = 1.0
        reason = "executed"
        needs_vision_fallback = False
        fallback_reason = None
        candidates: list[dict[str, Any]] = []
        try:
            outcome = self._execute_action(page, step, dsl)
            locator_strategy = outcome.get("locator_strategy")
            element_ref = outcome.get("element_ref")
            confidence = outcome.get("confidence", 1.0)
            reason = outcome.get("reason", "executed")
            needs_vision_fallback = outcome.get("needs_vision_fallback", False)
            fallback_reason = outcome.get("fallback_reason")
            candidates = outcome.get("candidates", [])
        except Exception as exc:
            status = "failed"
            error_summary = _error_summary(exc)
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

    def _execute_action(self, page: Any, step: dict[str, Any], dsl: dict[str, Any]) -> dict[str, Any]:
        action = step.get("action")
        target = step.get("target") or step.get("selector") or ""

        if action == "open_url":
            url = step.get("url") or target
            page.goto(url, wait_until="domcontentloaded")
            return _outcome("url", str(url), 1.0, "url opened")

        if action == "input":
            result = self.element_locator.locate(page, action="input", target=str(target), step=step)
            _require_locator(result).fill(str(step.get("value") or ""))
            return _locator_outcome(result)

        if action in {"click", "confirm_dialog"}:
            result = self.element_locator.locate(page, action="click", target=str(target), step=step)
            _require_locator(result).click()
            return _locator_outcome(result)

        if action == "navigate_menu":
            result = self.element_locator.locate(page, action="navigate_menu", target=str(target), step=step)
            _require_locator(result).click()
            return _locator_outcome(result)

        if action in {"wait_for_text", "assert_text_exists"}:
            page.get_by_text(str(target), exact=False).wait_for(state="visible")
            return _outcome("text_visible", str(target), 1.0, "text visible")

        if action == "assert_text_not_exists":
            count = page.get_by_text(str(target), exact=False).count()
            if count > 0:
                raise AssertionError(f"Text should not exist: {target}")
            return _outcome("text_absent", str(target), 1.0, "text absent")

        if action == "assert_url_contains":
            current_url = page.url
            if str(target) not in current_url:
                raise AssertionError(f"URL does not contain '{target}': {current_url}")
            return _outcome("url_contains", str(target), 1.0, "url contains target")

        if action == "select":
            result = self.element_locator.locate(page, action="select", target=str(target), step=step)
            _require_locator(result).select_option(str(step.get("value") or target))
            return _locator_outcome(result)

        if action == "upload_file":
            result = self.element_locator.locate(page, action="upload_file", target=str(target), step=step)
            _require_locator(result).set_input_files(str(step.get("file_path") or step.get("value") or ""))
            return _locator_outcome(result)

        if action == "wait":
            page.wait_for_timeout(int(step.get("ms") or step.get("timeoutMs") or 1000))
            return _outcome("timeout", str(step.get("ms") or step.get("timeoutMs") or 1000), 1.0, "waited")

        if action == "query_table":
            page.locator("table").first.wait_for(state="visible")
            return _outcome("table_visible", "table", 1.0, "table visible")

        if action == "auto_fill_form":
            test_data = dict(dsl.get("testData") or {})
            test_data.update(step.get("testData") or {})
            result = self.auto_form_filler.fill(page, test_data=test_data)
            if result.needs_clarification:
                raise RuntimeError("needs_clarification:" + ",".join(result.needs_clarification))
            return _outcome(
                "auto_form_filler",
                "form",
                0.82,
                _json_dumps(
                    {
                        "filled": result.filled,
                        "defaults_used": result.defaults_used,
                        "skipped": result.skipped,
                    }
                ),
            )

        if action == "click_table_row_action":
            row_text = str(step.get("rowText") or step.get("row_text") or "")
            action_name = str(step.get("button") or step.get("buttonText") or target)
            row = page.locator("tbody tr").filter(has_text=row_text)
            row.get_by_role("button", name=action_name, exact=True).click()
            return _outcome("table_row_action_exact", f"{row_text}:{action_name}", 0.95, "table row action")

        if action == "business_goal":
            return self.goal_executor.execute(page, target=str(target), step=step)

        raise ValueError(f"Unsupported DSL action: {action}")

    def _write_screenshot(self, page: Any, writer: ArtifactWriter, step_number: int) -> str | None:
        try:
            path = writer.screenshot_path(step_number)
            page.screenshot(path=str(path), full_page=True)
            return writer.relative(path)
        except PlaywrightError:
            return None

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
    if "password" in target or "密码" in target or redacted.get("secret_ref"):
        redacted["value"] = "***REDACTED***"
    return redacted


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
