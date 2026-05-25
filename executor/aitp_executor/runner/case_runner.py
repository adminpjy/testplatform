from datetime import datetime, timezone
from typing import Any

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from executor.aitp_executor.browser.local_playwright_provider import LocalPlaywrightProvider
from executor.aitp_executor.browser.sandbox_provider import SandboxProvider
from executor.aitp_executor.reports.artifact_writer import ArtifactWriter
from executor.aitp_executor.reports.report_writer import ReportWriter


class CaseRunner:
    def __init__(self, provider: SandboxProvider | None = None) -> None:
        self.provider = provider or LocalPlaywrightProvider(headless=True)

    def run(self, *, run_code: str, dsl: dict[str, Any]) -> dict[str, Any]:
        writer = ArtifactWriter(run_code)
        report_writer = ReportWriter(writer)
        started_at = _utc_now()
        steps = dsl.get("steps") or []
        results: list[dict[str, Any]] = []
        status = "passed"
        error_summary = None

        writer.append_jsonl(
            "runtime-stream.jsonl",
            {"type": "run.started", "run_code": run_code, "message": "测试执行开始"},
        )

        session = self.provider.start()
        try:
            page = session.page
            base_url = dsl.get("baseUrl") or dsl.get("base_url")
            if base_url:
                writer.append_jsonl(
                    "execution-trace.jsonl",
                    {"type": "base_url.open", "url": base_url},
                )
                page.goto(base_url, wait_until="domcontentloaded")

            for index, step in enumerate(steps, start=1):
                result = self._run_step(page, writer, index, step)
                results.append(result)
                if result["status"] != "passed":
                    status = "failed"
                    error_summary = result.get("error_summary")
                    break
        except Exception as exc:
            status = "failed"
            error_summary = str(exc)
            writer.append_jsonl(
                "runtime-stream.jsonl",
                {"type": "run.failed", "run_code": run_code, "message": error_summary},
            )
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
        report_path = report_writer.write(summary, results)
        writer.append_jsonl(
            "runtime-stream.jsonl",
            {"type": f"run.{status}", "run_code": run_code, "message": f"测试执行{status}"},
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

    def _run_step(self, page: Any, writer: ArtifactWriter, step_number: int, step: dict[str, Any]) -> dict[str, Any]:
        started_at = _utc_now()
        action = str(step.get("action") or "")
        target = str(step.get("target") or step.get("selector") or "")
        writer.append_jsonl(
            "runtime-stream.jsonl",
            {
                "type": "step.started",
                "step_number": step_number,
                "action": action,
                "target": target,
            },
        )
        writer.append_jsonl(
            "execution-trace.jsonl",
            {"type": "step.execute", "step_number": step_number, "step": _redact_step(step)},
        )

        status = "passed"
        error_summary = None
        locator_strategy = None
        element_ref = None
        try:
            locator_strategy, element_ref = self._execute_action(page, step)
        except Exception as exc:
            status = "failed"
            error_summary = _error_summary(exc)
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
            "confidence": 1.0 if status == "passed" else 0.0,
            "reason": "executed" if status == "passed" else "execution_failed",
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
            },
        )
        writer.append_jsonl(
            "runtime-stream.jsonl",
            {
                "type": "step.succeeded" if status == "passed" else "step.failed",
                "step_number": step_number,
                "message": error_summary or "步骤执行成功",
            },
        )
        return result

    def _execute_action(self, page: Any, step: dict[str, Any]) -> tuple[str | None, str | None]:
        action = step.get("action")
        target = step.get("target") or step.get("selector") or ""

        if action == "open_url":
            url = step.get("url") or target
            page.goto(url, wait_until="domcontentloaded")
            return "url", str(url)

        if action == "input":
            locator, strategy = _resolve_input_locator(page, step)
            locator.fill(str(step.get("value") or ""))
            return strategy, str(target)

        if action in {"click", "confirm_dialog"}:
            locator, strategy = _resolve_click_locator(page, step)
            locator.click()
            return strategy, str(target)

        if action == "navigate_menu":
            locator = page.locator("aside").get_by_role("button", name=str(target), exact=True)
            locator.click()
            return "side_menu_button_exact", str(target)

        if action in {"wait_for_text", "assert_text_exists"}:
            page.get_by_text(str(target), exact=False).wait_for(state="visible")
            return "text_visible", str(target)

        if action == "assert_text_not_exists":
            count = page.get_by_text(str(target), exact=False).count()
            if count > 0:
                raise AssertionError(f"Text should not exist: {target}")
            return "text_absent", str(target)

        if action == "assert_url_contains":
            current_url = page.url
            if str(target) not in current_url:
                raise AssertionError(f"URL does not contain '{target}': {current_url}")
            return "url_contains", str(target)

        if action == "select":
            locator, strategy = _resolve_input_locator(page, step)
            locator.select_option(str(step.get("value") or target))
            return strategy, str(target)

        if action == "upload_file":
            locator, strategy = _resolve_input_locator(page, step)
            locator.set_input_files(str(step.get("file_path") or step.get("value") or ""))
            return strategy, str(target)

        if action == "wait":
            page.wait_for_timeout(int(step.get("ms") or step.get("timeoutMs") or 1000))
            return "timeout", str(step.get("ms") or step.get("timeoutMs") or 1000)

        if action == "query_table":
            page.locator("table").first.wait_for(state="visible")
            return "table_visible", "table"

        if action == "click_table_row_action":
            row_text = str(step.get("rowText") or step.get("row_text") or "")
            action_name = str(step.get("button") or step.get("buttonText") or target)
            row = page.locator("tbody tr").filter(has_text=row_text)
            row.get_by_role("button", name=action_name, exact=True).click()
            return "table_row_action_exact", f"{row_text}:{action_name}"

        if action == "business_goal":
            if "审批通过" in str(target):
                page.get_by_role("button", name="审批", exact=True).click()
                return "business_goal_approval_pass", str(target)
            return "business_goal_recorded", str(target)

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


def _resolve_input_locator(page: Any, step: dict[str, Any]) -> tuple[Any, str]:
    if step.get("selector"):
        return page.locator(str(step["selector"])), "css_selector"
    target = str(step.get("target") or "")
    return page.get_by_label(target, exact=True), "label_exact"


def _resolve_click_locator(page: Any, step: dict[str, Any]) -> tuple[Any, str]:
    if step.get("selector"):
        return page.locator(str(step["selector"])), "css_selector"
    target = str(step.get("target") or "")
    if not target:
        raise ValueError("Click step requires target or selector.")
    role = page.get_by_role("button", name=target, exact=True)
    if role.count() > 0:
        return role, "button_exact"
    text = page.get_by_text(target, exact=True)
    if text.count() > 0:
        return text, "text_exact"
    return page.get_by_text(target, exact=False), "text_contains"


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
