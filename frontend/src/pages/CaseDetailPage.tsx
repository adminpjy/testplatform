import { CheckCircle2, History, Play, Save, Wand2 } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  activateCaseVersion,
  analyzeFailureSample,
  analyzeCase,
  applyFailureAnalysisSuggestion,
  formatCaseDsl,
  generateCaseDsl,
  getCase,
  getCaseFailureAnalyses,
  getCaseFailureSamples,
  getCaseFixApplications,
  getCaseRuns,
  getCaseVersions,
  rerunTestRun,
  runCaseVersion,
  saveCaseDsl,
  saveGeneratedCaseDsl,
  updateCase,
  validateCaseDsl,
  verifyFixApplication
} from "../api/platform";
import { DataTable } from "../components/DataTable";
import { JsonCollapseBlock } from "../components/JsonCollapseBlock";
import { StatusBadge } from "../components/StatusBadge";
import type {
  FailureAnalysis,
  FailureSample,
  FixApplication,
  FunctionalTestCase,
  TestCaseDSL,
  TestCaseVersion,
  TestRun
} from "../types/platform";
import { labelAction, labelFailureType, labelRisk } from "../utils/displayLabels";

type CaseTab = "info" | "dsl" | "test-data" | "runs" | "failures" | "fixes" | "knowledge";

const CASE_TABS: Array<{ id: CaseTab; label: string }> = [
  { id: "info", label: "用例信息" },
  { id: "dsl", label: "测试步骤设计" },
  { id: "test-data", label: "测试数据" },
  { id: "runs", label: "执行记录" },
  { id: "failures", label: "失败分析" },
  { id: "fixes", label: "修复历史" },
  { id: "knowledge", label: "知识与规则" }
];

