import { ChevronDown, ChevronUp, ExternalLink, ImageOff } from "lucide-react";
import { useState } from "react";

import { fileUrl } from "../api/client";
import type { TestArtifact, TestStepRun } from "../types/platform";
import { readableStepAction } from "../utils/runtimeDisplay";
import { JsonCollapseBlock } from "./JsonCollapseBlock";
import { StatusBadge } from "./StatusBadge";

export function StepScreenshotList({
  steps,
  artifacts,
  onPreview
}: {
  steps: TestStepRun[];
  artifacts: TestArtifact[];
  onPreview: (src: string, title: string) => void;
}) {
  const [expanded, setExpanded] = useState<number | null>(null);

  if (steps.length === 0) {
    return <div className="empty-state">执行后显示步骤与截图</div>;
  }

  return (
    <div className="step-screenshot-list">
      {steps.map((step, index) => {
        const open = expanded === step.id;
        const screenshot = step.screenshot_path ? fileUrl(step.screenshot_path) : null;
        const stepArtifacts = artifacts.filter((artifact) => artifact.step_id === step.id);
        const processScreenshots = stepArtifacts
          .filter((artifact) => artifact.artifact_type === "process_screenshot" && artifact.file_path)
          .sort(compareProcessScreenshots);
        return (
          <article className={step.status === "failed" ? "step-screenshot-row step-screenshot-row--failed" : "step-screenshot-row"} key={step.id}>
            <button className="step-screenshot-row__summary" type="button" onClick={() => setExpanded(open ? null : step.id)}>
              <span className="step-screenshot-row__index">S{String(index + 1).padStart(3, "0")}</span>
              <span className="step-screenshot-row__main">
                <strong>{step.step_name || step.target || `步骤 ${index + 1}`}</strong>
                <small>{readableStepAction(step)}</small>
              </span>
              <StatusBadge value={step.status} />
              <span className="step-screenshot-row__duration">{durationText(step)}</span>
              <span className="step-screenshot-row__thumb">
                {screenshot ? <img src={screenshot} alt={step.step_name || "步骤截图"} /> : <ImageOff size={18} />}
              </span>
              {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>

            {open ? (
              <div className="step-screenshot-row__details">
                {processScreenshots.length > 0 ? (
                  <div className="step-process-shot-grid">
                    {processScreenshots.map((artifact) => {
                      const src = fileUrl(artifact.file_path);
                      const title = processScreenshotLabel(artifact);
                      return (
                        <button className="step-process-shot" type="button" key={artifact.id} onClick={() => onPreview(src, title)}>
                          <img src={src} alt={title} />
                          <span>{title}</span>
                        </button>
                      );
                    })}
                  </div>
                ) : null}
                {screenshot ? (
                  <button className="step-screenshot-row__large-image" type="button" onClick={() => onPreview(screenshot, step.step_name || "步骤截图")}>
                    <img src={screenshot} alt={step.step_name || "步骤截图"} />
                  </button>
                ) : (
                  <div className="empty-state">暂无截图</div>
                )}
                <div className="artifact-link-grid">
                  {artifactLinks(stepArtifacts)}
                  {step.screenshot_path ? (
                    <a href={fileUrl(step.screenshot_path)} target="_blank" rel="noreferrer">
                      <ExternalLink size={13} />
                      当前步骤截图
                    </a>
                  ) : null}
                </div>
                {step.error_summary ? <pre className="error-detail error-detail--collapsed">{step.error_summary}</pre> : null}
                <JsonCollapseBlock title="查看原始步骤数据" value={step} />
              </div>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}

function artifactLinks(artifacts: TestArtifact[]) {
  return artifacts
    .filter((artifact) => artifact.file_path && !["screenshot", "process_screenshot"].includes(artifact.artifact_type))
    .map((artifact) => (
      <a href={fileUrl(artifact.file_path)} target="_blank" rel="noreferrer" key={artifact.id}>
        <ExternalLink size={13} />
        {artifactLabel(artifact.artifact_type)}
      </a>
    ));
}

function artifactLabel(type: string): string {
  if (type === "dom_snapshot") return "页面结构快照";
  if (type === "accessibility_snapshot") return "可访问性快照";
  if (type === "locator_debug") return "定位调试文件";
  if (type === "process_screenshot") return "过程截图";
  return "其他产物";
}

function compareProcessScreenshots(left: TestArtifact, right: TestArtifact): number {
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

function durationText(step: TestStepRun): string {
  if (!step.started_at || !step.ended_at) return "-";
  return `${Math.max(0, new Date(step.ended_at).getTime() - new Date(step.started_at).getTime())} 毫秒`;
}
