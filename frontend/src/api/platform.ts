import { apiUrl, getJson, postJson, putJson } from "./client";
import type {
  AbilityRule,
  AbilityStats,
  AbilityKnowledge,
  AnalyzeResult,
  FailureSample,
  HealthInfo,
  HumanIntervention,
  HumanInterventionCreate,
  NaturalLanguageTestRequest,
  PromptInfo,
  PromptPreview,
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

export function getPrompts(): Promise<PromptInfo[]> {
  return getJson<PromptInfo[]>("/api/prompts");
}

export function getPrompt(promptKey: string): Promise<PromptInfo> {
  return getJson<PromptInfo>(`/api/prompts/${encodeURIComponent(promptKey)}`);
}

export function reloadPrompts(): Promise<{ loaded: number; last_error: string | null }> {
  return postJson<{ loaded: number; last_error: string | null }>("/api/prompts/reload", {});
}

export function previewPrompt(promptKey: string, variables: Record<string, unknown>): Promise<PromptPreview> {
  return postJson<PromptPreview>(`/api/prompts/${encodeURIComponent(promptKey)}/preview`, { variables });
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

export async function streamAnalyzeAndPlan(
  payload: NaturalLanguageTestRequest,
  onMessage: (message: RuntimeMessageWire) => void
): Promise<void> {
  const response = await fetch(apiUrl("/api/test-runs/analyze-stream"), {
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
  if (!response.ok || !response.body) {
    throw new Error(`Analyze stream failed with HTTP ${response.status}.`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split(/\n\n/);
    buffer = events.pop() || "";
    for (const eventText of events) {
      const message = parseSseMessage(eventText);
      if (message) {
        onMessage(message);
      }
    }
  }
  if (buffer.trim()) {
    const message = parseSseMessage(buffer);
    if (message) {
      onMessage(message);
    }
  }
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

export function getAbilityRules(filters: { rule_type?: string; production_enabled?: boolean } = {}): Promise<AbilityRule[]> {
  const params = new URLSearchParams();
  if (filters.rule_type) params.set("rule_type", filters.rule_type);
  if (filters.production_enabled !== undefined) params.set("production_enabled", String(filters.production_enabled));
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return getJson<AbilityRule[]>(`/api/abilities/rules${suffix}`);
}

export function updateAbilityRule(ruleId: number, payload: Partial<AbilityRule>): Promise<AbilityRule> {
  return putJson<AbilityRule>(`/api/abilities/rules/${ruleId}`, payload);
}

export function getAbilityStats(): Promise<AbilityStats> {
  return getJson<AbilityStats>("/api/abilities/stats");
}

export function getAbilityKnowledge(): Promise<AbilityKnowledge[]> {
  return getJson<AbilityKnowledge[]>("/api/abilities/knowledge");
}

function parseSseMessage(eventText: string): RuntimeMessageWire | null {
  const dataLines = eventText
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart());
  if (dataLines.length === 0) {
    return null;
  }
  try {
    return JSON.parse(dataLines.join("\n")) as RuntimeMessageWire;
  } catch {
    return null;
  }
}
