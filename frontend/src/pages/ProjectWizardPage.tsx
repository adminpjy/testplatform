import { FileUp, Play, Radar, Save, Send, UploadCloud } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";

import {
  bootstrapProjectWizard,
  createCampaign,
  createMaintenanceFeedback,
  getCampaignReportSummary,
  importBootstrapCases,
  runProjectPrescan,
  startCampaign
} from "../api/platform";
import { DataTable } from "../components/DataTable";
import { StatusBadge } from "../components/StatusBadge";
import type {
  CampaignReportSummary,
  InitialCaseDraft,
  ImportBootstrapCasesResponse,
  PrescanResponse,
  ProjectAccountPayload,
  ProjectCreatePayload,
  ProjectWizardBootstrapResponse,
  TestCampaign
} from "../types/platform";

type WizardStep = "config" | "drafts" | "prescan" | "campaign";

const emptyProject: ProjectCreatePayload = {
  project_name: "",
  description: "",
  system_name: "",
  base_url: "",
  login_url: "",
  home_url: "",
  auth_type: "username_password",
  default_timeout_ms: 15000,
  enable_trace_default: true,
  enable_screenshot_default: true,
  enable_dom_snapshot_default: true,
  enable_accessibility_snapshot_default: true,
  enable_vision_fallback_default: true,
  status: "active"
};

const emptyAccount: ProjectAccountPayload = {
  account_name: "",
  username: "",
  password: "",
  role_name: "",
  allow_read: true,
  allow_write: true,
  allow_approval: true,
  allow_delete: false,
  is_default: true,
  status: "active"
};

