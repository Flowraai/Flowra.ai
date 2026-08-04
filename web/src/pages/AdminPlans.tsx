import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { ThemeToggle } from "../components/ThemeToggle";
import { useAuth } from "../auth/AuthContext";
import { adminPlans } from "../api/endpoints";
import { ApiError } from "../api/client";
import { money } from "../lib/format";
import type { BillingCycle, PlanAdmin } from "../api/types";
import "./Subscribe.css";
import "./AdminPlans.css";

interface Draft {
  name: string;
  reais: string; // preço em reais (string editável)
  cycle: BillingCycle;
  patient_limit: string;
  trial_days: string;
  description: string;
}

const EMPTY: Draft = { name: "", reais: "", cycle: "monthly", patient_limit: "", trial_days: "0", description: "" };

function toCents(reais: string): number {
  const n = Number(reais.replace(/\./g, "").replace(",", "."));
  return Number.isFinite(n) ? Math.round(n * 100) : 0;
}

export function AdminPlans() {
  const { doctor } = useAuth();
  const [plans, setPlans] = useState<PlanAdmin[]>([]);
  const [loading, setLoading] = useState(true);
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setPlans(await adminPlans.list());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Falha ao carregar planos.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Guard de rota: só admin.
  if (doctor && !doctor.is_admin) return <Navigate to="/" replace />;

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await adminPlans.create({
        name: draft.name.trim(),
        description: draft.description.trim() || null,
        price_cents: toCents(draft.reais),
        cycle: draft.cycle,
        patient_limit: draft.patient_limit ? Number(draft.patient_limit) : null,
        trial_days: Number(draft.trial_days) || 0,
      });
      setDraft(EMPTY);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível criar o plano.");
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(p: PlanAdmin) {
    await adminPlans.update(p.id, { active: !p.active });
    await load();
  }

  async function changePrice(p: PlanAdmin) {
    const input = window.prompt(`Novo preço de "${p.name}" (em reais):`, (p.price_cents / 100).toFixed(2));
    if (input == null) return;
    await adminPlans.update(p.id, { price_cents: toCents(input) });
    await load();
  }

  async function remove(p: PlanAdmin) {
    if (!window.confirm(`Excluir o plano "${p.name}"? (se já houver assinantes, ele é só desativado)`)) return;
    await adminPlans.remove(p.id);
    await load();
  }

  return (
    <AppShell title="Planos" subtitle="Gerencie os planos de assinatura do Flowra Care" actions={<ThemeToggle />}>
      <div className="sub-wrap">
        <form className="card sub-form" onSubmit={onCreate}>
          <div className="set-section">Novo plano</div>
          <div className="set-row">
            <label>
              Nome
              <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} required />
            </label>
            <label>
              Preço (R$)
              <input
                value={draft.reais}
                onChange={(e) => setDraft({ ...draft, reais: e.target.value })}
                placeholder="149,90"
                required
              />
            </label>
          </div>
          <div className="set-row">
            <label>
              Ciclo
              <select
                value={draft.cycle}
                onChange={(e) => setDraft({ ...draft, cycle: e.target.value as BillingCycle })}
              >
                <option value="monthly">Mensal</option>
                <option value="yearly">Anual</option>
              </select>
            </label>
            <label>
              Limite de pacientes <span className="muted">(vazio = ilimitado)</span>
              <input
                value={draft.patient_limit}
                onChange={(e) => setDraft({ ...draft, patient_limit: e.target.value })}
                placeholder="ilimitado"
                inputMode="numeric"
              />
            </label>
            <label>
              Teste grátis (dias)
              <input
                value={draft.trial_days}
                onChange={(e) => setDraft({ ...draft, trial_days: e.target.value })}
                inputMode="numeric"
              />
            </label>
          </div>
          <label>
            Descrição <span className="muted">(opcional)</span>
            <input
              value={draft.description}
              onChange={(e) => setDraft({ ...draft, description: e.target.value })}
              placeholder="Ex.: ideal para consultório em crescimento"
            />
          </label>
          {error ? <div className="set-error">{error}</div> : null}
          <div className="set-actions">
            <button className="btn" type="submit" disabled={busy}>
              {busy ? "Criando…" : "Criar plano"}
            </button>
          </div>
        </form>

        {loading ? (
          <div className="state">
            <div className="spinner" />
          </div>
        ) : (
          <div className="card plan-table">
            <table>
              <thead>
                <tr>
                  <th>Plano</th>
                  <th>Preço</th>
                  <th>Ciclo</th>
                  <th>Pacientes</th>
                  <th>Teste</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {plans.map((p) => (
                  <tr key={p.id} className={p.active ? "" : "inactive"}>
                    <td>
                      <b>{p.name}</b>
                      {p.description ? <div className="muted">{p.description}</div> : null}
                    </td>
                    <td className="mono">{money(p.price_cents)}</td>
                    <td>{p.cycle === "yearly" ? "Anual" : "Mensal"}</td>
                    <td>{p.patient_limit ?? "∞"}</td>
                    <td>{p.trial_days ? `${p.trial_days}d` : "—"}</td>
                    <td>
                      <span className={`pill ${p.active ? "on" : "off"}`}>{p.active ? "Ativo" : "Inativo"}</span>
                    </td>
                    <td className="row-actions">
                      <button onClick={() => changePrice(p)}>Preço</button>
                      <button onClick={() => toggleActive(p)}>{p.active ? "Desativar" : "Ativar"}</button>
                      <button className="danger" onClick={() => remove(p)}>
                        Excluir
                      </button>
                    </td>
                  </tr>
                ))}
                {plans.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="muted" style={{ textAlign: "center", padding: "20px" }}>
                      Nenhum plano criado ainda.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AppShell>
  );
}
