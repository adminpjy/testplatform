from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.abilities.common_operation_model import (
    SUPPORTED_ABILITY_RULE_TYPES,
    SUPPORTED_FAILURE_PATTERNS,
    SUPPORTED_KNOWLEDGE_TYPES,
    SUPPORTED_OPERATION_INTENTS,
)


def test_common_operation_rule_types_cover_required_mis_abilities() -> None:
    required = {
        "login",
        "global_interruption",
        "navigation",
        "query",
        "table_detection",
        "table_row_action",
        "form_control",
        "form_fill",
        "dropdown",
        "date_picker",
        "org_selector",
        "person_selector",
        "tree_selector",
        "dialog_selector",
        "file_upload",
        "detail_navigation",
        "create",
        "update",
        "delete",
        "approval_workflow",
        "assertion",
        "recovery_policy",
        "vision_fallback",
        "candidate_ranking",
    }
    assert required.issubset(set(SUPPORTED_ABILITY_RULE_TYPES))


def test_common_operation_intents_and_knowledge_types_are_registered() -> None:
    assert "navigate_path" in SUPPORTED_OPERATION_INTENTS
    assert "process_table_rows" in SUPPORTED_OPERATION_INTENTS
    assert "select_from_dialog" in SUPPORTED_OPERATION_INTENTS
    assert "navigation_path" in SUPPORTED_KNOWLEDGE_TYPES
    assert "table_row_action" in SUPPORTED_KNOWLEDGE_TYPES
    assert "recovery_solution" in SUPPORTED_KNOWLEDGE_TYPES


def test_common_failure_patterns_are_registered() -> None:
    assert "menu_child_not_found" in SUPPORTED_FAILURE_PATTERNS
    assert "table_no_action_found" in SUPPORTED_FAILURE_PATTERNS
    assert "form_required_field_missing" in SUPPORTED_FAILURE_PATTERNS
    assert "vision_fallback_not_configured" in SUPPORTED_FAILURE_PATTERNS
