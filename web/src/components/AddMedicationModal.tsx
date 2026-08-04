import { useState, type FormEvent } from "react";
import { patients } from "../api/endpoints";
import { ApiError } from "../api/client";
import "./NewPatientModal.css";
import "./AddMedicationModal.css";

const HHMM = /^([01]\d|2[0-3]):[0-5]\d$/;

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export function AddMedicationModal({
  patientId,
  onClose,
  onCreated,
}: {
  patientId: string;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [dose, setDose] = useState("");
  const [times, setTimes] = useState<string[]>([]);
  const [timeDraft, setTimeDraft] = useState("");
  const [startDate, setStartDate] = useState(today());
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function addTime() {
    const v = timeDraft.trim();
    if (!HHMM.test(v)) {
      setError("Horário inválido — use HH:MM (24h).");
      return;
    }
    if (!times.includes(v)) setTimes((prev) => [...prev, v].sort());
    setTimeDraft("");
    setError(null);
  }

  const canSubmit = name.trim() && dose.trim() && times.length > 0 && !busy;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    try {
      await patients.createMedication(patientId, {
        name: name.trim(),
        dose: dose.trim(),
        times,
        start_date: startDate,
        notes: notes.trim() || null,
      });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível salvar. Tente novamente.");
      setBusy(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <form className="modal-card np-form" onClick={(e) => e.stopPropagation()} onSubmit={onSubmit}>
        <h3>Adicionar medicação</h3>
        <label>
          Medicamento
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="ex.: Escitalopram" required autoFocus />
        </label>
        <label>
          Dose
          <input value={dose} onChange={(e) => setDose(e.target.value)} placeholder="ex.: 10mg" required />
        </label>

        <div className="med-times">
          <span className="med-label">Horários (HH:MM)</span>
          <div className="med-time-add">
            <input
              value={timeDraft}
              onChange={(e) => setTimeDraft(e.target.value)}
              placeholder="08:00"
              inputMode="numeric"
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addTime();
                }
              }}
            />
            <button type="button" className="btn ghost sm" onClick={addTime}>
              Adicionar
            </button>
          </div>
          {times.length > 0 ? (
            <div className="med-chips">
              {times.map((t) => (
                <span className="med-chip" key={t}>
                  {t}
                  <button type="button" onClick={() => setTimes((prev) => prev.filter((x) => x !== t))} aria-label={`Remover ${t}`}>
                    ×
                  </button>
                </span>
              ))}
            </div>
          ) : null}
        </div>

        <label>
          Início
          <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} required />
        </label>
        <label>
          Observações <span className="muted">(opcional)</span>
          <input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="ex.: tomar após a refeição" />
        </label>

        {error ? <div className="np-error">{error}</div> : null}

        <div className="np-actions">
          <button type="button" className="btn ghost" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className="btn" disabled={!canSubmit}>
            {busy ? "Salvando…" : "Salvar"}
          </button>
        </div>
      </form>
    </div>
  );
}
