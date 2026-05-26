import { CheckCircle2, Link2, Save, ShieldCheck } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  checkSystemConnectivity,
  checkSystemLogin,
  createSystem,
  getSystems,
  getTestRuns,
  updateSystem
} from "../api/platform";
import { StatusBadge } from "../components/StatusBadge";
import type { SystemCheckResult, TestRun, TestSystem, TestSystemCreate } from "../types/platform";

const emptyForm: TestSystemCreate = {
  system_code: "",
  system_name: "",
  description: "",
  base_url: "",
  login_url: "",
  home_url: "",
  environment: "test",
  auth_type: "username_password",
  default_timeout_ms: 15000,
  allow_write: false,
  allow_approval: false,
  allow_delete: false,
  status: "active",
  config_json: {},
  default_account: {
    environment: "test",
    username: "",
    password: "",
    role_name: "",
    allow_write: false,
    allow_approval: false,
    allow_delete: false,
    status: "active"
  }
};

export function TestSystemsPage() {
  const [systems, setSystems] = useState<TestSystem[]>([]);
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [form, setForm] = useState<TestSystemCreate>(emptyForm);
  const [checkResult, setCheckResult] = useState<SystemCheckResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const selectedSystem = useMemo(
    () => systems.find((system) => system.id === selectedId) || null,
    [systems, selectedId]
  );
  const recentRuns = runs.filter((run) => run.system_id === selectedId).slice(0, 6);

  useEffect(() => {
    void load();
  }, []);

  async function load() {
    setError(null);
    try {
      const [systemList, runList] = await Promise.all([getSystems(), getTestRuns()]);
      setSystems(systemList);
      setRuns(runList);
      if (!selectedId && systemList.length > 0) {
        selectSystem(systemList[0]);
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : String(requestError));
    }
  }

  function selectSystem(system: TestSystem) {
    setSelectedId(system.id);
    setForm({
      system_code: system.system_code,
      system_name: system.system_name,
      description: system.description || "",
      base_url: system.base_url,
      login_url: system.login_url || "",
      home_url: system.home_url || "",
      environment: system.environment,
      auth_type: system.auth_type,
      default_timeout_ms: system.default_timeout_ms,
      allow_write: system.allow_write,
      allow_approval: system.allow_approval,
      allow_delete: system.allow_delete,
      status: system.status,
      config_json: system.config_json || {},
      default_account: {
        environment: system.environment,
        username: system.accounts[0]?.username || "",
        password: "",
        role_name: system.accounts[0]?.role_name || "",
        allow_write: system.accounts[0]?.allow_write || false,
        allow_approval: system.accounts[0]?.allow_approval || false,
        allow_delete: system.accounts[0]?.allow_delete || false,
        status: system.accounts[0]?.status || "active"
      }
    });
  }

  function newSystem() {
    setSelectedId(null);
    setForm(emptyForm);
    setCheckResult(null);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const payload = sanitizePayload(form);
      const saved = selectedId ? await updateSystem(selectedId, payload) : await createSystem(payload);
      await load();
      selectSystem(saved);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : String(requestError));
    } finally {
      setLoading(false);
    }
  }

  async function runConnectivityCheck() {
    if (!selectedId) return;
    setLoading(true);
    setError(null);
    try {
      setCheckResult(await checkSystemConnectivity(selectedId));
      await load();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : String(requestError));
    } finally {
      setLoading(false);
    }
  }

  async function runLoginCheck() {
    if (!selectedId) return;
    setLoading(true);
    setError(null);
    try {
      setCheckResult(await checkSystemLogin(selectedId));
      await load();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : String(requestError));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-grid page-grid--systems">
      <section className="surface-panel systems-list">
        <div className="panel-heading">
          <h1>被测系统管理</h1>
          <button className="secondary-button" type="button" onClick={newSystem}>新增系统</button>
        </div>
        <div className="run-history__list">
          {systems.map((system) => (
            <button
              className={selectedId === system.id ? "run-history__item run-history__item--active" : "run-history__item"}
              key={system.id}
              type="button"
              onClick={() => selectSystem(system)}
            >
              <span>{system.system_name}</span>
              <StatusBadge value={system.status} />
            </button>
          ))}
          {systems.length === 0 ? <div className="empty-state">尚未配置被测系统</div> : null}
        </div>
      </section>

      <form className="surface-panel system-editor" onSubmit={submit}>
        <div className="panel-heading">
          <h2>{selectedSystem ? "编辑系统" : "新增系统"}</h2>
          <button className="primary-button" type="submit" disabled={loading || !form.system_code || !form.system_name || !form.base_url}>
            <Save size={16} />
            {loading ? "保存中" : "保存"}
          </button>
        </div>
        {error ? <pre className="error-detail error-detail--collapsed">{error}</pre> : null}

        <div className="form-grid">
          <Field label="系统编码" value={form.system_code} onChange={(value) => setForm({ ...form, system_code: value })} />
          <Field label="系统名称" value={form.system_name} onChange={(value) => setForm({ ...form, system_name: value })} />
          <Field label="base_url" value={form.base_url} onChange={(value) => setForm({ ...form, base_url: value })} />
          <Field label="login_url" value={form.login_url || ""} onChange={(value) => setForm({ ...form, login_url: value })} />
          <Field label="home_url" value={form.home_url || ""} onChange={(value) => setForm({ ...form, home_url: value })} />
          <label>
            <span>环境</span>
            <select value={form.environment} onChange={(event) => setForm({ ...form, environment: event.target.value })}>
              <option value="dev">dev</option>
              <option value="test">test</option>
              <option value="uat">uat</option>
              <option value="preprod">preprod</option>
              <option value="prod">prod</option>
            </select>
          </label>
          <label>
            <span>认证方式</span>
            <select value={form.auth_type} onChange={(event) => setForm({ ...form, auth_type: event.target.value })}>
              <option value="username_password">username_password</option>
              <option value="sso">sso</option>
              <option value="token">token</option>
              <option value="other">other</option>
            </select>
          </label>
          <label>
            <span>超时 ms</span>
            <input
              type="number"
              value={form.default_timeout_ms}
              onChange={(event) => setForm({ ...form, default_timeout_ms: Number(event.target.value) })}
            />
          </label>
        </div>

        <div className="toggle-grid">
          <Toggle label="允许写操作" checked={form.allow_write} onChange={(value) => setForm({ ...form, allow_write: value })} />
          <Toggle label="允许审批" checked={form.allow_approval} onChange={(value) => setForm({ ...form, allow_approval: value })} />
          <Toggle label="允许删除" checked={form.allow_delete} onChange={(value) => setForm({ ...form, allow_delete: value })} />
        </div>

        <section className="sub-panel">
          <h3>测试账号</h3>
          <div className="form-grid">
            <Field label="用户名" value={form.default_account?.username || ""} onChange={(value) => updateAccount("username", value)} />
            <label>
              <span>密码</span>
              <input
                type="password"
                value={form.default_account?.password || ""}
                onChange={(event) => updateAccount("password", event.target.value)}
                placeholder="保存后不回显"
              />
            </label>
            <Field label="角色" value={form.default_account?.role_name || ""} onChange={(value) => updateAccount("role_name", value)} />
          </div>
        </section>
      </form>

      <section className="surface-panel systems-actions">
        <div className="panel-heading">
          <h2>检查</h2>
        </div>
        <div className="action-bar">
          <button className="secondary-button" type="button" onClick={runConnectivityCheck} disabled={!selectedId || loading}>
            <Link2 size={16} />
            连通性检查
          </button>
          <button className="secondary-button" type="button" onClick={runLoginCheck} disabled={!selectedId || loading}>
            <ShieldCheck size={16} />
            登录检查
          </button>
        </div>
        {checkResult ? (
          <div className="check-result">
            <div>
              <CheckCircle2 size={18} />
              <strong>{checkResult.check_type}</strong>
              <StatusBadge value={checkResult.status} />
            </div>
            <dl className="settings-list">
              <dt>HTTP</dt>
              <dd>{checkResult.http_status ?? "-"}</dd>
              <dt>耗时</dt>
              <dd>{checkResult.response_time_ms ?? "-"} ms</dd>
              <dt>说明</dt>
              <dd>{checkResult.message}</dd>
            </dl>
          </div>
        ) : null}
      </section>

      <section className="surface-panel systems-runs">
        <div className="panel-heading">
          <h2>最近测试运行</h2>
          <span>{recentRuns.length} 条</span>
        </div>
        <div className="run-history__list">
          {recentRuns.map((run) => (
            <div className="run-history__item" key={run.id}>
              <span>{run.run_code}</span>
              <StatusBadge value={run.status} />
            </div>
          ))}
          {recentRuns.length === 0 ? <div className="empty-state">暂无运行记录</div> : null}
        </div>
      </section>
    </div>
  );

  function updateAccount(key: "username" | "password" | "role_name", value: string) {
    setForm({
      ...form,
      default_account: {
        ...(form.default_account || emptyForm.default_account!),
        [key]: value
      }
    });
  }
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

function sanitizePayload(form: TestSystemCreate): TestSystemCreate {
  const account = form.default_account;
  return {
    ...form,
    login_url: form.login_url || null,
    home_url: form.home_url || null,
    description: form.description || null,
    default_account: account?.username
      ? {
          ...account,
          password: account.password || null,
          role_name: account.role_name || null
        }
      : null
  };
}
