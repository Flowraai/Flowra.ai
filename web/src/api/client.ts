// Cliente HTTP fino: injeta o token JWT, trata 401 e desserializa JSON.

const BASE = import.meta.env.VITE_API_BASE_URL ?? "";
const API = `${BASE}/api/v1`;
const TOKEN_KEY = "flowra-access-token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
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

type Options = {
  method?: string;
  body?: unknown;
  auth?: boolean;
};

export async function api<T>(path: string, opts: Options = {}): Promise<T> {
  const { method = "GET", body, auth = true } = opts;
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = getToken();
  if (auth && token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401) {
    setToken(null);
    throw new ApiError(401, "Sessão expirada. Faça login novamente.");
  }
  if (res.status === 402) {
    // Assinatura necessária — avisa a app para levar à tela de planos.
    try {
      window.dispatchEvent(new CustomEvent("flowra:payment-required"));
    } catch {
      /* ignore (SSR/testes) */
    }
    throw new ApiError(402, "Assinatura necessária para acessar o painel.");
  }
  if (!res.ok) {
    let detail = `Erro ${res.status}`;
    try {
      const data = await res.json();
      if (typeof data?.detail === "string") detail = data.detail;
    } catch {
      /* keep default */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Baixa um anexo autenticado e devolve um object URL (o <img>/<audio> não
 * consegue enviar o header Authorization sozinho). Lembre de revogar depois. */
export async function attachmentObjectUrl(id: string): Promise<string> {
  const token = getToken();
  const res = await fetch(`${API}/attachments/${id}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new ApiError(res.status, "Falha ao carregar o anexo.");
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}
