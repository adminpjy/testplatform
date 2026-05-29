import { ExternalLink } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { apiUrl, fileUrl } from "../api/client";
import {
  convertInterventionToRule,
  createTestRun,
  executeIntervention,
  getCase,
  getProjects,
  getProjectCases,
  getSystems,
  getRunFailureSamples,
  getRunHumanInterventions,
  getTestRun,
  getTestRunArtifacts,
  getTestRuns,
  getTestRunSteps,
  interveneStep,
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
import { TestRunConfigCard } from "../components/TestRunConfigCard";
import { TraceViewerCard } from "../components/TraceViewerCard";
import type {
  AnalyzeResult,
  FailureSample,
  HumanIntervention,
  RuleDraft,
  TestArtifact,
  TestCaseDSL,
  TestCaseStep,
  FunctionalTestCase,
  TestProject,
  TestRun,
  TestStepRun,
  TestSystem
} from "../types/platform";
import type { RuntimeMessage } from "../types/runtime";
import { normalizeRuntimeMessage } from "../types/runtime";

const DEFAULT_TEST_DATA = `{
  "用户名": "test001",
  "手机号": "13800000000",
  "组织机构": "信息中心",
  "负责人": "张三",
  "开始日期": "2026-06-01",
  "结束日期": "2026-06-03"
}`;

type TestRunTab = "steps" | "history" | "failures" | "debug" | "artifacts";

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
  const [systems, setSystems] = useState<TestSystem[]>([]);
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<number | "">("");
  const [selectedCaseId, setSelectedCaseId] = useState<number | "">("");
  const [selectedSystemId, setSelectedSystemId] = useState<number | "">("");
  const [baseUrl, setBaseUrl] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [testDataJson, setTestDataJson] = useState(DEFAULT_TEST_DATA);
  const [visionFallback, setVisionFallback] = useState(false);
  const [instruction, setInstruction] = useState("1.打开真实内网系统 https://work.bypc.com.cn/，如果跳转到统一身份认证页面，等待登录页面加载完成，输入测试账号和密码，点击登录，登录后验证进入系统首页。2.进入“工作台-我的待办”3.获取待办列表数量4.循环点击列表中的链接，弹出对话框5.点击“返回”/取消/关闭等代表关闭对话框的按钮，关闭对话框6.反复4-5步，直至所有行被点击.");
  const [analysis, setAnalysis] = useState<AnalyzeResult | null>(null);
  const [plannedDsl, setPlannedDsl] = useState<TestCaseDSL | null>(null);
  const [analysisMessages, setAnalysisMessages] = useState<RuntimeMessage[]>([]);
  const [activeRun, setActiveRun] = useState<TestRun | null>(null);
  const [steps, setSteps] = useState<TestStepRun[]>([]);
  const [artifacts, setArtifacts] = useState<TestArtifact[]>([]);
  const [failureSamples, setFailureSamples] = useState<FailureSample[]>([]);
  const [interventions, setInterventions] = useState<HumanIntervention[]>([]);
  const [latestRuleDraft, setLatestRuleDraft] = useState<RuleDraft | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
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
      const [projectList, systemList, runList] = await Promise.all([getProjects(), getSystems(), getTestRuns()]);
      setProjects(projectList);
      setSystems(systemList);
      setRuns(runList);
      const hashCaseId = caseIdFromHash();
      if (hashCaseId) {
        const savedCase = await getCase(hashCaseId);
        setSelectedCaseId(savedCase.id);
        setSelectedProjectId(savedCase.project_id);
        await loadCasesForProject(savedCase.project_id, savedCase.id);
        applyCaseToForm(savedCase, projectList);
        return;
      }
      if (projectList.length > 0) {
        const project = projectList[0];
        setSelectedProjectId(project.id);
        await loadCasesForProject(project.id);
        if (project.base_url) setBaseUrl(project.login_url || project.base_url);
        if (project.default_account?.username) setUsername(project.default_account.username);
      }
      if (systemList.length > 0) {
        const system = systemList[0];
        setSelectedSystemId(system.id);
        setBaseUrl(resolveSystemUrl(system));
        setUsername(system.accounts[0]?.username || "");
      }
    } catch (error) {
      setApiError(error instanceof Error ? error.message : String(error));
    }
  }

  async function selectRun(run: TestRun, focusRuntime = false) {
    setActiveRun(run);
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

  async function handleProjectChange(projectId: number) {
    setSelectedProjectId(projectId);
    setSelectedCaseId("");
    setPlannedDsl(null);
    const project = projects.find((item) => item.id === projectId);
    if (project) {
      setBaseUrl(project.login_url || project.base_url || baseUrl);
      setUsername(project.default_account?.username || username);
      const system = systems.find((item) => item.id === project.system_id);
      if (system) {
        handleSystemChange(system.id);
      }
    }
    await loadCasesForProject(projectId);
  }

  async function loadCasesForProject(projectId: number, preferredCaseId?: number) {
    const caseList = await getProjectCases(projectId);
    setProjectCases(caseList);
    if (preferredCaseId && !caseList.some((item) => item.id === preferredCaseId)) {
      setSelectedCaseId("");
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
      missingFields: savedCase.dsl_json ? [] : ["DSL"],
      clarifyingQuestions: savedCase.dsl_json ? [] : ["该用例尚未保存 DSL，请在用例详情页生成或保存 DSL。"],
      assumptions: ["使用已保存的功能测试用例配置。"],
      riskLevel: savedCase.risk_level || "low",
      normalizedInstruction: savedCase.natural_language_goal || savedCase.case_name
    });
  }

  function handleSystemChange(systemId: number) {
    setSelectedSystemId(systemId);
    const system = systems.find((item) => item.id === systemId);
    if (system) {
      setBaseUrl(resolveSystemUrl(system));
      setUsername(system.accounts[0]?.username || username);
    }
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
        system_id: selectedSystemId ? Number(selectedSystemId) : undefined,
        instruction,
        base_url: baseUrl,
        credentials: { username, password },
        testData: parseTestData(),
        settings: { visionFallbackEnabled: visionFallback },
        stream: true
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
      setApiError("请先完成分析并生成 DSL 后再开始执行。");
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
        system_id: selectedSystemId ? Number(selectedSystemId) : null,
        case_id: selectedCaseId ? Number(selectedCaseId) : null,
        instruction,
        base_url: baseUrl,
        dsl_json: executableDsl
      });
      const runList = await getTestRuns();
      setRuns(runList);
      await selectRun(run);
    } catch (error) {
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
      await reloadRunDetails(activeRun);
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

  return (
    <div className="test-run-workspace">
      <section className="workspace-section">
        <div className="workspace-section__heading">
          <div>
            <h2>基础配置区</h2>
            <p>选择被测系统、账号、测试数据和自然语言测试目标。</p>
          </div>
        </div>
        <TestRunConfigCard
          collapsed={configCollapsed}
          testDataOpen={testDataOpen}
          projects={projects}
          cases={projectCases}
          systems={systems}
          selectedProjectId={selectedProjectId}
          selectedCaseId={selectedCaseId}
          selectedSystemId={selectedSystemId}
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
          onSystemChange={(value) => {
            if (value === "") {
              setSelectedSystemId("");
              return;
            }
            handleSystemChange(value);
          }}
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
      </section>

      <section className="workspace-section task-observation-section">
        <div className="workspace-section__heading">
          <div>
            <h2>任务分解观察区</h2>
            <p>查看 LLM 交互状态、信息完整性判断和生成的 DSL 步骤。</p>
          </div>
        </div>
        {analysisMessages.length > 0 || plannedDsl || isAnalyzing ? (
          <AnalysisTracePanel messages={analysisMessages} analyzing={isAnalyzing} dsl={plannedDsl} />
        ) : (
          <div className="surface-panel empty-state">点击“分析”后显示 LLM 交互状态和 DSL 步骤预览</div>
        )}
      </section>

      <section className="workspace-section execution-observation-section">
        <div className="workspace-section__heading">
          <div>
            <h2>AI 执行观察区</h2>
            <p>实时查看执行消息、Cube 执行环境状态、当前截图和失败摘要。</p>
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
            AI 执行观察区仅显示当前执行或从“运行记录”中选择的运行。
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
              <RunHistoryTab runs={runs} activeRun={activeRun} onSelectRun={(run) => void selectRun(run, true)} />
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
                  <h2>{sample.failure_type || "失败样本"}</h2>
                  <span>{sample.status}</span>
                </div>
                <p>{sample.failure_summary || "暂无摘要"}</p>
                {screenshot ? (
                  <button className="failure-sample__screenshot" type="button" onClick={() => onPreview(screenshot, "失败截图")}>
                    <img src={screenshot} alt="失败截图" />
                  </button>
                ) : null}
                <div className="artifact-link-grid">
                  {sample.dom_snapshot_path ? <a href={fileUrl(sample.dom_snapshot_path)} target="_blank" rel="noreferrer">DOM Snapshot</a> : null}
                  {sample.accessibility_snapshot_path ? <a href={fileUrl(sample.accessibility_snapshot_path)} target="_blank" rel="noreferrer">Accessibility Snapshot</a> : null}
                  {sample.locator_debug_path ? <a href={fileUrl(sample.locator_debug_path)} target="_blank" rel="noreferrer">locator-debug</a> : null}
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
      <JsonCollapseBlock title="查看运行 JSON" value={run} />
      <JsonCollapseBlock title="查看步骤 JSON" value={steps} />
      <JsonCollapseBlock title="查看产物 JSON" value={artifacts} />
      <JsonCollapseBlock title="查看失败样本 JSON" value={failureSamples} />
      <JsonCollapseBlock title="查看人工介入 JSON" value={interventions} />
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
  if (type === "dom_snapshot") return "DOM Snapshot";
  if (type === "accessibility_snapshot") return "Accessibility Snapshot";
  if (type === "locator_debug") return "locator-debug";
  if (type === "runtime_stream") return "运行消息";
  if (type === "execution_trace") return "执行轨迹";
  if (type === "playwright_trace") return "trace.zip";
  if (type === "summary") return "summary.json";
  if (type === "report") return "report.html";
  if (type === "screenshot") return "步骤截图";
  if (type === "sandbox_screenshot") return "执行环境启动截图";
  return type;
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
  if (isAnalyzing) return "正在分析，等待 DSL 生成后才能开始执行。";
  if (!selectedProjectId) return "请选择项目后再分析。";
  if (!instruction.trim()) return "请输入自然语言测试目标。";
  const errorMessage = [...analysisMessages].reverse().find((message) => message.type === "error");
  if (errorMessage?.content) {
    return `DSL 未生成：${compactText(errorMessage.content)}`;
  }
  const analysis = latestAnalysisResult(analysisMessages);
  if (analysis && analysis.readyToExecute === false) {
    const missingFields = Array.isArray(analysis.missingFields) ? analysis.missingFields.map(String) : [];
    const questions = Array.isArray(analysis.clarifyingQuestions) ? analysis.clarifyingQuestions.map(String) : [];
    const reasons = [...missingFields.map((field) => `缺少 ${field}`), ...questions];
    return reasons.length > 0 ? `DSL 未生成：${reasons[0]}` : "DSL 未生成：当前信息不足。";
  }
  if (analysisMessages.length > 0) {
    return "DSL 未生成：请查看任务分解观察区中的失败原因。";
  }
  return "请先点击“分析”，生成 DSL 后再开始执行。";
}

function latestAnalysisResult(messages: RuntimeMessage[]): Record<string, unknown> | null {
  const message = [...messages].reverse().find((item) => item.metadata.analysis && typeof item.metadata.analysis === "object");
  return message?.metadata.analysis as Record<string, unknown> | null;
}

function compactText(value: string): string {
  const normalized = value.replace(/\s+/g, " ").trim();
  return normalized.length > 90 ? `${normalized.slice(0, 90)}...` : normalized;
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
  return {
    ...planned,
    caseName: planned.caseName || "自然语言测试执行",
    baseUrl: context.baseUrl || planned.baseUrl,
    credentials: {
      username: context.username,
      password: context.password,
      secret_ref: "runtime_form_password"
    },
    testData: {
      ...(planned.testData || {}),
      ...context.testData
    },
    settings: {
      ...planned.settings,
      visionFallbackEnabled: context.visionFallback
    },
    steps: steps.map((step) => hydrateStep(step, context))
  };
}

function hydrateStep(step: TestCaseStep, context: { baseUrl: string; username: string; password: string }): TestCaseStep {
  const target = String(step.target || "");
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
    steps.push({ action: "assert_text_exists", target: "工作台" });
  }
  return steps;
}

function resolveSystemUrl(system: TestSystem): string {
  return system.login_url || system.base_url || "";
}

function parseTestDataFromJson(value: string): Record<string, unknown> {
  if (!value.trim()) {
    return {};
  }
  const parsed = JSON.parse(value) as unknown;
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("测试数据 JSON 必须是对象。");
  }
  return parsed as Record<string, unknown>;
}

function caseIdFromHash(): number | null {
  const match = window.location.hash.match(/[?&]caseId=(\d+)/);
  return match ? Number(match[1]) : null;
}
