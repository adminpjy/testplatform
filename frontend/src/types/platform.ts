export interface TestProject {
  id: number;
  project_code: string;
  project_name: string | null;
  name: string;
  description: string | null;
  system_id: number | null;
  system_name: string | null;
  base_url: string | null;
  login_url: string | null;
  home_url?: string | null;
  auth_type?: string;
  environment: string | null;
  default_timeout_ms?: number;
  enable_trace_default?: boolean;
  enable_screenshot_default?: boolean;
  enable_dom_snapshot_default?: boolean;
  enable_accessibility_snapshot_default?: boolean;
  enable_vision_fallback_default?: boolean;
  default_account_id?: number | null;
  default_account?: ProjectAccount | null;
  account_count?: number;
  case_count?: number;
  last_run_status?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectAccount {
  id: number;
  project_id: number | null;
  account_name: string | null;
  username: string;
  role_name: string | null;
  description: string | null;
  allow_read: boolean;
  allow_write: boolean;
  allow_approval: boolean;
  allow_delete: boolean;
  is_default: boolean;
  status: string;
  secret_ref: string | null;
  has_password: boolean;
  expires_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreatePayload {
  project_name: string;
  description?: string | null;
  system_name?: string | null;
  base_url?: string | null;
  login_url?: string | null;
  home_url?: string | null;
  auth_type?: string;
  default_timeout_ms?: number;
  enable_trace_default?: boolean;
  enable_screenshot_default?: boolean;
  enable_dom_snapshot_default?: boolean;
  enable_accessibility_snapshot_default?: boolean;
  enable_vision_fallback_default?: boolean;
  status?: string;
}

export interface ProjectAccountPayload {
  account_name?: string | null;
  username?: string;
  password?: string | null;
  secret_ref?: string | null;
  role_name?: string | null;
  description?: string | null;
  allow_read?: boolean;
  allow_write?: boolean;
  allow_approval?: boolean;
  allow_delete?: boolean;
  is_default?: boolean;
  status?: string;
}

export interface FunctionalTestCase {
  id: number;
  project_id: number;
  case_code: string | null;
  case_name: string;
  description: string | null;
  source_type: string;
  natural_language_goal: string | null;
  menu_path: string | null;
  business_intent: string | null;
  inherit_project_account: boolean;
  account_id: number | null;
  test_data_json: Record<string, unknown> | null;
  preconditions_json: Record<string, unknown> | null;
  success_criteria_json: Record<string, unknown> | null;
  settings_json: Record<string, unknown> | null;
  dsl_json: TestCaseDSL | null;
  risk_level: string;
  status: string;
  current_version_id: number | null;
  last_run_id: number | null;
  last_run_status: string | null;
  last_run_at: string | null;
  run_count: number;
  pass_count: number;
  fail_count: number;
  created_at: string;
  updated_at: string;
}

export interface FunctionalTestCasePayload {
  case_name?: string;
  description?: string | null;
  source_type?: string;
  natural_language_goal?: string | null;
  menu_path?: string | null;
  business_intent?: string | null;
  inherit_project_account?: boolean;
  account_id?: number | null;
  test_data_json?: Record<string, unknown> | null;
  preconditions_json?: Record<string, unknown> | null;
  success_criteria_json?: Record<string, unknown> | null;
  settings_json?: Record<string, unknown> | null;
  dsl_json?: TestCaseDSL | null;
  risk_level?: string;
  status?: string;
}

export interface TestCaseVersion {
  id: number;
  case_id: number;
  version_no: number;
  version_label: string | null;
  natural_language_goal: string | null;
  dsl_json: TestCaseDSL | null;
  test_data_json: Record<string, unknown> | null;
  preconditions_json: Record<string, unknown> | null;
  success_criteria_json: Record<string, unknown> | null;
  settings_json: Record<string, unknown> | null;
  change_type: string;
  change_summary: string | null;
  created_at: string;
}

export interface DslValidationResult {
  valid: boolean;
  errors: string[];
  dsl_json: TestCaseDSL | null;
}

export interface FailureAnalysis {
  id: number;
  case_id: number | null;
  run_id: number;
  failure_sample_id: number;
  analysis_status: string;
  failure_category: string | null;
  root_cause: string | null;
  confidence: number | null;
  evidence_json: Record<string, unknown> | null;
  suggestions_json: Record<string, unknown> | null;
  recommended_actions_json: Record<string, unknown> | null;
  risk_level: string;
  requires_human_review: boolean;
  error_summary: string | null;
  created_at: string;
  updated_at: string;
}

export interface FixApplication {
  id: number;
  case_id: number | null;
  run_id: number | null;
  failure_analysis_id: number | null;
  fix_type: string;
  status: string;
  before_snapshot_json: Record<string, unknown> | null;
  after_snapshot_json: Record<string, unknown> | null;
  created_case_version_id: number | null;
  created_rule_draft_id: number | null;
  verify_run_id: number | null;
  reason: string | null;
  defect_draft_json: Record<string, unknown> | null;
  created_at: string;
  applied_at: string | null;
  verified_at: string | null;
}

export interface AnalyzeResult {
  readyToExecute: boolean;
  confidence: number;
  understoodGoal: string;
  missingFields: string[];
  clarifyingQuestions: string[];
  assumptions: string[];
  riskLevel: "low" | "medium" | "high" | string;
  normalizedInstruction: string;
}

export interface NaturalLanguageTestRequest {
  project_id?: number;
  system_id?: number;
  instruction: string;
  base_url?: string;
  credentials?: Record<string, unknown>;
  testData?: Record<string, unknown>;
  settings?: Record<string, unknown>;
  stream?: boolean;
}

export interface TestCaseDSL {
  caseName: string;
  baseUrl: string;
  credentials: Record<string, unknown>;
  testData: Record<string, unknown>;
  settings: Record<string, unknown>;
  steps: TestCaseStep[];
  missingFields?: string[];
  clarifyingQuestions?: string[];
}

export interface TestCaseStep {
  action: string;
  target?: string;
  selector?: string;
  value?: string;
  description?: string;
  [key: string]: unknown;
}

export interface TestRunCreate {
  project_id: number;
  system_id?: number | null;
  case_id?: number | null;
  instruction?: string | null;
  base_url?: string | null;
  dsl_json?: TestCaseDSL | null;
}

export interface TestRun {
  id: number;
  run_code: string;
  project_id: number;
  system_id: number | null;
  case_id: number | null;
  instruction: string | null;
  base_url: string | null;
  status: string;
  current_phase: string | null;
  dsl_json: Record<string, unknown> | null;
  summary_json: Record<string, unknown> | null;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TestAccount {
  id: number;
  system_id: number | null;
  environment: string;
  username: string;
  role_name: string | null;
  allow_write: boolean;
  allow_approval: boolean;
  allow_delete: boolean;
  status: string;
  expires_at: string | null;
  secret_ref: string | null;
  has_password: boolean;
  created_at: string;
  updated_at: string;
}

export interface TestSystem {
  id: number;
  system_code: string;
  system_name: string;
  description: string | null;
  base_url: string;
  login_url: string | null;
  home_url: string | null;
  environment: "dev" | "test" | "uat" | "preprod" | "prod" | string;
  auth_type: "username_password" | "sso" | "token" | "other" | string;
  default_timeout_ms: number;
  allow_write: boolean;
  allow_approval: boolean;
  allow_delete: boolean;
  status: string;
  config_json: Record<string, unknown> | null;
  accounts: TestAccount[];
  created_at: string;
  updated_at: string;
}

export interface TestSystemCreate {
  system_code: string;
  system_name: string;
  description?: string | null;
  base_url: string;
  login_url?: string | null;
  home_url?: string | null;
  environment: string;
  auth_type: string;
  default_timeout_ms: number;
  allow_write: boolean;
  allow_approval: boolean;
  allow_delete: boolean;
  status: string;
  config_json?: Record<string, unknown> | null;
  default_account?: {
    environment: string;
    username: string;
    password?: string | null;
    secret_ref?: string | null;
    role_name?: string | null;
    allow_write: boolean;
    allow_approval: boolean;
    allow_delete: boolean;
    status: string;
  } | null;
}

export interface SystemCheckResult {
  system_id: number;
  check_type: string;
  status: string;
  http_status: number | null;
  response_time_ms: number | null;
  screenshot_path: string | null;
  runtime_stream_path: string | null;
  message: string;
  metadata: Record<string, unknown>;
}

export interface TestStepRun {
  id: number;
  run_id: number;
  step_id: string | null;
  step_name: string | null;
  action: string | null;
  target: string | null;
  status: string;
  locator_strategy: string | null;
  element_ref: string | null;
  confidence: number | null;
  reason: string | null;
  screenshot_path: string | null;
  error_summary: string | null;
  started_at: string | null;
  ended_at: string | null;
}

export interface TestArtifact {
  id: number;
  run_id: number;
  step_id: number | null;
  artifact_type: string;
  file_path: string;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
}

export interface TraceViewerResponse {
  enabled: boolean;
  status: "running" | "stopped" | "not_started" | "failed" | string;
  viewerUrl: string | null;
  port?: number | null;
  tracePath?: string | null;
  pid?: number | null;
  startedAt?: string | null;
  lastAccessedAt?: string | null;
  error?: string | null;
  message?: string | null;
}

export interface FailureSample {
  id: number;
  run_id: number;
  step_id: number | null;
  failure_type: string | null;
  failure_summary: string | null;
  screenshot_path: string | null;
  dom_snapshot_path: string | null;
  accessibility_snapshot_path: string | null;
  locator_debug_path: string | null;
  runtime_stream_path: string | null;
  execution_trace_path: string | null;
  report_path: string | null;
  ai_analysis_json: Record<string, unknown> | null;
  suggested_rule_json: Record<string, unknown> | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export type InterventionAction =
  | "click"
  | "input"
  | "select"
  | "choose_radio"
  | "close_dialog"
  | "confirm_dialog"
  | "wait"
  | "retry_step"
  | "assert_text_exists"
  | "assert_url_contains";

export interface InterventionPlanStep {
  action: InterventionAction;
  target?: string | null;
  value?: string | null;
  reason?: string | null;
}

export interface InterventionPlan {
  summary: string;
  steps: InterventionPlanStep[];
  safety_notes: string[];
}

export interface HumanIntervention {
  id: number;
  run_id: number;
  step_id: number | null;
  user_instruction: string | null;
  llm_plan_json: InterventionPlan | null;
  execution_result_json: Record<string, unknown> | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface HumanInterventionCreate {
  user_instruction: string;
}

export interface RuleDraft {
  id: number;
  source_type: string;
  source_id: number | null;
  rule_type: string;
  rule_name: string;
  proposed_content_json: Record<string, unknown> | null;
  reason: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface AbilityRule {
  id: number;
  rule_code: string;
  rule_name: string;
  rule_type: string;
  intent: string | null;
  status: string;
  priority: number;
  match_config_json: Record<string, unknown> | null;
  action_config_json: Record<string, unknown> | null;
  success_criteria_json: Record<string, unknown> | null;
  fallback_strategies_json: Record<string, unknown> | null;
  failure_patterns_json: Record<string, unknown> | null;
  recovery_strategies_json: Record<string, unknown> | null;
  risk_level: string;
  confidence_threshold: number;
  auto_handle?: boolean;
  requires_human_confirmation?: boolean;
  version?: string;
  source: string | null;
  production_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface AbilityOperationOverview {
  key: string;
  label: string;
  ruleTypes: string[];
  ruleCount: number;
  activeCount: number;
  recentHitCount: number;
  recentFailureCount: number;
}

export interface AbilityStats {
  operationOverview: AbilityOperationOverview[];
  ruleTypeStats: Record<string, { total: number; active: number }>;
  ruleHitCountsByType: Record<string, number>;
  ruleHitCountsByCode: Record<string, number>;
  failureTypeDistribution: Record<string, number>;
  failureCountsByCategory: Record<string, number>;
  humanInterventionCount: number;
  ruleDraftCount: number;
  visionFallbackCount: number;
  llmDecisionCount: number;
}

export interface AbilityKnowledge {
  id: number;
  knowledge_type: string;
  system_id: number | null;
  project_id: number | null;
  page_url_pattern: string | null;
  page_fingerprint: string | null;
  semantic_target: string | null;
  business_intent: string | null;
  success_locator_json: Record<string, unknown> | null;
  action_path_json: Record<string, unknown> | null;
  rejected_candidates_json: Record<string, unknown> | null;
  confidence: number | null;
  success_count: number;
  failure_count: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface PromptInfo {
  key: string;
  name: string;
  version: string;
  enabled: boolean;
  model_profile: string;
  temperature: number | null;
  max_tokens: number | null;
  output_format: string;
  description: string | null;
  variables: string[];
  file: string;
  system: string;
  user: string;
  examples?: unknown[];
}

export interface PromptPreview {
  prompt_key: string;
  prompt_version: string;
  system: string;
  user: string;
}

export interface SystemInfo {
  service: string;
  version: string;
  environment: string;
  database: {
    connected: boolean;
    url?: string;
    error?: string;
  };
  project_count: number;
  system_count: number;
  ability_rule_count: number;
}

export interface HealthInfo {
  status: string;
  service: string;
  database: {
    connected: boolean;
    url?: string;
    error?: string;
  };
}
