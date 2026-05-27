from enum import Enum


class AbilityRuleType(str, Enum):
    LOGIN = "login"
    GLOBAL_INTERRUPTION = "global_interruption"
    NAVIGATION = "navigation"
    QUERY = "query"
    TABLE_DETECTION = "table_detection"
    TABLE_ROW_ACTION = "table_row_action"
    FORM_CONTROL = "form_control"
    FORM_FILL = "form_fill"
    DROPDOWN = "dropdown"
    DATE_PICKER = "date_picker"
    ORG_SELECTOR = "org_selector"
    PERSON_SELECTOR = "person_selector"
    TREE_SELECTOR = "tree_selector"
    DIALOG_SELECTOR = "dialog_selector"
    FILE_UPLOAD = "file_upload"
    DETAIL_NAVIGATION = "detail_navigation"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    APPROVAL_WORKFLOW = "approval_workflow"
    ASSERTION = "assertion"
    RECOVERY_POLICY = "recovery_policy"
    VISION_FALLBACK = "vision_fallback"
    CANDIDATE_RANKING = "candidate_ranking"


class OperationIntent(str, Enum):
    LOGIN = "login"
    ENTER_PAGE = "enter_page"
    NAVIGATE_PATH = "navigate_path"
    QUERY_LIST = "query_list"
    OPEN_TABLE_ROW = "open_table_row"
    PROCESS_TABLE_ROWS = "process_table_rows"
    CLICK_TABLE_ROW_ACTION = "click_table_row_action"
    CREATE_RECORD = "create_record"
    UPDATE_RECORD = "update_record"
    DELETE_RECORD = "delete_record"
    VIEW_DETAIL = "view_detail"
    VIEW_FLOW = "view_flow"
    SUBMIT_FOR_APPROVAL = "submit_for_approval"
    APPROVAL_PASS = "approval_pass"
    APPROVAL_REJECT = "approval_reject"
    FILL_FORM = "fill_form"
    FILL_FIELD = "fill_field"
    SELECT_DROPDOWN = "select_dropdown"
    SELECT_DATE = "select_date"
    SELECT_DATE_RANGE = "select_date_range"
    SELECT_ORG = "select_org"
    SELECT_PERSON = "select_person"
    SELECT_TREE_NODE = "select_tree_node"
    SELECT_FROM_DIALOG = "select_from_dialog"
    UPLOAD_FILE = "upload_file"
    HANDLE_DIALOG = "handle_dialog"
    ASSERT_RESULT = "assert_result"


class AbilityKnowledgeType(str, Enum):
    PAGE_LOCATOR = "page_locator"
    NAVIGATION_PATH = "navigation_path"
    TABLE_ROW_ACTION = "table_row_action"
    FORM_FILL_PATH = "form_fill_path"
    DROPDOWN_SOLUTION = "dropdown_solution"
    DATE_PICKER_SOLUTION = "date_picker_solution"
    ORG_SELECTOR_SOLUTION = "org_selector_solution"
    PERSON_SELECTOR_SOLUTION = "person_selector_solution"
    DIALOG_SOLUTION = "dialog_solution"
    BUSINESS_ACTION_PATH = "business_action_path"
    REJECTED_CANDIDATE = "rejected_candidate"
    VISUAL_PATTERN = "visual_pattern"
    INTERRUPTION_SOLUTION = "interruption_solution"
    RECOVERY_SOLUTION = "recovery_solution"


class FailurePatternType(str, Enum):
    LOGIN_FAILED = "login_failed"
    ACCOUNT_EXPIRED = "account_expired"
    FORCED_PASSWORD_CHANGE = "forced_password_change"
    NON_BLOCKING_NOTICE_DETECTED = "non_blocking_notice_detected"
    BLOCKING_DIALOG_DETECTED = "blocking_dialog_detected"
    MENU_PARENT_NOT_FOUND = "menu_parent_not_found"
    MENU_CHILD_NOT_FOUND = "menu_child_not_found"
    MENU_EXPAND_FAILED = "menu_expand_failed"
    NAVIGATION_GOAL_NOT_REACHED = "navigation_goal_not_reached"
    TABLE_NOT_FOUND = "table_not_found"
    TABLE_NO_DATA_ROWS = "table_no_data_rows"
    TABLE_TARGET_ROW_NOT_FOUND = "table_target_row_not_found"
    TABLE_NO_ACTION_FOUND = "table_no_action_found"
    TABLE_ROW_LOOP_FAILED = "table_row_loop_failed"
    FORM_REQUIRED_FIELD_MISSING = "form_required_field_missing"
    DROPDOWN_OPTION_NOT_FOUND = "dropdown_option_not_found"
    DATE_NOT_SELECTABLE = "date_not_selectable"
    ORG_VALUE_MISSING = "org_value_missing"
    PERSON_VALUE_MISSING = "person_value_missing"
    DIALOG_NOT_FOUND = "dialog_not_found"
    CLICK_NO_EFFECT = "click_no_effect"
    PERMISSION_DENIED = "permission_denied"
    ASSERTION_NOT_MET = "assertion_not_met"
    VISION_FALLBACK_NOT_CONFIGURED = "vision_fallback_not_configured"


class RuleStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    ACTIVE = "active"
    DISABLED = "disabled"
    REJECTED = "rejected"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RuleSource(str, Enum):
    BUILTIN = "builtin"
    MANUAL = "manual"
    AI_SUGGESTED = "ai_suggested"
    HUMAN_INTERVENTION = "human_intervention"


SUPPORTED_ABILITY_RULE_TYPES = [item.value for item in AbilityRuleType]
SUPPORTED_OPERATION_INTENTS = [item.value for item in OperationIntent]
SUPPORTED_KNOWLEDGE_TYPES = [item.value for item in AbilityKnowledgeType]
SUPPORTED_FAILURE_PATTERNS = [item.value for item in FailurePatternType]
