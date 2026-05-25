export type RuntimeMessageType = "text" | "progress" | "warning" | "error" | "success";

export interface RuntimeMessage {
  id: number;
  runId: number | null;
  type: RuntimeMessageType;
  phase: string | null;
  content: string | null;
  method: string | null;
  metadata: Record<string, unknown>;
  createdAt: string | null;
}

export interface RuntimeMessageWire {
  id: number;
  runId?: number | null;
  run_id?: number | null;
  type: RuntimeMessageType;
  phase?: string | null;
  content?: string | null;
  method?: string | null;
  metadata?: Record<string, unknown> | null;
  metadata_json?: Record<string, unknown> | null;
  createdAt?: string | null;
  created_at?: string | null;
}

export const runtimeMessageTypes: RuntimeMessageType[] = [
  "text",
  "progress",
  "warning",
  "error",
  "success"
];

export function normalizeRuntimeMessage(message: RuntimeMessageWire): RuntimeMessage {
  return {
    id: message.id,
    runId: message.runId ?? message.run_id ?? null,
    type: message.type,
    phase: message.phase ?? null,
    content: message.content ?? null,
    method: message.method ?? null,
    metadata: message.metadata ?? message.metadata_json ?? {},
    createdAt: message.createdAt ?? message.created_at ?? null
  };
}
