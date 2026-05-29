import { Copy, LogIn, Network, Plus, Save, Trash2 } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  checkSystemConnectivity,
  checkSystemLogin,
  copyCase,
  createProject,
  createProjectAccount,
  createProjectCase,
  deleteCase,
  deleteProject,
  deleteProjectAccount,
  disableCase,
  getProjectAccounts,
  getProjectCases,
  getProjects,
  getTestRuns,
  setProjectDefaultAccount,
  updateProject,
  updateProjectAccount
} from "../api/platform";
import { DataTable } from "../components/DataTable";
import { StatusBadge } from "../components/StatusBadge";
import type {
  FunctionalTestCase,
  ProjectAccount,
  ProjectAccountPayload,
  ProjectCreatePayload,
  TestProject,
  TestRun
} from "../types/platform";

type ProjectTab = "config" | "accounts" | "cases" | "runs" | "failures" | "knowledge";

const PROJECT_TABS: Array<{ id: ProjectTab; label: string }> = [
  { id: "config", label: "项目配置" },
  { id: "accounts", label: "测试账号" },
  { id: "cases", label: "功能测试用例" },
  { id: "runs", label: "运行记录" },
  { id: "failures", label: "失败分析" },
  { id: "knowledge", label: "规则与知识" }
];

const emptyProjectForm: ProjectCreatePayload = {
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
  enable_vision_fallback_default: false,
  status: "active"
};

const emptyAccountForm: ProjectAccountPayload = {
  account_name: "",
  username: "",
  password: "",
  role_name: "",
  description: "",
  allow_read: true,
  allow_write: false,
  allow_approval: false,
  allow_delete: false,
  is_default: false,
  status: "active"
};

const emptyCaseForm = {
  case_name: "",
  description: "",
  natural_language_goal: "",
  menu_path: "",
  business_intent: "",
  inherit_project_account: true,
  account_id: "",
  status: "draft"
};

