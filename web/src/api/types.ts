// Tipos espelhando os schemas do backend (app/schemas/*).

export type RiskLevel = "green" | "yellow" | "orange" | "red";
export type AlertUrgency = "immediate" | "routine";
export type AlertStatus = "pending" | "notified" | "acknowledged" | "resolved";

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface DoctorProfile {
  id: string;
  tenant_id: string;
  name: string;
  specialty: string;
  clinic: string | null;
  council_id: string | null;
  notification_email: string | null;
  notification_phone: string | null;
  email: string;
  tenant_name: string | null;
}

export interface PatientPanelItem {
  id: string;
  name: string;
  current_risk: RiskLevel;
  last_checkin_at: string | null;
  open_alerts: number;
  days_since_checkin: number | null;
  inactive: boolean;
}

export interface Patient {
  id: string;
  tenant_id: string;
  name: string;
  contact: string | null;
  birth_date: string | null;
  doctor_id: string;
  active_protocol_id: string | null;
  current_risk: RiskLevel;
  last_checkin_at: string | null;
  consent_given_at: string | null;
  is_active: boolean;
  created_at: string;
}

export interface CheckIn {
  id: string;
  patient_id: string;
  protocol_id: string | null;
  structured_responses: Record<string, unknown>;
  free_text: string | null;
  audio_url: string | null;
  audio_transcript: string | null;
  risk_level: RiskLevel;
  risk_reasons: string[];
  category_risks: Record<string, string>;
  created_at: string;
}

export interface Alert {
  id: string;
  patient_id: string;
  checkin_id: string | null;
  level: RiskLevel;
  urgency: AlertUrgency;
  reason: string;
  reasons_detail: string[];
  status: AlertStatus;
  created_at: string;
}

export interface PatientCreated extends Patient {
  access_token: string;
}

export interface PatientCreateInput {
  name: string;
  contact?: string | null;
  consent_given: boolean;
  consent_version?: string | null;
}

export interface PatientSummary {
  summary: string;
  generated_by: "llm" | "deterministic";
  context: Record<string, unknown>;
}

export interface MedicationPlan {
  id: string;
  patient_id: string;
  name: string;
  dose: string;
  times: string[];
  start_date: string;
  end_date: string | null;
  notes: string | null;
  active: boolean;
}

export interface MedicationPlanInput {
  name: string;
  dose: string;
  times: string[];
  start_date: string;
  end_date?: string | null;
  notes?: string | null;
}

export interface MedicationAdherence {
  total: number;
  taken: number;
  later: number;
  missed: number;
  pending: number;
  adherence_rate: number;
}

export type AppointmentKind = "consultation" | "return";
export type AppointmentStatus = "scheduled" | "confirmed" | "cancelled" | "completed";

export interface Appointment {
  id: string;
  patient_id: string;
  doctor_id: string;
  scheduled_at: string;
  kind: AppointmentKind;
  status: AppointmentStatus;
  location: string | null;
  notes: string | null;
}

export interface AppointmentInput {
  scheduled_at: string;
  kind: AppointmentKind;
  location?: string | null;
  notes?: string | null;
}

export type MessageSender = "patient" | "doctor" | "ai";

export interface ChatMessage {
  id: string;
  sender: MessageSender;
  body: string;
  attachments: unknown[];
  read_at: string | null;
  created_at: string;
}
