import { api } from "./client";
import type {
  ChatMessage,
  CheckInResult,
  IntakeStatus,
  MedicationDose,
  PatientToday,
  Protocol,
} from "./types";

export const patientApi = {
  today: (token?: string) => api<PatientToday>("/patient/today", { token }),
  protocol: () => api<Protocol>("/patient/protocol"),
  submitCheckin: (structured: Record<string, unknown>, freeText: string | null) =>
    api<CheckInResult>("/patient/checkins", {
      method: "POST",
      body: { structured_responses: structured, free_text: freeText, audio_url: null },
    }),
  medicationsToday: () => api<MedicationDose[]>("/patient/medications/today"),
  respondDose: (intakeId: string, status: IntakeStatus) =>
    api<unknown>(`/patient/medications/intakes/${intakeId}/respond`, {
      method: "POST",
      body: { status },
    }),
  messages: () => api<ChatMessage[]>("/patient/messages"),
  sendMessage: (bodyText: string) =>
    api<ChatMessage>("/patient/messages", { method: "POST", body: { body: bodyText, attachments: [] } }),
  registerDevice: (token: string, platform: "ios" | "android" | "web") =>
    api<unknown>("/patient/devices", { method: "POST", body: { token, platform } }),
};
