import { api, upload } from "./client";
import type {
  Appointment,
  AttachmentRef,
  ChatMessage,
  CheckInResult,
  Exam,
  IntakeStatus,
  MedicationDose,
  PatientToday,
  Prescription,
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
  sendMessage: (bodyText: string, attachments: unknown[] = []) =>
    api<ChatMessage>("/patient/messages", { method: "POST", body: { body: bodyText, attachments } }),
  uploadAttachment: (file: { uri: string; name: string; type: string }) => {
    const form = new FormData();
    // React Native aceita { uri, name, type } como parte de arquivo do FormData.
    form.append("file", file as unknown as Blob);
    return upload<AttachmentRef>("/patient/attachments", form);
  },
  aiHistory: () => api<ChatMessage[]>("/patient/ai-chat"),
  aiSend: (bodyText: string) =>
    api<ChatMessage>("/patient/ai-chat", { method: "POST", body: { body: bodyText, attachments: [] } }),
  registerDevice: (token: string, platform: "ios" | "android" | "web") =>
    api<unknown>("/patient/devices", { method: "POST", body: { token, platform } }),
  appointments: () => api<Appointment[]>("/patient/appointments"),
  confirmAppointment: (id: string) =>
    api<Appointment>(`/patient/appointments/${id}/confirm`, { method: "POST" }),
  exams: () => api<Exam[]>("/patient/exams"),
  prescriptions: () => api<Prescription[]>("/patient/prescriptions"),
};
