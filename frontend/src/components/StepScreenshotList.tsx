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
                <JsonCollapseBlock title="查看原始步骤 JSON" value={step} />
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
    .filter((artifact) => artifact.file_path && artifact.artifact_type !== "screenshot")
    .map((artifact) => (
      <a href={fileUrl(artifact.file_path)} target="_blank" rel="noreferrer" key={artifact.id}>
        <ExternalLink size={13} />
        {artifactLabel(artifact.artifact_type)}
      </a>
    ));
}

function artifactLabel(type: string): string {
  if (type === "dom_snapshot") return "DOM Snapshot";
  if (type === "accessibility_snapshot") return "Accessibility Snapshot";
  if (type === "locator_debug") return "locator-debug";
  return type;
}

function durationText(step: TestStepRun): string {
  if (!step.started_at || !step.ended_at) return "-";
  return `${Math.max(0, new Date(step.ended_at).getTime() - new Date(step.started_at).getTime())} ms`;
}
