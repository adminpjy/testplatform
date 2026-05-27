from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.base import Base
from app.models import FailureSample, TestProject as ProjectModel, TestRun as RunModel, TestStepRun as StepRunModel
from app.services.failure_analyzer import FailureAnalyzer
from app.services.test_run_execution import _add_failure_sample


def test_navigation_failure_does_not_use_vision_as_primary_type() -> None:
    analysis = FailureAnalyzer().analyze_step_failure(
        {
            "action": "navigate_path",
            "target": "工作台/我的待办",
            "error_summary": "vision_fallback_not_configured",
            "fallback_reason": "vision_fallback_not_configured",
        }
    )
    assert analysis["failureType"] == "navigation_path_unresolved"
    assert analysis["visionFallback"] == "not_configured"
    assert any(item["code"] == "try_menu_search" for item in analysis["suggestedRecovery"])


def test_login_failure_overrides_navigation_failure() -> None:
    analysis = FailureAnalyzer().analyze_step_failure(
        {
            "action": "navigate_path",
            "target": "工作台/我的待办",
            "error_summary": "Login was failed, and you have 4 retries. Wrong user name or password.",
            "failure_type": "menu_parent_not_found",
            "failure_details": {
                "auth_state": {
                    "authState": "login_failed",
                    "evidence": ["Login was failed", "Wrong user name or password", "you have 4 retries"],
                }
            },
        }
    )
    assert analysis["failureType"] == "login_failed"
    assert analysis["category"] == "authentication"
    assert any(item["code"] == "check_test_account" for item in analysis["suggestedRecovery"])


def test_protected_step_blocked_keeps_root_cause_login_failed() -> None:
    analysis = FailureAnalyzer().analyze_step_failure(
        {
            "action": "navigate_path",
            "target": "工作台/我的待办",
            "error_summary": "protected_step_blocked_by_login_failure: 当前仍停留在认证中心登录页。",
            "failure_type": "protected_step_blocked_by_login_failure",
            "failure_details": {
                "rootCause": "login_failed",
                "auth_state": {"authState": "login_failed", "remainingRetries": 3},
                "blockedStep": "工作台/我的待办",
                "blockedAction": "navigate_path",
            },
        }
    )
    assert analysis["failureType"] == "protected_step_blocked_by_login_failure"
    assert analysis["rootCause"] == "login_failed"
    assert any(item["code"] == "rerun_login_check" for item in analysis["suggestedRecovery"])


def test_recovery_suggestions_for_common_mis_failures() -> None:
    dropdown = FailureAnalyzer().analyze_step_failure(
        {"action": "select", "target": "状态", "error_summary": "dropdown_option_not_found: 停用"}
    )
    org = FailureAnalyzer().analyze_step_failure(
        {"action": "fill_form", "target": "组织机构", "error_summary": "needs_clarification:组织机构"}
    )
    table = FailureAnalyzer().analyze_step_failure(
        {"action": "click_table_row_action", "target": "审批", "error_summary": "table_no_action_found: 审批"}
    )
    approval = FailureAnalyzer().analyze_step_failure(
        {"action": "business_goal", "target": "审批通过", "error_summary": "approval_result_option_not_found"}
    )
    assert dropdown["failureType"] == "dropdown_option_not_found"
    assert any(item["code"] == "search_option_text" for item in dropdown["suggestedRecovery"])
    assert org["failureType"] == "org_value_missing"
    assert org["suggestedRecovery"] == [{"code": "request_org_value", "label": "提示用户补充组织机构", "automatic": False}]
    assert table["failureType"] == "table_no_action_found"
    assert any(item["code"] == "try_more_actions" for item in table["suggestedRecovery"])
    assert approval["failureType"] == "approval_result_option_not_found"
    assert any(item["code"] == "find_radio_option" for item in approval["suggestedRecovery"])


