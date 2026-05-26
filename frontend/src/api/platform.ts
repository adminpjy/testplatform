import { getJson, postJson, putJson } from "./client";
import type {
  AbilityRule,
  AbilityKnowledge,
  AnalyzeResult,
  FailureSample,
  HealthInfo,
  HumanIntervention,
  HumanInterventionCreate,
  NaturalLanguageTestRequest,
  RuleDraft,
  SystemInfo,
  SystemCheckResult,
  TestArtifact,
  TestCaseDSL,
  TestProject,
  TestRun,
  TestRunCreate,
  TestStepRun,
  TestSystem,
  TestSystemCreate
} from "../types/platform";
import type { RuntimeMessageWire } from "../types/runtime";

export function getHealth(): Promise<HealthInfo> {
  return getJson<HealthInfo>("/health");
}

export function getSystemInfo(): Promise<SystemInfo> {
  return getJson<SystemInfo>("/api/system/info");
}

export function getProjects(): Promise<TestProject[]> {
  return getJson<TestProject[]>("/api/projects");
}

export function getSystems(): Promise<TestSystem[]> {
  return getJson<TestSystem[]>("/api/systems");
}

export function createSystem(payload: TestSystemCreate): Promise<TestSystem> {
  return postJson<TestSystem>("/api/systems", payload);
}

export function updateSystem(systemId: number, payload: Partial<TestSystemCreate>): Promise<TestSystem> {
  return putJson<TestSystem>(`/api/systems/${systemId}`, payload);
}

export function checkSystemConnectivity(systemId: number): Promise<SystemCheckResult> {
  return postJson<SystemCheckResult>(`/api/systems/${systemId}/check-connectivity`, {});
}

export function checkSystemLogin(systemId: number): Promise<SystemCheckResult> {
  return postJson<SystemCheckResult>(`/api/systems/${systemId}/check-login`, {});
}

export function analyzeTestRun(payload: NaturalLanguageTestRequest): Promise<AnalyzeResult> {
  return postJson<AnalyzeResult>("/api/test-runs/analyze", payload);
}

export function planTestRun(payload: NaturalLanguageTestRequest): Promise<TestCaseDSL> {
  return postJson<TestCaseDSL>("/api/test-runs/plan", payload);
}

export function createTestRun(payload: TestRunCreate): Promise<TestRun> {
  return postJson<TestRun>("/api/test-runs", payload);
}

export function getTestRuns(): Promise<TestRun[]> {
  return getJson<TestRun[]>("/api/test-runs");
}

export function getTestRunSteps(runId: number): Promise<TestStepRun[]> {
  return getJson<TestStepRun[]>(`/api/test-runs/${runId}/steps`);
}

export function getTestRunArtifacts(runId: number): Promise<TestArtifact[]> {
  return getJson<TestArtifact[]>(`/api/test-runs/${runId}/artifacts`);
}

export function getRuntimeMessages(runId: number): Promise<RuntimeMessageWire[]> {
  return getJson<RuntimeMessageWire[]>(`/api/test-runs/${runId}/runtime-messages`);
}

export function getFailureSamples(runId?: number): Promise<FailureSample[]> {
  const suffix = runId ? `?run_id=${runId}` : "";
  return getJson<FailureSample[]>(`/api/failure-samples${suffix}`);
}

export function getRunFailureSamples(runId: number): Promise<FailureSample[]> {
  return getJson<FailureSample[]>(`/api/test-runs/${runId}/failure-samples`);
}

export function getHumanInterventions(runId?: number): Promise<HumanIntervention[]> {
  const suffix = runId ? `?run_id=${runId}` : "";
  return getJson<HumanIntervention[]>(`/api/human-interventions${suffix}`);
}

export function getRunHumanInterventions(runId: number): Promise<HumanIntervention[]> {
  return getJson<HumanIntervention[]>(`/api/test-runs/${runId}/interventions`);
}

export function interveneStep(
  runId: number,
  stepId: number,
  payload: HumanInterventionCreate
): Promise<HumanIntervention> {
  return postJson<HumanIntervention>(`/api/test-runs/${runId}/steps/${stepId}/intervene`, payload);
}

export function executeIntervention(runId: number, interventionId: number): Promise<HumanIntervention> {
  return postJson<HumanIntervention>(`/api/test-runs/${runId}/interventions/${interventionId}/execute`, {});
}

export function convertInterventionToRule(runId: number, interventionId: number): Promise<RuleDraft> {
  return postJson<RuleDraft>(`/api/test-runs/${runId}/interventions/${interventionId}/convert-to-rule`, {});
}

export function getRuleDrafts(): Promise<RuleDraft[]> {
  return getJson<RuleDraft[]>("/api/rule-drafts");
}

export function enableRuleDraft(draftId: number): Promise<AbilityRule> {
  return postJson<AbilityRule>(`/api/rule-drafts/${draftId}/enable`, {});
}

export function getAbilityRules(): Promise<AbilityRule[]> {
  return getJson<AbilityRule[]>("/api/abilities/rules?production_enabled=true");
}

export function getAbilityKnowledge(): Promise<AbilityKnowledge[]> {
  return getJson<AbilityKnowledge[]>("/api/abilities/knowledge");
}
