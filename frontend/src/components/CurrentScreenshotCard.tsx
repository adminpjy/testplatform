import { Image, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { apiUrl, fileUrl } from "../api/client";
import type { TestArtifact, TestRun, TestStepRun } from "../types/platform";
import { readableStepAction } from "../utils/runtimeDisplay";
import { StatusBadge } from "./StatusBadge";

type DisplayImage = {
  src: string;
  title: string;
  label: string;
};

export function CurrentScreenshotCard({
  run,
  steps,
  artifacts,
  refreshKey,
  onRefresh,
  onPreview
}: {
  run: TestRun | null;
  steps: TestStepRun[];
  artifacts: TestArtifact[];
  refreshKey: number;
  onRefresh: () => void;
  onPreview: (src: string, title: string) => void;
}) {
  const [imageFailed, setImageFailed] = useState(false);
  const [displayedImage, setDisplayedImage] = useState<DisplayImage | null>(null);
  const [pendingImage, setPendingImage] = useState<DisplayImage | null>(null);

  useEffect(() => {
    if (run?.status !== "running") return;
    const timer = window.setInterval(onRefresh, 2000);
    return () => window.clearInterval(timer);
  }, [onRefresh, run?.status]);

  const currentStep = useMemo(() => {
    return steps.find((step) => step.status === "running") || steps.find((step) => step.status === "failed") || steps[steps.length - 1] || null;
  }, [steps]);
  const processScreenshots = useMemo(() => {
    return artifacts
      .filter((artifact) => artifact.artifact_type === "process_screenshot" && artifact.file_path)
      .sort(compareProcessScreenshots);
  }, [artifacts]);
  const latestProcessScreenshot = processScreenshots[processScreenshots.length - 1] || null;
  const candidateImage = useMemo<DisplayImage | null>(() => {
    if (!run) return null;
    if (latestProcessScreenshot?.file_path) {
      const label = processScreenshotLabel(latestProcessScreenshot);
      return {
        src: fileUrl(latestProcessScreenshot.file_path),
        title: `${currentStep?.step_name || currentStep?.target || "当前步骤"} - ${label}`,
        label
      };
    }
    if (currentStep?.screenshot_path) {
      return {
        src: fileUrl(currentStep.screenshot_path),
        title: currentStep.step_name || currentStep.target || "步骤截图",
        label: currentStep.status === "failed" ? "异常现场" : "步骤截图"
      };
    }
    return {
      src: apiUrl(`/api/test-runs/${run.id}/latest-screenshot?t=${refreshKey}`),
      title: currentStep?.step_name || "当前截图",
      label: "实时截图"
    };
  }, [currentStep, latestProcessScreenshot, refreshKey, run]);

  useEffect(() => {
    setDisplayedImage(null);
    setPendingImage(null);
    setImageFailed(false);
  }, [run?.id]);

  useEffect(() => {
    if (!candidateImage) {
      setPendingImage(null);
      if (!run) setDisplayedImage(null);
      return;
    }
    if (candidateImage.src === displayedImage?.src) {
      return;
    }
    setPendingImage(candidateImage);
    if (!displayedImage) {
      setImageFailed(false);
    }
  }, [candidateImage, displayedImage, run]);

  const visibleImage = displayedImage;

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

      {pendingImage && pendingImage.src !== visibleImage?.src ? (
        <img
          alt=""
          className="screenshot-card__preloader"
          src={pendingImage.src}
          onLoad={() => {
            setDisplayedImage(pendingImage);
            setPendingImage(null);
            setImageFailed(false);
          }}
          onError={() => {
            setPendingImage(null);
            setImageFailed((failed) => (visibleImage ? failed : true));
          }}
        />
      ) : null}

      {visibleImage && !imageFailed ? (
        <button className="screenshot-card__image-button" type="button" onClick={() => onPreview(visibleImage.src, visibleImage.title)}>
          <img
            alt="当前执行截图"
            src={visibleImage.src}
            onError={() => {
              setImageFailed(true);
            }}
          />
          <span className="screenshot-card__status">
            {pendingImage ? "正在刷新，当前保留最后有效截图" : visibleImage.label}
          </span>
        </button>
      ) : (
        <div className="empty-state">{run ? "正在获取执行截图" : "执行后显示当前截图"}</div>
      )}

      {processScreenshots.length > 0 ? (
        <div className="current-process-strip" aria-label="过程截图">
          {processScreenshots.map((artifact) => {
            const src = fileUrl(artifact.file_path);
            const title = processScreenshotLabel(artifact);
            return (
              <button className="current-process-strip__item" type="button" key={artifact.id} onClick={() => onPreview(src, title)}>
                <img alt={title} src={src} />
                <span>{title}</span>
              </button>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}

function compareProcessScreenshots(left: TestArtifact, right: TestArtifact): number {
  const leftStep = metadataNumber(left, "step_number");
  const rightStep = metadataNumber(right, "step_number");
  if (leftStep !== rightStep) return leftStep - rightStep;
  const leftIndex = metadataNumber(left, "index");
  const rightIndex = metadataNumber(right, "index");
  if (leftIndex !== rightIndex) return leftIndex - rightIndex;
  return left.id - right.id;
}

function metadataNumber(artifact: TestArtifact, key: string): number {
  const value = artifact.metadata_json?.[key];
  return typeof value === "number" ? value : Number(value || 0);
}

function processScreenshotLabel(artifact: TestArtifact): string {
  const label = String(artifact.metadata_json?.label || "");
  if (label === "before_step") return "步骤开始";
  if (label === "after_action") return "动作完成";
  if (label === "on_error") return "异常现场";
  if (label === "login_username_filled") return "账号已填";
  if (label === "login_password_filled") return "密码已填";
  if (label === "login_before_submit") return "提交前";
  if (label.includes("before_click")) return "点击前";
  if (label.includes("after_click")) return "点击后";
  if (label === "navigation_new_page_after_leaf_click") return "新页面";
  return label || "过程截图";
}

function formatTime(value?: string | null): string {
  if (!value) return "-";
  return new Date(value).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
