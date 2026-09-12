// Camada de API do paciente: autentica por X-Patient-Token (token opaco do link
// de convite), separada do login do médico. Guarda o token só deste navegador.

const BASE = import.meta.env.VITE_API_BASE_URL ?? "";
const API = `${BASE}/api/v1`;
const PKEY = "flowra-patient-token";

export function getPatientToken(): string | null {
  try {
    return localStorage.getItem(PKEY);
  } catch {
    return null;
  }
}

export function setPatientToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(PKEY, token);
    else localStorage.removeItem(PKEY);
  } catch {
    /* ignore */
  }
}

export class PatientApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function pApi<T>(
  path: string,
  opts: { method?: string; body?: unknown; silent401?: boolean } = {},
): Promise<T> {
  const { method = "GET", body, silent401 = false } = opts;
  const token = getPatientToken();
  const headers: Record<string, string> = {};
  if (token) headers["X-Patient-Token"] = token;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const res = await fetch(`${API}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  // Nas telas de login/recuperação, o 401 é "credencial errada" — repassa a
  // mensagem do servidor e NÃO apaga token (o usuário está justamente entrando).
  if (res.status === 401 && silent401) {
    let detail = "CPF ou senha incorretos.";
    try {
      const data = await res.json();
      if (typeof data?.detail === "string") detail = data.detail;
    } catch {
      /* keep default */
    }
    throw new PatientApiError(401, detail);
  }
  if (res.status === 401) {
    // Token inválido/expirado — limpa para cair na tela de acesso.
    setPatientToken(null);
    throw new PatientApiError(401, "Seu acesso expirou. Peça um novo link ao seu médico.");
  }
  if (!res.ok) {
    let detail = `Erro ${res.status}`;
    try {
      const data = await res.json();
      if (typeof data?.detail === "string") detail = data.detail;
    } catch {
      /* keep default */
    }
    throw new PatientApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ---- Tipos (espelham os schemas do backend consumidos pelo paciente) ----
export type QuestionType = "scale" | "integer" | "choice" | "boolean" | "free_text";
export type IntakeStatus = "pending" | "taken" | "later" | "missed";
export type MessageSender = "patient" | "doctor" | "ai";
export type AppointmentKind = "consultation" | "return";
export type AppointmentStatus = "scheduled" | "confirmed" | "cancelled" | "completed";

export interface PatientToday {
  patient_name: string;
  checked_in_today: boolean;
  last_checkin_at: string | null;
}

export interface Question {
  id: string;
  code: string;
  category: string;
  text: string;
  type: QuestionType;
  position: number;
  required: boolean;
  options: {
    min?: number;
    max?: number;
    unit?: string;
    direction?: string;
    choices?: string[];
    scale_style?: string;
    emojis?: { emoji: string; value: number }[];
  } | null;
}

export interface Protocol {
  id: string;
  name: string;
  questions: Question[];
}

export interface CheckInResult {
  id: string;
  received_at: string;
  message: string;
}

export interface MedicationDose {
  intake_id: string;
  plan_id: string;
  name: string;
  dose: string;
  scheduled_for: string;
  status: IntakeStatus;
}

export interface ChatMessage {
  id: string;
  sender: MessageSender;
  body: string;
  read_at: string | null;
  created_at: string;
}

export interface Appointment {
  id: string;
  scheduled_at: string;
  kind: AppointmentKind;
  status: AppointmentStatus;
  location: string | null;
  notes: string | null;
  reschedule_requested_at: string | null;
  reschedule_note: string | null;
}

export interface CalendarDay {
  date: string; // YYYY-MM-DD
  checked_in: boolean;
  can_fill: boolean;
  is_today: boolean;
  mood: number | null;
}

export type Answers = Record<string, string | number>;

export interface ScaleDef {
  code: string;
  name: string;
  description: string;
  period: string;
  items: string[];
  options: string[];
  bands: { min: number; max: number; label: string; level: string }[];
  max_score: number;
  flag_item: number | null;
}
export interface ScalePending {
  id: string;
  scale: ScaleDef;
}
export interface ScaleSubmitResult {
  message: string;
  safety: string | null;
}

export interface WearableDay {
  day: string; // YYYY-MM-DD
  sleep_minutes: number | null;
  resting_hr: number | null;
  hrv_ms: number | null;
  steps: number | null;
}

export interface WearableSummary {
  connected: boolean;
  provider: string | null;
  provider_name: string | null;
  requires_oauth: boolean;
  last_sync_at: string | null;
  latest: WearableDay | null;
  avg_sleep_minutes: number | null;
  avg_resting_hr: number | null;
  avg_hrv_ms: number | null;
  avg_steps: number | null;
  days: WearableDay[];
}

export interface WearableConnectResult {
  connected: boolean;
  connect_url: string | null;
}

export interface PatientAccount {
  name: string;
  activated: boolean;
  has_contact: boolean;
}

export interface PatientSession {
  access_token: string;
}

export const patientAuth = {
  account: () => pApi<PatientAccount>("/patient/account"),
  activate: (cpf: string, password: string) =>
    pApi<PatientSession>("/patient/activate", { method: "POST", body: { cpf, password }, silent401: true }),
  login: (cpf: string, password: string) =>
    pApi<PatientSession>("/patient/login", { method: "POST", body: { cpf, password }, silent401: true }),
  forgot: (cpf: string) =>
    pApi<{ message: string }>("/patient/forgot-password", { method: "POST", body: { cpf }, silent401: true }),
  reset: (cpf: string, code: string, newPassword: string) =>
    pApi<PatientSession>("/patient/reset-password", {
      method: "POST",
      body: { cpf, code, new_password: newPassword },
      silent401: true,
    }),
};

export const patientApi = {
  today: () => pApi<PatientToday>("/patient/today"),
  protocol: () => pApi<Protocol>("/patient/protocol"),
  submitCheckin: (structured: Answers, freeText: string | null, forDate?: string) =>
    pApi<CheckInResult>("/patient/checkins", {
      method: "POST",
      body: { structured_responses: structured, free_text: freeText, for_date: forDate ?? null },
    }),
  calendar: (days = 35) => pApi<CalendarDay[]>(`/patient/checkins/calendar?days=${days}`),
  medicationsToday: () => pApi<MedicationDose[]>("/patient/medications/today"),
  respondIntake: (intakeId: string, status: IntakeStatus) =>
    pApi<{ status: IntakeStatus }>(`/patient/medications/intakes/${intakeId}/respond`, {
      method: "POST",
      body: { status },
    }),
  appointments: () => pApi<Appointment[]>("/patient/appointments"),
  confirmAppointment: (id: string) =>
    pApi<Appointment>(`/patient/appointments/${id}/confirm`, { method: "POST" }),
  requestReschedule: (id: string, note?: string) =>
    pApi<Appointment>(`/patient/appointments/${id}/reschedule`, {
      method: "POST",
      body: { note: note ?? null },
    }),
  messages: () => pApi<ChatMessage[]>("/patient/messages"),
  sendMessage: (body: string) =>
    pApi<ChatMessage>("/patient/messages", { method: "POST", body: { body, attachments: [] } }),
  aiHistory: () => pApi<ChatMessage[]>("/patient/ai-chat"),
  sendAi: (body: string) =>
    pApi<ChatMessage>("/patient/ai-chat", { method: "POST", body: { body, attachments: [] } }),
  pendingScales: () => pApi<ScalePending[]>("/patient/scales"),
  submitScale: (entryId: string, answers: number[]) =>
    pApi<ScaleSubmitResult>(`/patient/scales/${entryId}`, { method: "POST", body: { answers } }),
  wearable: () => pApi<WearableSummary>("/patient/wearable"),
  wearableConnect: () =>
    pApi<WearableConnectResult>("/patient/wearable/connect", { method: "POST" }),
  wearableSync: () => pApi<WearableSummary>("/patient/wearable/sync", { method: "POST" }),
  wearableDisconnect: () =>
    pApi<void>("/patient/wearable/disconnect", { method: "POST" }),
};
