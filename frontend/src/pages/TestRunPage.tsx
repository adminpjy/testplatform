import { ExternalLink } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { apiUrl, fileUrl } from "../api/client";
import {
  convertInterventionToRule,
  createCampaign,
  createTestRun,
  executeIntervention,
  getCampaignReportSummary,
  getCase,
  getProjects,
  getProjectCases,
  getProjectCampaigns,
  getRunFailureSamples,
  getRunHumanInterventions,
  getTestRun,
  getTestRunArtifacts,
  getTestRuns,
  getTestRunSteps,
  interveneStep,
  rerunTestRun,
  startCampaign,
  streamAnalyzeAndPlan
} from "../api/platform";
import { AnalysisTracePanel } from "../components/AnalysisTracePanel";
import { DebugDrawer } from "../components/DebugDrawer";
import { ErrorSummaryCard } from "../components/ErrorSummaryCard";
import { CurrentScreenshotCard } from "../components/CurrentScreenshotCard";
import { JsonCollapseBlock } from "../components/JsonCollapseBlock";
import { RunHistoryTab } from "../components/RunHistoryTab";
import { RuntimeStreamPanel } from "../components/RuntimeStreamPanel";
import { ScreenshotPreviewModal } from "../components/ScreenshotPreviewModal";
import { StepScreenshotList } from "../components/StepScreenshotList";
import { StatusBadge } from "../components/StatusBadge";
import { TestRunConfigCard } from "../components/TestRunConfigCard";
import { TraceViewerCard } from "../components/TraceViewerCard";
import type {
  AnalyzeResult,
  CampaignReportSummary,
  FailureSample,
  HumanIntervention,
  RuleDraft,
  TestArtifact,
  TestCaseDSL,
  TestCaseStep,
  FunctionalTestCase,
  TestProject,
  TestRun,
  TestCampaign,
  TestStepRun
} from "../types/platform";
import type { RuntimeMessage } from "../types/runtime";
import { normalizeRuntimeMessage } from "../types/runtime";
import { labelFailureType, labelStatus } from "../utils/displayLabels";

const DEFAULT_TEST_DATA = `{
}`;

type TestRunTab = "steps" | "history" | "failures" | "debug" | "artifacts";
type ExecutionMode = "single" | "project";

const TEST_RUN_TABS: Array<{ id: TestRunTab; label: string }> = [
  { id: "steps", label: "步骤与截图" },
  { id: "history", label: "运行记录" },
  { id: "failures", label: "失败分析" },
  { id: "debug", label: "调试详情" },
  { id: "artifacts", label: "报告与产物" }
];

