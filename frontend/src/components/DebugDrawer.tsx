import { PanelRightClose } from "lucide-react";

import type { TestArtifact, TestRun, TestStepRun } from "../types/platform";

export interface DebugDrawerProps {
  open: boolean;
  title: string;
  run: TestRun | null;
  steps: TestStepRun[];
  artifacts: TestArtifact[];
  interventionMode?: boolean;
  onClose: () => void;
}

export function DebugDrawer({
  open,
  title,
  run,
  steps,
  artifacts,
  interventionMode = false,
  onClose
}: DebugDrawerProps) {
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

      {interventionMode ? (
        <section className="debug-section">
          <h3>人工介入</h3>
          <textarea
            aria-label="人工介入指令"
            placeholder="输入人工判断、修正步骤或复盘说明。当前阶段保留入口，不会直接改写执行结果。"
            rows={6}
          />
          <button className="primary-button" type="button" disabled>
            记录人工指令
          </button>
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
    </aside>
  );
}
