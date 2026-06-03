import { Download, ExternalLink, Play, Square, Terminal } from "lucide-react";
import { useMemo, useState } from "react";

import { fileUrl } from "../api/client";
import { startTraceViewer, stopTraceViewer } from "../api/platform";
import type { TestArtifact, TestRun, TraceViewerResponse } from "../types/platform";

export function TraceViewerCard({ run, artifacts }: { run: TestRun | null; artifacts: TestArtifact[] }) {
  const [status, setStatus] = useState<TraceViewerResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const traceArtifact = useMemo(() => findTraceArtifact(artifacts), [artifacts]);
  const tracePath = traceArtifact?.file_path || status?.tracePath || "";
  const localCommand = tracePath ? `npx playwright show-trace ${tracePath}` : "npx playwright show-trace artifacts/runs/{run_code}/traces/trace.zip";
  const errorText = status?.status === "failed" ? traceErrorMessage(status) : null;

  async function handlePlay() {
    if (!run) return;
    setLoading(true);
    try {
      const result = await startTraceViewer(run.id);
      setStatus(result);
      if (result.status === "running" && result.viewerUrl) {
        window.open(result.viewerUrl, "_blank", "noopener,noreferrer");
      }
    } catch (error) {
      setStatus({
        enabled: true,
        status: "failed",
        viewerUrl: "",
        error: "trace_viewer_request_failed",
        message: error instanceof Error ? error.message : String(error)
      });
    } finally {
      setLoading(false);
    }
  }

  async function handleStop() {
    if (!run) return;
    setLoading(true);
    try {
      setStatus(await stopTraceViewer(run.id));
    } catch (error) {
      setStatus({
        enabled: true,
        status: "failed",
        viewerUrl: "",
        error: "trace_viewer_stop_failed",
        message: error instanceof Error ? error.message : String(error)
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="trace-viewer-card">
      <div className="trace-viewer-card__heading">
        <div>
          <h3>浏览器执行轨迹回放</h3>
          <p>执行轨迹可能包含页面截图、页面结构、网络请求和业务数据。请仅在内网或本机查看，不要上传到公网。</p>
        </div>
        <span data-status={status?.status || (traceArtifact ? "ready" : "missing")}>
          {traceArtifact ? "执行轨迹已生成" : "未检测到执行轨迹"}
        </span>
      </div>

      <div className="trace-viewer-card__meta">
        <div>
          <span>录制时间</span>
          <strong>{traceArtifact?.created_at ? new Date(traceArtifact.created_at).toLocaleString("zh-CN") : "-"}</strong>
        </div>
        <div>
          <span>文件大小</span>
          <strong>{formatFileSize(traceArtifact?.metadata_json?.file_size_bytes)}</strong>
        </div>
        <div>
          <span>查看器状态</span>
          <strong>{statusLabel(status?.status)}</strong>
        </div>
      </div>

      {errorText ? <pre className="error-detail error-detail--collapsed">{errorText}</pre> : null}

      <div className="trace-viewer-card__actions">
        {traceArtifact ? (
          <a className="secondary-link" href={fileUrl(traceArtifact.file_path)} target="_blank" rel="noreferrer">
            <Download size={14} />
            下载执行轨迹
          </a>
        ) : null}
        <button className="primary-button" type="button" onClick={() => void handlePlay()} disabled={!run || loading}>
          <Play size={14} />
          {loading ? "处理中" : "播放执行轨迹"}
        </button>
        <button className="secondary-button" type="button" onClick={() => void handleStop()} disabled={!run || loading}>
          <Square size={14} />
          停止查看器
        </button>
        {status?.viewerUrl ? (
          <a className="secondary-link" href={status.viewerUrl} target="_blank" rel="noreferrer">
            <ExternalLink size={14} />
            打开查看器
          </a>
        ) : null}
        <button className="ghost-button" type="button" onClick={() => setCommandOpen((value) => !value)}>
          <Terminal size={14} />
          查看本地命令
        </button>
      </div>

      {commandOpen ? <code className="trace-viewer-card__command">{localCommand}</code> : null}
    </section>
  );
}

function findTraceArtifact(artifacts: TestArtifact[]): TestArtifact | null {
  return (
    artifacts.find((artifact) => ["playwright_trace", "trace", "trace_zip"].includes(artifact.artifact_type)) ||
    artifacts.find((artifact) => artifact.file_path.replace(/\\/g, "/").endsWith("/traces/trace.zip")) ||
    null
  );
}

function statusLabel(value: string | null | undefined): string {
  if (value === "running") return "运行中";
  if (value === "stopped") return "已停止";
  if (value === "failed") return "启动失败";
  if (value === "not_started") return "未启动";
  return "未启动";
}

function traceErrorMessage(response: TraceViewerResponse): string {
  if (response.error === "trace_viewer_dependency_missing") {
    return response.message || "服务器未安装 Playwright 命令行工具，请安装 Node.js 后执行 npm install -g playwright。";
  }
  if (response.error === "trace_file_not_found") {
    return "当前运行未生成执行轨迹文件，请确认该运行已完成且执行轨迹录制已开启。";
  }
  return response.message || response.error || "执行轨迹查看器启动失败。";
}

function formatFileSize(value: unknown): string {
  const bytes = Number(value);
  if (!Number.isFinite(bytes) || bytes <= 0) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
