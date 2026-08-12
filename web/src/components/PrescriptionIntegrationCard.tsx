import { useEffect, useState } from "react";
import { prescriptions } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { PrescriptionIntegration, PrescriptionProviderInfo } from "../api/types";

export function PrescriptionIntegrationCard() {
  const [providers, setProviders] = useState<PrescriptionProviderInfo[]>([]);
  const [integration, setIntegration] = useState<PrescriptionIntegration | null>(null);
  const [selected, setSelected] = useState<string>("none");
  const [credential, setCredential] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const [pv, integ] = await Promise.all([prescriptions.providers(), prescriptions.integration()]);
      setProviders(pv);
      setIntegration(integ);
      setSelected(integ.provider);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Falha ao carregar.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const info = providers.find((p) => p.slug === selected);

  async function onSave() {
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const cred = info?.requires_credential && credential.trim() ? credential.trim() : undefined;
      const integ = await prescriptions.setIntegration(selected, cred);
      setIntegration(integ);
      setCredential("");
      setSaved(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Não foi possível salvar.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="card settings-card">
        <div className="set-section">Emissão de receita</div>
        <p className="muted">Carregando…</p>
      </div>
    );
  }

  return (
    <div className="card settings-card">
      <div className="set-section">Emissão de receita</div>
      <p className="muted set-hint">
        Escolha a plataforma que assina suas receitas e conecte a sua conta. A receita sai
        assinada no seu CRM — cada médico usa a própria conta.
      </p>

      <label>
        Plataforma
        <select value={selected} onChange={(e) => setSelected(e.target.value)}>
          {providers.map((p) => (
            <option key={p.slug} value={p.slug}>
              {p.name}
              {p.available ? "" : " (em breve)"}
            </option>
          ))}
        </select>
      </label>

      {info ? <p className="muted set-hint">{info.description}</p> : null}

      {info && !info.legal_value ? (
        <div className="set-error" style={{ background: "transparent" }}>
          ⚠️ Sem valor legal — serve só como registro/histórico. Não vale como receita na farmácia
          (e não use para controlados).
        </div>
      ) : null}

      {info?.requires_credential ? (
        <label>
          {info.credential_label ?? "Credencial"}
          <input
            type="password"
            value={credential}
            onChange={(e) => setCredential(e.target.value)}
            placeholder={integration?.connected ? "•••••••• (já conectado — preencha para trocar)" : "Cole seu token"}
            autoComplete="off"
          />
        </label>
      ) : null}

      {info && !info.available ? (
        <p className="muted set-hint">
          A conexão já pode ser salva. A <b>emissão</b> é habilitada assim que a integração com{" "}
          {info.name} for concluída.
        </p>
      ) : null}

      {integration ? (
        <p className="muted set-hint">
          Status: <b>{integration.provider_name}</b> —{" "}
          {integration.connected ? "conectado ✓" : "falta a credencial"}
          {integration.legal_value ? " · com valor legal" : " · sem valor legal"}
        </p>
      ) : null}

      {error ? <div className="set-error">{error}</div> : null}
      {saved ? <div className="set-saved">Integração salva ✓</div> : null}

      <div className="set-actions">
        <button className="btn" type="button" onClick={onSave} disabled={busy}>
          {busy ? "Salvando…" : "Salvar integração"}
        </button>
      </div>
    </div>
  );
}
