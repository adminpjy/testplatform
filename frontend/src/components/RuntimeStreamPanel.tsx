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
import type { RuntimeMessage } from "../types/runtime";
import {
  methodLabel,
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
  const emptyText = useMemo(() => {
    return visibleMessages.length === 0 ? "暂无运行消息" : null;
  }, [visibleMessages.length]);

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
        {visibleMessages.map((message, index) => {
          const step = findMessageStep(message, steps);
          const screenshot = step?.screenshot_path ? fileUrl(step.screenshot_path) : null;
          const loading = index === visibleMessages.length - 1 && connected && message.type === "progress";
          const detail = runtimeDetailView(message);
          return (
            <article className={`runtime-stream-message runtime-stream-message--${message.type}`} key={message.id}>
              <div className="runtime-stream-message__icon">{messageIcon(message, loading)}</div>
              <div className="runtime-stream-message__content">
                <div className="runtime-stream-message__title-row">
                  <time dateTime={message.createdAt || undefined}>{formatTime(message.createdAt)}</time>
                  <strong>{readableRuntimeTitle(message)}</strong>
                </div>
                <p>{readableRuntimeMessage(message)}</p>
                <div className="runtime-stream-message__meta">
                  <span>方法：{methodLabel(message.method)}</span>
                  {step ? <span>步骤：{step.step_id || step.id}</span> : null}
                </div>
                <div className="runtime-stream-message__actions">
                  {screenshot ? (
                    <button
                      className="ghost-button"
                      type="button"
                      onClick={() => onPreviewScreenshot?.(screenshot, step?.step_name || "步骤截图")}
                    >
                      <Image size={14} />
                      查看截图
                    </button>
                  ) : (
                    <span className="runtime-stream-message__no-shot">暂无截图</span>
                  )}
                  {detail ? (
                    <details className="runtime-stream-message__details">
                      <summary>
                        <Eye size={14} />
                        查看详情
                      </summary>
                      <ul className="runtime-detail-list">
                        {detail.lines.map((line) => (
                          <li key={line}>{line}</li>
                        ))}
                      </ul>
                    </details>
                  ) : null}
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
