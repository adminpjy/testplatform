import { Image, RefreshCw } from "lucide-react";

import { apiUrl } from "../api/client";
import type { TestRun } from "../types/platform";

export interface ScreenshotPanelProps {
  run: TestRun | null;
  refreshKey: number;
  onRefresh: () => void;
}

export function ScreenshotPanel({ run, refreshKey, onRefresh }: ScreenshotPanelProps) {
  return (
    <section className="surface-panel screenshot-panel">
      <div className="panel-heading">
        <h2>
          <Image size={16} />
          最新截图
        </h2>
        <button className="icon-button" type="button" onClick={onRefresh} disabled={!run} title="刷新截图">
          <RefreshCw size={16} />
        </button>
      </div>
      {run ? (
        <div className="screenshot-panel__frame">
          <img
            alt="最新执行截图"
            src={apiUrl(`/api/test-runs/${run.id}/latest-screenshot?t=${refreshKey}`)}
            onError={(event) => {
              event.currentTarget.style.display = "none";
            }}
          />
        </div>
      ) : (
        <div className="empty-state">执行后显示最新截图</div>
      )}
    </section>
  );
}
