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

  const loginFailure = isLoginFailure(errorText);
  const remainingRetries = loginFailure ? remainingRetriesFrom(errorText) : null;
  const summaryText = loginFailure
    ? "系统检测到当前仍停留在认证中心登录页，并发现登录失败提示。为了避免账号被锁定，系统没有继续执行后续业务步骤。"
    : shortSummary(errorText);
  return (
    <section className="surface-panel error-summary-card">
      <div className="panel-heading">
        <h2>
          <AlertTriangle size={16} />
          {loginFailure ? "登录失败，已停止后续测试步骤" : "错误摘要"}
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
          <strong>{loginFailure ? "login_failed" : failedStep ? readableStepAction(failedStep) : apiError ? "接口错误" : run?.status || "failed"}</strong>
        </div>
      </div>
      <p>{summaryText}</p>
      {loginFailure ? (
        <>
          <div className="error-summary-card__suggestion">
            <strong>证据：</strong>
            <ul>
              {loginEvidence(errorText).map((item) => <li key={item}>{item}</li>)}
              {remainingRetries !== null ? <li>剩余重试次数：{remainingRetries}</li> : null}
            </ul>
          </div>
          <div className="error-summary-card__suggestion">
            <strong>可能原因：</strong>
            <ul>
              <li>用户名或密码错误；</li>
              <li>账号被禁用、锁定或未绑定；</li>
              <li>AD 密码未同步；</li>
              <li>测试账号无效或无权访问目标系统。</li>
            </ul>
          </div>
          <p className="error-summary-card__suggestion">建议检查被测系统配置中的测试账号和密码，或联系系统管理员确认账号状态。登录未成功前，系统不会继续执行后续业务步骤。</p>
        </>
      ) : (
        <p className="error-summary-card__suggestion">建议先查看当前截图和步骤证据；如果页面存在业务弹窗或特殊控件，可发起人工介入并沉淀规则草案。</p>
      )}
      <div className="action-bar">
        {loginFailure ? (
          <>
            <button className="secondary-button" type="button" onClick={onDebug} disabled={!run}>
              修改账号信息
            </button>
            <button className="ghost-button" type="button" onClick={onDebug} disabled={!run}>
              重新执行登录检查
            </button>
          </>
        ) : null}
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

function isLoginFailure(value: string): boolean {
  const lower = value.toLowerCase();
  return [
    "login_failed",
    "protected_step_blocked_by_login_failure",
    "auth_state_not_logged_in",
    "authentication_failed",
    "login was failed",
    "wrong user name or password",
    "wrong username or password",
    "invalid username or password",
    "authentication failed",
    "account disabled",
    "account locked",
    "retries",
    "登录失败",
    "用户名或密码错误",
    "账号或密码错误",
    "认证失败",
    "密码错误",
    "账号已锁定",
    "账户已锁定",
    "账号被禁用",
    "账户被禁用",
  ].some((token) => lower.includes(token.toLowerCase()));
}

function remainingRetriesFrom(value: string): number | null {
  const match = value.match(/(?:you have|剩余|还有)\s*(\d+)\s*(?:retr(?:y|ies)|次)?/i);
  if (!match) return null;
  const parsed = Number.parseInt(match[1], 10);
  return Number.isFinite(parsed) ? parsed : null;
}

function loginEvidence(value: string): string[] {
  const lower = value.toLowerCase();
  const evidence: string[] = [];
  if (lower.includes("login was failed") || value.includes("登录失败")) evidence.push("Login was failed");
  if (lower.includes("wrong user name or password") || lower.includes("wrong username or password") || value.includes("用户名或密码错误")) {
    evidence.push("Wrong user name or password");
  }
  if (lower.includes("authentication center") || value.includes("认证中心")) evidence.push("Authentication Center / 用户认证中心可见");
  evidence.push("登录表单仍可见");
  evidence.push("未检测到业务系统主菜单");
  return Array.from(new Set(evidence));
}
