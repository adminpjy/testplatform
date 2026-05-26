import { RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { getHealth, getSystemInfo } from "../api/platform";
import { StatusBadge } from "../components/StatusBadge";
import type { HealthInfo, SystemInfo } from "../types/platform";

export function SystemSettingsPage() {
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void loadSettings();
  }, []);

  async function loadSettings() {
    setLoading(true);
    setError(null);
    try {
      const [nextHealth, nextSystemInfo] = await Promise.all([getHealth(), getSystemInfo()]);
      setHealth(nextHealth);
      setSystemInfo(nextSystemInfo);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : String(requestError));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-stack">
      <section className="surface-panel">
        <div className="panel-heading">
          <h1>系统设置</h1>
          <button className="secondary-button" type="button" onClick={() => void loadSettings()}>
            <RefreshCw size={16} />
            {loading ? "刷新中" : "刷新"}
          </button>
        </div>
        {error ? <pre className="error-detail error-detail--collapsed">{error}</pre> : null}
      </section>

      <section className="settings-grid">
        <div className="surface-panel">
          <div className="panel-heading">
            <h2>服务状态</h2>
            <StatusBadge value={health?.status || "unknown"} />
          </div>
          <dl className="settings-list">
            <dt>服务名称</dt>
            <dd>{systemInfo?.service || health?.service || "-"}</dd>
            <dt>版本</dt>
            <dd>{systemInfo?.version || "-"}</dd>
            <dt>环境</dt>
            <dd>{systemInfo?.environment || "-"}</dd>
          </dl>
        </div>

        <div className="surface-panel">
          <div className="panel-heading">
            <h2>数据连接</h2>
            <StatusBadge value={systemInfo?.database.connected ? "connected" : "error"} />
          </div>
          <dl className="settings-list">
            <dt>数据库</dt>
            <dd>{systemInfo?.database.connected ? "已连接" : "未连接"}</dd>
            <dt>项目数量</dt>
            <dd>{systemInfo?.project_count ?? "-"}</dd>
            <dt>被测系统</dt>
            <dd>{systemInfo?.system_count ?? "-"}</dd>
            <dt>能力规则</dt>
            <dd>{systemInfo?.ability_rule_count ?? "-"}</dd>
          </dl>
        </div>

        <div className="surface-panel">
          <div className="panel-heading">
            <h2>前端运行</h2>
          </div>
          <dl className="settings-list">
            <dt>API Base</dt>
            <dd>{(import.meta.env.VITE_API_BASE_URL as string | undefined) || "同源代理"}</dd>
            <dt>视觉兜底</dt>
            <dd>执行时按测试运行页开关传入</dd>
          </dl>
        </div>
      </section>
    </div>
  );
}