export function ProjectsPage({ initialProjectId }: { initialProjectId?: number | null }) {
  const [projects, setProjects] = useState<TestProject[]>([]);
  const [accounts, setAccounts] = useState<ProjectAccount[]>([]);
  const [cases, setCases] = useState<FunctionalTestCase[]>([]);
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(initialProjectId || null);
  const [activeTab, setActiveTab] = useState<ProjectTab>("config");
  const [projectForm, setProjectForm] = useState<ProjectCreatePayload>(emptyProjectForm);
  const [accountForm, setAccountForm] = useState<ProjectAccountPayload>(emptyAccountForm);
  const [editingAccountId, setEditingAccountId] = useState<number | null>(null);
  const [caseForm, setCaseForm] = useState(emptyCaseForm);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === selectedProjectId) || null,
    [projects, selectedProjectId]
  );
  const projectRuns = runs.filter((run) => run.project_id === selectedProjectId).slice(0, 20);

  useEffect(() => {
    void loadProjects(initialProjectId || null);
  }, [initialProjectId]);

  async function loadProjects(preferredId = selectedProjectId) {
    setError(null);
    const [projectList, runList] = await Promise.all([getProjects(), getTestRuns()]);
    setProjects(projectList);
    setRuns(runList);
    const nextProject = projectList.find((project) => project.id === preferredId) || projectList[0] || null;
    if (nextProject) {
      await selectProject(nextProject.id, projectList);
    } else {
      setSelectedProjectId(null);
      setProjectForm(emptyProjectForm);
      setAccounts([]);
      setCases([]);
    }
  }

  async function selectProject(projectId: number, projectList = projects) {
    const project = projectList.find((item) => item.id === projectId);
    if (!project) return;
    setSelectedProjectId(projectId);
    setProjectForm(projectToForm(project));
    window.history.replaceState(null, "", `#projects/${projectId}`);
    const [accountList, caseList] = await Promise.all([getProjectAccounts(projectId), getProjectCases(projectId)]);
    setAccounts(accountList);
    setCases(caseList);
  }

  function startNewProject() {
    setSelectedProjectId(null);
    setProjectForm(emptyProjectForm);
    setAccounts([]);
    setCases([]);
    window.history.replaceState(null, "", "#projects");
  }

  async function saveProject(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setMessage(null);
    setError(null);
    try {
      const saved = selectedProjectId
        ? await updateProject(selectedProjectId, sanitizeProject(projectForm))
        : await createProject(sanitizeProject(projectForm));
      setMessage("项目已保存。");
      await loadProjects(saved.id);
    } catch (requestError) {
      setError(formatError(requestError));
    } finally {
      setLoading(false);
    }
  }

  async function removeProject() {
    if (!selectedProjectId) return;
    if (!window.confirm("确认停用并软删除该项目？历史运行记录会保留。")) return;
    setLoading(true);
    try {
      await deleteProject(selectedProjectId);
      await loadProjects(null);
      setMessage("项目已删除。");
    } catch (requestError) {
      setError(formatError(requestError));
    } finally {
      setLoading(false);
    }
  }

  async function runProjectCheck(type: "connectivity" | "login") {
    if (!selectedProject?.system_id) {
      setError("当前项目未关联旧被测系统记录，连通性和登录检查将在后续阶段直接接入项目。");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = type === "connectivity"
        ? await checkSystemConnectivity(selectedProject.system_id)
        : await checkSystemLogin(selectedProject.system_id);
      setMessage(`${type === "connectivity" ? "连通性检查" : "登录检查"}：${result.status}，${result.message}`);
    } catch (requestError) {
      setError(formatError(requestError));
    } finally {
      setLoading(false);
    }
  }

  async function saveAccount(event: FormEvent) {
    event.preventDefault();
    if (!selectedProjectId) return;
    setLoading(true);
    setError(null);
    try {
      const payload = sanitizeAccount(accountForm);
      if (editingAccountId) {
        await updateProjectAccount(editingAccountId, payload);
      } else {
        await createProjectAccount(selectedProjectId, payload);
      }
      setAccountForm(emptyAccountForm);
      setEditingAccountId(null);
      await selectProject(selectedProjectId);
    } catch (requestError) {
      setError(formatError(requestError));
    } finally {
      setLoading(false);
    }
  }

  async function removeAccount(accountId: number) {
    if (!window.confirm("确认删除该测试账号？")) return;
    await deleteProjectAccount(accountId);
    if (selectedProjectId) await selectProject(selectedProjectId);
  }

  async function makeDefaultAccount(accountId: number) {
    await setProjectDefaultAccount(accountId);
    if (selectedProjectId) await selectProject(selectedProjectId);
  }

  async function saveCase(event: FormEvent) {
    event.preventDefault();
    if (!selectedProjectId) return;
    setLoading(true);
    setError(null);
    try {
      await createProjectCase(selectedProjectId, {
        ...caseForm,
        account_id: caseForm.account_id ? Number(caseForm.account_id) : null,
        dsl_json: minimalDsl(caseForm.case_name, selectedProject?.base_url || "", caseForm.menu_path)
      });
      setCaseForm(emptyCaseForm);
      await selectProject(selectedProjectId);
      setMessage("功能测试用例已创建。");
    } catch (requestError) {
      setError(formatError(requestError));
    } finally {
      setLoading(false);
    }
  }

  async function duplicateCase(caseId: number) {
    await copyCase(caseId);
    if (selectedProjectId) await selectProject(selectedProjectId);
  }

  async function removeCase(caseId: number) {
    if (!window.confirm("确认删除该功能测试用例？")) return;
    await deleteCase(caseId);
    if (selectedProjectId) await selectProject(selectedProjectId);
  }

  async function pauseCase(caseId: number) {
    await disableCase(caseId);
    if (selectedProjectId) await selectProject(selectedProjectId);
  }

  return (
    <div className="project-page page-stack">
      <section className="surface-panel project-page__header">
        <div className="panel-heading">
          <div>
            <h1>项目管理</h1>
            <span>维护被测系统配置、测试账号和可重复执行的功能测试用例。</span>
          </div>
          <button className="primary-button" type="button" onClick={startNewProject}>
            <Plus size={16} />
            新增项目
          </button>
        </div>
      </section>

      {message ? <div className="debug-feedback">{message}</div> : null}
      {error ? <pre className="error-detail error-detail--collapsed">{error}</pre> : null}

      <div className="project-management-grid">
        <section className="surface-panel project-list-panel">
          <div className="panel-heading">
            <h2>项目列表</h2>
            <span>{projects.length} 个</span>
          </div>
          <DataTable
            rows={projects}
            emptyText="请先创建项目"
            getRowKey={(project) => project.id}
            columns={[
              { key: "name", title: "项目名称", render: (project) => <button className="link-button" type="button" onClick={() => void selectProject(project.id)}>{project.project_name || project.name}</button> },
              { key: "system", title: "被测系统", render: (project) => project.system_name || "-" },
              { key: "url", title: "base_url", render: (project) => <span className="text-cell">{project.base_url || "-"}</span> },
              { key: "account", title: "默认账号", render: (project) => project.default_account?.username || "-" },
              { key: "case_count", title: "用例", render: (project) => project.case_count ?? 0 },
              { key: "run", title: "最近运行", render: (project) => project.last_run_status ? <StatusBadge value={project.last_run_status} /> : "-" },
              { key: "status", title: "状态", render: (project) => <StatusBadge value={project.status} /> }
            ]}
          />
        </section>

        <section className="surface-panel project-detail-panel">
          <div className="tab-strip">
            {PROJECT_TABS.map((tab) => (
              <button className={activeTab === tab.id ? "tab-button tab-button--active" : "tab-button"} key={tab.id} type="button" onClick={() => setActiveTab(tab.id)}>
                {tab.label}
              </button>
            ))}
          </div>

          {activeTab === "config" ? (
            <form className="project-form" onSubmit={saveProject}>
              <div className="panel-heading">
                <h2>{selectedProjectId ? "编辑项目" : "新增项目"}</h2>
                <div className="action-bar">
                  <button className="secondary-button" type="button" onClick={() => void runProjectCheck("connectivity")} disabled={!selectedProjectId || loading}>
                    <Network size={16} />
                    连通性检查
                  </button>
                  <button className="secondary-button" type="button" onClick={() => void runProjectCheck("login")} disabled={!selectedProjectId || loading}>
                    <LogIn size={16} />
                    登录检查
                  </button>
                  <button className="primary-button" type="submit" disabled={!projectForm.project_name || loading}>
                    <Save size={16} />
                    保存
                  </button>
                  <button className="ghost-button" type="button" onClick={() => void removeProject()} disabled={!selectedProjectId || loading}>
                    <Trash2 size={16} />
                    删除
                  </button>
                </div>
              </div>
              <ProjectForm form={projectForm} onChange={setProjectForm} />
            </form>
          ) : null}

          {activeTab === "accounts" ? (
            <div className="project-tab-panel">
              <form className="sub-panel" onSubmit={saveAccount}>
                <h3>{editingAccountId ? "编辑测试账号" : "新增测试账号"}</h3>
                <AccountForm form={accountForm} onChange={setAccountForm} />
                <div className="action-bar">
                  <button className="primary-button" type="submit" disabled={!selectedProjectId || !accountForm.username || loading}>保存账号</button>
                  {editingAccountId ? <button className="secondary-button" type="button" onClick={() => { setEditingAccountId(null); setAccountForm(emptyAccountForm); }}>取消编辑</button> : null}
                </div>
              </form>
              <DataTable
                rows={accounts}
                emptyText="当前项目还没有测试账号"
                getRowKey={(account) => account.id}
                columns={[
                  { key: "name", title: "账号名称", render: (account) => account.account_name || "-" },
                  { key: "username", title: "用户名", render: (account) => account.username },
                  { key: "role", title: "角色", render: (account) => account.role_name || "-" },
                  { key: "default", title: "默认", render: (account) => account.is_default ? "是" : <button className="table-link-button" type="button" onClick={() => void makeDefaultAccount(account.id)}>设为默认</button> },
                  { key: "perm", title: "权限", render: (account) => permissionText(account) },
                  { key: "status", title: "状态", render: (account) => <StatusBadge value={account.status} /> },
                  { key: "actions", title: "操作", render: (account) => (
                    <div className="table-actions">
                      <button className="table-link-button" type="button" onClick={() => { setEditingAccountId(account.id); setAccountForm(accountToForm(account)); }}>编辑</button>
                      <button className="table-link-button" type="button" onClick={() => void removeAccount(account.id)}>删除</button>
                    </div>
                  ) }
                ]}
              />
            </div>
          ) : null}

          {activeTab === "cases" ? (
            <div className="project-tab-panel">
              <form className="sub-panel" onSubmit={saveCase}>
                <h3>新增功能测试用例</h3>
                <CaseForm form={caseForm} accounts={accounts} onChange={setCaseForm} />
                <div className="action-bar">
                  <button className="primary-button" type="submit" disabled={!selectedProjectId || !caseForm.case_name || loading}>保存用例</button>
                </div>
              </form>
              <DataTable
                rows={cases}
                emptyText="当前项目还没有功能测试用例，请新增用例。"
                getRowKey={(item) => item.id}
                columns={[
                  { key: "name", title: "用例名称", render: (item) => <a className="link-button" href={`#cases/${item.id}`}>{item.case_name}</a> },
                  { key: "menu", title: "菜单路径", render: (item) => item.menu_path || "-" },
                  { key: "intent", title: "业务意图", render: (item) => item.business_intent || "-" },
                  { key: "account", title: "账号来源", render: (item) => item.inherit_project_account ? "继承项目默认账号" : `账号 ${item.account_id || "-"}` },
                  { key: "status", title: "状态", render: (item) => <StatusBadge value={item.status} /> },
                  { key: "last", title: "最近运行", render: (item) => item.last_run_status ? <StatusBadge value={item.last_run_status} /> : "-" },
                  { key: "count", title: "运行次数", render: (item) => item.run_count },
                  { key: "rate", title: "通过率", render: (item) => passRate(item) },
                  { key: "actions", title: "操作", render: (item) => (
                    <div className="table-actions">
                      <a className="table-link-button" href={`#cases/${item.id}`}>详情</a>
                      <a className="table-link-button" href={`#test-run?caseId=${item.id}`}>执行</a>
                      <button className="table-link-button" type="button" onClick={() => void duplicateCase(item.id)}><Copy size={14} />复制</button>
                      <button className="table-link-button" type="button" onClick={() => void pauseCase(item.id)}>停用</button>
                      <button className="table-link-button" type="button" onClick={() => void removeCase(item.id)}>删除</button>
                    </div>
                  ) }
                ]}
              />
            </div>
          ) : null}

          {activeTab === "runs" ? <ProjectRuns runs={projectRuns} /> : null}
          {activeTab === "failures" ? <div className="empty-state">失败分析会在用例详情和失败样本中展示。</div> : null}
          {activeTab === "knowledge" ? <div className="empty-state">规则和页面知识可在能力中心继续维护。</div> : null}
        </section>
      </div>
    </div>
  );
}