export function ProjectWizardPage() {
  const [activeStep, setActiveStep] = useState<WizardStep>("config");
  const [projectForm, setProjectForm] = useState<ProjectCreatePayload>(emptyProject);
  const [accountForm, setAccountForm] = useState<ProjectAccountPayload>(emptyAccount);
  const [fileA, setFileA] = useState<File | null>(null);
  const [fileB, setFileB] = useState<File | null>(null);
  const [bootstrap, setBootstrap] = useState<ProjectWizardBootstrapResponse | null>(null);
  const [selectedDrafts, setSelectedDrafts] = useState<number[]>([]);
  const [importResult, setImportResult] = useState<ImportBootstrapCasesResponse | null>(null);
  const [prescan, setPrescan] = useState<PrescanResponse | null>(null);
  const [campaign, setCampaign] = useState<TestCampaign | null>(null);
  const [report, setReport] = useState<CampaignReportSummary | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const importedCaseIds = importResult?.importedCaseIds || [];
  const selectedCount = selectedDrafts.length;
  const failedCampaignCase = useMemo(
    () => campaign?.cases.find((item) => ["failed", "blocked", "stopped", "aborted"].includes(item.status)) || null,
    [campaign]
  );

  async function generateDrafts(event: FormEvent) {
    event.preventDefault();
    if (!fileA || !fileB) {
      setError("请上传两份项目资料。");
      return;
    }
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const [contentA, contentB] = await Promise.all([fileA.text(), fileB.text()]);
      const result = await bootstrapProjectWizard({
        project: sanitizeProject(projectForm),
        account: accountForm.username ? sanitizeAccount(accountForm) : null,
        files: [
          { file_name: fileA.name, role: "baseline", content: contentA },
          { file_name: fileB.name, role: "current", content: contentB }
        ],
        sourceType: "two_file_compare"
      });
      setBootstrap(result);
      setSelectedDrafts(result.drafts.map((draft) => draft.index));
      setActiveStep("drafts");
      setMessage(`已生成 ${result.drafts.length} 条初始用例草案。`);
    } catch (requestError) {
      setError(formatError(requestError));
    } finally {
      setLoading(false);
    }
  }

  async function importDrafts() {
    if (!bootstrap) return;
    setLoading(true);
    setError(null);
    try {
      const result = await importBootstrapCases(bootstrap.package.id, { draftIndexes: selectedDrafts, activate: true });
      setImportResult(result);
      setActiveStep("prescan");
      setMessage(`已导入 ${result.importedCaseIds.length} 条功能测试用例。`);
    } catch (requestError) {
      setError(formatError(requestError));
    } finally {
      setLoading(false);
    }
  }

  async function startPrescan() {
    const projectId = importResult?.projectId || bootstrap?.projectId;
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await runProjectPrescan(projectId, { caseIds: importedCaseIds.length ? importedCaseIds : null, mode: "case_driven", dryRun: true });
      setPrescan(result);
      setActiveStep("campaign");
      setMessage(`预扫完成，生成 ${result.ruleDraftIds.length} 条规则草案。`);
    } catch (requestError) {
      setError(formatError(requestError));
    } finally {
      setLoading(false);
    }
  }

  async function runCampaign() {
    const projectId = importResult?.projectId || bootstrap?.projectId;
    if (!projectId || !importedCaseIds.length) return;
    setLoading(true);
    setError(null);
    try {
      const created = await createCampaign(projectId, {
        name: `${projectForm.project_name || "项目"} 功能测试批次`,
        caseIds: importedCaseIds,
        settings: { source: "project_wizard", prescanSessionId: prescan?.session.id || null }
      });
      const started = await startCampaign(created.id, { settingsOverride: { source: "project_wizard" } });
      const summary = await getCampaignReportSummary(started.id);
      setCampaign(started);
      setReport(summary);
      setMessage("批次已启动，运行状态会在运行记录中持续更新。");
    } catch (requestError) {
      setError(formatError(requestError));
    } finally {
      setLoading(false);
    }
  }

  async function sendFeedback() {
    if (!failedCampaignCase?.run_id) {
      setError("当前批次没有可反馈的失败运行。");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const feedback = await createMaintenanceFeedback({
        runId: failedCampaignCase.run_id,
        summary: failedCampaignCase.failure_summary || "批次执行失败，需要维护人员复核。",
        userNote: "由项目向导批次执行入口提交。"
      });
      setMessage(`反馈已提交：${feedback.feedback_code}`);
    } catch (requestError) {
      setError(formatError(requestError));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="wizard-page page-stack">
      <section className="surface-panel project-page__header">
        <div className="panel-heading">
          <div>
            <h1>项目初始化向导</h1>
            <span>配置项目、导入初始用例、预扫增强并启动批次测试。</span>
          </div>
        </div>
      </section>

      {message ? <div className="debug-feedback">{message}</div> : null}
      {error ? <pre className="error-detail error-detail--collapsed">{error}</pre> : null}

      <div className="wizard-layout">
        <aside className="surface-panel wizard-steps">
          <StepButton id="config" label="配置与资料" active={activeStep === "config"} done={Boolean(bootstrap)} onClick={setActiveStep} />
          <StepButton id="drafts" label="用例导入" active={activeStep === "drafts"} done={Boolean(importResult)} onClick={setActiveStep} disabled={!bootstrap} />
          <StepButton id="prescan" label="预扫增强" active={activeStep === "prescan"} done={Boolean(prescan)} onClick={setActiveStep} disabled={!importResult} />
          <StepButton id="campaign" label="批次执行" active={activeStep === "campaign"} done={Boolean(campaign)} onClick={setActiveStep} disabled={!importResult} />
        </aside>

        <section className="surface-panel wizard-main">
          {activeStep === "config" ? (
            <form onSubmit={generateDrafts}>
              <div className="panel-heading">
                <h2>项目配置</h2>
                <button className="primary-button" type="submit" disabled={!projectForm.project_name || !fileA || !fileB || loading}>
                  <UploadCloud size={16} />
                  生成初始用例
                </button>
              </div>
              <ProjectFields form={projectForm} onChange={setProjectForm} />
              <div className="sub-panel">
                <h3>默认测试账号</h3>
                <AccountFields form={accountForm} onChange={setAccountForm} />
              </div>
              <div className="sub-panel">
                <h3>项目资料</h3>
                <div className="form-grid">
                  <FileField label="资料文件一" file={fileA} onChange={setFileA} />
                  <FileField label="资料文件二" file={fileB} onChange={setFileB} />
                </div>
              </div>
            </form>
          ) : null}

          {activeStep === "drafts" && bootstrap ? (
            <div className="wizard-panel">
              <div className="panel-heading">
                <div>
                  <h2>初始用例草案</h2>
                  <span>{selectedCount} / {bootstrap.drafts.length} 条将导入</span>
                </div>
                <button className="primary-button" type="button" onClick={() => void importDrafts()} disabled={!selectedCount || loading}>
                  <Save size={16} />
                  导入用例
                </button>
              </div>
              <DraftTable drafts={bootstrap.drafts} selected={selectedDrafts} onChange={setSelectedDrafts} />
            </div>
          ) : null}

          {activeStep === "prescan" ? (
            <div className="wizard-panel">
              <div className="panel-heading">
                <div>
                  <h2>预扫增强</h2>
                  <span>{importedCaseIds.length} 条用例</span>
                </div>
                <button className="primary-button" type="button" onClick={() => void startPrescan()} disabled={!importedCaseIds.length || loading}>
                  <Radar size={16} />
                  开始预扫
                </button>
              </div>
              {prescan ? <PrescanSummary prescan={prescan} /> : <div className="empty-state">导入用例后可执行只读预扫。</div>}
            </div>
          ) : null}

          {activeStep === "campaign" ? (
            <div className="wizard-panel">
              <div className="panel-heading">
                <div>
                  <h2>批次执行</h2>
                  <span>{campaign ? campaign.campaign_code : `${importedCaseIds.length} 条待执行`}</span>
                </div>
                <div className="action-bar">
                  <button className="primary-button" type="button" onClick={() => void runCampaign()} disabled={!importedCaseIds.length || loading}>
                    <Play size={16} />
                    启动批次
                  </button>
                  <button className="secondary-button" type="button" onClick={() => void sendFeedback()} disabled={!failedCampaignCase?.run_id || loading}>
                    <Send size={16} />
                    一键反馈
                  </button>
                </div>
              </div>
              {campaign ? <CampaignSummary campaign={campaign} report={report} /> : <div className="empty-state">完成预扫后可启动批次测试。</div>}
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
}

function StepButton({
  id,
  label,
  active,
  done,
  disabled,
  onClick
}: {
  id: WizardStep;
  label: string;
  active: boolean;
  done: boolean;
  disabled?: boolean;
  onClick: (step: WizardStep) => void;
}) {
  return (
    <button className={active ? "wizard-step wizard-step--active" : "wizard-step"} type="button" onClick={() => onClick(id)} disabled={disabled}>
      <span>{label}</span>
      {done ? <StatusBadge value="completed" /> : null}
    </button>
  );
}

function ProjectFields({ form, onChange }: { form: ProjectCreatePayload; onChange: (next: ProjectCreatePayload) => void }) {
  return (
    <div className="form-grid">
      <Field label="项目名称" value={form.project_name || ""} onChange={(value) => onChange({ ...form, project_name: value })} />
      <Field label="被测系统" value={form.system_name || ""} onChange={(value) => onChange({ ...form, system_name: value })} />
      <Field label="base_url" value={form.base_url || ""} onChange={(value) => onChange({ ...form, base_url: value })} />
      <Field label="login_url" value={form.login_url || ""} onChange={(value) => onChange({ ...form, login_url: value })} />
      <Field label="home_url" value={form.home_url || ""} onChange={(value) => onChange({ ...form, home_url: value })} />
      <label>
        <span>认证方式</span>
        <select value={form.auth_type || "username_password"} onChange={(event) => onChange({ ...form, auth_type: event.target.value })}>
          <option value="username_password">username_password</option>
          <option value="sso">sso</option>
          <option value="other">other</option>
        </select>
      </label>
    </div>
  );
}

function AccountFields({ form, onChange }: { form: ProjectAccountPayload; onChange: (next: ProjectAccountPayload) => void }) {
  return (
    <>
      <div className="form-grid">
        <Field label="账号名称" value={form.account_name || ""} onChange={(value) => onChange({ ...form, account_name: value })} />
        <Field label="用户名" value={form.username || ""} autoComplete="username" onChange={(value) => onChange({ ...form, username: value })} />
        <label>
          <span>密码</span>
          <input type="password" autoComplete="current-password" value={form.password || ""} onChange={(event) => onChange({ ...form, password: event.target.value })} />
        </label>
        <Field label="角色" value={form.role_name || ""} onChange={(value) => onChange({ ...form, role_name: value })} />
      </div>
      <div className="toggle-grid">
        <Toggle label="写" checked={Boolean(form.allow_write)} onChange={(value) => onChange({ ...form, allow_write: value })} />
        <Toggle label="审批" checked={Boolean(form.allow_approval)} onChange={(value) => onChange({ ...form, allow_approval: value })} />
        <Toggle label="删除" checked={Boolean(form.allow_delete)} onChange={(value) => onChange({ ...form, allow_delete: value })} />
      </div>
    </>
  );
}

function FileField({ label, file, onChange }: { label: string; file: File | null; onChange: (file: File | null) => void }) {
  return (
    <label className="file-drop-field">
      <span>{label}</span>
      <input type="file" accept=".txt,.md,.json,.csv,.docx,.pdf" onChange={(event) => onChange(event.target.files?.[0] || null)} />
      <strong><FileUp size={15} />{file ? file.name : "未选择"}</strong>
    </label>
  );
}

function DraftTable({
  drafts,
  selected,
  onChange
}: {
  drafts: InitialCaseDraft[];
  selected: number[];
  onChange: (next: number[]) => void;
}) {
  function toggle(index: number) {
    onChange(selected.includes(index) ? selected.filter((item) => item !== index) : [...selected, index]);
  }
  return (
    <DataTable
      rows={drafts}
      emptyText="未生成草案"
      getRowKey={(draft) => draft.index}
      columns={[
        { key: "select", title: "选择", render: (draft) => <input className="table-checkbox" type="checkbox" checked={selected.includes(draft.index)} onChange={() => toggle(draft.index)} /> },
        { key: "name", title: "用例名称", render: (draft) => draft.caseName },
        { key: "goal", title: "测试目标", render: (draft) => <span className="text-cell">{draft.naturalLanguageGoal}</span> },
        { key: "menu", title: "菜单路径", render: (draft) => draft.menuPath || "-" },
        { key: "risk", title: "风险", render: (draft) => <StatusBadge value={draft.riskLevel} /> },
        { key: "confidence", title: "置信度", render: (draft) => `${Math.round(draft.confidence * 100)}%` }
      ]}
    />
  );
}

function PrescanSummary({ prescan }: { prescan: PrescanResponse }) {
  return (
    <div className="wizard-summary-grid">
      <Metric label="规则草案" value={prescan.ruleDraftIds.length} />
      <Metric label="页面知识" value={prescan.abilityKnowledgeIds.length} />
      <Metric label="增强建议" value={prescan.enhancedCases.length} />
      <pre className="json-snippet">{JSON.stringify(prescan.summary, null, 2)}</pre>
    </div>
  );
}

function CampaignSummary({ campaign, report }: { campaign: TestCampaign; report: CampaignReportSummary | null }) {
  return (
    <div className="wizard-panel">
      <div className="wizard-summary-grid">
        <Metric label="总数" value={campaign.total_count} />
        <Metric label="运行中" value={campaign.running_count} />
        <Metric label="通过" value={campaign.passed_count} />
        <Metric label="失败" value={campaign.failed_count + campaign.blocked_count} />
      </div>
      <DataTable
        rows={campaign.cases}
        emptyText="暂无批次用例"
        getRowKey={(item) => item.id}
        columns={[
          { key: "case", title: "用例", render: (item) => item.case_id },
          { key: "run", title: "运行", render: (item) => item.run_id ? <a className="table-link-button" href={`#/reports?runId=${item.run_id}`}>{item.run_id}</a> : "-" },
          { key: "status", title: "状态", render: (item) => <StatusBadge value={item.status} /> },
          { key: "summary", title: "摘要", render: (item) => item.failure_summary || "-" }
        ]}
      />
      {report ? <pre className="json-snippet">{JSON.stringify(report.totals, null, 2)}</pre> : null}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="metric-tile">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Field({
  label,
  value,
  autoComplete,
  onChange
}: {
  label: string;
  value: string;
  autoComplete?: string;
  onChange: (value: string) => void;
}) {
  return (
    <label>
      <span>{label}</span>
      <input value={value} autoComplete={autoComplete} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className="toggle-row">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

function sanitizeProject(form: ProjectCreatePayload): ProjectCreatePayload {
  return {
    ...form,
    description: form.description || null,
    system_name: form.system_name || null,
    base_url: form.base_url || null,
    login_url: form.login_url || null,
    home_url: form.home_url || null
  };
}

function sanitizeAccount(form: ProjectAccountPayload): ProjectAccountPayload {
  return {
    ...form,
    account_name: form.account_name || null,
    password: form.password || null,
    role_name: form.role_name || null,
    description: form.description || null
  };
}

function formatError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
