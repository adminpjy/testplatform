import { PanelRightClose } from "lucide-react";
import { useEffect, useState } from "react";

import type { FailureSample, HumanIntervention, RuleDraft, TestArtifact, TestRun, TestStepRun } from "../types/platform";
import { labelAction, labelStatus } from "../utils/displayLabels";

export interface DebugDrawerProps {
  open: boolean;
  title: string;
  run: TestRun | null;
  steps: TestStepRun[];
  artifacts: TestArtifact[];
  failureSamples?: FailureSample[];
  interventions?: HumanIntervention[];
  latestRuleDraft?: RuleDraft | null;
  interventionMode?: boolean;
  onCreateIntervention?: (instruction: string) => Promise<void>;
  onExecuteIntervention?: (interventionId: number) => Promise<void>;
  onConvertIntervention?: (interventionId: number) => Promise<void>;
  onClose: () => void;
}

const DEFAULT_INTERVENTION_INSTRUCTION = "请根据失败截图和错误提示生成恢复方案；如果需要人工完成验证码、扫码或安全确认，我已在页面上完成后继续检测。";

const INTERVENTION_PRESETS = [
  "已完成验证码/扫码认证，继续检测登录状态。",
  "关闭当前弹窗后重试原失败步骤。",
  "点击继续访问，等待页面稳定后重试。",
  "等待主页面加载完成后再执行原步骤。"
];

