import { AlertTriangle, Bot, CheckCircle2, Loader2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import type { TestCaseDSL } from "../types/platform";
import type { RuntimeMessage } from "../types/runtime";
import { methodLabel, readableRuntimeTitle } from "../utils/runtimeDisplay";
import { JsonCollapseBlock } from "./JsonCollapseBlock";

export function AnalysisTracePanel({
  messages,
  analyzing,
  dsl
}: {
  messages: RuntimeMessage[];
  analyzing: boolean;
  dsl: TestCaseDSL | null;
}) {
  const [showChunks, setShowChunks] = useState(true);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const visibleMessages = messages.filter((message) => message.phase !== "llm_chunk");
  const chunks = useMemo(() => collectChunks(messages), [messages]);
  const status = useMemo(() => buildAnalysisStatus(messages, dsl), [messages, dsl]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  if (!analyzing && messages.length === 0 && !dsl) {
    return null;
  }

  return (
    <section className="surface-panel analysis-trace-panel">
      <div className="panel-heading">
        <h2>
          <Bot size={16} />
          任务分解观察
        </h2>
        <span>{analyzing ? "流式分析中" : "分析已结束"}</span>
      </div>

      <div className="llm-status-grid">
        <div>
          <span>LLM 交互</span>
          <strong>{status.provider} / {status.model}</strong>
          <small>{status.endpoint || "使用本地 Mock Provider"}</small>
        </div>
        <div>
          <span>当前状态</span>
          <strong>{status.currentStage}</strong>
          <small>{status.latestMessage}</small>
        </div>
        <div>
          <span>流式回复</span>
          <strong>{status.analyzeChunks + status.planChunks} 段</strong>
          <small>分析 {status.analyzeChunks} 段，DSL {status.planChunks} 段</small>
        </div>
        <div>
          <span>DSL 步骤</span>
          <strong>{status.dslSteps > 0 ? `${status.dslSteps} 步` : "待生成"}</strong>
          <small>{dsl ? "已生成可执行步骤" : "信息足够后自动生成"}</small>
        </div>
      </div>

      <div className="analysis-trace-grid">
        <div className="analysis-trace-stream">
          {visibleMessages.map((message) => (
            <article className={`analysis-trace-message analysis-trace-message--${message.type}`} key={message.id}>
              <span className="analysis-trace-message__icon">{messageIcon(message, analyzing)}</span>
              <div>
                <div className="analysis-trace-message__title">
                  <time>{formatTime(message.createdAt)}</time>
                  <strong>{readableTitle(message)}</strong>
                </div>
                <p>{message.content}</p>
                <div className="runtime-stream-message__meta">
                  <span>方法：{methodLabel(message.method)}</span>
                  {message.phase ? <span>阶段：{phaseLabel(message.phase)}</span> : null}
                </div>
                {Object.keys(message.metadata).length > 0 ? <JsonCollapseBlock title="查看请求/响应详情" value={message.metadata} /> : null}
              </div>
            </article>
          ))}
          <div ref={bottomRef} />
        </div>

        <aside className="dsl-preview-panel">
          <div className="dsl-preview-panel__heading">
            <strong>DSL 步骤预览</strong>
            {dsl ? <span>{dsl.steps.length} 步</span> : <span>等待生成</span>}
          </div>
          {dsl ? (
            <>
              <dl className="settings-list">
                <dt>用例</dt>
                <dd>{dsl.caseName || "-"}</dd>
                <dt>入口</dt>
                <dd>{dsl.baseUrl || "-"}</dd>
              </dl>
              <ol className="dsl-step-list">
                {dsl.steps.map((step, index) => (
                  <li key={`${step.action}-${step.target || index}`}>
                    <span>S{String(index + 1).padStart(3, "0")}</span>
                    <strong>{String(step.action)}</strong>
                    <em>{String(step.target || step.description || "")}</em>
                  </li>
                ))}
              </ol>
              <JsonCollapseBlock title="查看完整 DSL JSON" value={dsl} />
            </>
          ) : (
            <div className="empty-state">分析完成且信息足够后展示 DSL</div>
          )}
        </aside>
      </div>

      {(chunks.analyze || chunks.plan) && showChunks ? (
        <div className="llm-chunk-grid">
          <button className="ghost-button llm-chunk-grid__toggle" type="button" onClick={() => setShowChunks(false)}>
            收起 LLM 原始流式输出
          </button>
          {chunks.analyze ? (
            <div>
              <strong>Analyze 流式输出</strong>
              <pre className="metadata-block llm-chunk-block">{chunks.analyze}</pre>
            </div>
          ) : null}
          {chunks.plan ? (
            <div>
              <strong>Plan / DSL 流式输出</strong>
              <pre className="metadata-block llm-chunk-block">{chunks.plan}</pre>
            </div>
          ) : null}
        </div>
      ) : chunks.analyze || chunks.plan ? (
        <button className="ghost-button" type="button" onClick={() => setShowChunks(true)}>
          展开 LLM 原始流式输出
        </button>
      ) : null}
    </section>
  );
}

function collectChunks(messages: RuntimeMessage[]): { analyze: string; plan: string } {
  return messages.reduce(
    (result, message) => {
      if (message.phase !== "llm_chunk") return result;
      const stage = message.metadata.stage === "plan" ? "plan" : "analyze";
      result[stage] += message.content || "";
      return result;
    },
    { analyze: "", plan: "" }
  );
}

function readableTitle(message: RuntimeMessage): string {
  if (message.phase === "llm_request") return message.metadata.stage === "plan" ? "正在调用 LLM 生成 DSL" : "正在调用 LLM 分析目标";
  if (message.phase === "llm_response") return message.metadata.stage === "plan" ? "DSL 回复已接收" : "分析回复已接收";
  if (message.phase === "json_repair") return "正在校验 LLM JSON 输出";
  if (message.phase === "analysis_result") return "分析结果已生成";
  if (message.phase === "dsl_generated") return "DSL 已生成";
  return readableRuntimeTitle(message);
}

function phaseLabel(phase: string): string {
  if (phase === "llm_request") return "LLM 请求";
  if (phase === "llm_response") return "LLM 回复";
  if (phase === "json_repair") return "JSON 提取/修复";
  if (phase === "analysis_result") return "信息完整性判断";
  if (phase === "dsl_generated") return "DSL 生成";
  return phase;
}

function buildAnalysisStatus(messages: RuntimeMessage[], dsl: TestCaseDSL | null) {
  const providerMessage = messages.find((message) => metadataValue(message, "provider") || metadataValue(message, "model"));
  const latest = [...messages].reverse().find((message) => message.phase !== "llm_chunk");
  const analyzeChunks = messages.filter((message) => message.phase === "llm_chunk" && message.metadata.stage !== "plan").length;
  const planChunks = messages.filter((message) => message.phase === "llm_chunk" && message.metadata.stage === "plan").length;
  return {
    provider: metadataValue(providerMessage, "provider") || "mock",
    model: metadataValue(providerMessage, "model") || "DeepSeek-V4",
    endpoint: metadataValue(providerMessage, "endpoint"),
    currentStage: latest ? readableTitle(latest) : "等待分析",
    latestMessage: latest?.content || "点击分析后显示 LLM 交互状态",
    analyzeChunks,
    planChunks,
    dslSteps: dsl?.steps.length || 0
  };
}

function metadataValue(message: RuntimeMessage | undefined, key: string): string | null {
  const value = message?.metadata[key];
  if (value === undefined || value === null || value === "") return null;
  return typeof value === "string" || typeof value === "number" || typeof value === "boolean" ? String(value) : null;
}

function messageIcon(message: RuntimeMessage, analyzing: boolean) {
  if (analyzing && message.type === "progress") {
    return <Loader2 className="runtime-stream-message__spinner" size={15} />;
  }
  if (message.type === "success") return <CheckCircle2 size={15} />;
  if (message.type === "warning" || message.type === "error") return <AlertTriangle size={15} />;
  return <Bot size={15} />;
}

function formatTime(value: string | null): string {
  if (!value) return "--:--:--";
  return new Date(value).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
