import type { AuthResponse } from "./types";

const API_URL = (process.env.EXPO_PUBLIC_API_URL ?? "http://127.0.0.1:8787/api/v1").replace(
  /\/$/,
  "",
);

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

function errorMessage(body: unknown): string {
  if (!body || typeof body !== "object" || !("detail" in body)) return "Something went wrong";
  const detail = body.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (!item || typeof item !== "object") return null;
        if ("msg" in item && typeof item.msg === "string") return item.msg.replace(/^Value error,\s*/i, "");
        return null;
      })
      .filter((message): message is string => Boolean(message));
    if (messages.length) return messages.join("\n");
  }
  return "Please check the information you entered.";
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.status === 204) return undefined as T;
  const contentType = response.headers.get("content-type") ?? "";
  const body = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    throw new ApiError(errorMessage(body), response.status);
  }
  return body as T;
}

export async function publicApi<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  return parseResponse<T>(
    await fetch(`${API_URL}${path}`, {
      ...options,
      headers,
    }),
  );
}

export type AuthenticatedApi = <T>(path: string, options?: RequestInit) => Promise<T>;

export function makeAuthenticatedApi(
  getAccessToken: () => string | null,
  refresh: () => Promise<AuthResponse | null>,
): AuthenticatedApi {
  return async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const send = async (token: string | null) => {
      const headers = new Headers(options.headers);
      if (token) headers.set("Authorization", `Bearer ${token}`);
      if (!(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
      return fetch(`${API_URL}${path}`, { ...options, headers });
    };

    let response = await send(getAccessToken());
    if (response.status === 401) {
      const session = await refresh();
      if (session) response = await send(session.access_token);
    }
    return parseResponse<T>(response);
  };
}

export function submissionImageUrl(id: string): string {
  return `${API_URL}/submissions/${id}/image`;
}

export function rewardImageUrl(id: string): string {
  return `${API_URL}/rewards/${id}/image`;
}

export function realtimeUrl(ticket: string): string {
  const websocketBase = API_URL.replace(/^http:/, "ws:").replace(/^https:/, "wss:");
  return `${websocketBase}/realtime?ticket=${encodeURIComponent(ticket)}`;
}