export function CaseDetailPage({ caseId }: { caseId: number | null }) {
  const [testCase, setTestCase] = useState<FunctionalTestCase | null>(null);
  const [versions, setVersions] = useState<TestCaseVersion[]>([]);
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [samples, setSamples] = useState<FailureSample[]>([]);
  const [analyses, setAnalyses] = useState<FailureAnalysis[]>([]);
  const [fixes, setFixes] = useState<FixApplication[]>([]);
  const [activeTab, setActiveTab] = useState<CaseTab>("info");
  const [infoForm, setInfoForm] = useState({ case_name: "", description: "", natural_language_goal: "", menu_path: "", business_intent: "", status: "draft" });
  const [dslText, setDslText] = useState("{}");
  const [jsonText, setJsonText] = useState({ testData: "{}", preconditions: "{}", success: "{}", settings: "{}" });
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const currentVersion = useMemo(
    () => versions.find((version) => version.id === testCase?.current_version_id) || versions[0] || null,
    [versions, testCase?.current_version_id]
  );

  useEffect(() => {
    if (caseId) {
      void load(caseId);
    }
  }, [caseId]);

  async function load(id: number) {
    setError(null);
    const [caseData, versionList, runList, sampleList, analysisList, fixList] = await Promise.all([
      getCase(id),
      getCaseVersions(id),
      getCaseRuns(id),
      getCaseFailureSamples(id),
      getCaseFailureAnalyses(id),
      getCaseFixApplications(id)
    ]);
    setTestCase(caseData);
    setVersions(versionList);
    setRuns(runList);
    setSamples(sampleList);
    setAnalyses(analysisList);
    setFixes(fixList);
    setInfoForm({
      case_name: caseData.case_name,
      description: caseData.description || "",
      natural_language_goal: caseData.natural_language_goal || "",
      menu_path: caseData.menu_path || "",
      business_intent: caseData.business_intent || "",
      status: caseData.status
    });
    setDslText(JSON.stringify(caseData.dsl_json || emptyDsl(caseData.case_name), null, 2));
    setJsonText({
      testData: JSON.stringify(caseData.test_data_json || {}, null, 2),
      preconditions: JSON.stringify(caseData.preconditions_json || {}, null, 2),
      success: JSON.stringify(caseData.success_criteria_json || {}, null, 2),
      settings: JSON.stringify(caseData.settings_json || {}, null, 2)
    });
  }

  async function saveInfo(event: FormEvent) {
    event.preventDefault();
    if (!caseId) return;
    setLoading(true);
    setError(null);
    try {
      const saved = await updateCase(caseId, infoForm);
      setTestCase(saved);
      setMessage("用例信息已保存。");
      await load(caseId);
    } catch (requestError) {
      setError(formatError(requestError));
    } finally {
      setLoading(false);
    }
  }

  async function handleFormatDsl() {
    if (!caseId) return;
    try {
      const formatted = await formatCaseDsl(caseId, parseDsl());
      setDslText(JSON.stringify(formatted, null, 2));
      setMessage("测试步骤已格式化。");
    } catch (requestError) {
      setError(formatError(requestError));
    }
  }

  async function handleValidateDsl() {
    if (!caseId) return;
    const result = await validateCaseDsl(caseId, parseDsl());
    setMessage(result.valid ? "测试步骤校验通过。" : `测试步骤校验失败：${result.errors.join("；")}`);
  }

  async function handleSaveDsl() {
    if (!caseId) return;
    setLoading(true);
    try {
      await saveCaseDsl(caseId, parseDsl(), "前端编辑测试步骤");
      await load(caseId);
      setMessage("测试步骤已保存为新版本。");
    } catch (requestError) {
      setError(formatError(requestError));
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerateDsl() {
    if (!caseId) return;
    setLoading(true);
    try {
      const analysis = await analyzeCase(caseId, infoForm.natural_language_goal);
      if (!analysis.readyToExecute) {
        setMessage(`暂未生成测试步骤：${analysis.clarifyingQuestions[0] || "信息不足"}`);
        return;
      }
      const dsl = await generateCaseDsl(caseId, infoForm.natural_language_goal, parseObject(jsonText.testData));
      setDslText(JSON.stringify(dsl, null, 2));
      setMessage("已生成测试步骤，确认后可保存为新版本。");
    } catch (requestError) {
      setError(formatError(requestError));
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveGeneratedDsl() {
    if (!caseId) return;
    await saveGeneratedCaseDsl(caseId, parseDsl(), parseObject(jsonText.testData), "从用例详情页生成");
    await load(caseId);
    setMessage("生成的测试步骤已保存。");
  }

  async function saveTestData() {
    if (!caseId) return;
    await updateCase(caseId, {
      test_data_json: parseObject(jsonText.testData),
      preconditions_json: parseObject(jsonText.preconditions),
      success_criteria_json: parseObject(jsonText.success),
      settings_json: parseObject(jsonText.settings)
    });
    await load(caseId);
    setMessage("测试数据和设置已保存为新版本。");
  }

  async function useVersion(versionId: number) {
    if (!caseId) return;
    await activateCaseVersion(caseId, versionId);
    await load(caseId);
    setMessage("历史版本已激活。");
  }

  async function executeVersion(versionId: number) {
    if (!caseId) return;
    const run = await runCaseVersion(caseId, versionId);
    setMessage(`已按指定版本创建运行：${run.run_code}`);
    await load(caseId);
  }

  async function rerun(runId: number) {
    if (!caseId) return;
    const run = await rerunTestRun(runId);
    setMessage(`已重新运行：${run.run_code}`);
    await load(caseId);
  }

  async function runFailureAnalysis(sampleId: number) {
    if (!caseId) return;
    const analysis = await analyzeFailureSample(sampleId);
    setMessage(`智能分析完成：${analysis.root_cause || labelFailureType(analysis.failure_category)}`);
    await load(caseId);
  }

  async function applySuggestion(analysisId: number, suggestionIndex: number, action: string) {
    if (!caseId) return;
    const response = await applyFailureAnalysisSuggestion(analysisId, { suggestionIndex, action, confirm: true });
    setMessage(`修复建议已应用：${response.message}`);
    await load(caseId);
  }

  async function verifyFix(fixId: number) {
    if (!caseId) return;
    const run = await verifyFixApplication(fixId);
    setMessage(`已创建修复验证运行：${run.run_code}`);
    await load(caseId);
  }

  function parseDsl(): TestCaseDSL {
    return parseObject(dslText) as unknown as TestCaseDSL;
  }

  if (!caseId) {
    return <div className="surface-panel empty-state">未指定功能测试用例。</div>;
  }

  if (!testCase) {
    return <div className="surface-panel empty-state">正在加载功能测试用例...</div>;
  }

  return (
    <div className="case-detail-page page-stack">
      <section className="surface-panel project-page__header">
        <div className="panel-heading">
          <div>
            <h1>{testCase.case_name}</h1>
            <span>{testCase.case_code || `CASE-${testCase.id}`} / 当前版本 {currentVersion ? `v${currentVersion.version_no}` : "-"}</span>
          </div>
          <div className="action-bar">
            <a className="secondary-link" href={`#projects/${testCase.project_id}`}>返回项目</a>
            <a className="primary-button" href={`#test-run?caseId=${testCase.id}`}>
              <Play size={16} />
              执行用例
            </a>
          </div>
        </div>
      </section>

      {message ? <div className="debug-feedback">{message}</div> : null}
      {error ? <pre className="error-detail error-detail--collapsed">{error}</pre> : null}

      <section className="surface-panel case-detail-card">
        <div className="tab-strip">
          {CASE_TABS.map((tab) => (
            <button className={activeTab === tab.id ? "tab-button tab-button--active" : "tab-button"} key={tab.id} type="button" onClick={() => setActiveTab(tab.id)}>
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === "info" ? (
          <form className="case-info-form" onSubmit={saveInfo}>
            <div className="form-grid">
              <Field label="用例名称" value={infoForm.case_name} onChange={(value) => setInfoForm({ ...infoForm, case_name: value })} />
              <Field label="菜单路径" value={infoForm.menu_path} onChange={(value) => setInfoForm({ ...infoForm, menu_path: value })} />
              <Field label="业务意图" value={infoForm.business_intent} onChange={(value) => setInfoForm({ ...infoForm, business_intent: value })} />
              <label>
                <span>状态</span>
                <select value={infoForm.status} onChange={(event) => setInfoForm({ ...infoForm, status: event.target.value })}>
                  <option value="draft">草稿</option>
                  <option value="active">启用</option>
                  <option value="disabled">停用</option>
                </select>
              </label>
            </div>
            <label className="stacked-field compact-textarea">
              <span>自然语言测试目标</span>
              <textarea value={infoForm.natural_language_goal} onChange={(event) => setInfoForm({ ...infoForm, natural_language_goal: event.target.value })} />
            </label>
            <label className="stacked-field compact-textarea">
              <span>描述</span>
              <textarea value={infoForm.description} onChange={(event) => setInfoForm({ ...infoForm, description: event.target.value })} />
            </label>
            <div className="action-bar">
              <button className="primary-button" type="submit" disabled={loading}>
                <Save size={16} />
                保存用例信息
              </button>
            </div>
          </form>
        ) : null}

        {activeTab === "dsl" ? (
          <div className="case-dsl-layout">
            <section>
              <div className="panel-heading">
                <h2>测试步骤设计</h2>
                <div className="action-bar">
                  <button className="secondary-button" type="button" onClick={() => void handleFormatDsl()}>格式化</button>
                  <button className="secondary-button" type="button" onClick={() => void handleValidateDsl()}><CheckCircle2 size={16} />校验</button>
                  <button className="secondary-button" type="button" onClick={() => void handleGenerateDsl()}><Wand2 size={16} />重新生成测试步骤</button>
                  <button className="primary-button" type="button" onClick={() => void handleSaveDsl()} disabled={loading}><Save size={16} />保存新版本</button>
                  <button className="secondary-button" type="button" onClick={() => void handleSaveGeneratedDsl()}>保存生成结果</button>
                </div>
              </div>
              <DslStepPreview dslText={dslText} />
              <textarea className="case-json-editor" value={dslText} onChange={(event) => setDslText(event.target.value)} />
            </section>
            <VersionHistory versions={versions} currentVersionId={testCase.current_version_id} onActivate={useVersion} onRun={executeVersion} />
          </div>
        ) : null}

        {activeTab === "test-data" ? (
          <div className="case-json-grid">
            <JsonEditor title="测试数据" value={jsonText.testData} onChange={(value) => setJsonText({ ...jsonText, testData: value })} />
            <JsonEditor title="前置条件" value={jsonText.preconditions} onChange={(value) => setJsonText({ ...jsonText, preconditions: value })} />
            <JsonEditor title="成功判断" value={jsonText.success} onChange={(value) => setJsonText({ ...jsonText, success: value })} />
            <JsonEditor title="执行设置" value={jsonText.settings} onChange={(value) => setJsonText({ ...jsonText, settings: value })} />
            <div className="action-bar">
              <button className="primary-button" type="button" onClick={() => void saveTestData()}>保存为新版本</button>
            </div>
          </div>
        ) : null}

        {activeTab === "runs" ? <RunTable runs={runs} onRerun={rerun} /> : null}
        {activeTab === "failures" ? <FailurePanel samples={samples} analyses={analyses} onAnalyze={runFailureAnalysis} onApply={applySuggestion} /> : null}
        {activeTab === "fixes" ? <FixPanel fixes={fixes} onVerify={verifyFix} /> : null}
        {activeTab === "knowledge" ? <div className="empty-state">该用例命中的规则和知识会在后续执行后持续沉淀。</div> : null}
      </section>
    </div>
  );
}

function DslStepPreview({ dslText }: { dslText: string }) {
  try {
    const dsl = parseObject(dslText) as unknown as TestCaseDSL;
    return (
      <ol className="dsl-step-list">
        {(dsl.steps || []).map((step, index) => (
          <li key={`${step.action}-${index}`}>
            <span>{step.id ? String(step.id) : `S${index + 1}`}</span>
            <strong>{readableAction(step.action)}</strong>
            <em>{step.action === "navigate_path" && Array.isArray(step.pathSegments) ? (step.pathSegments as string[]).join(" → ") : step.target || step.description || "-"}</em>
          </li>
        ))}
      </ol>
    );
  } catch {
    return <div className="dsl-empty-reason">测试步骤暂时无法解析，请修正后再校验。</div>;
  }
}

function VersionHistory({
  versions,
  currentVersionId,
  onActivate,
  onRun
}: {
  versions: TestCaseVersion[];
  currentVersionId: number | null;
  onActivate: (versionId: number) => Promise<void>;
  onRun: (versionId: number) => Promise<void>;
}) {
  return (
    <aside className="case-version-panel">
      <div className="panel-heading">
        <h2><History size={16} />版本历史</h2>
      </div>
      <div className="run-history__list">
        {versions.map((version) => (
          <div className="run-history__item" key={version.id}>
            <span>v{version.version_no} {labelVersionChangeType(version.change_type)}</span>
            <div className="table-actions">
              {version.id === currentVersionId ? <StatusBadge value="active" /> : <button className="table-link-button" type="button" onClick={() => void onActivate(version.id)}>激活</button>}
              <button className="table-link-button" type="button" onClick={() => void onRun(version.id)}>运行</button>
            </div>
          </div>
        ))}
        {versions.length === 0 ? <div className="empty-state">暂无版本</div> : null}
      </div>
    </aside>
  );
}

function RunTable({ runs, onRerun }: { runs: TestRun[]; onRerun: (runId: number) => Promise<void> }) {
  return (
    <DataTable
      rows={runs}
      emptyText="该用例暂无执行记录"
      getRowKey={(run) => run.id}
      columns={[
        { key: "code", title: "运行编号", render: (run) => run.run_code },
        { key: "status", title: "状态", render: (run) => <StatusBadge value={run.status} /> },
        { key: "start", title: "开始时间", render: (run) => run.started_at || run.created_at },
        { key: "duration", title: "耗时", render: (run) => run.ended_at && run.started_at ? `${Date.parse(run.ended_at) - Date.parse(run.started_at)} 毫秒` : "-" },
        { key: "account", title: "账号", render: (run) => String(run.account_snapshot?.username || "-") },
        { key: "report", title: "操作", render: (run) => (
          <div className="table-actions">
            <a className="table-link-button" href={`#/reports?runId=${run.id}`}>查看报告</a>
            <button className="table-link-button" type="button" onClick={() => void onRerun(run.id)}>重新运行</button>
          </div>
        ) }
      ]}
    />
  );
}

function FailurePanel({
  samples,
  analyses,
  onAnalyze,
  onApply
}: {
  samples: FailureSample[];
  analyses: FailureAnalysis[];
  onAnalyze: (sampleId: number) => Promise<void>;
  onApply: (analysisId: number, suggestionIndex: number, action: string) => Promise<void>;
}) {
  return (
    <div className="case-json-grid">
      <DataTable
        rows={samples}
        emptyText="该用例暂无失败样本"
        getRowKey={(sample) => sample.id}
        columns={[
          { key: "type", title: "失败类型", render: (sample) => labelFailureType(sample.failure_type) },
          { key: "summary", title: "摘要", render: (sample) => sample.failure_summary || "-" },
          { key: "status", title: "状态", render: (sample) => <StatusBadge value={sample.status} /> },
          { key: "actions", title: "操作", render: (sample) => <button className="table-link-button" type="button" onClick={() => void onAnalyze(sample.id)}>智能分析错误</button> }
        ]}
      />
      <div className="failure-analysis-card-list">
        {analyses.map((analysis) => (
          <article className="surface-panel ability-stat-card" key={analysis.id}>
            <span>失败分析 #{analysis.id}</span>
            <strong>{labelFailureType(analysis.failure_category)}</strong>
            <p>{analysis.root_cause || analysis.error_summary || "暂无根因说明"}</p>
            <dl className="settings-list">
              <dt>置信度</dt>
              <dd>{analysis.confidence == null ? "-" : `${Math.round(analysis.confidence * 100)}%`}</dd>
              <dt>风险</dt>
              <dd>{labelRisk(analysis.risk_level)}</dd>
              <dt>人工复核</dt>
              <dd>{analysis.requires_human_review ? "需要" : "不需要"}</dd>
            </dl>
            <JsonCollapseBlock title="查看证据" value={analysis.evidence_json || {}} />
            <JsonCollapseBlock title="查看建议" value={analysis.suggestions_json || {}} />
            <div className="suggestion-action-list">
              {suggestions(analysis).map((item, index) => (
                <button className="secondary-button" type="button" key={`${item.type}-${index}`} onClick={() => void onApply(analysis.id, index, actionForSuggestion(item.type))}>
                  {suggestionActionLabel(item.type)}
                </button>
              ))}
            </div>
          </article>
        ))}
        {analyses.length === 0 ? <div className="empty-state">暂无智能失败分析，选择失败样本后点击“智能分析错误”。</div> : null}
      </div>
    </div>
  );
}

function FixPanel({ fixes, onVerify }: { fixes: FixApplication[]; onVerify: (fixId: number) => Promise<void> }) {
  return (
    <DataTable
      rows={fixes}
      emptyText="暂无修复历史"
      getRowKey={(fix) => fix.id}
      columns={[
        { key: "type", title: "修复类型", render: (fix) => labelFixType(fix.fix_type) },
        { key: "status", title: "状态", render: (fix) => <StatusBadge value={fix.status} /> },
        { key: "version", title: "新版本", render: (fix) => fix.created_case_version_id || "-" },
        { key: "verify", title: "验证运行", render: (fix) => fix.verify_run_id || "-" },
        { key: "time", title: "时间", render: (fix) => fix.created_at },
        { key: "action", title: "操作", render: (fix) => <button className="table-link-button" type="button" onClick={() => void onVerify(fix.id)}>重新验证</button> }
      ]}
    />
  );
}

function JsonEditor({ title, value, onChange }: { title: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="stacked-field">
      <span>{title}</span>
      <textarea className="case-json-editor case-json-editor--small" value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label>
      <span>{label}</span>
      <input value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function parseObject(value: string): Record<string, unknown> {
  const parsed = JSON.parse(value || "{}") as unknown;
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("结构化数据必须是对象。");
  }
  return parsed as Record<string, unknown>;
}

function emptyDsl(caseName: string): TestCaseDSL {
  return { caseName, baseUrl: "", credentials: {}, testData: {}, settings: {}, steps: [] };
}

function readableAction(action: string): string {
  const mapping: Record<string, string> = {
    navigate_path: "菜单路径导航",
    query_table: "查询列表",
    open_table_row: "打开表格行",
    process_table_rows: "处理表格行",
    fill_form: "填写表单",
    business_goal: "业务目标"
  };
  return mapping[action] || labelAction(action);
}

function suggestions(analysis: FailureAnalysis): Array<{ type: string }> {
  const items = analysis.suggestions_json?.items;
  return Array.isArray(items) ? (items as Array<{ type: string }>) : [];
}

function suggestionActionLabel(type: string): string {
  const mapping: Record<string, string> = {
    modify_dsl: "应用到测试步骤",
    add_rule: "生成规则草案",
    update_rule: "更新规则",
    modify_test_data: "修改测试数据",
    modify_account: "修改账号",
    add_precondition: "更新前置条件",
    modify_success_criteria: "修改成功判断",
    human_intervention: "发起人工介入",
    environment_issue: "标记为环境问题",
    defect_candidate: "标记为缺陷"
  };
  return mapping[type] || "查看建议";
}

function actionForSuggestion(type: string): string {
  const mapping: Record<string, string> = {
    modify_dsl: "apply_to_dsl",
    add_rule: "create_rule_draft",
    update_rule: "create_rule_draft",
    modify_test_data: "modify_test_data",
    modify_account: "mark_environment_issue",
    add_precondition: "add_precondition",
    modify_success_criteria: "modify_success_criteria",
    human_intervention: "create_human_intervention",
    environment_issue: "mark_environment_issue",
    defect_candidate: "create_defect_candidate"
  };
  return mapping[type] || "create_human_intervention";
}

function labelVersionChangeType(value: string): string {
  const labels: Record<string, string> = {
    create: "创建",
    update: "更新",
    generated: "自动生成",
    rollback: "回滚",
    manual_edit: "人工编辑"
  };
  return labels[value] || "版本变更";
}

function labelFixType(value: string): string {
  const labels: Record<string, string> = {
    dsl_patch: "步骤修复",
    test_data_patch: "测试数据修复",
    rule_patch: "规则修复",
    account_patch: "账号修复",
    precondition_patch: "前置条件修复",
    success_criteria_patch: "成功判断修复"
  };
  return labels[value] || "其他修复";
}

function formatError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
