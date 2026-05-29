import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Circle,
  Eye,
  Image,
  Loader2,
  Pause,
  Play,
  XCircle
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { openRuntimeStream } from "../api/runtimeStream";
import { fileUrl } from "../api/client";
import type { TestStepRun } from "../types/platform";
import type { RuntimeMessage, RuntimeMessageType } from "../types/runtime";
import {
  methodLabel,
  metadataString,
  readableRuntimeMessage,
  readableRuntimeTitle,
  runtimeDetailView,
  runtimeFilterOf,
  type RuntimeFilter
} from "../utils/runtimeDisplay";
import "../styles/runtime-stream.css";

export interface RuntimeStreamPanelProps {
  runId: number;
  baseUrl?: string;
  className?: string;
  initialMessages?: RuntimeMessage[];
  steps?: TestStepRun[];
  onPreviewScreenshot?: (src: string, title: string) => void;
}

const EMPTY_RUNTIME_MESSAGES: RuntimeMessage[] = [];
const EMPTY_STEPS: TestStepRun[] = [];
const FILTERS: Array<{ value: RuntimeFilter; label: string }> = [
  { value: "all", label: "全部" },
  { value: "action", label: "执行动作" },
  { value: "page", label: "页面分析" },
  { value: "llm", label: "LLM" },
  { value: "vision", label: "视觉兜底" },
  { value: "error", label: "错误" }
];

interface RuntimeStepGroup {
  key: string;
  title: string;
  summary: string;
  type: RuntimeMessageType;
  latest: RuntimeMessage;
  messages: RuntimeMessage[];
  step: TestStepRun | null;
  stepLabel: string | null;
  screenshotPath: string | null;
}

