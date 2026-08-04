// Chamadas à API por domínio.

import { api } from "./client";
import type {
  Alert,
  AlertStatus,
  ChatMessage,
  CheckIn,
  DoctorProfile,
  Patient,
  PatientCreated,
  PatientCreateInput,
  PatientPanelItem,
  PatientSummary,
  TokenPair,
} from "./types";

export const auth = {
  login: (email: string, password: string) =>
    api<TokenPair>("/auth/login", { method: "POST", auth: false, body: { email, password } }),
  me: () => api<DoctorProfile>("/auth/me"),
};

export const patients = {
  list: () => api<PatientPanelItem[]>("/patients"),
  create: (input: PatientCreateInput) =>
    api<PatientCreated>("/patients", { method: "POST", body: input }),
  get: (id: string) => api<Patient>(`/patients/${id}`),
  checkins: (id: string, limit = 14) => api<CheckIn[]>(`/patients/${id}/checkins?limit=${limit}`),
  summary: (id: string) => api<PatientSummary>(`/patients/${id}/summary`),
  messages: (id: string) => api<ChatMessage[]>(`/patients/${id}/messages`),
  sendMessage: (id: string, bodyText: string) =>
    api<ChatMessage>(`/patients/${id}/messages`, {
      method: "POST",
      body: { body: bodyText, attachments: [] },
    }),
};

export const alerts = {
  list: (statusFilter?: string) =>
    api<Alert[]>(`/alerts${statusFilter ? `?status_filter=${statusFilter}` : ""}`),
  updateStatus: (id: string, status: AlertStatus) =>
    api<Alert>(`/alerts/${id}`, { method: "PATCH", body: { status } }),
};
