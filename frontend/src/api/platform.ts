import { ApiError, apiUrl, deleteJson, getJson, postJson, putJson } from "./client";
import type {
  AbilityRule,
  AbilityStats,
  AbilityKnowledge,
  AnalyzeResult,
  DslValidationResult,
  DocumentSource,
  ExtractedCaseDraft,
  FailureSample,
  FailureAnalysis,
  FixApplication,
  FunctionalTestCase,
  FunctionalTestCasePayload,
  HealthInfo,
  HumanIntervention,
  HumanInterventionCreate,
  NaturalLanguageTestRequest,
  ProjectAccount,
  ProjectAccountPayload,
  ProjectCreatePayload,
  PromptInfo,
  PromptPreview,
  RuleDraft,
  SystemInfo,
  SystemCheckResult,
  TestArtifact,
  TestCaseVersion,
  TestCaseDSL,
  TestProject,
  TestRun,
  TestRunCreate,
  TestStepRun,
  TestSystem,
  TestSystemCreate,
  TraceViewerResponse
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

export function createProject(payload: ProjectCreatePayload): Promise<TestProject> {
  return postJson<TestProject>("/api/projects", payload);
}

export function updateProject(projectId: number, payload: Partial<ProjectCreatePayload>): Promise<TestProject> {
  return putJson<TestProject>(`/api/projects/${projectId}`, payload);
}

export async function deleteProject(projectId: number): Promise<void> {
  try {
    await deleteJson<void>(`/api/projects/${projectId}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 405) {
      await postJson<void>(`/api/projects/${projectId}/delete`, {});
      return;
    }
    throw error;
  }
}

export function getProjectAccounts(projectId: number): Promise<ProjectAccount[]> {
  return getJson<ProjectAccount[]>(`/api/projects/${projectId}/accounts`);
}

export function createProjectAccount(projectId: number, payload: ProjectAccountPayload): Promise<ProjectAccount> {
  return postJson<ProjectAccount>(`/api/projects/${projectId}/accounts`, payload);
}

export function updateProjectAccount(accountId: number, payload: ProjectAccountPayload): Promise<ProjectAccount> {
  return putJson<ProjectAccount>(`/api/accounts/${accountId}`, payload);
}

export function deleteProjectAccount(accountId: number): Promise<void> {
  return deleteJson<void>(`/api/accounts/${accountId}`);
}

export function setProjectDefaultAccount(accountId: number): Promise<ProjectAccount> {
  return postJson<ProjectAccount>(`/api/accounts/${accountId}/set-default`, {});
}

export function getProjectCases(projectId: number): Promise<FunctionalTestCase[]> {
  return getJson<FunctionalTestCase[]>(`/api/projects/${projectId}/cases`);
}

export function getProjectDocuments(projectId: number): Promise<DocumentSource[]> {
  return getJson<DocumentSource[]>(`/api/projects/${projectId}/documents`);
}

export function uploadProjectDocument(projectId: number, payload: { file_name: string; doc_type: string; content: string }): Promise<DocumentSource> {
  return postJson<DocumentSource>(`/api/projects/${projectId}/documents`, payload);
}

export function extractDocumentTestCases(documentId: number): Promise<ExtractedCaseDraft[]> {
  return postJson<ExtractedCaseDraft[]>(`/api/documents/${documentId}/extract-test-cases`, {});
}

export function getProjectExtractedDrafts(projectId: number): Promise<ExtractedCaseDraft[]> {
  return getJson<ExtractedCaseDraft[]>(`/api/projects/${projectId}/extracted-case-drafts`);
}

export function updateExtractedDraft(draftId: number, payload: Partial<ExtractedCaseDraft>): Promise<ExtractedCaseDraft> {
  return putJson<ExtractedCaseDraft>(`/api/extracted-case-drafts/${draftId}`, payload);
}

export function acceptExtractedDraft(draftId: number): Promise<FunctionalTestCase> {
  return postJson<FunctionalTestCase>(`/api/extracted-case-drafts/${draftId}/accept`, {});
}

export function rejectExtractedDraft(draftId: number): Promise<ExtractedCaseDraft> {
  return postJson<ExtractedCaseDraft>(`/api/extracted-case-drafts/${draftId}/reject`, {});
}

export function createProjectCase(projectId: number, payload: FunctionalTestCasePayload): Promise<FunctionalTestCase> {
  return postJson<FunctionalTestCase>(`/api/projects/${projectId}/cases`, payload);
}

export function getCase(caseId: number): Promise<FunctionalTestCase> {
  return getJson<FunctionalTestCase>(`/api/cases/${caseId}`);
}

export function updateCase(caseId: number, payload: FunctionalTestCasePayload): Promise<FunctionalTestCase> {
  return putJson<FunctionalTestCase>(`/api/cases/${caseId}`, payload);
}

export function deleteCase(caseId: number): Promise<void> {
  return deleteJson<void>(`/api/cases/${caseId}`);
}

export function enableCase(caseId: number): Promise<FunctionalTestCase> {
  return postJson<FunctionalTestCase>(`/api/cases/${caseId}/enable`, {});
}

export function disableCase(caseId: number): Promise<FunctionalTestCase> {
  return postJson<FunctionalTestCase>(`/api/cases/${caseId}/disable`, {});
}

export function copyCase(caseId: number): Promise<FunctionalTestCase> {
  return postJson<FunctionalTestCase>(`/api/cases/${caseId}/copy`, {});
}

export function getCaseVersions(caseId: number): Promise<TestCaseVersion[]> {
  return getJson<TestCaseVersion[]>(`/api/cases/${caseId}/versions`);
}

export function activateCaseVersion(caseId: number, versionId: number): Promise<FunctionalTestCase> {
  return postJson<FunctionalTestCase>(`/api/cases/${caseId}/versions/${versionId}/activate`, {});
}

export function validateCaseDsl(caseId: number, dsl_json: TestCaseDSL): Promise<DslValidationResult> {
  return postJson<DslValidationResult>(`/api/cases/${caseId}/dsl/validate`, { dsl_json });
}

export function formatCaseDsl(caseId: number, dsl_json: TestCaseDSL): Promise<TestCaseDSL> {
  return postJson<TestCaseDSL>(`/api/cases/${caseId}/dsl/format`, { dsl_json });
}

export function saveCaseDsl(caseId: number, dsl_json: TestCaseDSL, change_summary?: string): Promise<FunctionalTestCase> {
  return putJson<FunctionalTestCase>(`/api/cases/${caseId}/dsl`, {
    dsl_json,
    change_summary,
    change_type: "manual_edit"
  });
}

export function analyzeCase(caseId: number, instruction?: string, testData?: Record<string, unknown>): Promise<AnalyzeResult> {
  return postJson<AnalyzeResult>(`/api/cases/${caseId}/analyze`, { instruction, testData });
}

export function generateCaseDsl(caseId: number, instruction?: string, testData?: Record<string, unknown>): Promise<TestCaseDSL> {
  return postJson<TestCaseDSL>(`/api/cases/${caseId}/generate-dsl`, { instruction, testData });
}

export function saveGeneratedCaseDsl(
  caseId: number,
  dsl_json: TestCaseDSL,
  test_data_json?: Record<string, unknown>,
  change_summary?: string
): Promise<FunctionalTestCase> {
  return postJson<FunctionalTestCase>(`/api/cases/${caseId}/save-generated-dsl`, {
    dsl_json,
    test_data_json,
    change_summary
  });
}

export function getCaseRuns(caseId: number): Promise<TestRun[]> {
  return getJson<TestRun[]>(`/api/cases/${caseId}/runs`);
}

export function getCaseFailureSamples(caseId: number): Promise<FailureSample[]> {
  return getJson<FailureSample[]>(`/api/cases/${caseId}/failure-samples`);
}

export function getCaseFailureAnalyses(caseId: number): Promise<FailureAnalysis[]> {
  return getJson<FailureAnalysis[]>(`/api/cases/${caseId}/failure-analyses`);
}

export function getCaseFixApplications(caseId: number): Promise<FixApplication[]> {
  return getJson<FixApplication[]>(`/api/cases/${caseId}/fix-applications`);
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

export function createRunFromCase(
  caseId: number,
  payload: {
    caseVersionId?: number | null;
    accountId?: number | null;
    testDataOverride?: Record<string, unknown>;
    settingsOverride?: Record<string, unknown>;
    runName?: string | null;
  } = {}
): Promise<TestRun> {
  return postJson<TestRun>(`/api/cases/${caseId}/runs`, payload);
}

export function rerunLatestCase(caseId: number): Promise<TestRun> {
  return postJson<TestRun>(`/api/cases/${caseId}/rerun-latest`, {});
}

export function runCaseVersion(caseId: number, versionId: number): Promise<TestRun> {
  return postJson<TestRun>(`/api/cases/${caseId}/versions/${versionId}/run`, {});
}

export function rerunTestRun(runId: number): Promise<TestRun> {
  return postJson<TestRun>(`/api/test-runs/${runId}/rerun`, {});
}

export function saveRunAsCase(payload: {
  runId: number;
  projectId: number;
  caseName: string;
  description?: string | null;
}): Promise<FunctionalTestCase> {
  return postJson<FunctionalTestCase>("/api/test-runs/save-as-case", payload);
}

export function getTestRuns(): Promise<TestRun[]> {
  return getJson<TestRun[]>("/api/test-runs");
}

export function getTestRun(runId: number): Promise<TestRun> {
  return getJson<TestRun>(`/api/test-runs/${runId}`);
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

export function startTraceViewer(runId: number): Promise<TraceViewerResponse> {
  return postJson<TraceViewerResponse>(`/api/test-runs/${runId}/trace-viewer/start`, {});
}

export function getTraceViewerStatus(runId: number): Promise<TraceViewerResponse> {
  return getJson<TraceViewerResponse>(`/api/test-runs/${runId}/trace-viewer/status`);
}

export function stopTraceViewer(runId: number): Promise<TraceViewerResponse> {
  return postJson<TraceViewerResponse>(`/api/test-runs/${runId}/trace-viewer/stop`, {});
}

export function getFailureSamples(runId?: number): Promise<FailureSample[]> {
  const suffix = runId ? `?run_id=${runId}` : "";
  return getJson<FailureSample[]>(`/api/failure-samples${suffix}`);
}

export function analyzeFailureSample(sampleId: number): Promise<FailureAnalysis> {
  return postJson<FailureAnalysis>(`/api/failure-samples/${sampleId}/analyze`, {});
}

export function applyFailureAnalysisSuggestion(
  analysisId: number,
  payload: {
    suggestionIndex: number;
    action: string;
    confirm: boolean;
  }
): Promise<{ fixApplicationId: number; status: string; createdCaseVersionId: number | null; createdRuleDraftId: number | null; message: string }> {
  return postJson(`/api/failure-analyses/${analysisId}/apply`, payload);
}

export function getFixApplication(fixId: number): Promise<FixApplication> {
  return getJson<FixApplication>(`/api/fix-applications/${fixId}`);
}

export function verifyFixApplication(fixId: number): Promise<TestRun> {
  return postJson<TestRun>(`/api/fix-applications/${fixId}/verify-run`, {});
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
