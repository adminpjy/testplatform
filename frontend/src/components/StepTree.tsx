import { CheckCircle2, CircleDashed, XCircle } from "lucide-react";

import type { TestStepRun } from "../types/platform";
import { readableStepAction } from "../utils/runtimeDisplay";
import { StatusBadge } from "./StatusBadge";

export interface StepTreeProps {
  steps: TestStepRun[];
}

export function StepTree({ steps }: StepTreeProps) {
  return (
    <section className="surface-panel step-tree">
      <div className="panel-heading">
        <h2>简化步骤树</h2>
        <span>{steps.length} 步</span>
      </div>
      {steps.length === 0 ? (
        <div className="empty-state">执行后显示步骤结果</div>
      ) : (
        <ol className="step-tree__list">
          {steps.map((step, index) => (
            <li className="step-tree__item" key={step.id}>
              <div className="step-tree__marker">{statusIcon(step.status)}</div>
              <div className="step-tree__content">
                <div className="step-tree__title">
                  <strong>{step.step_name || step.target || `步骤 ${index + 1}`}</strong>
                  <StatusBadge value={step.status} />
                </div>
                <div className="step-tree__meta">
                  <span>{readableStepAction(step)}</span>
                  {step.target ? <span>{step.target}</span> : null}
                  {step.locator_strategy ? <span>{locatorStrategyText(step.locator_strategy)}</span> : null}
                  {step.confidence !== null && step.confidence !== undefined ? (
                    <span>置信度 {Math.round(step.confidence * 100)}%</span>
                  ) : null}
                </div>
                {step.error_summary ? <pre className="error-detail error-detail--collapsed">{step.error_summary}</pre> : null}
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function locatorStrategyText(value: string): string {
  if (value.includes("llm")) return "大模型辅助定位";
  if (value.includes("vision")) return "视觉兜底定位";
  if (value.includes("semantic")) return "页面语义定位";
  if (value.includes("playwright")) return "页面结构定位";
  if (value.includes("knowledge")) return "知识库定位";
  return "系统定位";
}

function statusIcon(status: string) {
  if (status === "passed") {
    return <CheckCircle2 size={18} />;
  }
  if (status === "failed") {
    return <XCircle size={18} />;
  }
  return <CircleDashed size={18} />;
}
