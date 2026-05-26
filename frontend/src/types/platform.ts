export interface TestProject {
  id: number;
  project_code: string;
  name: string;
  description: string | null;
  system_name: string | null;
  base_url: string | null;
  login_url: string | null;
  environment: string | null;
  status: string;
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
  instruction: string;
  base_url?: string;
  credentials?: Record<string, unknown>;
  settings?: Record<string, unknown>;
  stream?: boolean;
}

export interface TestCaseDSL {
  caseName: string;
  baseUrl: string;
  credentials: Record<string, unknown>;
  settings: Record<string, unknown>;
  steps: TestCaseStep[];
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
  case_id?: number | null;
  instruction?: string | null;
  base_url?: string | null;
  dsl_json?: TestCaseDSL | null;
}

export interface TestRun {
  id: number;
  run_code: string;
  project_id: number;
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
  risk_level: string;
  confidence_threshold: number;
  source: string | null;
  production_enabled: boolean;
  created_at: string;
  updated_at: string;
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
