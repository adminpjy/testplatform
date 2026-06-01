from pathlib import Path
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.test_run_execution import (
    _apply_executor_runtime_env,
    _apply_instruction_record_criteria,
    _hydrate_login_steps,
    _insert_intervention_steps,
    _intervention_plan_steps_to_dsl,
    _redact_dsl_for_storage,
    _source_dsl_for_rerun,
)
from app.services import test_run_execution as execution_service


def test_hydrate_login_fill_form_step_with_account_credentials() -> None:
    dsl = {"steps": [{"action": "fill_form", "target": "登录表单"}]}

    _hydrate_login_steps(dsl, SimpleNamespace(username="tester01"), "secret123")

    assert dsl["steps"][0]["formData"] == {"username": "tester01", "password": "secret123"}


def test_redact_login_form_data_before_storage() -> None:
    dsl = {
        "credentials": {"username": "tester01", "password": "secret123"},
        "testData": {"username": "tester01", "password": "secret123"},
        "steps": [
            {
                "action": "fill_form",
                "target": "登录表单",
                "formData": {"username": "tester01", "password": "secret123"},
            }
        ],
    }

    redacted = _redact_dsl_for_storage(dsl)

    assert redacted["credentials"] == {"username": "tester01", "secret_ref": "redacted_password"}
    assert redacted["testData"]["password"] == "***REDACTED***"
    assert redacted["steps"][0]["formData"]["password"] == "***REDACTED***"


def test_intervention_plan_steps_are_translated_to_recovery_dsl() -> None:
    plan = {
        "steps": [
            {"action": "wait", "value": "2000", "reason": "等待页面稳定"},
            {"action": "close_dialog", "target": "当前弹窗"},
            {"action": "retry_step", "target": "S003"},
        ]
    }

    steps = _intervention_plan_steps_to_dsl(plan)

    assert steps[0]["action"] == "wait"
    assert steps[0]["ms"] == 2000
    assert steps[1]["action"] == "close_dialog_by_common_controls"
    assert all(step["source"] == "human_intervention" for step in steps)
    assert not any(step.get("sourceAction") == "retry_step" for step in steps)


def test_insert_intervention_steps_before_failed_step() -> None:
    dsl = {
        "steps": [
            {"action": "open_url", "target": "/"},
            {"action": "fill_form", "target": "登录表单"},
            {"action": "click", "target": "登录按钮"},
        ]
    }
    recovery_steps = [{"action": "wait", "ms": 1000, "source": "human_intervention"}]

    result = _insert_intervention_steps(dsl, recovery_steps, failed_index=2)

    assert [step["action"] for step in result["steps"]] == ["open_url", "fill_form", "wait", "click"]


def test_apply_executor_runtime_env_bridges_playwright_certificate_settings(monkeypatch) -> None:
    monkeypatch.setattr(execution_service.app_settings, "executor_mode", "cube")
    monkeypatch.setattr(execution_service.app_settings, "playwright_ignore_https_errors", True)
    monkeypatch.setattr(execution_service.app_settings, "playwright_auto_continue_security_interstitial", True)
    monkeypatch.delenv("PLAYWRIGHT_IGNORE_HTTPS_ERRORS", raising=False)
    monkeypatch.delenv("PLAYWRIGHT_AUTO_CONTINUE_SECURITY_INTERSTITIAL", raising=False)

    _apply_executor_runtime_env()

    assert os.environ["EXECUTOR_MODE"] == "cube"
    assert os.environ["PLAYWRIGHT_IGNORE_HTTPS_ERRORS"] == "true"
    assert os.environ["PLAYWRIGHT_AUTO_CONTINUE_SECURITY_INTERSTITIAL"] == "true"


def test_source_dsl_for_rerun_requires_saved_executable_dsl() -> None:
    run = SimpleNamespace(dsl_snapshot=None, dsl_json=None, account_id=None)

    try:
        _source_dsl_for_rerun(run, account=None)
    except ValueError as exc:
        assert "没有保存可执行 DSL" in str(exc)
    else:
        raise AssertionError("Expected missing DSL to fail.")


def test_source_dsl_for_rerun_blocks_redacted_runtime_password_without_account() -> None:
    run = SimpleNamespace(
        dsl_snapshot={
            "caseName": "login",
            "baseUrl": "https://example.test",
            "credentials": {"username": "tester01", "secret_ref": "runtime_form_password"},
            "steps": [{"action": "business_goal", "target": "用户登录"}],
        },
        dsl_json=None,
        account_id=None,
    )

    try:
        _source_dsl_for_rerun(run, account=None)
    except ValueError as exc:
        assert "临时输入的密码" in str(exc)
    else:
        raise AssertionError("Expected redacted runtime password to fail without account.")


def test_source_dsl_for_rerun_allows_saved_dsl_with_account() -> None:
    run = SimpleNamespace(
        dsl_snapshot={
            "caseName": "login",
            "baseUrl": "https://example.test",
            "credentials": {"username": "tester01", "secret_ref": "runtime_form_password"},
            "steps": [{"action": "business_goal", "target": "用户登录"}],
        },
        dsl_json=None,
        account_id=1,
    )

    dsl = _source_dsl_for_rerun(run, account=SimpleNamespace(id=1))

    assert dsl["steps"][0]["target"] == "用户登录"


def test_instruction_record_criteria_overrides_execution_test_data() -> None:
    test_data = _apply_instruction_record_criteria({"实例号": "26097", "其他": "保留"}, "审批实例号“26058”")

    assert test_data == {"实例号": "26058", "其他": "保留"}
