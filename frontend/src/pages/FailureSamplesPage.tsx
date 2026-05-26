import { ExternalLink, RefreshCw, UserRoundCheck } from "lucide-react";
import { useEffect, useState } from "react";

import { apiUrl, fileUrl } from "../api/client";
import { getFailureSamples } from "../api/platform";
import { StatusBadge } from "../components/StatusBadge";
import type { FailureSample } from "../types/platform";

export function FailureSamplesPage() {
  const [samples, setSamples] = useState<FailureSample[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void loadSamples();
  }, []);

  async function loadSamples() {
    setLoading(true);
    setError(null);
    try {
      setSamples(await getFailureSamples());
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
          <button className="secondary-button" type="button" onClick={() => void loadSamples()}>
            <RefreshCw size={16} />
            {loading ? "刷新中" : "刷新"}
          </button>
        </div>
        {error ? <pre className="error-detail error-detail--collapsed">{error}</pre> : null}
      </section>

      <div className="failure-sample-list">
        {samples.length === 0 ? <section className="surface-panel empty-state">暂无失败样本</section> : null}
        {samples.map((sample) => (
          <section className="surface-panel failure-sample" key={sample.id}>
            <div className="panel-heading">
              <h2>Sample #{sample.id}</h2>
              <StatusBadge value={sample.status} />
            </div>
            <div className="failure-sample__meta">
              <span>Run #{sample.run_id}</span>
              <span>Step #{sample.step_id || "-"}</span>
              <span>{sample.failure_type || "unknown_failure"}</span>
              <span>{new Date(sample.created_at).toLocaleString("zh-CN")}</span>
            </div>
            <pre className="error-detail error-detail--collapsed">
              {sample.failure_summary || "失败摘要待补充"}
            </pre>
            <div className="artifact-link-grid">
              {sample.screenshot_path ? <a href={fileUrl(sample.screenshot_path)} target="_blank" rel="noreferrer">截图</a> : null}
              {sample.dom_snapshot_path ? <a href={fileUrl(sample.dom_snapshot_path)} target="_blank" rel="noreferrer">DOM</a> : null}
              {sample.accessibility_snapshot_path ? <a href={fileUrl(sample.accessibility_snapshot_path)} target="_blank" rel="noreferrer">Accessibility</a> : null}
              {sample.locator_debug_path ? <a href={fileUrl(sample.locator_debug_path)} target="_blank" rel="noreferrer">locator-debug</a> : null}
              {sample.runtime_stream_path ? <a href={fileUrl(sample.runtime_stream_path)} target="_blank" rel="noreferrer">runtime-stream</a> : null}
            </div>
            <div className="action-bar">
              {sample.report_path ? (
                <a className="secondary-link" href={apiUrl(`/api/reports/${sample.run_id}`)} target="_blank" rel="noreferrer">
                  <ExternalLink size={16} />
                  打开报告
                </a>
              ) : null}
              <a className="secondary-link" href="#test-run">
                <UserRoundCheck size={16} />
                人工介入
              </a>
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
