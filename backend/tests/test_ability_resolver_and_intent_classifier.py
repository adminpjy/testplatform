from pathlib import Path
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.base import Base
from app.api.abilities import delete_ability_rule
from app.models import AbilityRule
from app.services.abilities import ensure_base_ability_rules
from app.services.abilities import list_rules
from app.services.abilities import validate_rule_config
from app.services.ability_resolver import annotate_dsl_with_abilities, resolve_abilities
from app.services.operation_intent_classifier import OperationIntentClassifier


def test_operation_intent_classifier_recognizes_common_mis_intents() -> None:
    classifier = OperationIntentClassifier()
    assert classifier.classify(action="business_goal", target="工作台/我的待办").intent == "navigate_path"
    assert classifier.classify(action="open_url", target="https://work.bypc.com.cn", instruction="输入账号密码").intent == "enter_page"
    assert classifier.classify(action="business_goal", target="登录系统", instruction="输入账号密码").intent == "login"
    assert classifier.classify(target="审批通过").intent == "approval_pass"
    assert classifier.classify(target="查看审批流程").intent == "view_flow"
    assert classifier.classify(target="选择状态").intent == "select_dropdown"
    assert classifier.classify(target="所属组织机构").intent == "select_org"


def test_ability_resolver_matches_navigation_approval_form_dropdown_and_org_rules() -> None:
    with _session() as db:
        cases = [
            ("login", ["login", "risk_policy"], "LOGIN-USERNAME-PASSWORD-v1"),
            ("navigate_path", ["navigation"], "NAV-MENU-PATH-v1"),
            ("approval_pass", ["approval_workflow"], "APPROVAL-PASS-v1"),
            ("fill_form", ["form_fill", "form_control"], "FORM-FILL-TEXT-v1"),
            ("select_dropdown", ["dropdown"], "DROPDOWN-CUSTOM-SELECT-v1"),
            ("select_org", ["org_selector", "tree_selector", "dialog_selector"], "ORG-REQUIRE-CLARIFICATION-v1"),
        ]
        for intent, rule_types, expected_rule in cases:
            resolution = resolve_abilities(
                db,
                {
                    "intent": intent,
                    "ruleTypes": rule_types,
                    "environment": "test",
                    "pageContext": {"target": "工作台/我的待办 审批通过 选择状态 所属组织机构"},
                },
            )
            selected_codes = {rule["rule_code"] for rule in resolution["selectedRules"]}
            assert expected_rule in selected_codes
            assert resolution["source"] == "database"


def test_ability_resolver_exposes_executable_rule_config() -> None:
    with _session() as db:
        resolution = resolve_abilities(
            db,
            {
                "intent": "process_table_rows",
                "ruleTypes": ["table_row_action", "table_detection"],
                "environment": "test",
                "pageContext": {"target": "我的待办列表", "instruction": "审批所有待办"},
            },
        )
        todo_rule = next(rule for rule in resolution["selectedRules"] if rule["rule_code"] == "ROW-OPEN-TODO-v1")
        assert todo_rule["actionConfig"]["rowLinkSelectors"]
        assert "js_click" in todo_rule["actionConfig"]["clickStrategies"]
        assert todo_rule["successCriteria"]["criteria"]


def test_annotate_dsl_with_abilities_adds_intent_and_rule_metadata() -> None:
    with _session() as db:
        dsl = {
            "caseName": "case",
            "steps": [
                {"action": "navigate_path", "target": "工作台/我的待办", "pathSegments": ["工作台", "我的待办"]},
                {"action": "auto_fill_form", "target": "新增表单"},
            ],
        }
        annotated = annotate_dsl_with_abilities(db, dsl, instruction="进入工作台/我的待办后填写新增表单")
        first = annotated["steps"][0]
        second = annotated["steps"][1]
        assert first["operationIntent"]["intent"] == "navigate_path"
        assert "NAV-MENU-PATH-v1" in first["ruleHints"]
        assert second["operationIntent"]["intent"] == "fill_form"
        assert "FORM-FILL-TEXT-v1" in second["ruleHints"]


