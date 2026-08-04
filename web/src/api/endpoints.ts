// Chamadas à API por domínio.

import { api } from "./client";
import type {
  Alert,
  AlertStatus,
  Appointment,
  AppointmentInput,
  AppointmentStatus,
  ChatMessage,
  CheckIn,
  DoctorProfile,
  Exam,
  ExamInput,
  ExamStatus,
  MedicationAdherence,
  MedicationPlan,
  MedicationPlanInput,
  Patient,
  PatientCreated,
  PatientCreateInput,
  PatientPanelItem,
  PatientSummary,
  Prescription,
  PrescriptionCreateInput,
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
  medications: (id: string) => api<MedicationPlan[]>(`/patients/${id}/medications`),
  createMedication: (id: string, input: MedicationPlanInput) =>
    api<MedicationPlan>(`/patients/${id}/medications`, { method: "POST", body: input }),
  adherence: (id: string) => api<MedicationAdherence>(`/patients/${id}/medications/adherence`),
  appointments: (id: string) => api<Appointment[]>(`/patients/${id}/appointments`),
  createAppointment: (id: string, input: AppointmentInput) =>
    api<Appointment>(`/patients/${id}/appointments`, { method: "POST", body: input }),
  exams: (id: string) => api<Exam[]>(`/patients/${id}/exams`),
  createExam: (id: string, input: ExamInput) =>
    api<Exam>(`/patients/${id}/exams`, { method: "POST", body: input }),
  prescriptions: (id: string) => api<Prescription[]>(`/patients/${id}/prescriptions`),
  createPrescription: (id: string, input: PrescriptionCreateInput) =>
    api<Prescription>(`/patients/${id}/prescriptions`, { method: "POST", body: input }),
};

export const medications = {
  update: (planId: string, patch: { active?: boolean }) =>
    api<MedicationPlan>(`/medications/${planId}`, { method: "PATCH", body: patch }),
};

export const appointments = {
  update: (id: string, patch: { status?: AppointmentStatus }) =>
    api<Appointment>(`/appointments/${id}`, { method: "PATCH", body: patch }),
};

export const exams = {
  update: (id: string, patch: { status?: ExamStatus; result_url?: string | null }) =>
    api<Exam>(`/exams/${id}`, { method: "PATCH", body: patch }),
};

export const prescriptions = {
  issue: (id: string) => api<Prescription>(`/prescriptions/${id}/issue`, { method: "POST" }),
  cancel: (id: string) => api<Prescription>(`/prescriptions/${id}/cancel`, { method: "POST" }),
};

export const alerts = {
  list: (statusFilter?: string) =>
    api<Alert[]>(`/alerts${statusFilter ? `?status_filter=${statusFilter}` : ""}`),
  updateStatus: (id: string, status: AlertStatus) =>
    api<Alert>(`/alerts/${id}`, { method: "PATCH", body: { status } }),
};
