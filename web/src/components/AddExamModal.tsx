import { useState, type FormEvent } from "react";
import { patients } from "../api/endpoints";
import { ApiError } from "../api/client";
import "./NewPatientModal.css";

export function AddExamModal({
  patientId,
  onClose,
  onCreated,
}: {
  patientId: string;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      await patients.createExam(patientId, { name: name.trim(), notes: notes.trim() || null });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível solicitar. Tente novamente.");
      setBusy(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <form className="modal-card np-form" onClick={(e) => e.stopPropagation()} onSubmit={onSubmit}>
        <h3>Solicitar exame</h3>
        <label>
          Exame
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="ex.: Hemograma completo" required autoFocus />
        </label>
        <label>
          Observações <span className="muted">(opcional)</span>
          <input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="ex.: em jejum" />
        </label>
        {error ? <div className="np-error">{error}</div> : null}
        <div className="np-actions">
          <button type="button" className="btn ghost" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className="btn" disabled={busy || !name.trim()}>
            {busy ? "Solicitando…" : "Solicitar"}
          </button>
        </div>
      </form>
    </div>
  );
}
