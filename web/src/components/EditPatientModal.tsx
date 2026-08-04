import { useState, type FormEvent } from "react";
import { patients } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { Patient } from "../api/types";
import "./NewPatientModal.css";
import "./EditPatientModal.css";

export function EditPatientModal({
  patient,
  onClose,
  onSaved,
  onDeleted,
}: {
  patient: Patient;
  onClose: () => void;
  onSaved: () => void;
  onDeleted: () => void;
}) {
  const [name, setName] = useState(patient.name);
  const [contact, setContact] = useState(patient.contact ?? "");
  const [birth, setBirth] = useState(patient.birth_date ? patient.birth_date.slice(0, 10) : "");
  const [active, setActive] = useState(patient.is_active);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      await patients.update(patient.id, {
        name: name.trim(),
        contact: contact.trim() || null,
        birth_date: birth ? new Date(birth).toISOString() : null,
        is_active: active,
      });
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível salvar. Tente novamente.");
      setBusy(false);
    }
  }

  async function onDelete() {
    setBusy(true);
    setError(null);
    try {
      await patients.remove(patient.id);
      onDeleted();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível excluir. Tente novamente.");
      setBusy(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <form className="modal-card np-form" onClick={(e) => e.stopPropagation()} onSubmit={onSubmit}>
        <h3>Editar paciente</h3>
        <label>
          Nome
          <input value={name} onChange={(e) => setName(e.target.value)} required />
        </label>
        <label>
          Contato <span className="muted">(e-mail ou telefone)</span>
          <input value={contact} onChange={(e) => setContact(e.target.value)} placeholder="para enviar o acesso" />
        </label>
        <label>
          Nascimento <span className="muted">(opcional)</span>
          <input type="date" value={birth} onChange={(e) => setBirth(e.target.value)} />
        </label>
        <label className="np-consent">
          <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
          <span>Paciente <b>ativo</b> (em acompanhamento). Desmarque para pausar sem excluir.</span>
        </label>

        {error ? <div className="np-error">{error}</div> : null}

        <div className="np-actions">
          <button type="button" className="btn ghost" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className="btn" disabled={busy || !name.trim()}>
            {busy ? "Salvando…" : "Salvar"}
          </button>
        </div>

        <div className="danger-zone">
          {confirmDelete ? (
            <div className="dz-confirm">
              <p>
                Excluir <b>{patient.name}</b> e <b>todos os dados de saúde</b> (check-ins, alertas, medicação…)?
                Esta ação é <b>irreversível</b> (direito de eliminação, LGPD).
              </p>
              <div className="dz-actions">
                <button type="button" className="btn ghost" onClick={() => setConfirmDelete(false)}>
                  Manter
                </button>
                <button type="button" className="btn danger" disabled={busy} onClick={onDelete}>
                  {busy ? "Excluindo…" : "Excluir definitivamente"}
                </button>
              </div>
            </div>
          ) : (
            <button type="button" className="dz-open" onClick={() => setConfirmDelete(true)}>
              Excluir paciente e dados (LGPD)
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
