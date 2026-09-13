import { useState, type FormEvent } from "react";
import { patients } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { CertKind } from "../api/types";
import "./NewPatientModal.css";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export function CertificateModal({
  patientId,
  onClose,
  onCreated,
}: {
  patientId: string;
  onClose: () => void;
  onCreated: (certId: string) => void;
}) {
  const [kind, setKind] = useState<CertKind>("afastamento");
  const [days, setDays] = useState("1");
  const [startDate, setStartDate] = useState(today());
  const [cid, setCid] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const cert = await patients.createCertificate(patientId, {
        kind,
        days: kind === "afastamento" ? Math.max(1, Number(days) || 1) : null,
        start_date: startDate || null,
        cid: cid.trim() || null,
        notes: notes.trim() || null,
      });
      onCreated(cert.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível emitir. Tente novamente.");
      setBusy(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <form className="modal-card np-form" onClick={(e) => e.stopPropagation()} onSubmit={onSubmit}>
        <h3>Emitir atestado / declaração</h3>

        <label>
          Tipo
          <select value={kind} onChange={(e) => setKind(e.target.value as CertKind)} className="note-select">
            <option value="afastamento">Atestado de afastamento</option>
            <option value="comparecimento">Declaração de comparecimento</option>
          </select>
        </label>

        <div className="set-row">
          {kind === "afastamento" ? (
            <label>
              Dias de afastamento
              <input type="number" min={1} max={365} value={days} onChange={(e) => setDays(e.target.value)} />
            </label>
          ) : null}
          <label>
            {kind === "afastamento" ? "A partir de" : "Data do comparecimento"}
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
          </label>
        </div>

        {kind === "afastamento" ? (
          <label>
            CID <span className="muted">(opcional — só com autorização do paciente)</span>
            <input value={cid} onChange={(e) => setCid(e.target.value)} placeholder="ex.: F41.1" />
          </label>
        ) : null}

        <label>
          Observação <span className="muted">(opcional)</span>
          <input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="texto adicional no documento" />
        </label>

        {error ? <div className="np-error">{error}</div> : null}
        <div className="np-actions">
          <button type="button" className="btn ghost" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn" disabled={busy}>
            {busy ? "Emitindo…" : "Emitir e abrir"}
          </button>
        </div>
      </form>
    </div>
  );
}
