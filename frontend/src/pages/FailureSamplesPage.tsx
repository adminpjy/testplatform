import { ExternalLink, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { apiUrl } from "../api/client";
import { getTestRuns } from "../api/platform";
import { StatusBadge } from "../components/StatusBadge";
import type { TestRun } from "../types/platform";

export function FailureSamplesPage() {
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void loadRuns();
  }, []);

  async function loadRuns() {
    setLoading(true);
    setError(null);
    try {
      setRuns((await getTestRuns()).filter((run) => run.status === "failed"));
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
          <h1>失败样本</h1>
          <button className="secondary-button" type="button" onClick={() => void loadRuns()}>
            <RefreshCw size={16} />
            {loading ? "刷新中" : "刷新"}
          </button>
        </div>
        {error ? <pre className="error-detail error-detail--collapsed">{error}</pre> : null}
      </section>

      <div className="failure-sample-list">
        {runs.length === 0 ? <section className="surface-panel empty-state">暂无失败样本</section> : null}
        {runs.map((run) => (
          <section className="surface-panel failure-sample" key={run.id}>
            <div className="panel-heading">
              <h2>{run.run_code}</h2>
              <StatusBadge value={run.status} />
            </div>
            <div className="failure-sample__meta">
              <span>{run.instruction || "未记录测试目标"}</span>
              <span>{run.started_at ? new Date(run.started_at).toLocaleString("zh-CN") : "未记录开始时间"}</span>
            </div>
            <pre className="error-detail error-detail--collapsed">
              {String(run.summary_json?.errorSummary || "失败摘要待补充")}
            </pre>
            <div className="action-bar">
              <a className="secondary-link" href={apiUrl(`/api/reports/${run.id}`)} target="_blank" rel="noreferrer">
                <ExternalLink size={16} />
                打开报告
              </a>
              <button className="ghost-button" type="button" disabled>
                沉淀规则草案
              </button>
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
