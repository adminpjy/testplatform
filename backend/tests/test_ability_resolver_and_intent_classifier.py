from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.base import Base
from app.services.abilities import ensure_base_ability_rules
from app.services.ability_resolver import annotate_dsl_with_abilities, resolve_abilities
from app.services.operation_intent_classifier import OperationIntentClassifier


def test_operation_intent_classifier_recognizes_common_mis_intents() -> None:
    classifier = OperationIntentClassifier()
    assert classifier.classify(action="business_goal", target="工作台/我的待办").intent == "navigate_path"
    assert classifier.classify(target="审批通过").intent == "approval_pass"
    assert classifier.classify(target="查看审批流程").intent == "view_flow"
    assert classifier.classify(target="选择状态").intent == "select_dropdown"
    assert classifier.classify(target="所属组织机构").intent == "select_org"


def test_ability_resolver_matches_navigation_approval_form_dropdown_and_org_rules() -> None:
    with _session() as db:
        cases = [
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


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session = Session(bind=engine)
    ensure_base_ability_rules(session)
    return session