export function DebugDrawer({
  open,
  title,
  run,
  steps,
  artifacts,
  failureSamples = [],
  interventions = [],
  latestRuleDraft = null,
  interventionMode = false,
  onCreateIntervention,
  onExecuteIntervention,
  onConvertIntervention,
  onClose
}: DebugDrawerProps) {
  const [instruction, setInstruction] = useState(DEFAULT_INTERVENTION_INSTRUCTION);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const latestIntervention = interventions[0] || null;

  useEffect(() => {
    if (interventionMode) {
      setInstruction(DEFAULT_INTERVENTION_INSTRUCTION);
      setFeedback(null);
    }
  }, [interventionMode, run?.id]);

  async function runAction(label: string, action: () => Promise<void>) {
    setBusy(true);
    setFeedback(`${label}中...`);
    try {
      await action();
      setFeedback(`${label}完成。`);
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className={`debug-drawer ${open ? "debug-drawer--open" : ""}`} aria-hidden={!open}>
      <div className="debug-drawer__header">
        <div>
          <h2>{title}</h2>
          <span>{run ? run.run_code : "尚未选择运行"}</span>
        </div>
        <button className="icon-button" type="button" onClick={onClose} title="关闭">
          <PanelRightClose size={18} />
        </button>
      </div>

      <div className="debug-drawer__body">
        {interventionMode ? (
          <section className="debug-section">
            <h3>人工介入</h3>
            <p className="debug-section__hint">
              先用大模型把人工判断生成受控方案，再一键执行。执行时会启动恢复运行；原失败运行的浏览器会话结束后不能在原页面继续。
            </p>
            <div className="intervention-presets" aria-label="常用介入说明">
              {INTERVENTION_PRESETS.map((preset) => (
                <button key={preset} className="intervention-preset" type="button" onClick={() => setInstruction(preset)}>
                  {preset}
                </button>
              ))}
            </div>
            <textarea
              aria-label="人工介入指令"
              value={instruction}
              onChange={(event) => setInstruction(event.target.value)}
              placeholder="用普通话描述你看到的问题和希望系统怎么恢复，例如：已完成验证码，等待 2 秒后重试原步骤。"
              rows={6}
            />
            <div className="action-bar">
              <button
                className="primary-button"
                type="button"
                disabled={busy || !run || !onCreateIntervention}
                onClick={() => onCreateIntervention && void runAction("用大模型生成方案", () => onCreateIntervention(instruction))}
              >
                {busy ? "处理中" : "用大模型生成方案"}
              </button>
              <button
                className="secondary-button"
                type="button"
                disabled={busy || !latestIntervention || !onExecuteIntervention}
                onClick={() =>
                  latestIntervention && onExecuteIntervention
                    ? void runAction("执行方案并启动恢复运行", () => onExecuteIntervention(latestIntervention.id))
                    : undefined
                }
              >
                执行方案并重跑
              </button>
              <button
                className="ghost-button"
                type="button"
                disabled={busy || !latestIntervention || !onConvertIntervention}
                onClick={() =>
                  latestIntervention && onConvertIntervention
                    ? void runAction("生成规则草案", () => onConvertIntervention(latestIntervention.id))
                    : undefined
                }
              >
                生成规则草案
              </button>
            </div>
            {feedback ? <div className="debug-feedback">{feedback}</div> : null}
            {latestIntervention ? (
              <div className="intervention-plan-card">
                <div className="intervention-plan-card__meta">
                  <strong>当前方案：{labelStatus(latestIntervention.status)}</strong>
                  <span>#{latestIntervention.id}</span>
                </div>
                <p>{latestIntervention.llm_plan_json?.summary || "已生成介入方案。"}</p>
                <ol>
                  {(latestIntervention.llm_plan_json?.steps || []).map((step, index) => (
                    <li key={`${step.action}-${index}`}>
                      <strong>{labelAction(String(step.action || ""))}</strong>
                      {step.value ? <span> {step.value} 毫秒</span> : null}
                      {step.target ? <span> - {step.target}</span> : null}
                      {step.reason ? <small>{step.reason}</small> : null}
                    </li>
                  ))}
                </ol>
                {latestIntervention.execution_result_json ? (
                  <div className="intervention-result">
                    <strong>{interventionResultTitle(latestIntervention)}</strong>
                    <p>{interventionResultMessage(latestIntervention)}</p>
                  </div>
                ) : null}
              </div>
            ) : null}
            {latestRuleDraft ? (
              <dl className="settings-list">
                <dt>规则草案</dt>
                <dd>#{latestRuleDraft.id} {latestRuleDraft.rule_name}</dd>
                <dt>状态</dt>
                <dd>{labelStatus(latestRuleDraft.status)}</dd>
              </dl>
            ) : null}
          </section>
        ) : null}

        {failureSamples.length > 0 ? (
          <section className="debug-section">
            <h3>失败样本</h3>
            <pre>{JSON.stringify(failureSamples, null, 2)}</pre>
          </section>
        ) : null}

        {interventions.length > 0 ? (
          <section className="debug-section">
            <h3>人工介入记录</h3>
            <pre>{JSON.stringify(interventions, null, 2)}</pre>
          </section>
        ) : null}

        <section className="debug-section">
          <h3>运行摘要</h3>
          <pre>{JSON.stringify(run?.summary_json || {}, null, 2)}</pre>
        </section>
        <section className="debug-section">
          <h3>执行测试步骤</h3>
          <pre>{JSON.stringify(run?.dsl_json || {}, null, 2)}</pre>
        </section>
        <section className="debug-section">
          <h3>步骤结果</h3>
          <pre>{JSON.stringify(steps, null, 2)}</pre>
        </section>
        <section className="debug-section">
          <h3>产物</h3>
          <pre>{JSON.stringify(artifacts, null, 2)}</pre>
        </section>
      </div>
    </aside>
  );
}

function interventionResultTitle(intervention: HumanIntervention): string {
  const result = intervention.execution_result_json || {};
  const status = String(result["status"] || intervention.status || "");
  if (status === "recovery_run_started") return "恢复运行已启动";
  if (status === "failed_to_start_recovery_run") return "恢复运行启动失败";
  return "执行结果";
}

function interventionResultMessage(intervention: HumanIntervention): string {
  const result = intervention.execution_result_json || {};
  const message = result["message"] ? String(result["message"]) : "";
  if (message) return message;
  const recoveryRunCode = result["recoveryRunCode"] ? String(result["recoveryRunCode"]) : "";
  if (recoveryRunCode) return `已启动恢复运行 ${recoveryRunCode}。`;
  return "介入方案已完成安全校验。";
}
