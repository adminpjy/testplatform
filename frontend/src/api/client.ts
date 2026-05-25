const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || "";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(formatApiError(status, detail));
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export async function getJson<T>(path: string): Promise<T> {
  return requestJson<T>(path);
}

export async function postJson<T>(path: string, body: unknown): Promise<T> {
  return requestJson<T>(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body)
  });
}

export function apiUrl(path: string): string {
  if (/^https?:\/\//.test(path)) {
    return path;
  }
  return `${API_BASE_URL}${path}`;
}

export function fileUrl(filePath: string): string {
  const encoded = filePath.split(/[\\/]/).map(encodeURIComponent).join("/");
  return apiUrl(`/files/${encoded}`);
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.headers || {})
    }
  });

  if (!response.ok) {
    throw new ApiError(response.status, await readErrorBody(response));
  }

  return (await response.json()) as T;
}

async function readErrorBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return response.statusText;
  }
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

function formatApiError(status: number, detail: unknown): string {
  if (typeof detail === "string") {
    return `${status}: ${detail}`;
  }
  if (detail && typeof detail === "object" && "detail" in detail) {
    return `${status}: ${JSON.stringify((detail as { detail: unknown }).detail)}`;
  }
  return `${status}: ${JSON.stringify(detail)}`;
}
