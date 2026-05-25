import { useEffect, useMemo, useRef, useState } from "react";

import { openRuntimeStream } from "../api/runtimeStream";
import type { RuntimeMessage } from "../types/runtime";
import "../styles/runtime-stream.css";

export interface RuntimeStreamPanelProps {
  runId: number;
  baseUrl?: string;
  className?: string;
  initialMessages?: RuntimeMessage[];
}

const typeLabels: Record<RuntimeMessage["type"], string> = {
  text: "消息",
  progress: "进度",
  warning: "警告",
  error: "错误",
  success: "成功"
};

export function RuntimeStreamPanel({
  runId,
  baseUrl,
  className,
  initialMessages = []
}: RuntimeStreamPanelProps) {
  const [messages, setMessages] = useState<RuntimeMessage[]>(() => dedupeMessages(initialMessages));
  const [connected, setConnected] = useState(false);
  const [finished, setFinished] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setMessages(dedupeMessages(initialMessages));
    setFinished(false);
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
    bottomRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [messages]);

  const statusText = finished ? "运行已结束" : connected ? "实时连接中" : "等待运行消息";
  const emptyText = useMemo(() => {
    return messages.length === 0 ? "暂无运行消息" : null;
  }, [messages.length]);

  return (
    <section className={["runtime-stream-panel", className].filter(Boolean).join(" ")}>
      <header className="runtime-stream-panel__header">
        <div>
          <h2>运行过程</h2>
          <span>Run #{runId}</span>
        </div>
        <strong data-connected={connected}>{statusText}</strong>
      </header>

      <div className="runtime-stream-panel__body" aria-live="polite">
        {emptyText ? <div className="runtime-stream-panel__empty">{emptyText}</div> : null}
        {messages.map((message) => (
          <article
            className={`runtime-stream-message runtime-stream-message--${message.type}`}
            key={message.id}
          >
            <div className="runtime-stream-message__main">
              <span>{typeLabels[message.type]}</span>
              <p>{message.content || "运行消息"}</p>
            </div>
            <div className="runtime-stream-message__meta">
              {message.phase ? <span>{message.phase}</span> : null}
              {message.method ? <span>{message.method}</span> : null}
              {message.createdAt ? <time dateTime={message.createdAt}>{formatTime(message.createdAt)}</time> : null}
            </div>
            {Object.keys(message.metadata).length > 0 ? (
              <details className="runtime-stream-message__details">
                <summary>metadata</summary>
                <pre>{JSON.stringify(message.metadata, null, 2)}</pre>
              </details>
            ) : null}
          </article>
        ))}
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

function formatTime(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  }).format(new Date(value));
}