def test_failure_sample_persists_artifact_paths_and_recovery_analysis() -> None:
    session = _session()
    project = ProjectModel(project_code="P", name="Project", status="active")
    session.add(project)
    session.flush()
    run = RunModel(run_code="RUN-1", project_id=project.id, status="failed")
    session.add(run)
    session.flush()
    step = StepRunModel(run_id=run.id, step_id="S001", status="failed", action="select", target="状态")
    session.add(step)
    session.flush()

    _add_failure_sample(
        session,
        run,
        step,
        {
            "action": "select",
            "target": "状态",
            "status": "failed",
            "error_summary": "dropdown_option_not_found: 停用",
            "screenshot_path": "runs/RUN-1/screenshots/step-001.png",
            "dom_snapshot_path": "runs/RUN-1/dom/step-001.html",
            "accessibility_snapshot_path": "runs/RUN-1/accessibility/step-001.json",
        },
        {
            "locator_debug": "runs/RUN-1/locator-debug.jsonl",
            "runtime_stream": "runs/RUN-1/runtime-stream.jsonl",
            "execution_trace": "runs/RUN-1/execution-trace.jsonl",
            "report": "runs/RUN-1/report.html",
        },
    )
    session.commit()
    sample = session.query(FailureSample).one()
    assert sample.failure_type == "dropdown_option_not_found"
    assert sample.screenshot_path
    assert sample.dom_snapshot_path
    assert sample.accessibility_snapshot_path
    assert sample.locator_debug_path
    assert sample.runtime_stream_path
    assert sample.execution_trace_path
    assert sample.report_path
    assert sample.ai_analysis_json["suggestedRecovery"]
    assert sample.suggested_rule_json["failureType"] == "dropdown_option_not_found"


def test_failure_sample_records_auth_root_cause() -> None:
    session = _session()
    project = ProjectModel(project_code="P2", name="Project 2", status="active")
    session.add(project)
    session.flush()
    run = RunModel(run_code="RUN-2", project_id=project.id, status="failed")
    session.add(run)
    session.flush()
    step = StepRunModel(run_id=run.id, step_id="S003", status="failed", action="navigate_path", target="工作台/我的待办")
    session.add(step)
    session.flush()

    _add_failure_sample(
        session,
        run,
        step,
        {
            "action": "navigate_path",
            "target": "工作台/我的待办",
            "status": "failed",
            "failure_type": "protected_step_blocked_by_login_failure",
            "error_summary": "protected_step_blocked_by_login_failure: Login was failed, and you have 3 retries.",
            "failure_details": {
                "rootCause": "login_failed",
                "auth_state": {"authState": "login_failed", "remainingRetries": 3},
                "evidence": ["Login was failed", "Wrong user name or password", "login form visible"],
                "blockedStep": "工作台/我的待办",
                "blockedAction": "navigate_path",
            },
            "screenshot_path": "runs/RUN-2/screenshots/step-003.png",
            "dom_snapshot_path": "runs/RUN-2/dom/step-003.html",
            "accessibility_snapshot_path": "runs/RUN-2/accessibility/step-003.json",
        },
        {
            "locator_debug": "runs/RUN-2/locator-debug.jsonl",
            "runtime_stream": "runs/RUN-2/runtime-stream.jsonl",
            "execution_trace": "runs/RUN-2/execution-trace.jsonl",
            "report": "runs/RUN-2/report.html",
        },
    )
    session.commit()
    sample = session.query(FailureSample).filter(FailureSample.run_id == run.id).one()
    assert sample.failure_type == "protected_step_blocked_by_login_failure"
    assert sample.ai_analysis_json["rootCause"] == "login_failed"
    assert sample.ai_analysis_json["authState"] == "login_failed"
    assert sample.ai_analysis_json["remainingRetries"] == 3
    assert sample.ai_analysis_json["blockedStep"] == "工作台/我的待办"
    assert sample.suggested_rule_json["candidateRuleType"] == "login"


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return Session(bind=engine)
