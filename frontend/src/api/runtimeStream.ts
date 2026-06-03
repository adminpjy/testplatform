import {
  normalizeRuntimeMessage,
  runtimeMessageTypes,
  type RuntimeMessage,
  type RuntimeMessageWire
} from "../types/runtime";
import { getAuthToken } from "./client";

export interface RuntimeStreamOptions {
  baseUrl?: string;
  afterId?: number;
  closeOnTerminal?: boolean;
  onMessage: (message: RuntimeMessage) => void;
  onError?: (error: Event) => void;
}

export function openRuntimeStream(runId: number, options: RuntimeStreamOptions): EventSource {
  const source = new EventSource(runtimeStreamUrl(runId, options.baseUrl, options.afterId));
  const handleMessage = (event: MessageEvent<string>) => {
    const message = normalizeRuntimeMessage(JSON.parse(event.data) as RuntimeMessageWire);
    options.onMessage(message);
    if (options.closeOnTerminal !== false && (message.phase === "completed" || message.phase === "failed")) {
      source.close();
    }
  };

  runtimeMessageTypes.forEach((type) => {
    source.addEventListener(type, handleMessage as EventListener);
  });

  source.onerror = (event) => {
    options.onError?.(event);
  };

  return source;
}

export function runtimeStreamUrl(runId: number, baseUrl = "", afterId?: number): string {
  const url = new URL(`/api/test-runs/${runId}/stream`, baseUrl || window.location.origin);
  if (afterId !== undefined && afterId > 0) {
    url.searchParams.set("after_id", String(afterId));
  }
  const token = getAuthToken();
  if (token) {
    url.searchParams.set("token", token);
  }
  return url.toString();
}
