import { AlertTriangle, Bug, ChevronDown, ChevronUp, ClipboardCopy, UserRoundCheck } from "lucide-react";
import { useMemo, useState } from "react";

import type { TestRun, TestStepRun } from "../types/platform";
import { readableStepAction } from "../utils/runtimeDisplay";

export interface ErrorSummaryCardProps {
  run: TestRun | null;
  steps: TestStepRun[];
  apiError?: string | null;
  onIntervention?: () => void;
  onDebug?: () => void;
}

export function ErrorSummaryCard({ run, steps, apiError, onIntervention, onDebug }: ErrorSummaryCardProps) {
  const [expanded, setExpanded] = useState(false);
  const failedStep = useMemo(() => steps.find((step) => step.status === "failed") || null, [steps]);
  const errorText = useMemo(() => {
    if (apiError) {
      return apiError;
    }
    const summaryError = run?.summary_json?.errorSummary;
    if (typeof summaryError === "string" && summaryError.trim()) {
      return summaryError;
    }
    const failedStep = steps.find((step) => step.status === "failed" && step.error_summary);
    return failedStep?.error_summary || "";
  }, [apiError, run, steps]);

  if (!errorText) {
    return (
      <section className="surface-panel error-summary-card error-summary-card--empty">
        <div className="panel-heading">
          <h2>错误摘要</h2>
          <span>当前没有错误</span>
        </div>
      </section>
    );
  }

  const summaryText = shortSummary(errorText);
  return (
    <section className="surface-panel error-summary-card">
      <div className="panel-heading">
        <h2>
          <AlertTriangle size={16} />
          错误摘要
        </h2>
        <button className="ghost-button" type="button" onClick={() => setExpanded((value) => !value)}>
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          {expanded ? "收起完整错误" : "查看完整错误"}
        </button>
      </div>
      <div className="error-summary-card__grid">
        <div>
          <span>失败步骤</span>
          <strong>{failedStep?.step_name || failedStep?.target || (apiError ? "页面操作" : "未定位")}</strong>
        </div>
        <div>
          <span>失败类型</span>
          <strong>{failedStep ? readableStepAction(failedStep) : apiError ? "接口错误" : run?.status || "failed"}</strong>
        </div>
      </div>
      <p>{summaryText}</p>
      <p className="error-summary-card__suggestion">建议先查看当前截图和步骤证据；如果页面存在业务弹窗或特殊控件，可发起人工介入并沉淀规则草案。</p>
      <div className="action-bar">
        <button className="secondary-button" type="button" onClick={onIntervention} disabled={!run}>
          <UserRoundCheck size={16} />
          人工介入
        </button>
        <button className="ghost-button" type="button" onClick={onDebug} disabled={!run}>
          <Bug size={16} />
          查看调试详情
        </button>
        <button className="ghost-button" type="button" onClick={() => void navigator.clipboard?.writeText(errorText)}>
          <ClipboardCopy size={16} />
          复制完整错误
        </button>
      </div>
      {expanded ? <pre className="error-detail">{errorText}</pre> : null}
    </section>
  );
}

function shortSummary(value: string): string {
  const normalized = value.replace(/\s+/g, " ").trim();
  if (normalized.length <= 180) return normalized;
  return `${normalized.slice(0, 180)}...`;
}
