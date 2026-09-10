// Camada de API do app do paciente (mesma API do painel/PWA).
// Autentica por X-Patient-Token (token de sessão emitido no login por CPF+senha),
// guardado com segurança no aparelho (SecureStore).

import Constants from "expo-constants";
import * as SecureStore from "expo-secure-store";

const BASE = (Constants.expoConfig?.extra as { apiBaseUrl?: string })?.apiBaseUrl
  ?? "https://care.flowraai.com.br";
const API = `${BASE}/api/v1`;
const TOKEN_KEY = "flowra-patient-token";

let cachedToken: string | null = null;

export async function getToken(): Promise<string | null> {
  if (cachedToken) return cachedToken;
  try {
    cachedToken = await SecureStore.getItemAsync(TOKEN_KEY);
  } catch {
    cachedToken = null;
  }
  return cachedToken;
}

export async function setToken(token: string | null): Promise<void> {
  cachedToken = token;
  try {
    if (token) await SecureStore.setItemAsync(TOKEN_KEY, token);
    else await SecureStore.deleteItemAsync(TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function api<T>(
  path: string,
  opts: { method?: string; body?: unknown; auth?: boolean; silent401?: boolean } = {},
): Promise<T> {
  const { method = "GET", body, auth = true, silent401 = false } = opts;
  const headers: Record<string, string> = {};
  if (auth) {
    const token = await getToken();
    if (token) headers["X-Patient-Token"] = token;
  }
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const res = await fetch(`${API}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401 && !silent401) {
    await setToken(null);
    throw new ApiError(401, "Sua sessão expirou. Entre novamente.");
  }
  if (!res.ok) {
    let detail = `Erro ${res.status}`;
    try {
      const data = await res.json();
      if (typeof data?.detail === "string") detail = data.detail;
    } catch {
      /* keep */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ---- Tipos ----
export interface PatientToday {
  patient_name: string;
  checked_in_today: boolean;
  last_checkin_at: string | null;
}
export interface Session {
  access_token: string;
}
export interface WearableDay {
  day: string;
  sleep_minutes: number | null;
  resting_hr: number | null;
  hrv_ms: number | null;
  steps: number | null;
}
export interface WearableSummary {
  connected: boolean;
  provider_name: string | null;
  last_sync_at: string | null;
  latest: WearableDay | null;
  avg_sleep_minutes: number | null;
  avg_resting_hr: number | null;
  avg_hrv_ms: number | null;
  avg_steps: number | null;
}

// ---- Auth do paciente (CPF + senha) ----
export const auth = {
  login: (cpf: string, password: string) =>
    api<Session>("/patient/login", { method: "POST", auth: false, silent401: true, body: { cpf, password } }),
  forgot: (cpf: string) =>
    api<{ message: string }>("/patient/forgot-password", { method: "POST", auth: false, silent401: true, body: { cpf } }),
  reset: (cpf: string, code: string, newPassword: string) =>
    api<Session>("/patient/reset-password", {
      method: "POST", auth: false, silent401: true,
      body: { cpf, code, new_password: newPassword },
    }),
};

// ---- App do paciente ----
export const patient = {
  today: () => api<PatientToday>("/patient/today"),
  wearable: () => api<WearableSummary>("/patient/wearable"),
  pushHealth: (source: string, days: WearableDay[]) =>
    api<WearableSummary>("/patient/wearable/samples", { method: "POST", body: { source, days } }),
};
