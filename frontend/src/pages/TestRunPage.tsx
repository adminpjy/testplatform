import { ExternalLink } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { apiUrl, fileUrl } from "../api/client";
import {
  analyzeTestRun,
  convertInterventionToRule,
  createTestRun,
  executeIntervention,
  getProjects,
  getSystems,
  getRunFailureSamples,
  getRunHumanInterventions,
  getTestRunArtifacts,
  getTestRuns,
  getTestRunSteps,
  interveneStep,
  planTestRun
} from "../api/platform";
import { DebugDrawer } from "../components/DebugDrawer";
import { ErrorSummaryCard } from "../components/ErrorSummaryCard";
import { CurrentScreenshotCard } from "../components/CurrentScreenshotCard";
import { JsonCollapseBlock } from "../components/JsonCollapseBlock";
import { RunHistoryTab } from "../components/RunHistoryTab";
import { RuntimeStreamPanel } from "../components/RuntimeStreamPanel";
import { ScreenshotPreviewModal } from "../components/ScreenshotPreviewModal";
import { StepScreenshotList } from "../components/StepScreenshotList";
import { TestRunConfigCard } from "../components/TestRunConfigCard";
import type {
  AnalyzeResult,
  FailureSample,
  HumanIntervention,
  RuleDraft,
  TestArtifact,
  TestCaseDSL,
  TestCaseStep,
  TestProject,
  TestRun,
  TestStepRun,
  TestSystem
} from "../types/platform";

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
  const [systems, setSystems] = useState<TestSystem[]>([]);
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<number | "">("");
  const [selectedSystemId, setSelectedSystemId] = useState<number | "">("");
  const [baseUrl, setBaseUrl] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [testDataJson, setTestDataJson] = useState(DEFAULT_TEST_DATA);
  const [visionFallback, setVisionFallback] = useState(false);
  const [instruction, setInstruction] = useState("登录系统，进入我的待办，确认页面存在我的待办");
  const [analysis, setAnalysis] = useState<AnalyzeResult | null>(null);
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
  const mainViewRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    void bootstrap();
  }, []);

  async function bootstrap() {
    try {
      const [projectList, systemList, runList] = await Promise.all([getProjects(), getSystems(), getTestRuns()]);
      setProjects(projectList);
      setSystems(systemList);
      setRuns(runList);
      if (projectList.length > 0) {
        const project = projectList[0];
        setSelectedProjectId(project.id);
      }
      if (systemList.length > 0) {
        const system = systemList[0];
        setSelectedSystemId(system.id);
        setBaseUrl(resolveSystemUrl(system));
        setUsername(system.accounts[0]?.username || "");
      }
      if (runList.length > 0) {
        await selectRun(runList[0]);
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
    if (focusRuntime) {
      setActiveTab("steps");
      window.setTimeout(() => {
        mainViewRef.current?.scrollIntoView({ block: "start", behavior: "smooth" });
      }, 50);
    }
  }

  function handleProjectChange(projectId: number) {
    setSelectedProjectId(projectId);
    const project = projects.find((item) => item.id === projectId);
    if (project) {
      const system = systems.find((item) => item.id === project.system_id);
      if (system) {
        handleSystemChange(system.id);
      }
    }
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
    try {
      const result = await analyzeTestRun({
        project_id: Number(selectedProjectId),
        system_id: selectedSystemId ? Number(selectedSystemId) : undefined,
        instruction,
        base_url: baseUrl,
        credentials: { username, password },
        testData: parseTestData(),
        settings: { visionFallbackEnabled: visionFallback },
        stream: true
      });
      setAnalysis(result);
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
    setApiError(null);
    setIsExecuting(true);
    setConfigCollapsed(true);
    setActiveTab("steps");
    try {
      const planned = await planTestRun({
        project_id: Number(selectedProjectId),
        system_id: selectedSystemId ? Number(selectedSystemId) : undefined,
        instruction,
        base_url: baseUrl,
        credentials: { username, password },
        testData: parseTestData(),
        settings: { visionFallbackEnabled: visionFallback },
        stream: true
      });
      const executableDsl = materializeDsl(planned, { baseUrl, username, password, visionFallback, instruction, testData: parseTestData() });
      const run = await createTestRun({
        project_id: Number(selectedProjectId),
        system_id: selectedSystemId ? Number(selectedSystemId) : null,
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
    } catch (error) {
      setApiError(error instanceof Error ? error.message : String(error));
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
    } catch (error) {
      setApiError(error instanceof Error ? error.message : String(error));
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
    } catch (error) {
      setApiError(error instanceof Error ? error.message : String(error));
    }
  }

  return (
    <div className="test-run-workspace">
      <TestRunConfigCard
        collapsed={configCollapsed}
        testDataOpen={testDataOpen}
        projects={projects}
        systems={systems}
        selectedProjectId={selectedProjectId}
        selectedSystemId={selectedSystemId}
        baseUrl={baseUrl}
        username={username}
        password={password}
        visionFallback={visionFallback}
        instruction={instruction}
        testDataJson={testDataJson}
        analysis={analysis}
        isAnalyzing={isAnalyzing}
        isExecuting={isExecuting}
        hasActiveRun={Boolean(activeRun)}
        onToggleCollapsed={() => setConfigCollapsed((value) => !value)}
        onToggleTestData={() => setTestDataOpen((value) => !value)}
        onProjectChange={handleProjectChange}
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

      <div className="main-grid" ref={mainViewRef}>
        <div className="runtime-column">
          {activeRun ? (
            <RuntimeStreamPanel runId={activeRun.id} steps={steps} onPreviewScreenshot={openPreview} />
          ) : (
            <div className="surface-panel empty-state runtime-empty-state">执行后显示 AI 执行过程</div>
          )}
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
  if (type === "summary") return "summary.json";
  if (type === "report") return "report.html";
  if (type === "screenshot") return "步骤截图";
  return type;
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
    steps.push({ action: "business_goal", target: "工作台/我的待办" });
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
