import { PanelRightClose } from "lucide-react";
import { useEffect, useState } from "react";

import type { FailureSample, HumanIntervention, RuleDraft, TestArtifact, TestRun, TestStepRun } from "../types/platform";

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
  const [instruction, setInstruction] = useState("等待主页面加载完成后再执行原步骤。");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const latestIntervention = interventions[0] || null;

  useEffect(() => {
    if (interventionMode) {
      setInstruction("等待主页面加载完成后再执行原步骤。");
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
            <p className="debug-section__hint">用于把人工判断沉淀为受控恢复动作。常见场景：等待主页面加载、关闭弹窗、重试原失败步骤。</p>
            <textarea
              aria-label="人工介入指令"
              value={instruction}
              onChange={(event) => setInstruction(event.target.value)}
              placeholder="输入人工判断、修正步骤或复盘说明。"
              rows={6}
            />
            <div className="action-bar">
              <button
                className="primary-button"
                type="button"
                disabled={busy || !run || !onCreateIntervention}
                onClick={() => onCreateIntervention && void runAction("生成介入方案", () => onCreateIntervention(instruction))}
              >
                {busy ? "处理中" : "生成介入方案"}
              </button>
              <button
                className="secondary-button"
                type="button"
                disabled={busy || !latestIntervention || !onExecuteIntervention}
                onClick={() =>
                  latestIntervention && onExecuteIntervention
                    ? void runAction("执行介入方案", () => onExecuteIntervention(latestIntervention.id))
                    : undefined
                }
              >
                执行介入方案
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
                  <strong>当前方案：{latestIntervention.status}</strong>
                  <span>#{latestIntervention.id}</span>
                </div>
                <p>{latestIntervention.llm_plan_json?.summary || "已生成介入方案。"}</p>
                <ol>
                  {(latestIntervention.llm_plan_json?.steps || []).map((step, index) => (
                    <li key={`${step.action}-${index}`}>
                      <strong>{step.action}</strong>
                      {step.value ? <span> {step.value} ms</span> : null}
                      {step.target ? <span> - {step.target}</span> : null}
                      {step.reason ? <small>{step.reason}</small> : null}
                    </li>
                  ))}
                </ol>
                {latestIntervention.execution_result_json ? (
                  <pre>{JSON.stringify(latestIntervention.execution_result_json, null, 2)}</pre>
                ) : null}
              </div>
            ) : null}
            {latestRuleDraft ? (
              <pre>{JSON.stringify({ id: latestRuleDraft.id, status: latestRuleDraft.status, name: latestRuleDraft.rule_name }, null, 2)}</pre>
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
          <h3>执行 DSL</h3>
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
