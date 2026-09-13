import { useEffect, useState, type FormEvent } from "react";
import { patients, healthPlans } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { HealthPlan, PatientCreated } from "../api/types";
import "./NewPatientModal.css";

export function NewPatientModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [contact, setContact] = useState("");
  const [consent, setConsent] = useState(false);
  const [plans, setPlans] = useState<HealthPlan[]>([]);
  const [planId, setPlanId] = useState(""); // "" = particular
  const [card, setCard] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<PatientCreated | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    healthPlans.list().then(setPlans).catch(() => setPlans([]));
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!consent || !name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const p = await patients.create({
        name: name.trim(),
        contact: contact.trim() || null,
        consent_given: true,
        health_plan_id: planId || null,
        insurance_card: planId && card.trim() ? card.trim() : null,
      });
      setCreated(p);
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível cadastrar. Tente novamente.");
    } finally {
      setBusy(false);
    }
  }

  async function copyToken() {
    if (!created) return;
    try {
      await navigator.clipboard.writeText(created.access_token);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        {created ? (
          <div className="np-done">
            <div className="np-check">✓</div>
            <h3>Paciente cadastrado</h3>
            <p className="muted">
              Envie o <b>código de acesso</b> para <b>{created.name}</b>. Ele é exibido <b>uma única vez</b> —
              guarde ou copie agora.
            </p>
            <div className="token-box">
              <code>{created.access_token}</code>
              <button className="btn sm" onClick={copyToken}>
                {copied ? "Copiado ✓" : "Copiar"}
              </button>
            </div>
            <p className="muted np-hint">
              O paciente usa este código para entrar no app Flowra Care. Se preferir, o onboarding também é
              enviado ao contato informado.
            </p>
            <button className="btn" onClick={onClose}>
              Concluir
            </button>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="np-form">
            <h3>Novo paciente</h3>
            <label>
              Nome
              <input value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
            </label>
            <label>
              Contato <span className="muted">(e-mail ou telefone — opcional)</span>
              <input value={contact} onChange={(e) => setContact(e.target.value)} placeholder="para enviar o acesso" />
            </label>
            <label>
              Convênio
              <select value={planId} onChange={(e) => setPlanId(e.target.value)}>
                <option value="">Particular</option>
                {plans.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </label>
            {planId ? (
              <label>
                Carteirinha <span className="muted">(opcional)</span>
                <input value={card} onChange={(e) => setCard(e.target.value)} placeholder="nº da carteira" />
              </label>
            ) : null}
            <label className="np-consent">
              <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
              <span>
                Confirmo o <b>consentimento LGPD</b> do paciente para monitoramento de dados de saúde.
              </span>
            </label>

            {error ? <div className="np-error">{error}</div> : null}

            <div className="np-actions">
              <button type="button" className="btn ghost" onClick={onClose}>
                Cancelar
              </button>
              <button type="submit" className="btn" disabled={busy || !consent || !name.trim()}>
                {busy ? "Cadastrando…" : "Cadastrar"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