function ProjectForm({ form, onChange }: { form: ProjectCreatePayload; onChange: (next: ProjectCreatePayload) => void }) {
  return (
    <>
      <div className="form-grid">
        <Field label="项目名称" value={form.project_name || ""} onChange={(value) => onChange({ ...form, project_name: value })} />
        <Field label="被测系统名称" value={form.system_name || ""} onChange={(value) => onChange({ ...form, system_name: value })} />
        <Field label="base_url" value={form.base_url || ""} onChange={(value) => onChange({ ...form, base_url: value })} />
        <Field label="login_url" value={form.login_url || ""} onChange={(value) => onChange({ ...form, login_url: value })} />
        <Field label="home_url" value={form.home_url || ""} onChange={(value) => onChange({ ...form, home_url: value })} />
        <label>
          <span>认证方式</span>
          <select value={form.auth_type || "username_password"} onChange={(event) => onChange({ ...form, auth_type: event.target.value })}>
            <option value="username_password">username_password</option>
            <option value="sso">sso</option>
            <option value="token">token</option>
            <option value="other">other</option>
          </select>
        </label>
        <label>
          <span>默认超时 ms</span>
          <input type="number" value={form.default_timeout_ms || 15000} onChange={(event) => onChange({ ...form, default_timeout_ms: Number(event.target.value) })} />
        </label>
        <label>
          <span>状态</span>
          <select value={form.status || "active"} onChange={(event) => onChange({ ...form, status: event.target.value })}>
            <option value="active">active</option>
            <option value="disabled">disabled</option>
          </select>
        </label>
      </div>
      <label className="stacked-field compact-textarea">
        <span>描述</span>
        <textarea value={form.description || ""} onChange={(event) => onChange({ ...form, description: event.target.value })} />
      </label>
      <div className="toggle-grid">
        <Toggle label="Trace" checked={Boolean(form.enable_trace_default)} onChange={(value) => onChange({ ...form, enable_trace_default: value })} />
        <Toggle label="Screenshot" checked={Boolean(form.enable_screenshot_default)} onChange={(value) => onChange({ ...form, enable_screenshot_default: value })} />
        <Toggle label="DOM Snapshot" checked={Boolean(form.enable_dom_snapshot_default)} onChange={(value) => onChange({ ...form, enable_dom_snapshot_default: value })} />
        <Toggle label="Accessibility Snapshot" checked={Boolean(form.enable_accessibility_snapshot_default)} onChange={(value) => onChange({ ...form, enable_accessibility_snapshot_default: value })} />
        <Toggle label="Vision Fallback" checked={Boolean(form.enable_vision_fallback_default)} onChange={(value) => onChange({ ...form, enable_vision_fallback_default: value })} />
      </div>
    </>
  );
}

