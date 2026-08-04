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

/** Upload multipart (não define Content-Type: o fetch cuida do boundary). */
export async function upload<T>(path: string, form: FormData): Promise<T> {
  const headers: Record<string, string> = {};
  const t = currentToken();
  if (t) headers["X-Patient-Token"] = t;
  const res = await fetch(`${API}${path}`, { method: "POST", headers, body: form });
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
  return (await res.json()) as T;
}

/** URL absoluta de um anexo (para <Image>/player, com o header de auth). */
export function attachmentUrl(id: string): string {
  return `${API}/attachments/${id}`;
}

export function authHeader(): Record<string, string> {
  const t = currentToken();
  return t ? { "X-Patient-Token": t } : {};
}
