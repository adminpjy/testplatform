import { Image, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { apiUrl, fileUrl } from "../api/client";
import type { TestRun, TestStepRun } from "../types/platform";
import { readableStepAction } from "../utils/runtimeDisplay";
import { StatusBadge } from "./StatusBadge";

export function CurrentScreenshotCard({
  run,
  steps,
  refreshKey,
  onRefresh,
  onPreview
}: {
  run: TestRun | null;
  steps: TestStepRun[];
  refreshKey: number;
  onRefresh: () => void;
  onPreview: (src: string, title: string) => void;
}) {
  const [imageFailed, setImageFailed] = useState(false);

  useEffect(() => {
    if (run?.status !== "running") return;
    const timer = window.setInterval(onRefresh, 2000);
    return () => window.clearInterval(timer);
  }, [onRefresh, run?.status]);

  const currentStep = useMemo(() => {
    return steps.find((step) => step.status === "running") || steps.find((step) => step.status === "failed") || steps[steps.length - 1] || null;
  }, [steps]);
  const screenshotSrc = run
    ? currentStep?.status === "failed" && currentStep.screenshot_path
      ? fileUrl(currentStep.screenshot_path)
      : apiUrl(`/api/test-runs/${run.id}/latest-screenshot?t=${refreshKey}`)
    : null;

  useEffect(() => {
    setImageFailed(false);
  }, [screenshotSrc]);

  return (
    <section className="surface-panel current-screenshot-card">
      <div className="panel-heading">
        <h2>
          <Image size={16} />
          当前画面
        </h2>
        <button className="icon-button" type="button" onClick={onRefresh} disabled={!run} title="刷新截图">
          <RefreshCw size={16} />
        </button>
      </div>

      {run ? (
        <div className="current-step-summary">
          <div>
            <span>当前状态</span>
            <StatusBadge value={run.status} />
          </div>
          <div>
            <span>当前步骤</span>
            <strong>{currentStep?.step_name || currentStep?.target || "等待步骤信息"}</strong>
          </div>
          <div>
            <span>当前动作</span>
            <strong>{currentStep ? readableStepAction(currentStep) : "等待执行"}</strong>
          </div>
          <div>
            <span>更新时间</span>
            <strong>{formatTime(currentStep?.ended_at || currentStep?.started_at || run.updated_at)}</strong>
          </div>
        </div>
      ) : null}

      {screenshotSrc && !imageFailed ? (
        <button className="screenshot-card__image-button" type="button" onClick={() => onPreview(screenshotSrc, currentStep?.step_name || "当前截图")}>
          <img
            alt="当前执行截图"
            src={screenshotSrc}
            onError={(event) => {
              event.currentTarget.style.display = "none";
              setImageFailed(true);
            }}
          />
        </button>
      ) : (
        <div className="empty-state">{run ? "暂无截图" : "执行后显示当前截图"}</div>
      )}
    </section>
  );
}

function formatTime(value?: string | null): string {
  if (!value) return "-";
  return new Date(value).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