function AccountForm({ form, onChange }: { form: ProjectAccountPayload; onChange: (next: ProjectAccountPayload) => void }) {
  return (
    <>
      <div className="form-grid">
        <Field label="账号名称" value={form.account_name || ""} onChange={(value) => onChange({ ...form, account_name: value })} />
        <Field label="用户名" value={form.username || ""} onChange={(value) => onChange({ ...form, username: value })} />
        <label>
          <span>修改密码</span>
          <input type="password" value={form.password || ""} placeholder="不回显历史密码" onChange={(event) => onChange({ ...form, password: event.target.value })} />
        </label>
        <Field label="角色" value={form.role_name || ""} onChange={(value) => onChange({ ...form, role_name: value })} />
      </div>
      <div className="toggle-grid">
        <Toggle label="默认账号" checked={Boolean(form.is_default)} onChange={(value) => onChange({ ...form, is_default: value })} />
        <Toggle label="读" checked={Boolean(form.allow_read ?? true)} onChange={(value) => onChange({ ...form, allow_read: value })} />
        <Toggle label="写" checked={Boolean(form.allow_write)} onChange={(value) => onChange({ ...form, allow_write: value })} />
        <Toggle label="审批" checked={Boolean(form.allow_approval)} onChange={(value) => onChange({ ...form, allow_approval: value })} />
        <Toggle label="删除" checked={Boolean(form.allow_delete)} onChange={(value) => onChange({ ...form, allow_delete: value })} />
      </div>
    </>
  );
}

