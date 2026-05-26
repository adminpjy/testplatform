import { Clock3 } from "lucide-react";

import type { TestRun } from "../types/platform";
import { StatusBadge } from "./StatusBadge";

export function RunHistoryTab({
  runs,
  activeRun,
  onSelectRun
}: {
  runs: TestRun[];
  activeRun: TestRun | null;
  onSelectRun: (run: TestRun) => void;
}) {
  if (runs.length === 0) {
    return <div className="empty-state">暂无运行记录</div>;
  }

  return (
    <div className="run-history-tab">
      <div className="run-history-tab__header">
        <strong>最近运行</strong>
        <span>默认显示最近 20 条</span>
      </div>
      <div className="run-history-tab__list">
        {runs.slice(0, 20).map((run) => (
          <button
            className={activeRun?.id === run.id ? "run-history-row run-history-row--active" : "run-history-row"}
            key={run.id}
            type="button"
            onClick={() => onSelectRun(run)}
          >
            <span className="run-history-row__code">{run.run_code}</span>
            <StatusBadge value={run.status} />
            <span>{formatDateTime(run.started_at || run.created_at)}</span>
            <span className="run-history-row__duration">
              <Clock3 size={14} />
              {durationText(run)}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

function durationText(run: TestRun): string {
  if (!run.started_at) return "-";
  const end = run.ended_at ? new Date(run.ended_at).getTime() : Date.now();
  const start = new Date(run.started_at).getTime();
  const seconds = Math.max(0, Math.round((end - start) / 1000));
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

function formatDateTime(value?: string | null): string {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}
