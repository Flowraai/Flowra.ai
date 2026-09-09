import { useState, type FormEvent } from "react";
import { patients } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { PrescriptionItem } from "../api/types";
import "./NewPatientModal.css";
import "./AddPrescriptionModal.css";

type Item = { name: string; dose: string; instructions: string; times: string };
const blank = (): Item => ({ name: "", dose: "", instructions: "", times: "" });

const HHMM = /^([01]\d|2[0-3]):[0-5]\d$/;

// "08:00, 20h, 8:5" -> {ok:["08:00","20:00"]} ou erro no primeiro inválido.
function parseTimes(raw: string): { times: string[]; error: string | null } {
  const parts = raw
    .split(/[,;\s]+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => (s.length === 4 && s.includes(":") ? `0${s}` : s)); // "8:00" -> "08:00"
  for (const p of parts) {
    if (!HHMM.test(p)) return { times: [], error: `Horário inválido: "${p}" (use HH:MM, 24h).` };
  }
  return { times: Array.from(new Set(parts)).sort(), error: null };
}

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
      const payload: PrescriptionItem[] = [];
      for (const it of valid) {
        const { times, error: tErr } = parseTimes(it.times);
        if (tErr) {
          setError(`${it.name.trim()}: ${tErr}`);
          setBusy(false);
          return;
        }
        payload.push({
          name: it.name.trim(),
          dose: it.dose.trim(),
          instructions: it.instructions.trim() || null,
          times,
        });
      }
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
              <input
                placeholder="Horários p/ lembrete — ex.: 08:00, 20:00 (opcional)"
                value={it.times}
                onChange={(e) => update(i, { times: e.target.value })}
                inputMode="numeric"
              />
              <span className="rx-hint">Com horário, ao emitir vira lembrete + adesão na Medicação. Sem horário, fica só na receita.</span>
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
