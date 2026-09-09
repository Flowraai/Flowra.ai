import { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { auth } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { MessagePrefs } from "../api/types";

const DEFAULTS: MessagePrefs = {
  send_onboarding: true,
  send_medication_reminder: true,
  send_appointment_reminder: true,
  signature: null,
};

const TOGGLES: { key: keyof MessagePrefs; label: string; hint: string }[] = [
  {
    key: "send_onboarding",
    label: "Convite de acesso ao cadastrar",
    hint: "Envia o link do app assim que você cadastra um paciente.",
  },
  {
    key: "send_medication_reminder",
    label: "Lembrete de medicação",
    hint: "Avisa o paciente na hora de cada dose.",
  },
  {
    key: "send_appointment_reminder",
    label: "Lembrete de consulta (24h antes)",
    hint: "Pede que o paciente confirme a presença ou peça para remarcar.",
  },
];

export function MessagePrefsCard() {
  const { doctor, refresh } = useAuth();
  const initial: MessagePrefs = { ...DEFAULTS, ...(doctor?.message_prefs ?? {}) };
  const [prefs, setPrefs] = useState<MessagePrefs>(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  function set<K extends keyof MessagePrefs>(key: K, value: MessagePrefs[K]) {
    setSaved(false);
    setPrefs((p) => ({ ...p, [key]: value }));
  }

  async function save() {
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      await auth.updateMe({
        message_prefs: { ...prefs, signature: prefs.signature?.trim() || null },
      });
      await refresh();
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível salvar. Tente novamente.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card settings-card">
      <div className="set-section">Mensagens automáticas</div>
      <p className="muted set-hint">
        Escolha o que o Flowra Care envia aos seus pacientes. As mensagens saem pelo seu WhatsApp
        (se conectado) ou pelos canais do servidor.
      </p>

      <div className="msg-prefs">
        {TOGGLES.map((t) => (
          <label className="msg-toggle" key={t.key}>
            <input
              type="checkbox"
              checked={Boolean(prefs[t.key])}
              onChange={(e) => set(t.key, e.target.checked as never)}
            />
            <span>
              <b>{t.label}</b>
              <span className="muted set-hint" style={{ display: "block", margin: 0 }}>
                {t.hint}
              </span>
            </span>
          </label>
        ))}
      </div>

      <label style={{ marginTop: 14 }}>
        Assinatura das mensagens <span className="muted">(opcional)</span>
        <input
          value={prefs.signature ?? ""}
          maxLength={120}
          placeholder="Ex.: Dra. Ana Souza — CRM 00000"
          onChange={(e) => set("signature", e.target.value)}
        />
      </label>
      <p className="muted set-hint">Acrescentada ao fim de cada mensagem enviada ao paciente.</p>

      {error ? <div className="set-error">{error}</div> : null}
      {saved ? <div className="set-saved">Preferências salvas ✓</div> : null}

      <div className="set-actions">
        <button className="btn" onClick={save} disabled={busy}>
          {busy ? "Salvando…" : "Salvar preferências"}
        </button>
      </div>
    </div>
  );
}