export function TestRunPage() {
  const [projects, setProjects] = useState<TestProject[]>([]);
  const [projectCases, setProjectCases] = useState<FunctionalTestCase[]>([]);
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [campaigns, setCampaigns] = useState<TestCampaign[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<number | "">("");
  const [selectedCaseId, setSelectedCaseId] = useState<number | "">("");
  const [baseUrl, setBaseUrl] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [testDataJson, setTestDataJson] = useState(DEFAULT_TEST_DATA);
  const [visionFallback, setVisionFallback] = useState(false);
  const [instruction, setInstruction] = useState("");
  const [analysis, setAnalysis] = useState<AnalyzeResult | null>(null);
  const [plannedDsl, setPlannedDsl] = useState<TestCaseDSL | null>(null);
  const [analysisMessages, setAnalysisMessages] = useState<RuntimeMessage[]>([]);
  const [activeRun, setActiveRun] = useState<TestRun | null>(null);
  const [executionMode, setExecutionMode] = useState<ExecutionMode>("single");
  const [activeCampaign, setActiveCampaign] = useState<TestCampaign | null>(null);
  const [campaignReport, setCampaignReport] = useState<CampaignReportSummary | null>(null);
  const [steps, setSteps] = useState<TestStepRun[]>([]);
  const [artifacts, setArtifacts] = useState<TestArtifact[]>([]);
  const [failureSamples, setFailureSamples] = useState<FailureSample[]>([]);
  const [interventions, setInterventions] = useState<HumanIntervention[]>([]);
  const [latestRuleDraft, setLatestRuleDraft] = useState<RuleDraft | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [isCampaignExecuting, setIsCampaignExecuting] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [interventionOpen, setInterventionOpen] = useState(false);
  const [screenshotRefreshKey, setScreenshotRefreshKey] = useState(Date.now());
  const [configCollapsed, setConfigCollapsed] = useState(false);
  const [testDataOpen, setTestDataOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<TestRunTab>("steps");
  const [preview, setPreview] = useState<{ src: string; title: string } | null>(null);
  const [runtimeReloadKey, setRuntimeReloadKey] = useState(0);
  const mainViewRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    void bootstrap();
  }, []);

  useEffect(() => {
    if (!activeRun || !["created", "running", "analyzing", "planned"].includes(activeRun.status)) {
      return;
    }
    const timer = window.setInterval(() => {
      void refreshActiveRun(activeRun.id);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [activeRun?.id, activeRun?.status]);

  async function bootstrap() {
    try {
      const [projectList, runList] = await Promise.all([getProjects(), getTestRuns()]);
      setProjects(projectList);
      setRuns(runList);
      const hashCaseId = caseIdFromHash();
      if (hashCaseId) {
        const savedCase = await getCase(hashCaseId);
        setSelectedCaseId(savedCase.id);
        setSelectedProjectId(savedCase.project_id);
        await loadCasesForProject(savedCase.project_id, savedCase.id);
        await loadCampaignsForProject(savedCase.project_id);
        applyCaseToForm(savedCase, projectList);
        return;
      }
      if (projectList.length > 0) {
        const project = projectList[0];
        setSelectedProjectId(project.id);
        await loadCasesForProject(project.id);
        await loadCampaignsForProject(project.id);
        if (project.base_url) setBaseUrl(project.login_url || project.base_url);
        if (project.default_account?.username) setUsername(project.default_account.username);
      }
    } catch (error) {
      setApiError(error instanceof Error ? error.message : String(error));
    }
  }

  async function selectRun(run: TestRun, focusRuntime = false, applyToForm = true) {
    setApiError(null);
    setActiveRun(run);
    if (applyToForm) {
      await applyRunToForm(run);
    }
    const [stepList, artifactList, sampleList, interventionList] = await Promise.all([
      getTestRunSteps(run.id),
      getTestRunArtifacts(run.id),
      getRunFailureSamples(run.id),
      getRunHumanInterventions(run.id)
    ]);
    setSteps(stepList);
    setArtifacts(artifactList);
    setFailureSamples(sampleList);
    setInterventions(interventionList);
    setLatestRuleDraft(null);
    setScreenshotRefreshKey(Date.now());
    setRuntimeReloadKey((value) => value + 1);
    if (focusRuntime) {
      setActiveTab("steps");
      window.setTimeout(() => {
        mainViewRef.current?.scrollIntoView({ block: "start", behavior: "smooth" });
      }, 50);
    }
  }

  async function applyRunToForm(run: TestRun) {
    const runDsl = dslFromRun(run);
    setSelectedProjectId(run.project_id);
    await loadCasesForProject(run.project_id, run.case_id || undefined);
    setSelectedCaseId(run.case_id || "");
    setInstruction(run.instruction_snapshot || run.instruction || runDsl?.caseName || "");
    setBaseUrl(run.base_url_snapshot || run.base_url || runDsl?.baseUrl || "");
    setPlannedDsl(runDsl);
    setAnalysisMessages([]);
    const runTestData = asRecord(run.test_data_snapshot) || runDsl?.testData || {};
    setTestDataJson(JSON.stringify(runTestData, null, 2));
    const runSettings = asRecord(run.settings_snapshot) || runDsl?.settings || {};
    setVisionFallback(Boolean(runSettings.visionFallbackEnabled));
    const accountSnapshot = asRecord(run.account_snapshot);
    const credentials = asRecord(runDsl?.credentials);
    setUsername(String(accountSnapshot?.username || credentials?.username || ""));
    setPassword("");
    setAnalysis({
      readyToExecute: Boolean(runDsl),
      confidence: runDsl ? 1 : 0,
      understoodGoal: run.instruction_snapshot || run.instruction || runDsl?.caseName || run.run_code,
      missingFields: runDsl ? [] : ["测试步骤"],
      clarifyingQuestions: runDsl ? [] : ["该运行记录没有保存可执行测试步骤，无法直接带入执行。"],
      assumptions: [
        `已从运行记录 ${run.run_code} 带入配置。`,
        "密码不会从历史记录中回填；直接重跑会优先使用项目测试账号。"
      ],
      riskLevel: "low",
      normalizedInstruction: run.instruction_snapshot || run.instruction || runDsl?.caseName || ""
    });
  }

  async function handleProjectChange(projectId: number) {
    setSelectedProjectId(projectId);
    setSelectedCaseId("");
    setPlannedDsl(null);
    const project = projects.find((item) => item.id === projectId);
    if (project) {
      setBaseUrl(project.login_url || project.base_url || baseUrl);
      setUsername(project.default_account?.username || username);
    }
    await loadCasesForProject(projectId);
    await loadCampaignsForProject(projectId);
  }

  async function loadCasesForProject(projectId: number, preferredCaseId?: number) {
    const caseList = await getProjectCases(projectId);
    setProjectCases(caseList);
    if (preferredCaseId && !caseList.some((item) => item.id === preferredCaseId)) {
      setSelectedCaseId("");
    }
  }

  async function loadCampaignsForProject(projectId: number) {
    try {
      const campaignList = await getProjectCampaigns(projectId);
      setCampaigns(campaignList);
      if (campaignList[0]) {
        setActiveCampaign(campaignList[0]);
        const report = await getCampaignReportSummary(campaignList[0].id).catch(() => null);
        setCampaignReport(report);
      }
    } catch {
      setCampaigns([]);
    }
  }

  async function handleCaseChange(caseId: number | "") {
    setSelectedCaseId(caseId);
    if (!caseId) {
      setPlannedDsl(null);
      return;
    }
    const savedCase = await getCase(caseId);
    applyCaseToForm(savedCase, projects);
  }

  function applyCaseToForm(savedCase: FunctionalTestCase, projectList: TestProject[]) {
    const project = projectList.find((item) => item.id === savedCase.project_id);
    setInstruction(savedCase.natural_language_goal || savedCase.case_name);
    setPlannedDsl(savedCase.dsl_json);
    setTestDataJson(JSON.stringify(savedCase.test_data_json || {}, null, 2));
    if (project?.base_url) {
      setBaseUrl(project.login_url || project.base_url);
    }
    if (project?.default_account?.username) {
      setUsername(project.default_account.username);
    }
    setAnalysis({
      readyToExecute: Boolean(savedCase.dsl_json),
      confidence: savedCase.dsl_json ? 1 : 0,
      understoodGoal: savedCase.natural_language_goal || savedCase.case_name,
      missingFields: savedCase.dsl_json ? [] : ["测试步骤"],
      clarifyingQuestions: savedCase.dsl_json ? [] : ["该用例尚未保存测试步骤，请在用例详情页生成或保存测试步骤。"],
      assumptions: ["使用已保存的功能测试用例配置。"],
      riskLevel: savedCase.risk_level || "low",
      normalizedInstruction: savedCase.natural_language_goal || savedCase.case_name
    });
  }

  async function handleAnalyze() {
    setApiError(null);
    setIsAnalyzing(true);
    setAnalysis(null);
    setPlannedDsl(null);
    setAnalysisMessages([]);
    clearSelectedRun();
    try {
      await streamAnalyzeAndPlan({
        project_id: Number(selectedProjectId),
        instruction,
        base_url: baseUrl,
        credentials: { username, password },
        testData: parseTestData(),
        settings: { visionFallbackEnabled: visionFallback }
      }, (wireMessage) => {
        const message = normalizeRuntimeMessage(wireMessage);
        if (message.phase === "llm_chunk") {
          return;
        }
        setAnalysisMessages((current) => appendRuntimeMessage(current, message));
        const metadata = message.metadata;
        if (metadata.analysis && typeof metadata.analysis === "object") {
          setAnalysis(metadata.analysis as AnalyzeResult);
        }
        if (metadata.dsl && typeof metadata.dsl === "object") {
          setPlannedDsl(metadata.dsl as TestCaseDSL);
        }
        if (message.type === "error") {
          setApiError(message.content || "分析失败。");
        }
      });
    } catch (error) {
      setApiError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsAnalyzing(false);
    }
  }

  async function handleExecute() {
    if (!selectedProjectId) {
      setApiError("请先选择项目。");
      return;
    }
    if (!plannedDsl) {
      setApiError("请先完成分析并生成测试步骤后再开始执行。");
      return;
    }
    setApiError(null);
    setIsExecuting(true);
    setConfigCollapsed(true);
    setActiveTab("steps");
    try {
      const executableDsl = materializeDsl(plannedDsl, { baseUrl, username, password, visionFallback, instruction, testData: parseTestData() });
      const run = await createTestRun({
        project_id: Number(selectedProjectId),
        case_id: selectedCaseId ? Number(selectedCaseId) : null,
        instruction,
        base_url: baseUrl,
        dsl_json: executableDsl,
        testDataOverride: executableDsl.testData,
        settingsOverride: executableDsl.settings
      });
      const runList = await getTestRuns();
      setRuns(runList);
      await selectRun(run, false, false);
    } catch (error) {
      setApiError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsExecuting(false);
    }
  }

  async function handleProjectCampaignRun() {
    if (!selectedProjectId) {
      setApiError("请先选择项目。");
      return;
    }
    if (!canRunProjectCampaign) {
      setApiError("当前用户没有执行整个项目测试的权限，请联系项目负责人授权。");
      return;
    }
    setApiError(null);
    setIsCampaignExecuting(true);
    setConfigCollapsed(true);
    setActiveTab("history");
    try {
      const project = projects.find((item) => item.id === Number(selectedProjectId));
      const campaign = await createCampaign(Number(selectedProjectId), {
        name: `${project?.project_name || project?.name || "项目"} 全量测试 ${new Date().toLocaleString()}`,
        description: "从测试运行页发起的整个项目功能测试。",
        caseIds: null,
        settings: { source: "test_run_project_mode", visionFallbackEnabled: visionFallback }
      });
      const started = await startCampaign(campaign.id, {
        settingsOverride: { source: "test_run_project_mode", visionFallbackEnabled: visionFallback }
      });
      setActiveCampaign(started);
      const [runList, campaignList, report] = await Promise.all([
        getTestRuns(),
        getProjectCampaigns(Number(selectedProjectId)),
        getCampaignReportSummary(started.id)
      ]);
      setRuns(runList);
      setCampaigns(campaignList);
      setCampaignReport(report);
    } catch (error) {
      setApiError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsCampaignExecuting(false);
    }
  }

  async function refreshActiveCampaign() {
    if (!activeCampaign || !selectedProjectId) return;
    try {
      const [campaignList, report, runList] = await Promise.all([
        getProjectCampaigns(Number(selectedProjectId)),
        getCampaignReportSummary(activeCampaign.id),
        getTestRuns()
      ]);
      setCampaigns(campaignList);
      setActiveCampaign(campaignList.find((item) => item.id === activeCampaign.id) || activeCampaign);
      setCampaignReport(report);
      setRuns(runList);
    } catch (error) {
      setApiError(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleRerunFromHistory(run: TestRun) {
    setApiError(null);
    setIsExecuting(true);
    setConfigCollapsed(true);
    setActiveTab("steps");
    try {
      const nextRun = await rerunTestRun(run.id);
      const runList = await getTestRuns();
      setRuns(runList);
      await selectRun(nextRun, true);
    } catch (error) {
      await selectRun(run, true);
      setConfigCollapsed(false);
      setApiError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsExecuting(false);
    }
  }

  function parseTestData(): Record<string, unknown> {
    try {
      return parseTestDataFromJson(testDataJson);
    } catch (error) {
      setApiError(error instanceof Error ? error.message : String(error));
      throw error;
    }
  }

  function openPreview(src: string, title: string) {
    setPreview({ src, title });
  }

  function clearSelectedRun() {
    setActiveRun(null);
    setSteps([]);
    setArtifacts([]);
    setFailureSamples([]);
    setInterventions([]);
    setLatestRuleDraft(null);
    setScreenshotRefreshKey(Date.now());
    setRuntimeReloadKey((value) => value + 1);
  }

  async function handleCreateIntervention(userInstruction: string) {
    if (!activeRun) {
      setApiError("请先选择失败运行。");
      return;
    }
    const targetStep = steps.find((step) => step.status === "failed") || steps[steps.length - 1];
    if (!targetStep) {
      setApiError("当前运行没有可介入的步骤。");
      return;
    }
    setApiError(null);
    try {
      const intervention = await interveneStep(activeRun.id, targetStep.id, { user_instruction: userInstruction });
      setInterventions((current) => [intervention, ...current.filter((item) => item.id !== intervention.id)]);
      await reloadRunDetails(activeRun);
    } catch (error) {
      setApiError(error instanceof Error ? error.message : String(error));
      throw error;
    }
  }

  async function handleExecuteIntervention(interventionId: number) {
    if (!activeRun) {
      return;
    }
    setApiError(null);
    try {
      const intervention = await executeIntervention(activeRun.id, interventionId);
      setInterventions((current) => [intervention, ...current.filter((item) => item.id !== intervention.id)]);
      const recoveryRunId = Number(intervention.execution_result_json?.["recoveryRunId"] || 0);
      if (recoveryRunId > 0) {
        await refreshActiveRun(recoveryRunId);
      } else {
        await reloadRunDetails(activeRun);
      }
    } catch (error) {
      setApiError(error instanceof Error ? error.message : String(error));
      throw error;
    }
  }

  async function handleConvertIntervention(interventionId: number) {
    if (!activeRun) {
      return;
    }
    setApiError(null);
    try {
      const draft = await convertInterventionToRule(activeRun.id, interventionId);
      setLatestRuleDraft(draft);
      setRuntimeReloadKey((value) => value + 1);
    } catch (error) {
      setApiError(error instanceof Error ? error.message : String(error));
      throw error;
    }
  }

  async function reloadRunDetails(run: TestRun) {
    const [stepList, artifactList, sampleList, interventionList] = await Promise.all([
      getTestRunSteps(run.id),
      getTestRunArtifacts(run.id),
      getRunFailureSamples(run.id),
      getRunHumanInterventions(run.id)
    ]);
    setSteps(stepList);
    setArtifacts(artifactList);
    setFailureSamples(sampleList);
    setInterventions(interventionList);
    setScreenshotRefreshKey(Date.now());
    setRuntimeReloadKey((value) => value + 1);
  }

  async function refreshActiveRun(runId: number) {
    try {
      const [nextRun, stepList, artifactList, sampleList, interventionList, runList] = await Promise.all([
        getTestRun(runId),
        getTestRunSteps(runId),
        getTestRunArtifacts(runId),
        getRunFailureSamples(runId),
        getRunHumanInterventions(runId),
        getTestRuns()
      ]);
      setActiveRun(nextRun);
      setSteps(stepList);
      setArtifacts(artifactList);
      setFailureSamples(sampleList);
      setInterventions(interventionList);
      setRuns(runList);
      setScreenshotRefreshKey(Date.now());
    } catch (error) {
      setApiError(error instanceof Error ? error.message : String(error));
    }
  }

  const canExecute = Boolean(plannedDsl && selectedProjectId && instruction.trim() && !isAnalyzing && !isExecuting);
  const executeDisabledReason = executionGateReason({
    plannedDsl,
    selectedProjectId,
    instruction,
    isAnalyzing,
    isExecuting,
    analysisMessages
  });
  const canIntervene = Boolean(activeRun && ["failed", "needs_human"].includes(activeRun.status));
  const selectedProject = projects.find((item) => item.id === Number(selectedProjectId)) || null;
  const canRunProjectCampaign = Boolean(
    selectedProject?.current_user_permissions?.run_campaign || selectedProject?.current_user_role === "owner" || selectedProject?.current_user_role === "admin"
  );

  return (
    <div className="test-run-workspace">
      <section className="workspace-section">
        <div className="workspace-section__heading">
          <div>
            <h2>基础配置区</h2>
            <p>选择项目、功能测试用例、账号、测试数据和自然语言测试目标。</p>
          </div>
        </div>
        <div className="surface-panel execution-mode-panel">
          <div className="segmented-control">
            <button className={executionMode === "single" ? "segmented-control__item segmented-control__item--active" : "segmented-control__item"} type="button" onClick={() => setExecutionMode("single")}>单个目标/用例</button>
            <button className={executionMode === "project" ? "segmented-control__item segmented-control__item--active" : "segmented-control__item"} type="button" onClick={() => setExecutionMode("project")}>整个项目测试</button>
          </div>
        </div>
        {executionMode === "project" ? (
          <ProjectCampaignPanel
            projects={projects}
            cases={projectCases}
            campaigns={campaigns}
            selectedProjectId={selectedProjectId}
            visionFallback={visionFallback}
            activeCampaign={activeCampaign}
            campaignReport={campaignReport}
            canRunProjectCampaign={canRunProjectCampaign}
            isCampaignExecuting={isCampaignExecuting}
            onProjectChange={(value) => void handleProjectChange(value)}
            onVisionFallbackChange={setVisionFallback}
            onStart={() => void handleProjectCampaignRun()}
            onRefresh={() => void refreshActiveCampaign()}
            onSelectCampaign={(campaign) => {
              setActiveCampaign(campaign);
              void getCampaignReportSummary(campaign.id).then(setCampaignReport).catch((error) => setApiError(error instanceof Error ? error.message : String(error)));
            }}
          />
        ) : (
          <TestRunConfigCard
            collapsed={configCollapsed}
            testDataOpen={testDataOpen}
            projects={projects}
            cases={projectCases}
            selectedProjectId={selectedProjectId}
            selectedCaseId={selectedCaseId}
            baseUrl={baseUrl}
            username={username}
            password={password}
            visionFallback={visionFallback}
            instruction={instruction}
            testDataJson={testDataJson}
            analysis={analysis}
            canExecute={canExecute}
            executeDisabledReason={executeDisabledReason}
            canIntervene={canIntervene}
            isAnalyzing={isAnalyzing}
            isExecuting={isExecuting}
            hasActiveRun={Boolean(activeRun)}
            onToggleCollapsed={() => setConfigCollapsed((value) => !value)}
            onToggleTestData={() => setTestDataOpen((value) => !value)}
            onProjectChange={(value) => void handleProjectChange(value)}
            onCaseChange={(value) => void handleCaseChange(value)}
            onBaseUrlChange={setBaseUrl}
            onUsernameChange={setUsername}
            onPasswordChange={setPassword}
            onVisionFallbackChange={setVisionFallback}
            onInstructionChange={setInstruction}
            onTestDataChange={setTestDataJson}
            onAnalyze={() => void handleAnalyze()}
            onExecute={() => void handleExecute()}
            onIntervention={() => setInterventionOpen(true)}
            onDebug={() => setDrawerOpen(true)}
          />
        )}
        {apiError ? <pre className="error-detail error-detail--collapsed test-run-api-error">{displayErrorText(apiError)}</pre> : null}
      </section>

      <section className="workspace-section task-observation-section">
        <div className="workspace-section__heading">
          <div>
            <h2>任务分解观察区</h2>
            <p>查看大模型交互状态、信息完整性判断和生成的测试步骤。</p>
          </div>
        </div>
        {analysisMessages.length > 0 || plannedDsl || isAnalyzing ? (
          <AnalysisTracePanel messages={analysisMessages} analyzing={isAnalyzing} dsl={plannedDsl} onDslChange={setPlannedDsl} />
        ) : (
          <div className="surface-panel empty-state">点击“分析”后显示大模型交互状态和测试步骤预览</div>
        )}
      </section>

      <section className="workspace-section execution-observation-section">
        <div className="workspace-section__heading">
          <div>
            <h2>智能执行观察区</h2>
            <p>实时查看执行消息、执行环境状态、当前截图和失败摘要。</p>
          </div>
        </div>
        {activeRun ? (
          <div className="main-grid execution-observation-grid" ref={mainViewRef}>
            <div className="runtime-column">
              <RuntimeStreamPanel
                key={`${activeRun.id}-${runtimeReloadKey}`}
                runId={activeRun.id}
                steps={steps}
                onPreviewScreenshot={openPreview}
              />
            </div>
            <div className="screenshot-column">
              <CurrentScreenshotCard
                run={activeRun}
                steps={steps}
                artifacts={artifacts}
                refreshKey={screenshotRefreshKey}
                onRefresh={() => setScreenshotRefreshKey(Date.now())}
                onPreview={openPreview}
              />
              <ErrorSummaryCard
                run={activeRun}
                steps={steps}
                apiError={apiError}
                onIntervention={() => setInterventionOpen(true)}
                onDebug={() => setDrawerOpen(true)}
              />
            </div>
          </div>
        ) : (
          <div className="surface-panel empty-state runtime-empty-state" ref={mainViewRef}>
            智能执行观察区仅显示当前执行或从“运行记录”中选择的运行。
          </div>
        )}
      </section>

      <section className="workspace-section result-analysis-section">
        <div className="workspace-section__heading">
          <div>
            <h2>结果分析区</h2>
            <p>查看步骤截图、运行记录、失败样本、调试详情和报告产物。</p>
          </div>
        </div>
        <section className="surface-panel tabs-area">
          <div className="tab-strip test-run-tabs">
            {TEST_RUN_TABS.map((tab) => (
              <button
                className={activeTab === tab.id ? "tab-button tab-button--active" : "tab-button"}
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <div className="tab-content-panel">
            {activeTab === "steps" ? <StepScreenshotList steps={steps} artifacts={artifacts} onPreview={openPreview} /> : null}
            {activeTab === "history" ? (
              <RunHistoryTab
                runs={runs}
                activeRun={activeRun}
                onSelectRun={(run) => {
                  setConfigCollapsed(false);
                  void selectRun(run, true);
                }}
                onRerun={(run) => void handleRerunFromHistory(run)}
              />
            ) : null}
            {activeTab === "failures" ? (
              <FailureAnalysisTab
                run={activeRun}
                steps={steps}
                failureSamples={failureSamples}
                apiError={apiError}
                onIntervention={() => setInterventionOpen(true)}
                onDebug={() => setDrawerOpen(true)}
                onPreview={openPreview}
              />
            ) : null}
            {activeTab === "debug" ? (
              <DebugDetailsTab
                run={activeRun}
                steps={steps}
                artifacts={artifacts}
                failureSamples={failureSamples}
                interventions={interventions}
              />
            ) : null}
            {activeTab === "artifacts" ? <ReportArtifactsTab run={activeRun} artifacts={artifacts} /> : null}
          </div>
        </section>
      </section>

      <DebugDrawer
        open={drawerOpen || interventionOpen}
        title={interventionOpen ? "人工介入" : "调试详情"}
        run={activeRun}
        steps={steps}
        artifacts={artifacts}
        failureSamples={failureSamples}
        interventions={interventions}
        latestRuleDraft={latestRuleDraft}
        interventionMode={interventionOpen}
        onCreateIntervention={handleCreateIntervention}
        onExecuteIntervention={handleExecuteIntervention}
        onConvertIntervention={handleConvertIntervention}
        onClose={() => {
          setDrawerOpen(false);
          setInterventionOpen(false);
        }}
      />
      <ScreenshotPreviewModal src={preview?.src || null} title={preview?.title} onClose={() => setPreview(null)} />
    </div>
  );
}

function ProjectCampaignPanel({
  projects,
  cases,
  campaigns,
  selectedProjectId,
  visionFallback,
  activeCampaign,
  campaignReport,
  canRunProjectCampaign,
  isCampaignExecuting,
  onProjectChange,
  onVisionFallbackChange,
  onStart,
  onRefresh,
  onSelectCampaign
}: {
  projects: TestProject[];
  cases: FunctionalTestCase[];
  campaigns: TestCampaign[];
  selectedProjectId: number | "";
  visionFallback: boolean;
  activeCampaign: TestCampaign | null;
  campaignReport: CampaignReportSummary | null;
  canRunProjectCampaign: boolean;
  isCampaignExecuting: boolean;
  onProjectChange: (projectId: number) => void;
  onVisionFallbackChange: (value: boolean) => void;
  onStart: () => void;
  onRefresh: () => void;
  onSelectCampaign: (campaign: TestCampaign) => void;
}) {
  const selectedProject = projects.find((item) => item.id === Number(selectedProjectId)) || null;
  const executableCaseCount = cases.filter((item) => item.status !== "deleted" && item.status !== "disabled").length;
  return (
    <section className="surface-panel project-campaign-panel">
      <div className="panel-heading">
        <div>
          <h2>整个项目测试</h2>
          <span>一次启动当前项目下所有可执行功能测试用例，最终形成项目级测试报告。</span>
        </div>
        <div className="action-bar">
          <button className="secondary-button" type="button" onClick={onRefresh} disabled={!activeCampaign}>刷新报告</button>
          <button className="primary-button" type="button" onClick={onStart} disabled={!selectedProjectId || !canRunProjectCampaign || isCampaignExecuting || executableCaseCount === 0}>
            {isCampaignExecuting ? "启动中" : "开始整个项目测试"}
          </button>
        </div>
      </div>
      <div className="form-grid">
        <label>
          <span>项目</span>
          <select value={selectedProjectId} onChange={(event) => onProjectChange(Number(event.target.value))}>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>{project.project_name || project.name}</option>
            ))}
          </select>
        </label>
        <label>
          <span>可执行用例数量</span>
          <input value={`${executableCaseCount} / ${cases.length}`} readOnly />
        </label>
        <label>
          <span>执行权限</span>
          <input value={canRunProjectCampaign ? "允许执行整个项目" : "未授权执行整个项目"} readOnly />
        </label>
      </div>
      <div className="toggle-grid">
        <label className="toggle-row">
          <input type="checkbox" checked={visionFallback} onChange={(event) => onVisionFallbackChange(event.target.checked)} />
          <span>启用视觉识别兜底</span>
        </label>
      </div>
      {!canRunProjectCampaign && selectedProject ? (
        <div className="empty-state compact-empty-state">当前用户没有“执行整个项目”权限，可由项目负责人在项目成员中开启。</div>
      ) : null}
      <div className="campaign-overview-grid">
        <div>
          <h3>最近批次</h3>
          <div className="campaign-list">
            {campaigns.slice(0, 5).map((campaign) => (
              <button
                className={activeCampaign?.id === campaign.id ? "campaign-list__item campaign-list__item--active" : "campaign-list__item"}
                key={campaign.id}
                type="button"
                onClick={() => onSelectCampaign(campaign)}
              >
                <span>{campaign.name}</span>
                <StatusBadge value={campaign.status} />
              </button>
            ))}
            {campaigns.length === 0 ? <div className="empty-state compact-empty-state">暂无项目批次</div> : null}
          </div>
        </div>
        <div>
          <h3>项目报告摘要</h3>
          {campaignReport ? (
            <div className="campaign-report-summary">
              <div><span>批次</span><strong>{campaignReport.campaignCode}</strong></div>
              <div><span>状态</span><StatusBadge value={campaignReport.status} /></div>
              <div><span>总数</span><strong>{String(campaignReport.totals.total ?? 0)}</strong></div>
              <div><span>通过</span><strong>{String(campaignReport.totals.passed ?? 0)}</strong></div>
              <div><span>失败</span><strong>{String(campaignReport.totals.failed ?? 0)}</strong></div>
              <div><span>阻塞</span><strong>{String(campaignReport.totals.blocked ?? 0)}</strong></div>
            </div>
          ) : (
            <div className="empty-state compact-empty-state">启动或选择批次后显示项目报告摘要。</div>
          )}
          {campaignReport?.recommendations?.length ? (
            <ul className="campaign-recommendations">
              {campaignReport.recommendations.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}
            </ul>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function FailureAnalysisTab({
  run,
  steps,
  failureSamples,
  apiError,
  onIntervention,
  onDebug,
  onPreview
}: {
  run: TestRun | null;
  steps: TestStepRun[];
  failureSamples: FailureSample[];
  apiError: string | null;
  onIntervention: () => void;
  onDebug: () => void;
  onPreview: (src: string, title: string) => void;
}) {
  if (!run && !apiError) {
    return <div className="empty-state">选择运行后显示失败分析</div>;
  }
  return (
    <div className="failure-analysis-tab">
      <ErrorSummaryCard run={run} steps={steps} apiError={apiError} onIntervention={onIntervention} onDebug={onDebug} />
      {failureSamples.length === 0 ? (
        <div className="empty-state">当前运行没有失败样本</div>
      ) : (
        <div className="failure-sample-list">
          {failureSamples.map((sample) => {
            const screenshot = sample.screenshot_path ? fileUrl(sample.screenshot_path) : null;
            return (
              <article className="failure-sample" key={sample.id}>
                <div className="panel-heading">
                  <h2>{labelFailureType(sample.failure_type)}</h2>
                  <span>{labelStatus(sample.status)}</span>
                </div>
                <p>{sample.failure_summary || "暂无摘要"}</p>
                {screenshot ? (
                  <button className="failure-sample__screenshot" type="button" onClick={() => onPreview(screenshot, "失败截图")}>
                    <img src={screenshot} alt="失败截图" />
                  </button>
                ) : null}
                <div className="artifact-link-grid">
                  {sample.dom_snapshot_path ? <a href={fileUrl(sample.dom_snapshot_path)} target="_blank" rel="noreferrer">页面结构快照</a> : null}
                  {sample.accessibility_snapshot_path ? <a href={fileUrl(sample.accessibility_snapshot_path)} target="_blank" rel="noreferrer">可访问性快照</a> : null}
                  {sample.locator_debug_path ? <a href={fileUrl(sample.locator_debug_path)} target="_blank" rel="noreferrer">定位调试文件</a> : null}
                  {sample.runtime_stream_path ? <a href={fileUrl(sample.runtime_stream_path)} target="_blank" rel="noreferrer">运行消息</a> : null}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}

function DebugDetailsTab({
  run,
  steps,
  artifacts,
  failureSamples,
  interventions
}: {
  run: TestRun | null;
  steps: TestStepRun[];
  artifacts: TestArtifact[];
  failureSamples: FailureSample[];
  interventions: HumanIntervention[];
}) {
  if (!run) {
    return <div className="empty-state">选择运行后显示调试详情</div>;
  }
  return (
    <div className="debug-details-tab">
      <JsonCollapseBlock title="查看运行原始数据" value={run} />
      <JsonCollapseBlock title="查看步骤原始数据" value={steps} />
      <JsonCollapseBlock title="查看产物原始数据" value={artifacts} />
      <JsonCollapseBlock title="查看失败样本原始数据" value={failureSamples} />
      <JsonCollapseBlock title="查看人工介入原始数据" value={interventions} />
    </div>
  );
}

function ReportArtifactsTab({ run, artifacts }: { run: TestRun | null; artifacts: TestArtifact[] }) {
  if (!run) {
    return <div className="empty-state">选择运行后显示报告与产物</div>;
  }
  return (
    <div className="report-artifacts-tab">
      <TraceViewerCard run={run} artifacts={artifacts} />
      <a className="secondary-link" href={apiUrl(`/api/reports/${run.id}`)} target="_blank" rel="noreferrer">
        <ExternalLink size={14} />
        打开测试报告
      </a>
      <div className="artifact-link-grid artifact-link-grid--dense">
        {artifacts.map((artifact) => (
          <a href={fileUrl(artifact.file_path)} target="_blank" rel="noreferrer" key={artifact.id}>
            {artifactLabel(artifact.artifact_type)}
          </a>
        ))}
      </div>
      {artifacts.length === 0 ? <div className="empty-state">暂无产物</div> : null}
    </div>
  );
}

function artifactLabel(type: string): string {
  if (type === "dom_snapshot") return "页面结构快照";
  if (type === "accessibility_snapshot") return "可访问性快照";
  if (type === "locator_debug") return "定位调试文件";
  if (type === "runtime_stream") return "运行消息";
  if (type === "execution_trace") return "执行轨迹";
  if (type === "process_screenshots") return "过程截图清单";
  if (type === "process_screenshot") return "过程截图";
  if (type === "playwright_trace") return "执行轨迹文件";
  if (type === "summary") return "运行摘要";
  if (type === "report") return "测试报告";
  if (type === "screenshot") return "步骤截图";
  if (type === "sandbox_screenshot") return "执行环境启动截图";
  return "其他产物";
}

function appendRuntimeMessage(current: RuntimeMessage[], next: RuntimeMessage): RuntimeMessage[] {
  const existingIndex = current.findIndex((message) => message.id === next.id);
  if (existingIndex >= 0) {
    const copy = [...current];
    copy[existingIndex] = next;
    return copy;
  }
  return [...current, next].sort((left, right) => left.id - right.id);
}

function executionGateReason({
  plannedDsl,
  selectedProjectId,
  instruction,
  isAnalyzing,
  isExecuting,
  analysisMessages
}: {
  plannedDsl: TestCaseDSL | null;
  selectedProjectId: number | "";
  instruction: string;
  isAnalyzing: boolean;
  isExecuting: boolean;
  analysisMessages: RuntimeMessage[];
}): string | null {
  if (isExecuting) return "当前正在执行。";
  if (plannedDsl) return null;
  if (isAnalyzing) return "正在分析，等待测试步骤生成后才能开始执行。";
  if (!selectedProjectId) return "请选择项目后再分析。";
  if (!instruction.trim()) return "请输入自然语言测试目标。";
  const errorMessage = [...analysisMessages].reverse().find((message) => message.type === "error");
  if (errorMessage?.content) {
    return `测试步骤未生成：${compactText(errorMessage.content)}`;
  }
  const analysis = latestAnalysisResult(analysisMessages);
  if (analysis && analysis.readyToExecute === false) {
    const missingFields = Array.isArray(analysis.missingFields) ? analysis.missingFields.map(String) : [];
    const questions = Array.isArray(analysis.clarifyingQuestions) ? analysis.clarifyingQuestions.map(String) : [];
    const reasons = [...missingFields.map((field) => `缺少 ${field}`), ...questions];
    return reasons.length > 0 ? `测试步骤未生成：${reasons[0]}` : "测试步骤未生成：当前信息不足。";
  }
  if (analysisMessages.length > 0) {
    return "测试步骤未生成：请查看任务分解观察区中的失败原因。";
  }
  return "请先点击“分析”，生成测试步骤后再开始执行。";
}

function latestAnalysisResult(messages: RuntimeMessage[]): Record<string, unknown> | null {
  const message = [...messages].reverse().find((item) => item.metadata.analysis && typeof item.metadata.analysis === "object");
  return message?.metadata.analysis as Record<string, unknown> | null;
}

function compactText(value: string): string {
  const normalized = value.replace(/\s+/g, " ").trim().replace(/LLM/g, "大模型").replace(/DSL/g, "测试步骤").replace(/JSON/g, "结构化输出");
  return normalized.length > 90 ? `${normalized.slice(0, 90)}...` : normalized;
}

function displayErrorText(value: string): string {
  return value
    .replace(/LLM provider/g, "大模型服务")
    .replace(/LLM/g, "大模型")
    .replace(/DSL/g, "测试步骤")
    .replace(/JSON/g, "结构化输出")
    .replace(/HTTP/g, "网络请求");
}

function materializeDsl(
  planned: TestCaseDSL,
  context: {
    baseUrl: string;
    username: string;
    password: string;
    visionFallback: boolean;
    instruction: string;
    testData: Record<string, unknown>;
  }
): TestCaseDSL {
  const steps = planned.steps.length > 0 ? planned.steps : fallbackSteps(context);
  const explicitCriteria = recordCriteriaFromInstruction(context.instruction);
  const mergedTestData = applyRecordCriteriaToTestData(
    {
      ...(planned.testData || {}),
      ...context.testData
    },
    explicitCriteria
  );
  const conflicts = recordCriteriaConflicts(context.testData, explicitCriteria);
  return {
    ...planned,
    caseName: planned.caseName || "自然语言测试执行",
    baseUrl: context.baseUrl || planned.baseUrl,
    credentials: {
      username: context.username,
      password: context.password,
      secret_ref: "runtime_form_password"
    },
    testData: mergedTestData,
    settings: {
      ...planned.settings,
      visionFallbackEnabled: context.visionFallback
    },
    steps: steps.map((step) => applyRecordCriteriaToStep(hydrateStep(step, context), explicitCriteria, conflicts))
  };
}

function dslFromRun(run: TestRun): TestCaseDSL | null {
  const raw = asRecord(run.dsl_snapshot) || asRecord(run.dsl_json);
  if (!raw) {
    return null;
  }
  const steps = Array.isArray(raw.steps) ? (raw.steps.filter((step) => step && typeof step === "object") as TestCaseStep[]) : [];
  if (steps.length === 0) {
    return null;
  }
  return {
    caseName: String(raw.caseName || raw.case_name || run.run_code),
    baseUrl: String(raw.baseUrl || raw.base_url || run.base_url_snapshot || run.base_url || ""),
    credentials: asRecord(raw.credentials) || {},
    testData: asRecord(raw.testData) || asRecord(raw.test_data) || {},
    settings: asRecord(raw.settings) || {},
    steps,
    missingFields: Array.isArray(raw.missingFields) ? raw.missingFields.map(String) : [],
    clarifyingQuestions: Array.isArray(raw.clarifyingQuestions) ? raw.clarifyingQuestions.map(String) : []
  };
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function recordCriteriaFromInstruction(instruction: string): Record<string, string> {
  const fields = ["流程实例号", "实例号", "申请编号", "单据编号", "工单号", "单号", "编号"];
  for (const field of fields) {
    const match = instruction.match(new RegExp(`${field}\\s*(?:为|是|=|:|：)?\\s*[“"']?\\s*([A-Za-z0-9_-]{3,})\\s*[”"']?`));
    if (match?.[1]) {
      return { [field.includes("实例号") ? "实例号" : field]: match[1] };
    }
  }
  const approvalMatch = instruction.match(/审批\s*[“"']?\s*([A-Za-z0-9_-]{3,})\s*[”"']?/);
  if (approvalMatch?.[1] && ["待办", "流程", "单据", "实例"].some((token) => instruction.includes(token))) {
    return { 实例号: approvalMatch[1] };
  }
  return {};
}

function applyRecordCriteriaToTestData(
  testData: Record<string, unknown>,
  criteria: Record<string, string>
): Record<string, unknown> {
  const next = { ...testData };
  for (const [field, value] of Object.entries(criteria)) {
    const aliases = recordFieldAliases(field);
    const matched = aliases.filter((alias) => Object.prototype.hasOwnProperty.call(next, alias));
    if (matched.length === 0) {
      next[field] = value;
    } else {
      for (const alias of matched) {
        next[alias] = value;
      }
    }
  }
  return next;
}

function applyRecordCriteriaToStep(
  step: TestCaseStep,
  criteria: Record<string, string>,
  conflicts: Array<[string, string]>
): TestCaseStep {
  if (Object.keys(criteria).length === 0) {
    return step;
  }
  const next: TestCaseStep = { ...step };
  if (["query_table", "query_table_count"].includes(String(next.action))) {
    next.queryConditions = mergeCriteriaObject(asRecord(next.queryConditions), criteria);
    next.criteria = mergeCriteriaObject(asRecord(next.criteria), criteria);
  }
  if (["open_table_row", "open_row_link_or_detail", "click_table_row_action"].includes(String(next.action))) {
    next.rowCriteria = mergeCriteriaObject(asRecord(next.rowCriteria), criteria);
  }
  for (const key of ["queryConditions", "query_conditions", "criteria", "conditions", "rowCriteria", "row_criteria"]) {
    const value = asRecord(next[key]);
    if (value) {
      next[key] = mergeCriteriaObject(value, criteria);
    }
  }
  for (const key of ["target", "description", "name", "stepName", "step_name", "readableDescription"]) {
    if (typeof next[key] === "string") {
      next[key] = replaceConflictingValues(String(next[key]), conflicts);
    }
  }
  return next;
}

function mergeCriteriaObject(current: Record<string, unknown> | null, criteria: Record<string, string>): Record<string, unknown> {
  const next = { ...(current || {}) };
  for (const [field, value] of Object.entries(criteria)) {
    const alias = recordFieldAliases(field).find((candidate) => Object.prototype.hasOwnProperty.call(next, candidate)) || field;
    next[alias] = value;
  }
  return next;
}

function recordCriteriaConflicts(
  testData: Record<string, unknown>,
  criteria: Record<string, string>
): Array<[string, string]> {
  const conflicts: Array<[string, string]> = [];
  for (const [field, value] of Object.entries(criteria)) {
    for (const alias of recordFieldAliases(field)) {
      const oldValue = testData[alias];
      if (oldValue != null && String(oldValue) !== value) {
        conflicts.push([String(oldValue), value]);
      }
    }
  }
  return conflicts;
}

function replaceConflictingValues(value: string, conflicts: Array<[string, string]>): string {
  return conflicts.reduce((current, [oldValue, newValue]) => current.split(oldValue).join(newValue), value);
}

function recordFieldAliases(field: string): string[] {
  if (field.includes("实例号")) {
    return ["实例号", "流程实例号", "instanceNo", "instance_no", "processInstanceId", "process_instance_id"];
  }
  if (["编号", "单据编号", "单号", "申请编号", "工单号"].includes(field)) {
    return [field, "编号", "单据编号", "单号", "申请编号", "工单号", "recordNo", "record_no"];
  }
  return [field];
}

function hydrateStep(step: TestCaseStep, context: { baseUrl: string; username: string; password: string }): TestCaseStep {
  const target = String(step.target || "");
  if (isBrittleLoginSuccessStep(step)) {
    return {
      ...step,
      action: "wait",
      target: "登录后页面稳定",
      ms: Number(step.ms || 1500),
      description: "登录成功后可能返回门户首页，不固定等待“工作台”等页面文字。",
      originalAction: step.originalAction || step.action,
      originalTarget: step.originalTarget || step.target,
      text: undefined,
      selector: undefined
    };
  }
  if (step.action === "business_goal" && target.includes("登录")) {
    return {
      ...step,
      username: context.username,
      password: context.password,
      credentials: {
        ...(step.credentials || {}),
        username: context.username,
        password: context.password,
        secret_ref: "runtime_form_password"
      }
    };
  }
  if (step.action === "assert_text_exists" && target === "我的待办") {
    return { ...step, action: "assert_url_contains", target: "/todo" };
  }
  if (step.action === "open_url") {
    return { ...step, target: context.baseUrl };
  }
  if (target.includes("用户名")) {
    return { ...step, value: context.username };
  }
  if (target.includes("密码")) {
    return { ...step, value: context.password };
  }
  return step;
}

function fallbackSteps(context: { baseUrl: string; username: string; password: string; instruction: string }): TestCaseStep[] {
  const steps: TestCaseStep[] = [
    { action: "open_url", target: context.baseUrl },
    { action: "input", target: "用户名", value: context.username },
    { action: "input", target: "密码", value: context.password },
    { action: "click", target: "登录" }
  ];
  if (context.instruction.includes("我的待办")) {
    steps.push({
      action: "navigate_path",
      target: "工作台/我的待办",
      pathSegments: ["工作台", "我的待办"],
      navigationType: "menu_path"
    });
    steps.push({ action: "assert_url_contains", target: "/todo" });
  } else {
    steps.push({ action: "wait", target: "登录后页面稳定", ms: 1500, description: "等待登录后跳转稳定。" });
  }
  return steps;
}

function isBrittleLoginSuccessStep(step: TestCaseStep): boolean {
  if (!["wait_for_text", "assert_text_exists"].includes(step.action)) return false;
  const target = String(step.target || "");
  const text = String(step.text || target || "");
  const context = [
    target,
    text,
    step.description,
    step.stepName,
    step.step_name,
    step.name
  ].map((value) => String(value || "")).join(" ");
  return mentionsLoginSuccess(context) && isGenericLoginHomeMarker(text);
}

function mentionsLoginSuccess(value: string): boolean {
  return ["登录成功", "登陆成功", "登录成功标识", "登陆成功标识", "登录后", "登录完成"].some((token) => value.includes(token));
}

function isGenericLoginHomeMarker(value: string): boolean {
  const normalized = value.replace(/[\s，,。；;：:"'“”‘’]+/g, "");
  return ["工作台", "首页", "主页", "门户", "门户首页", "系统首页", "后台首页", "Home", "home"].includes(normalized);
}

function parseTestDataFromJson(value: string): Record<string, unknown> {
  if (!value.trim()) {
    return {};
  }
  const parsed = JSON.parse(value) as unknown;
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("测试数据必须是结构化对象。");
  }
  return parsed as Record<string, unknown>;
}

function caseIdFromHash(): number | null {
  const match = window.location.hash.match(/[?&]caseId=(\d+)/);
  return match ? Number(match[1]) : null;
}
