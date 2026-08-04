// Tipos espelhando os schemas do backend consumidos pelo app do paciente.

export type QuestionType = "scale" | "integer" | "choice" | "boolean" | "free_text";
export type IntakeStatus = "pending" | "taken" | "later" | "missed";
export type MessageSender = "patient" | "doctor" | "ai";

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
  } | null;
}

export interface Protocol {
  id: string;
  name: string;
  specialty: string;
  version: string;
  description: string | null;
  is_active: boolean;
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
  attachments: unknown[];
  read_at: string | null;
  created_at: string;
}

export type AppointmentKind = "consultation" | "return";
export type AppointmentStatus = "scheduled" | "confirmed" | "cancelled" | "completed";

export interface Appointment {
  id: string;
  scheduled_at: string;
  kind: AppointmentKind;
  status: AppointmentStatus;
  location: string | null;
  notes: string | null;
}

export type ExamStatus = "requested" | "available";

export interface Exam {
  id: string;
  name: string;
  status: ExamStatus;
  result_url: string | null;
  notes: string | null;
  available_at: string | null;
  created_at: string;
}

export interface PrescriptionItem {
  name: string;
  dose: string;
  instructions?: string | null;
}

export interface Prescription {
  id: string;
  items: PrescriptionItem[];
  notes: string | null;
  status: string;
  pdf_url: string | null;
  issued_at: string | null;
  created_at: string;
}