def test_annotate_dsl_with_abilities_recursively_adds_rule_metadata_to_row_steps() -> None:
    with _session() as db:
        dsl = {
            "caseName": "batch approval",
            "steps": [
                {
                    "action": "process_table_rows",
                    "target": "我的待办列表",
                    "loopPolicy": {
                        "rowSteps": [
                            {"action": "business_goal", "target": "审批通过", "intent": "approval_pass"}
                        ]
                    },
                }
            ],
        }

        annotated = annotate_dsl_with_abilities(
            db,
            dsl,
            instruction="审批所有待办",
            project_id=5,
            system_id=7,
            environment="test",
        )

        assert annotated["runtimeContext"] == {"projectId": 5, "systemId": 7, "environment": "test"}
        process_step = annotated["steps"][0]
        row_step = process_step["loopPolicy"]["rowSteps"][0]
        assert process_step["abilityResolution"]["source"] == "database"
        assert row_step["operationIntent"]["intent"] == "approval_pass"
        assert row_step["abilityResolution"]["source"] == "database"
        assert "APPROVAL-PASS-v1" in row_step["ruleHints"]
        assert process_step["rowSteps"][0]["ruleHints"] == row_step["ruleHints"]


def test_database_resolver_does_not_fallback_to_builtin_when_database_rules_are_absent() -> None:
    with _session() as db:
        for rule in db.scalars(select(AbilityRule).where(AbilityRule.rule_type == "approval_workflow")).all():
            rule.status = "archived"
        db.commit()

        resolution = resolve_abilities(
            db,
            {
                "intent": "approval_pass",
                "ruleTypes": ["approval_workflow"],
                "environment": "test",
                "pageContext": {"target": "审批通过"},
            },
        )

        assert resolution["source"] == "database"
        assert resolution["matchedRules"] == []
        assert resolution["selectedRules"] == []


def test_delete_ability_rule_archives_and_default_list_hides_it() -> None:
    with _session() as db:
        rule = db.scalar(select(AbilityRule).where(AbilityRule.rule_code == "NAV-MENU-PATH-v1"))
        assert rule is not None

        delete_ability_rule(rule.id, db)

        archived = db.get(AbilityRule, rule.id)
        assert archived is not None
        assert archived.status == "archived"
        assert archived.production_enabled is False
        assert all(item.id != rule.id for item in list_rules(db))
        assert any(item.id == rule.id for item in list_rules(db, rule_status="archived"))

        ensure_base_ability_rules(db)
        resynced = db.get(AbilityRule, rule.id)
        assert resynced is not None
        assert resynced.status == "archived"
        assert resynced.production_enabled is False


def test_ensure_base_ability_rules_does_not_overwrite_existing_rule_config() -> None:
    with _session() as db:
        rule = db.scalar(select(AbilityRule).where(AbilityRule.rule_code == "APPROVAL-PASS-v1"))
        assert rule is not None
        rule.action_config_json = {"submitLabels": ["自定义提交"], "formReadyTexts": ["自定义表单"]}
        rule.rule_name = "自定义审批通过"
        db.add(rule)
        db.commit()

        ensure_base_ability_rules(db)

        preserved = db.scalar(select(AbilityRule).where(AbilityRule.rule_code == "APPROVAL-PASS-v1"))
        assert preserved is not None
        assert preserved.rule_name == "自定义审批通过"
        assert preserved.action_config_json == {"submitLabels": ["自定义提交"], "formReadyTexts": ["自定义表单"]}


def test_validate_rule_config_checks_executable_rule_shape() -> None:
    with _session() as db:
        rule = db.scalar(select(AbilityRule).where(AbilityRule.rule_code == "ROW-OPEN-TODO-v1"))
        assert rule is not None

        result = validate_rule_config(db, rule)

        assert result["status"] == "passed"
        assert any(check["scope"] == "executor_config" and check["passed"] for check in result["checks"])


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session = Session(bind=engine)
    ensure_base_ability_rules(session)
    return session
