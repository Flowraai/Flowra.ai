import { useState, type FormEvent } from "react";
import { patients, notes as notesApi } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { ClinicalNote, NoteKind } from "../api/types";
import "./NewPatientModal.css";

const KINDS: { value: NoteKind; label: string }[] = [
  { value: "note", label: "Anotação" },
  { value: "diagnosis", label: "Diagnóstico" },
  { value: "other", label: "Outro" },
];

export function NoteModal({
  patientId,
  appointmentId,
  note,
  onClose,
  onSaved,
}: {
  patientId: string;
  appointmentId?: string;
  note?: ClinicalNote;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [kind, setKind] = useState<NoteKind>(note?.kind ?? "note");
  const [body, setBody] = useState(note?.body ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const editing = Boolean(note);
  const canSubmit = body.trim().length > 0 && !busy;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    try {
      if (editing && note) {
        await notesApi.update(note.id, { kind, body: body.trim() });
      } else {
        await patients.createNote(patientId, {
          kind,
          body: body.trim(),
          appointment_id: appointmentId ?? null,
        });
      }
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível salvar. Tente novamente.");
      setBusy(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <form className="modal-card np-form" onClick={(e) => e.stopPropagation()} onSubmit={onSubmit}>
        <h3>
          {editing ? "Editar anotação" : appointmentId ? "Anotação da consulta" : "Nova anotação"}
        </h3>

        <label>
          Tipo
          <select value={kind} onChange={(e) => setKind(e.target.value as NoteKind)} className="note-select">
            {KINDS.map((k) => (
              <option key={k.value} value={k.value}>{k.label}</option>
            ))}
          </select>
        </label>

        <label>
          Conteúdo
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Evolução, diagnóstico, conduta, observações…"
            rows={7}
            autoFocus
            className="note-textarea"
          />
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
