import { AlertTriangle, ChevronDown, ChevronUp } from "lucide-react";
import { useMemo, useState } from "react";

import type { TestRun, TestStepRun } from "../types/platform";

export interface ErrorSummaryCardProps {
  run: TestRun | null;
  steps: TestStepRun[];
  apiError?: string | null;
}

export function ErrorSummaryCard({ run, steps, apiError }: ErrorSummaryCardProps) {
  const [expanded, setExpanded] = useState(false);
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

  const isLong = errorText.length > 320;
  return (
    <section className="surface-panel error-summary-card">
      <div className="panel-heading">
        <h2>
          <AlertTriangle size={16} />
          错误摘要
        </h2>
        {isLong ? (
          <button className="ghost-button" type="button" onClick={() => setExpanded((value) => !value)}>
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            {expanded ? "收起" : "展开"}
          </button>
        ) : null}
      </div>
      <pre className={expanded ? "error-detail" : "error-detail error-detail--collapsed"}>{errorText}</pre>
    </section>
  );
}