function CaseForm({ form, accounts, onChange }: { form: typeof emptyCaseForm; accounts: ProjectAccount[]; onChange: (next: typeof emptyCaseForm) => void }) {
  return (
    <>
      <div className="form-grid">
        <Field label="用例名称" value={form.case_name} onChange={(value) => onChange({ ...form, case_name: value })} />
        <Field label="菜单路径" value={form.menu_path} onChange={(value) => onChange({ ...form, menu_path: value })} />
        <Field label="业务意图" value={form.business_intent} onChange={(value) => onChange({ ...form, business_intent: value })} />
        <label>
          <span>账号配置</span>
          <select value={form.inherit_project_account ? "inherit" : form.account_id} onChange={(event) => {
            const value = event.target.value;
            onChange({ ...form, inherit_project_account: value === "inherit", account_id: value === "inherit" ? "" : value });
          }}>
            <option value="inherit">继承项目默认账号</option>
            {accounts.map((account) => <option key={account.id} value={account.id}>{account.account_name || account.username}</option>)}
          </select>
        </label>
      </div>
      <label className="stacked-field compact-textarea">
        <span>自然语言测试目标</span>
        <textarea value={form.natural_language_goal} onChange={(event) => onChange({ ...form, natural_language_goal: event.target.value })} />
      </label>
    </>
  );
}

