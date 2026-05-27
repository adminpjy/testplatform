from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.abilities.common_operation_model import (
    SUPPORTED_ABILITY_RULE_TYPES,
    SUPPORTED_FAILURE_PATTERNS,
    SUPPORTED_KNOWLEDGE_TYPES,
    SUPPORTED_OPERATION_INTENTS,
)
from app.abilities.base_pack import BASE_ABILITY_RULES


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


def test_common_operation_pack_has_unique_builtin_active_rules() -> None:
    codes = [rule["rule_code"] for rule in BASE_ABILITY_RULES]
    assert len(codes) == len(set(codes))
    for rule in BASE_ABILITY_RULES:
        assert rule["status"] == "active"
        assert rule["source"] == "builtin"
        assert rule["version"] == "1.0.0"
        assert rule["production_enabled"] is True


def test_common_operation_pack_contains_required_rule_codes() -> None:
    required_codes = {
        "LOGIN-USERNAME-PASSWORD-v1",
        "LOGIN-SUCCESS-DETECT-v1",
        "LOGIN-ACCOUNT-EXPIRY-v1",
        "LOGIN-PASSWORD-EXPIRY-v1",
        "LOGIN-FORCE-CHANGE-PASSWORD-v1",
        "INTERRUPT-LOW-RISK-CONTINUE-v1",
        "INTERRUPT-BLOCKING-MODAL-v1",
        "INTERRUPT-NON-BLOCKING-NOTICE-v1",
        "INTERRUPT-SESSION-TIMEOUT-v1",
        "NAV-MENU-PATH-v1",
        "NAV-ALREADY-ON-TARGET-v1",
        "NAV-EXPAND-PARENT-v1",
        "NAV-DASHBOARD-CARD-v1",
        "NAV-MENU-SEARCH-v1",
        "NAV-IFRAME-MENU-v1",
        "QUERY-KEYWORD-v1",
        "QUERY-ADVANCED-EXPAND-v1",
        "QUERY-DATE-RANGE-v1",
        "QUERY-DROPDOWN-v1",
        "QUERY-RESULT-REFRESH-v1",
        "QUERY-NO-DATA-v1",
        "TABLE-DETECT-BASIC-v1",
        "TABLE-HEADER-MAP-v1",
        "TABLE-DATA-ROW-v1",
        "TABLE-NON-DATA-ROW-v1",
        "TABLE-PAGINATION-v1",
        "TABLE-VIRTUAL-SCROLL-v1",
        "ROW-LOCATE-BY-SINGLE-FIELD-v1",
        "ROW-LOCATE-BY-MULTI-FIELD-v1",
        "ROW-CLICK-ACTION-v1",
        "ROW-MORE-ACTIONS-v1",
        "ROW-OPEN-TODO-v1",
        "ROW-SKIP-NON-PROCESSABLE-v1",
        "FORM-FILL-TEXT-v1",
        "FORM-FILL-REQUIRED-v1",
        "FORM-FILL-DEFAULT-DATA-v1",
        "FORM-FILL-LABEL-NEARBY-v1",
        "FORM-FILL-SKIP-READONLY-HIDDEN-v1",
        "FORM-FILL-VALIDATION-RETRY-v1",
        "DROPDOWN-NATIVE-SELECT-v1",
        "DROPDOWN-CUSTOM-SELECT-v1",
        "DROPDOWN-SEARCHABLE-v1",
        "DROPDOWN-MULTI-SELECT-v1",
        "DROPDOWN-REMOTE-SEARCH-v1",
        "DROPDOWN-BODY-POPUP-v1",
        "DROPDOWN-VIRTUAL-SCROLL-v1",
        "DROPDOWN-DEFAULT-OPTION-v1",
        "DATE-DIRECT-INPUT-v1",
        "DATE-PICKER-POPUP-v1",
        "DATE-RANGE-v1",
        "DATE-TIME-v1",
        "DATE-DISABLED-FALLBACK-v1",
        "ORG-TREE-SELECT-v1",
        "ORG-MODAL-SELECT-v1",
        "ORG-DROPDOWN-TREE-v1",
        "ORG-SEARCH-v1",
        "ORG-REQUIRE-CLARIFICATION-v1",
        "PERSON-MODAL-SELECT-v1",
        "PERSON-SEARCH-v1",
        "PERSON-DEPT-TREE-v1",
        "PERSON-CURRENT-USER-v1",
        "PERSON-APPROVER-CLARIFY-v1",
        "TREE-SELECT-NODE-v1",
        "TREE-SEARCH-NODE-v1",
        "TREE-LAZY-LOAD-v1",
        "DIALOG-OPEN-SELECTOR-v1",
        "DIALOG-QUERY-AND-SELECT-v1",
        "DIALOG-CONFIRM-SELECTION-v1",
        "DIALOG-VERIFY-FILLBACK-v1",
        "FILE-UPLOAD-INPUT-v1",
        "FILE-UPLOAD-CUSTOM-BUTTON-v1",
        "FILE-UPLOAD-DRAG-v1",
        "FILE-UPLOAD-REQUIRE-FILE-v1",
        "DETAIL-CLICK-ID-LINK-v1",
        "DETAIL-OPEN-DIALOG-v1",
        "DETAIL-OPEN-DRAWER-v1",
        "DETAIL-NEW-TAB-v1",
        "DETAIL-VERIFY-CONTENT-v1",
        "APPROVAL-SUBMIT-v1",
        "APPROVAL-PASS-v1",
        "APPROVAL-REJECT-v1",
        "APPROVAL-FILL-OPINION-v1",
        "APPROVAL-CONFIRM-v1",
        "APPROVAL-VIEW-FLOW-v1",
        "APPROVAL-VIEW-RECORD-v1",
        "ASSERT-MULTI-EVIDENCE-v1",
        "ASSERT-TABLE-RECORD-EXISTS-v1",
        "ASSERT-TABLE-RECORD-NOT-EXISTS-v1",
        "ASSERT-STATUS-CHANGED-v1",
        "ASSERT-TOAST-SUCCESS-v1",
        "RECOVERY-WAIT-AND-RETRY-v1",
        "RECOVERY-RELOAD-PAGE-v1",
        "RECOVERY-REOBSERVE-PAGE-v1",
        "RECOVERY-LLM-DISAMBIGUATION-v1",
        "RECOVERY-VISION-OPTIONAL-v1",
        "RECOVERY-ASK-HUMAN-v1",
    }
    available_codes = {rule["rule_code"] for rule in BASE_ABILITY_RULES}
    assert required_codes.issubset(available_codes)


def test_approval_pass_and_flow_view_are_distinguished() -> None:
    rules = {rule["rule_code"]: rule for rule in BASE_ABILITY_RULES}
    pass_rule = rules["APPROVAL-PASS-v1"]
    flow_rule = rules["APPROVAL-VIEW-FLOW-v1"]
    assert "查看审批流程" in pass_rule["match_config_json"]["negative_actions"]
    assert flow_rule["match_config_json"]["mustNotTriggerApprovalPass"] is True
