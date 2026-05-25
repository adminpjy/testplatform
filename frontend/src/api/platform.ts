import { getJson, postJson } from "./client";
import type {
  AbilityRule,
  AnalyzeResult,
  HealthInfo,
  NaturalLanguageTestRequest,
  SystemInfo,
  TestArtifact,
  TestCaseDSL,
  TestProject,
  TestRun,
  TestRunCreate,
  TestStepRun
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

export function getAbilityRules(): Promise<AbilityRule[]> {
  return getJson<AbilityRule[]>("/api/abilities/rules?production_enabled=true");
}
