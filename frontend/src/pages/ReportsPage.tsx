import { ExternalLink, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { apiUrl } from "../api/client";
import { getTestRuns } from "../api/platform";
import { DataTable } from "../components/DataTable";
import { StatusBadge } from "../components/StatusBadge";
import type { TestRun } from "../types/platform";

export function ReportsPage() {
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<TestRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void loadRuns();
  }, []);

  async function loadRuns() {
    setLoading(true);
    setError(null);
    try {
      const nextRuns = await getTestRuns();
      setRuns(nextRuns);
      setSelectedRun(nextRuns[0] || null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : String(requestError));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-grid page-grid--reports">
      <section className="surface-panel report-list-panel">
        <div className="panel-heading">
          <h1>测试报告</h1>
          <button className="secondary-button" type="button" onClick={() => void loadRuns()}>
            <RefreshCw size={16} />
            {loading ? "刷新中" : "刷新"}
          </button>
        </div>
        {error ? <pre className="error-detail error-detail--collapsed">{error}</pre> : null}
        <DataTable
          columns={[
            {
              key: "run",
              title: "运行编码",
              render: (run) => (
                <button className="table-link-button" type="button" onClick={() => setSelectedRun(run)}>
                  {run.run_code}
                </button>
              )
            },
            { key: "status", title: "状态", render: (run) => <StatusBadge value={run.status} /> },
            {
              key: "time",
              title: "时间",
              render: (run) => (run.started_at ? new Date(run.started_at).toLocaleString("zh-CN") : "-")
            }
          ]}
          rows={runs}
          emptyText="暂无测试报告"
          getRowKey={(run) => run.id}
        />
      </section>

      <section className="surface-panel report-preview-panel">
        <div className="panel-heading">
          <h2>报告预览</h2>
          {selectedRun ? (
            <a className="secondary-link" href={apiUrl(`/api/reports/${selectedRun.id}`)} target="_blank" rel="noreferrer">
              <ExternalLink size={16} />
              新窗口
            </a>
          ) : null}
        </div>
        {selectedRun ? (
          <iframe title="测试报告预览" src={apiUrl(`/api/reports/${selectedRun.id}`)} />
        ) : (
          <div className="empty-state">选择一条运行记录查看报告</div>
        )}
      </section>
    </div>
  );
}
