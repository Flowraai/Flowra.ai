import { useState, type FormEvent } from "react";
import { patients } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { PrescriptionItem } from "../api/types";
import "./NewPatientModal.css";
import "./AddPrescriptionModal.css";

type Item = { name: string; dose: string; instructions: string };
const blank = (): Item => ({ name: "", dose: "", instructions: "" });

export function AddPrescriptionModal({
  patientId,
  onClose,
  onCreated,
}: {
  patientId: string;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [items, setItems] = useState<Item[]>([blank()]);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function update(i: number, patch: Partial<Item>) {
    setItems((prev) => prev.map((it, idx) => (idx === i ? { ...it, ...patch } : it)));
  }

  const valid = items.filter((it) => it.name.trim() && it.dose.trim());
  const canSubmit = valid.length > 0 && !busy;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    try {
      const payload: PrescriptionItem[] = valid.map((it) => ({
        name: it.name.trim(),
        dose: it.dose.trim(),
        instructions: it.instructions.trim() || null,
      }));
      await patients.createPrescription(patientId, { items: payload, notes: notes.trim() || null });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível salvar. Tente novamente.");
      setBusy(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <form className="modal-card np-form rx-modal" onClick={(e) => e.stopPropagation()} onSubmit={onSubmit}>
        <h3>Nova receita</h3>
        <div className="rx-items">
          {items.map((it, i) => (
            <div className="rx-item" key={i}>
              <div className="rx-item-head">
                <span className="rx-n">Medicamento {i + 1}</span>
                {items.length > 1 ? (
                  <button type="button" className="rx-del" onClick={() => setItems((p) => p.filter((_, idx) => idx !== i))}>
                    remover
                  </button>
                ) : null}
              </div>
              <div className="rx-row">
                <input placeholder="Nome" value={it.name} onChange={(e) => update(i, { name: e.target.value })} />
                <input placeholder="Dose" value={it.dose} onChange={(e) => update(i, { dose: e.target.value })} className="rx-dose" />
              </div>
              <input placeholder="Instruções (opcional)" value={it.instructions} onChange={(e) => update(i, { instructions: e.target.value })} />
            </div>
          ))}
          <button type="button" className="btn ghost sm rx-add" onClick={() => setItems((p) => [...p, blank()])}>
            + Adicionar medicamento
          </button>
        </div>

        <label>
          Observações <span className="muted">(opcional)</span>
          <input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="ex.: uso contínuo" />
        </label>

        {error ? <div className="np-error">{error}</div> : null}
        <div className="np-actions">
          <button type="button" className="btn ghost" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className="btn" disabled={!canSubmit}>
            {busy ? "Salvando…" : "Salvar rascunho"}
          </button>
        </div>
      </form>
    </div>
  );
}
