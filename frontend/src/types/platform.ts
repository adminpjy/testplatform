export interface TestProject {
  id: number;
  project_code: string;
  project_name: string | null;
  name: string;
  owner_user_id?: number | null;
  created_by_user_id?: number | null;
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
  current_user_role?: string | null;
  current_user_permissions?: Record<string, boolean> | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface CurrentUser {
  id: number;
  username: string;
  display_name: string | null;
  role: "admin" | "owner" | "testuser" | string;
  status: string;
  permissions: Record<string, unknown>;
  navigation: string[];
  created_at?: string | null;
  updated_at?: string | null;
}

export interface LoginResponse {
  token: string;
  user: CurrentUser;
}

export interface ProjectMember {
  id: number;
  project_id: number;
  user_id: number;
  username: string;
  display_name: string | null;
  role: "owner" | "testuser" | string;
  permissions: Record<string, boolean>;
  status: string;
  created_at: string;
  updated_at: string | null;
}

export interface ProjectMemberPayload {
  username?: string;
  display_name?: string | null;
  role?: "owner" | "testuser" | string;
  permissions?: Record<string, boolean>;
  status?: string;
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
  generalized_pattern_json?: Record<string, unknown> | null;
  solution_json?: Record<string, unknown> | null;
  rule_draft_json?: Record<string, unknown> | null;
  validation_plan_json?: Record<string, unknown> | null;
  user_reply?: string | null;
  internal_notes?: string | null;
  llm_raw_response_json?: Record<string, unknown> | null;
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

export interface DocumentSource {
  id: number;
  project_id: number;
  file_name: string;
  file_path: string;
  doc_type: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface ExtractedCaseDraft {
  id: number;
  project_id: number;
  document_id: number;
  case_name: string;
  natural_language_goal: string | null;
  menu_path: string | null;
  test_data_json: Record<string, unknown> | null;
  suggested_account_role: string | null;
  confidence: number | null;
  status: string;
  created_case_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface BootstrapFilePayload {
  file_name: string;
  role: string;
  content: string;
}

export interface InitialCaseDraft {
  index: number;
  caseName: string;
  naturalLanguageGoal: string;
  menuPath: string | null;
  businessIntent: string | null;
  testData: Record<string, unknown>;
  riskLevel: string;
  confidence: number;
  source: string;
}

export interface ProjectBootstrapPackage {
  id: number;
  project_id: number;
  package_code: string;
  status: string;
  source_type: string;
  file_a_name: string | null;
  file_a_role: string | null;
  file_b_name: string | null;
  file_b_role: string | null;
  draft_cases_json: Record<string, unknown> | null;
  imported_case_ids_json: Record<string, unknown> | null;
  summary_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectWizardBootstrapRequest {
  project: ProjectCreatePayload & { project_code?: string | null };
  account?: ProjectAccountPayload | null;
  files: BootstrapFilePayload[];
  generatorResult?: Record<string, unknown> | Array<Record<string, unknown>> | null;
  sourceType?: string;
}

export interface ProjectWizardBootstrapResponse {
  projectId: number;
  package: ProjectBootstrapPackage;
  drafts: InitialCaseDraft[];
  summary: Record<string, unknown>;
}

export interface ImportBootstrapCasesResponse {
  packageId: number;
  projectId: number;
  importedCaseIds: number[];
  skippedIndexes: number[];
  summary: Record<string, unknown>;
}

export interface PrescanSession {
  id: number;
  project_id: number;
  session_code: string;
  status: string;
  mode: string;
  dry_run: boolean;
  case_ids_json: Record<string, unknown> | null;
  plan_json: Record<string, unknown> | null;
  findings_json: Record<string, unknown> | null;
  rule_draft_ids_json: Record<string, unknown> | null;
  ability_knowledge_ids_json: Record<string, unknown> | null;
  enhanced_cases_json: Record<string, unknown> | null;
  error_summary: string | null;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PrescanResponse {
  session: PrescanSession;
  summary: Record<string, unknown>;
  ruleDraftIds: number[];
  abilityKnowledgeIds: number[];
  enhancedCases: Array<Record<string, unknown>>;
}

export interface CampaignCase {
  id: number;
  campaign_id: number;
  project_id: number;
  case_id: number;
  case_version_id: number | null;
  run_id: number | null;
  order_index: number;
  status: string;
  failure_summary: string | null;
  result_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface TestCampaign {
  id: number;
  project_id: number;
  campaign_code: string;
  name: string;
  description: string | null;
  status: string;
  case_ids_json: Record<string, unknown> | null;
  settings_json: Record<string, unknown> | null;
  total_count: number;
  queued_count: number;
  running_count: number;
  passed_count: number;
  failed_count: number;
  blocked_count: number;
  summary_json: Record<string, unknown> | null;
  created_by_user_id?: number | null;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
  updated_at: string;
  cases: CampaignCase[];
}

export interface CampaignReportSummary {
  campaignId: number;
  campaignCode: string;
  projectId: number;
  name: string;
  status: string;
  totals: Record<string, unknown>;
  failures: Array<Record<string, unknown>>;
  runs: Array<Record<string, unknown>>;
  recommendations: string[];
}

export interface MaintenanceFeedback {
  id: number;
  feedback_code: string;
  project_id: number | null;
  case_id: number | null;
  run_id: number | null;
  failure_sample_id: number | null;
  status: string;
  summary: string | null;
  evidence_package_json: Record<string, unknown> | null;
  artifact_paths_json: Record<string, unknown> | null;
  maintainer_notes: string | null;
  created_at: string;
  updated_at: string;
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

export interface LLMProfile {
  id: string;
  name: string;
  provider: string;
  baseUrl: string;
  model: string;
  stream: boolean;
  verifySsl: boolean;
  timeoutSeconds: number;
  maxTokens: number;
  temperature: number;
  topP: number;
  caBundle: string;
  trustEnv: boolean;
  hasApiKey?: boolean;
  apiKeyMasked?: string | null;
  apiKey?: string | null;
}

export interface LLMSettings {
  activeProfileId: string;
  profiles: LLMProfile[];
  effective: LLMProfile | null;
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
  case_version_id?: number | null;
  account_id?: number | null;
  instruction?: string | null;
  base_url?: string | null;
  dsl_json?: TestCaseDSL | null;
  testDataOverride?: Record<string, unknown> | null;
  settingsOverride?: Record<string, unknown> | null;
}

export interface TestRun {
  id: number;
  run_code: string;
  project_id: number;
  system_id: number | null;
  case_id: number | null;
  case_version_id: number | null;
  campaign_id?: number | null;
  account_id: number | null;
  created_by_user_id?: number | null;
  instruction: string | null;
  instruction_snapshot?: string | null;
  base_url: string | null;
  base_url_snapshot?: string | null;
  login_url_snapshot?: string | null;
  home_url_snapshot?: string | null;
  status: string;
  current_phase: string | null;
  dsl_json: Record<string, unknown> | null;
  dsl_snapshot?: Record<string, unknown> | null;
  test_data_snapshot?: Record<string, unknown> | null;
  settings_snapshot?: Record<string, unknown> | null;
  account_snapshot?: Record<string, unknown> | null;
  error_summary?: string | null;
  duration_ms?: number | null;
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
  project_id?: number | null;
  case_id?: number | null;
  case_version_id?: number | null;
  run_id: number;
  step_id: number | null;
  failure_type: string | null;
  failure_summary: string | null;
  evidence_json?: Record<string, unknown> | null;
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

export interface PageResponse<T = Record<string, unknown>> {
  items: T[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
  hasNext: boolean;
  hasPrev: boolean;
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

export interface FailureContext {
  failureSampleId: number;
  context: Record<string, unknown>;
  latestAnalysis: Record<string, unknown> | null;
  latestSolution: Record<string, unknown> | null;
  latestValidation: Record<string, unknown> | null;
  maintenanceResponse: Record<string, unknown> | null;
}

export interface FailureSolution {
  id: number;
  solution_code: string;
  failure_sample_id: number;
  failure_analysis_id: number | null;
  pattern_id: number | null;
  project_id: number | null;
  case_id: number | null;
  run_id: number | null;
  rule_draft_id: number | null;
  root_cause: string | null;
  solution_summary: string | null;
  generalized_pattern_json: Record<string, unknown> | null;
  strategy_json: Record<string, unknown> | null;
  suggested_rule_json: Record<string, unknown> | null;
  validation_plan_json: Record<string, unknown> | null;
  context_snapshot_json: Record<string, unknown> | null;
  user_reply: string | null;
  internal_notes: string | null;
  admin_adjustment_json: Record<string, unknown> | null;
  status: string;
  created_by_user_id: number | null;
  updated_by_user_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface RuleValidation {
  id: number;
  validation_code: string;
  solution_id: number | null;
  rule_draft_id: number | null;
  ability_rule_id: number | null;
  project_id: number | null;
  case_id: number | null;
  run_id: number | null;
  validation_type: string;
  sample_ids_json: Record<string, unknown> | null;
  status: string;
  passed_count: number;
  failed_count: number;
  false_positive_count: number;
  result_json: Record<string, unknown> | null;
  report_json: Record<string, unknown> | null;
  created_by_user_id: number | null;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface MaintenanceResponse {
  id: number;
  response_code: string;
  failure_sample_id: number | null;
  solution_id: number | null;
  validation_id: number | null;
  project_id: number | null;
  case_id: number | null;
  run_id: number | null;
  submitted_by_user_id: number | null;
  handled_by_user_id: number | null;
  status: string;
  root_cause: string | null;
  fix_summary: string | null;
  validation_result: string | null;
  user_reply: string | null;
  internal_notes: string | null;
  evidence_summary_json: Record<string, unknown> | null;
  created_at: string;
  resolved_at: string | null;
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
