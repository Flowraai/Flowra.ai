import { useState, type FormEvent } from "react";
import { patients } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { AppointmentKind } from "../api/types";
import "./NewPatientModal.css";

function defaultWhen(): string {
  // amanhã às 09:00, no formato de datetime-local (hora local)
  const d = new Date();
  d.setDate(d.getDate() + 1);
  d.setHours(9, 0, 0, 0);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function AddAppointmentModal({
  patientId,
  onClose,
  onCreated,
}: {
  patientId: string;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [when, setWhen] = useState(defaultWhen());
  const [kind, setKind] = useState<AppointmentKind>("consultation");
  const [location, setLocation] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!when || busy) return;
    setBusy(true);
    setError(null);
    try {
      await patients.createAppointment(patientId, {
        // datetime-local é hora local; convertemos para instante UTC (ISO com Z).
        scheduled_at: new Date(when).toISOString(),
        kind,
        location: location.trim() || null,
        notes: notes.trim() || null,
      });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível agendar. Tente novamente.");
      setBusy(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <form className="modal-card np-form" onClick={(e) => e.stopPropagation()} onSubmit={onSubmit}>
        <h3>Agendar consulta</h3>
        <label>
          Data e hora
          <input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} required autoFocus />
        </label>
        <label>
          Tipo
          <select value={kind} onChange={(e) => setKind(e.target.value as AppointmentKind)}>
            <option value="consultation">Consulta</option>
            <option value="return">Retorno</option>
          </select>
        </label>
        <label>
          Local <span className="muted">(opcional)</span>
          <input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="ex.: Consultório / Telemedicina" />
        </label>
        <label>
          Observações <span className="muted">(opcional)</span>
          <input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="ex.: reavaliar dose" />
        </label>

        {error ? <div className="np-error">{error}</div> : null}

        <div className="np-actions">
          <button type="button" className="btn ghost" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className="btn" disabled={busy || !when}>
            {busy ? "Agendando…" : "Agendar"}
          </button>
        </div>
      </form>
    </div>
  );
}