export function RuntimeStreamPanel({
  runId,
  baseUrl,
  className,
  initialMessages = EMPTY_RUNTIME_MESSAGES,
  steps = EMPTY_STEPS,
  onPreviewScreenshot
}: RuntimeStreamPanelProps) {
  const [messages, setMessages] = useState<RuntimeMessage[]>(() => dedupeMessages(initialMessages));
  const [connected, setConnected] = useState(false);
  const [finished, setFinished] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [filter, setFilter] = useState<RuntimeFilter>("all");
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setMessages(dedupeMessages(initialMessages));
    setFinished(false);
    setAutoScroll(true);
    setFilter("all");
  }, [initialMessages, runId]);

  useEffect(() => {
    setConnected(false);
    setFinished(false);
    const source = openRuntimeStream(runId, {
      baseUrl,
      onMessage: (message) => {
        setConnected(true);
        setMessages((current) => appendMessage(current, message));
        if (message.phase === "completed" || message.phase === "failed") {
          setConnected(false);
          setFinished(true);
        }
      },
      onError: () => {
        setConnected(false);
      }
    });

    source.onopen = () => setConnected(true);
    return () => source.close();
  }, [baseUrl, runId]);

  useEffect(() => {
    if (autoScroll) {
      bottomRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
    }
  }, [autoScroll, messages]);

  const statusText = finished ? "运行已结束" : connected ? "实时连接中" : "等待运行消息";
  const visibleMessages = useMemo(() => {
    return filter === "all" ? messages : messages.filter((message) => runtimeFilterOf(message) === filter);
  }, [filter, messages]);
  const visibleGroups = useMemo(() => {
    return buildRuntimeGroups(visibleMessages, steps);
  }, [steps, visibleMessages]);
  const emptyText = useMemo(() => {
    return visibleGroups.length === 0 ? "暂无运行消息" : null;
  }, [visibleGroups.length]);

  return (
    <section className={["runtime-stream-panel", className].filter(Boolean).join(" ")}>
      <header className="runtime-stream-panel__header">
        <div>
          <h2>AI 执行过程</h2>
          <span>Run #{runId}</span>
        </div>
        <div className="runtime-stream-panel__header-actions">
          <button className="ghost-button" type="button" onClick={() => setAutoScroll((value) => !value)}>
            {autoScroll ? <Pause size={14} /> : <Play size={14} />}
            {autoScroll ? "暂停滚动" : "继续滚动"}
          </button>
          <strong data-connected={connected}>{statusText}</strong>
        </div>
      </header>

      <div className="runtime-stream-panel__filters">
        {FILTERS.map((item) => (
          <button
            className={filter === item.value ? "runtime-filter runtime-filter--active" : "runtime-filter"}
            key={item.value}
            type="button"
            onClick={() => setFilter(item.value)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="runtime-stream-panel__body" aria-live="polite">
        {emptyText ? <div className="runtime-stream-panel__empty">{emptyText}</div> : null}
        {visibleGroups.map((group, index) => {
          const screenshot = group.screenshotPath ? fileUrl(group.screenshotPath) : null;
          const loading = index === visibleGroups.length - 1 && connected && group.type === "progress";
          return (
            <article className={`runtime-step-group runtime-step-group--${group.type}`} key={group.key}>
              <div className="runtime-step-group__icon">{messageIcon(group.latest, loading)}</div>
              <div className="runtime-step-group__content">
                <div className="runtime-step-group__title-row">
                  <time dateTime={group.latest.createdAt || undefined}>{formatTime(group.latest.createdAt)}</time>
                  <strong>{group.title}</strong>
                  {loading ? <span className="runtime-step-group__running">执行中</span> : null}
                </div>
                <p>{group.summary}</p>
                <div className="runtime-step-group__meta">
                  {group.stepLabel ? <span>{group.stepLabel}</span> : null}
                  <span>{group.messages.length} 条过程日志</span>
                </div>
                <div className="runtime-step-group__actions">
                  {screenshot ? (
                    <button
                      className="ghost-button"
                      type="button"
                      onClick={() => onPreviewScreenshot?.(screenshot, group.step?.step_name || group.title)}
                    >
                      <Image size={14} />
                      查看步骤截图
                    </button>
                  ) : (
                    <span className="runtime-step-group__no-shot">等待步骤截图</span>
                  )}
                  <details className="runtime-step-group__details">
                    <summary>
                      <Eye size={14} />
                      查看详情
                    </summary>
                    <div className="runtime-log-list">
                      {group.messages.map((message) => (
                        <div className="runtime-log-line" key={message.id}>
                          <div className="runtime-log-line__header">
                            <time dateTime={message.createdAt || undefined}>{formatTime(message.createdAt)}</time>
                            <strong>{readableRuntimeTitle(message)}</strong>
                            <span>{methodLabel(message.method)}</span>
                          </div>
                          <p>{readableRuntimeMessage(message)}</p>
                          {runtimeDetailView(message) ? (
                            <ul>
                              {runtimeDetailView(message)?.lines.map((line) => (
                                <li key={line}>{line}</li>
                              ))}
                            </ul>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </details>
                </div>
              </div>
            </article>
          );
        })}
        <div ref={bottomRef} />
      </div>
    </section>
  );
}

function appendMessage(current: RuntimeMessage[], next: RuntimeMessage): RuntimeMessage[] {
  const existingIndex = current.findIndex((message) => message.id === next.id);
  if (existingIndex >= 0) {
    const copy = [...current];
    copy[existingIndex] = next;
    return copy;
  }
  return [...current, next].sort((left, right) => left.id - right.id);
}

function dedupeMessages(messages: RuntimeMessage[]): RuntimeMessage[] {
  return messages.reduce<RuntimeMessage[]>(appendMessage, []);
}

function buildRuntimeGroups(messages: RuntimeMessage[], steps: TestStepRun[]): RuntimeStepGroup[] {
  const grouped = new Map<string, RuntimeMessage[]>();
  for (const message of messages) {
    const key = runtimeGroupKey(message);
    grouped.set(key, [...(grouped.get(key) || []), message]);
  }

  return Array.from(grouped.entries()).map(([key, groupMessages]) => {
    const sorted = [...groupMessages].sort((left, right) => left.id - right.id);
    const latest = sorted[sorted.length - 1];
    const step = findMessageStep(latest, steps) || findGroupStep(sorted, steps);
    const stepNumber = groupStepNumber(sorted, step);
    const title = runtimeGroupTitle(key, latest, step, stepNumber);
    return {
      key,
      title,
      summary: runtimeGroupSummary(sorted, latest),
      type: runtimeGroupType(sorted),
      latest,
      messages: sorted,
      step,
      stepLabel: stepNumber ? `步骤 S${String(stepNumber).padStart(3, "0")}` : null,
      screenshotPath: runtimeGroupScreenshot(sorted, step)
    };
  });
}

function runtimeGroupKey(message: RuntimeMessage): string {
  const stepNumber = metadataString(message, "step_number") || metadataString(message, "step_id");
  if (stepNumber) return `step-${stepNumber}`;
  const phase = message.phase || "";
  if (
    [
      "understanding",
      "planning",
      "sandbox_starting",
      "sandbox_ready",
      "open_system",
      "open_url",
      "browser",
      "page_ready"
    ].includes(phase)
  ) {
    return "stage-prepare";
  }
  if (["reporting", "completed", "failed"].includes(phase)) {
    return "stage-result";
  }
  return `event-${phase || message.id}`;
}

function runtimeGroupTitle(
  key: string,
  latest: RuntimeMessage,
  step: TestStepRun | null,
  stepNumber: string | null
): string {
  if (key === "stage-prepare") return "执行准备";
  if (key === "stage-result") return "报告与结果";
  if (stepNumber || step) {
    const name = step?.step_name || metadataString(latest, "step_name") || metadataString(latest, "target");
    return `步骤 ${stepNumber ? `S${String(stepNumber).padStart(3, "0")}` : ""}${name ? `：${name}` : ""}`;
  }
  return readableRuntimeTitle(latest);
}

function runtimeGroupSummary(messages: RuntimeMessage[], latest: RuntimeMessage): string {
  const finalStepMessage = [...messages].reverse().find((message) => message.phase === "step");
  if (finalStepMessage?.type === "success") {
    return "步骤已完成，截图和调试证据已保存。";
  }
  if (finalStepMessage?.type === "error") {
    return readableRuntimeMessage(finalStepMessage);
  }
  const useful = [...messages]
    .reverse()
    .find((message) => !["ability_resolve", "auth_guard"].includes(message.phase || ""));
  return readableRuntimeMessage(useful || latest);
}

function runtimeGroupType(messages: RuntimeMessage[]): RuntimeMessageType {
  if (messages.some((message) => message.type === "error")) return "error";
  if (messages.some((message) => message.type === "warning")) return "warning";
  const latest = messages[messages.length - 1];
  if (latest?.type === "progress") return "progress";
  if (messages.some((message) => message.type === "success")) return "success";
  return latest?.type || "text";
}

function runtimeGroupScreenshot(messages: RuntimeMessage[], step: TestStepRun | null): string | null {
  const messageWithScreenshot = [...messages]
    .reverse()
    .find((message) => metadataString(message, "screenshot_path") || metadataString(message, "screenshotUrl"));
  return (
    (messageWithScreenshot
      ? metadataString(messageWithScreenshot, "screenshot_path") || metadataString(messageWithScreenshot, "screenshotUrl")
      : null) ||
    step?.screenshot_path ||
    null
  );
}

function findGroupStep(messages: RuntimeMessage[], steps: TestStepRun[]): TestStepRun | null {
  for (const message of [...messages].reverse()) {
    const step = findMessageStep(message, steps);
    if (step) return step;
  }
  return null;
}

function groupStepNumber(messages: RuntimeMessage[], step: TestStepRun | null): string | null {
  const messageWithStep = messages.find((message) => metadataString(message, "step_number") || metadataString(message, "step_id"));
  return (
    (messageWithStep ? metadataString(messageWithStep, "step_number") || metadataString(messageWithStep, "step_id") : null) ||
    (step ? String(step.step_id || step.id) : null)
  );
}

function formatTime(value: string | null): string {
  if (!value) return "--:--:--";
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  }).format(new Date(value));
}

function findMessageStep(message: RuntimeMessage, steps: TestStepRun[]): TestStepRun | null {
  const stepNumber = message.metadata.step_number;
  const stepId = message.metadata.step_id;
  const key = stepNumber ?? stepId;
  if (key === undefined || key === null) return null;
  const textKey = String(key);
  return (
    steps.find((step) => String(step.step_id || "") === textKey) ||
    steps.find((step) => String(step.id) === textKey) ||
    steps[Number(textKey) - 1] ||
    null
  );
}

function messageIcon(message: RuntimeMessage, loading: boolean) {
  if (loading) return <Loader2 className="runtime-stream-message__spinner" size={16} />;
  if (message.type === "success") return <CheckCircle2 size={16} />;
  if (message.type === "warning") return <AlertTriangle size={16} />;
  if (message.type === "error") return <XCircle size={16} />;
  if (runtimeFilterOf(message) === "llm") return <Bot size={16} />;
  return <Circle size={12} />;
}
