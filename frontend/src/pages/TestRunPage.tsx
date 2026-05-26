import { Bot, Bug, Play, Search, UserRoundCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

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
import { RuntimeStreamPanel } from "../components/RuntimeStreamPanel";
import { ScreenshotPanel } from "../components/ScreenshotPanel";
import { StatusBadge } from "../components/StatusBadge";
import { StepTree } from "../components/StepTree";
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

  useEffect(() => {
    void bootstrap();
  }, []);

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === selectedProjectId) || null,
    [projects, selectedProjectId]
  );
  const selectedSystem = useMemo(
    () => systems.find((system) => system.id === selectedSystemId) || null,
    [systems, selectedSystemId]
  );

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

  async function selectRun(run: TestRun) {
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
    <div className="page-grid page-grid--test-run">
      <section className="surface-panel test-run-form">
        <div className="panel-heading">
          <h1>测试运行</h1>
          {activeRun ? <StatusBadge value={activeRun.status} /> : <span>等待执行</span>}
        </div>

        <div className="form-grid">
          <label>
            <span>项目选择</span>
            <select value={selectedProjectId} onChange={(event) => handleProjectChange(Number(event.target.value))}>
              {projects.map((project) => (
                <option value={project.id} key={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>被测系统</span>
            <select value={selectedSystemId} onChange={(event) => {
              const value = event.target.value;
              if (!value) {
                setSelectedSystemId("");
                return;
              }
              handleSystemChange(Number(value));
            }}>
              <option value="">未选择</option>
              {systems.map((system) => (
                <option value={system.id} key={system.id}>
                  {system.system_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>baseUrl</span>
            <input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} />
          </label>
          <label>
            <span>用户名</span>
            <input value={username} onChange={(event) => setUsername(event.target.value)} />
          </label>
          <label>
            <span>密码</span>
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
        </div>

        <label className="toggle-row">
          <input
            type="checkbox"
            checked={visionFallback}
            onChange={(event) => setVisionFallback(event.target.checked)}
          />
          <span>启用视觉兜底</span>
        </label>

        <label className="stacked-field">
          <span>自然语言测试目标</span>
          <textarea value={instruction} rows={5} onChange={(event) => setInstruction(event.target.value)} />
        </label>

        <label className="stacked-field">
          <span>测试数据补充 JSON</span>
          <textarea value={testDataJson} rows={7} onChange={(event) => setTestDataJson(event.target.value)} />
        </label>

        <div className="action-bar">
          <button className="secondary-button" type="button" onClick={handleAnalyze} disabled={isAnalyzing || !instruction}>
            <Search size={16} />
            {isAnalyzing ? "分析中" : "分析"}
          </button>
          <button className="primary-button" type="button" onClick={handleExecute} disabled={isExecuting || !instruction}>
            <Play size={16} />
            {isExecuting ? "执行中" : "开始执行"}
          </button>
          <button className="secondary-button" type="button" onClick={() => setInterventionOpen(true)} disabled={!activeRun}>
            <UserRoundCheck size={16} />
            人工介入
          </button>
          <button className="ghost-button" type="button" onClick={() => setDrawerOpen(true)} disabled={!activeRun}>
            <Bug size={16} />
            调试详情
          </button>
        </div>

        {analysis ? <AnalysisPanel analysis={analysis} /> : null}
        {selectedProject ? (
          <div className="project-context">
            <strong>{selectedSystem?.system_name || selectedProject.name}</strong>
            <span>{selectedSystem?.environment || selectedProject.environment || "test"}</span>
          </div>
        ) : null}
      </section>

      <section className="surface-panel run-history">
        <div className="panel-heading">
          <h2>运行记录</h2>
          <span>{runs.length} 条</span>
        </div>
        <div className="run-history__list">
          {runs.slice(0, 8).map((run) => (
            <button
              className={activeRun?.id === run.id ? "run-history__item run-history__item--active" : "run-history__item"}
              key={run.id}
              type="button"
              onClick={() => void selectRun(run)}
            >
              <span>{run.run_code}</span>
              <StatusBadge value={run.status} />
            </button>
          ))}
        </div>
      </section>

      <div className="runtime-region">
        {activeRun ? <RuntimeStreamPanel runId={activeRun.id} /> : <div className="surface-panel empty-state">执行后显示 Runtime Stream</div>}
      </div>
      <ScreenshotPanel run={activeRun} refreshKey={screenshotRefreshKey} onRefresh={() => setScreenshotRefreshKey(Date.now())} />
      <StepTree steps={steps} />
      <ErrorSummaryCard run={activeRun} steps={steps} apiError={apiError} />
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
    </div>
  );
}

function AnalysisPanel({ analysis }: { analysis: AnalyzeResult }) {
  return (
    <section className="analysis-panel">
      <div className="analysis-panel__title">
        <Bot size={16} />
        <strong>{analysis.readyToExecute ? "信息足够，可以执行" : "需要补充信息"}</strong>
        <span>置信度 {Math.round(analysis.confidence * 100)}%</span>
      </div>
      <p>{analysis.understoodGoal || analysis.normalizedInstruction}</p>
      {analysis.clarifyingQuestions.length > 0 ? (
        <ul>
          {analysis.clarifyingQuestions.map((question) => (
            <li key={question}>{question}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
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