function ProjectRuns({ runs }: { runs: TestRun[] }) {
  return (
    <DataTable
      rows={runs}
      emptyText="当前项目暂无运行记录"
      getRowKey={(run) => run.id}
      columns={[
        { key: "code", title: "run_code", render: (run) => run.run_code },
        { key: "status", title: "状态", render: (run) => <StatusBadge value={run.status} /> },
        { key: "started", title: "开始时间", render: (run) => run.started_at || run.created_at },
        { key: "case", title: "用例", render: (run) => run.case_id || "-" },
        { key: "report", title: "报告", render: (run) => <a className="table-link-button" href={`#/reports?runId=${run.id}`}>查看</a> }
      ]}
    />
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

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className="toggle-row">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

function projectToForm(project: TestProject): ProjectCreatePayload {
  return {
    project_name: project.project_name || project.name,
    description: project.description || "",
    system_name: project.system_name || "",
    base_url: project.base_url || "",
    login_url: project.login_url || "",
    home_url: project.home_url || "",
    auth_type: project.auth_type || "username_password",
    default_timeout_ms: project.default_timeout_ms || 15000,
    enable_trace_default: project.enable_trace_default ?? true,
    enable_screenshot_default: project.enable_screenshot_default ?? true,
    enable_dom_snapshot_default: project.enable_dom_snapshot_default ?? true,
    enable_accessibility_snapshot_default: project.enable_accessibility_snapshot_default ?? true,
    enable_vision_fallback_default: project.enable_vision_fallback_default ?? false,
    status: project.status
  };
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

function accountToForm(account: ProjectAccount): ProjectAccountPayload {
  return {
    account_name: account.account_name || "",
    username: account.username,
    password: "",
    role_name: account.role_name || "",
    description: account.description || "",
    allow_read: account.allow_read,
    allow_write: account.allow_write,
    allow_approval: account.allow_approval,
    allow_delete: account.allow_delete,
    is_default: account.is_default,
    status: account.status
  };
}

function sanitizeAccount(form: ProjectAccountPayload): ProjectAccountPayload {
  return {
    ...form,
    account_name: form.account_name || null,
    password: form.password || null,
    role_name: form.role_name || null,
    description: form.description || null,
    status: form.status || "active"
  };
}

function minimalDsl(caseName: string, baseUrl: string, menuPath: string) {
  const steps = menuPath
    ? [{ action: "navigate_path", target: menuPath, pathSegments: menuPath.split(/[/>→\\-]/).map((item) => item.trim()).filter(Boolean), navigationType: "menu_path" }]
    : [];
  return { caseName, baseUrl, credentials: {}, testData: {}, settings: {}, steps };
}

function permissionText(account: ProjectAccount): string {
  return [
    account.allow_read ? "读" : null,
    account.allow_write ? "写" : null,
    account.allow_approval ? "审批" : null,
    account.allow_delete ? "删除" : null
  ].filter(Boolean).join(" / ") || "-";
}

function passRate(item: FunctionalTestCase): string {
  if (!item.run_count) return "-";
  return `${Math.round((item.pass_count / item.run_count) * 100)}%`;
}

function formatError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
