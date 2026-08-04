// Cliente HTTP do app do paciente: injeta o X-Patient-Token e trata erros.

import Constants from "expo-constants";
import { currentToken } from "../storage";

const BASE: string =
  (Constants.expoConfig?.extra as { apiBaseUrl?: string } | undefined)?.apiBaseUrl ??
  "http://localhost:8000";
const API = `${BASE}/api/v1`;

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

type Options = { method?: string; body?: unknown; token?: string };

export async function api<T>(path: string, opts: Options = {}): Promise<T> {
  const { method = "GET", body, token } = opts;
  const headers: Record<string, string> = {};
  const t = token ?? currentToken();
  if (t) headers["X-Patient-Token"] = t;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const res = await fetch(`${API}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let detail = `Erro ${res.status}`;
    try {
      const data = (await res.json()) as { detail?: unknown };
      if (typeof data?.detail === "string") detail = data.detail;
    } catch {
      /* keep default */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
