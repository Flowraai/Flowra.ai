import { useEffect, useMemo, useState, type FormEvent } from "react";
import { appointments } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { AppointmentKind, PatientDirectoryItem } from "../api/types";
import "./NewPatientModal.css";

function defaultWhen(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  d.setHours(9, 0, 0, 0);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function NewAppointmentModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [dir, setDir] = useState<PatientDirectoryItem[]>([]);
  const [query, setQuery] = useState("");
  const [patientId, setPatientId] = useState("");
  const [when, setWhen] = useState(defaultWhen());
  const [kind, setKind] = useState<AppointmentKind>("consultation");
  const [location, setLocation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    appointments
      .patientDirectory()
      .then(setDir)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Falha ao carregar pacientes."));
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = q ? dir.filter((p) => p.name.toLowerCase().includes(q)) : dir;
    return list.slice(0, 50);
  }, [dir, query]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!patientId || !when || busy) return;
    setBusy(true);
    setError(null);
    try {
      await appointments.create(patientId, {
        scheduled_at: new Date(when).toISOString(),
        kind,
        location: location.trim() || null,
        notes: null,
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
        <h3>Nova consulta</h3>

        <label>
          Paciente
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="buscar por nome…"
            autoFocus
          />
        </label>
        <label>
          <select value={patientId} onChange={(e) => setPatientId(e.target.value)} required size={1}>
            <option value="">{dir.length ? "Selecione o paciente" : "Carregando…"}</option>
            {filtered.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </label>

        <label>
          Data e hora
          <input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} required />
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

        {error ? <div className="np-error">{error}</div> : null}

        <div className="np-actions">
          <button type="button" className="btn ghost" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn" disabled={busy || !patientId || !when}>
            {busy ? "Agendando…" : "Agendar"}
          </button>
        </div>
      </form>
    </div>
  );
}
