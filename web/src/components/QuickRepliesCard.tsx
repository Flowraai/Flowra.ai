import { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { auth } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { MessagePrefs } from "../api/types";

const DEFAULTS: MessagePrefs = {
  send_onboarding: true,
  send_medication_reminder: true,
  send_appointment_reminder: true,
  send_checkin_reminder: true,
  send_appointment_confirmation: true,
  appointment_confirmation_template: null,
  signature: null,
  quick_replies: [],
};

export function QuickRepliesCard() {
  const { doctor, refresh } = useAuth();
  const [list, setList] = useState<string[]>(doctor?.message_prefs?.quick_replies ?? []);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  function add() {
    const t = draft.trim();
    if (!t || list.length >= 30) return;
    setList((prev) => [...prev, t]);
    setDraft("");
    setSaved(false);
  }
  function remove(i: number) {
    setList((prev) => prev.filter((_, idx) => idx !== i));
    setSaved(false);
  }

  async function save() {
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const current = { ...DEFAULTS, ...(doctor?.message_prefs ?? {}) };
      await auth.updateMe({ message_prefs: { ...current, quick_replies: list } });
      await refresh();
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível salvar.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card settings-card">
      <div className="set-section">Respostas rápidas</div>
      <p className="muted set-hint">
        Frases que você usa com frequência no chat com o paciente — insira com um toque e edite antes
        de enviar.
      </p>

      <div className="qr-add">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ex.: Lembre-se de tomar a medicação hoje. 💊"
          onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), add())}
        />
        <button type="button" className="btn ghost sm" onClick={add} disabled={!draft.trim() || list.length >= 30}>
          Adicionar
        </button>
      </div>

      {list.length > 0 ? (
        <div className="qr-list">
          {list.map((t, i) => (
            <div className="qr-item" key={i}>
              <span>{t}</span>
              <button type="button" onClick={() => remove(i)} aria-label="Remover">×</button>
            </div>
          ))}
        </div>
      ) : (
        <p className="muted set-hint">Nenhuma resposta rápida ainda.</p>
      )}

      {error ? <div className="set-error">{error}</div> : null}
      {saved ? <div className="set-saved">Salvo ✓</div> : null}
      <div className="set-actions">
        <button className="btn" onClick={save} disabled={busy}>
          {busy ? "Salvando…" : "Salvar"}
        </button>
      </div>
    </div>
  );
}
