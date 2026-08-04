import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { ThemeToggle } from "../components/ThemeToggle";
import { useAuth } from "../auth/AuthContext";
import { billing } from "../api/endpoints";
import { ApiError } from "../api/client";
import { money, relativeDate } from "../lib/format";
import type { Plan, Subscription } from "../api/types";
import "./Subscribe.css";

const STATUS_LABEL: Record<Subscription["status"], string> = {
  trialing: "Em teste grátis",
  pending: "Pagamento pendente",
  active: "Ativa",
  overdue: "Pagamento vencido",
  canceled: "Cancelada",
};

function cycleLabel(cycle: string): string {
  return cycle === "yearly" ? "/ano" : "/mês";
}

export function Subscribe() {
  const { refresh } = useAuth();
  const navigate = useNavigate();
  const [sub, setSub] = useState<Subscription | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [cpf, setCpf] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, p] = await Promise.all([billing.subscription(), billing.plans()]);
      setSub(s);
      setPlans(p);
      if (!selected && p.length) setSelected(p[0].id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Falha ao carregar planos.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const active = sub && (sub.status === "active" || sub.status === "trialing");

  async function onSubscribe(e: FormEvent) {
    e.preventDefault();
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const res = await billing.subscribe(selected, cpf, phone);
      if (res.checkout_url) {
        // Checkout hospedado do Asaas — o cartão é digitado lá.
        window.location.href = res.checkout_url;
        return;
      }
      // Sem checkout (modo manual): já ativou.
      await refresh();
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível iniciar a assinatura.");
      setBusy(false);
    }
  }

  async function onCancel() {
    if (!window.confirm("Cancelar a assinatura? O acesso ao painel será bloqueado ao fim do período.")) {
      return;
    }
    setBusy(true);
    try {
      await billing.cancel();
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível cancelar agora.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell title="Assinatura" subtitle="Seu plano do Flowra Care" actions={<ThemeToggle />}>
      {loading ? (
        <div className="state">
          <div className="spinner" />
        </div>
      ) : (
        <div className="sub-wrap">
          {sub && sub.status !== "pending" && sub.plan ? (
            <div className={`card sub-status sub-${sub.status}`}>
              <div>
                <div className="muted">Status</div>
                <b>{STATUS_LABEL[sub.status]}</b>
              </div>
              <div>
                <div className="muted">Plano</div>
                <b>{sub.plan.name}</b>
              </div>
              <div>
                <div className="muted">
                  {sub.status === "trialing" ? "Teste até" : "Válido até"}
                </div>
                <b>{relativeDate(sub.status === "trialing" ? sub.trial_end : sub.current_period_end)}</b>
              </div>
              {sub.card_last4 ? (
                <div>
                  <div className="muted">Cartão</div>
                  <b>•••• {sub.card_last4}</b>
                </div>
              ) : null}
              {active ? (
                <button className="btn ghost" onClick={onCancel} disabled={busy}>
                  Cancelar assinatura
                </button>
              ) : null}
            </div>
          ) : null}

          {sub && sub.status === "overdue" ? (
            <div className="sub-alert">
              Seu pagamento está vencido. Escolha um plano abaixo para regularizar e reabrir o painel.
            </div>
          ) : null}

          {!active ? (
            <form onSubmit={onSubscribe}>
              <div className="plan-grid">
                {plans.map((p) => (
                  <label
                    key={p.id}
                    className={`plan-card ${selected === p.id ? "picked" : ""}`}
                  >
                    <input
                      type="radio"
                      name="plan"
                      value={p.id}
                      checked={selected === p.id}
                      onChange={() => setSelected(p.id)}
                    />
                    <div className="plan-head">
                      <b>{p.name}</b>
                      <div className="plan-price">
                        {money(p.price_cents)}
                        <span>{cycleLabel(p.cycle)}</span>
                      </div>
                    </div>
                    {p.description ? <p className="muted">{p.description}</p> : null}
                    <ul className="plan-feats">
                      <li>
                        {p.patient_limit ? `Até ${p.patient_limit} pacientes` : "Pacientes ilimitados"}
                      </li>
                      {p.trial_days > 0 ? <li>{p.trial_days} dias de teste grátis</li> : null}
                    </ul>
                  </label>
                ))}
                {plans.length === 0 ? (
                  <div className="muted">Nenhum plano disponível no momento.</div>
                ) : null}
              </div>

              {plans.length ? (
                <div className="card sub-form">
                  <div className="set-section">Dados para a cobrança</div>
                  <div className="set-row">
                    <label>
                      CPF ou CNPJ
                      <input
                        value={cpf}
                        onChange={(e) => setCpf(e.target.value)}
                        placeholder="Somente números"
                        required
                      />
                    </label>
                    <label>
                      Telefone <span className="muted">(opcional)</span>
                      <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+55…" />
                    </label>
                  </div>
                  <p className="muted set-hint">
                    O pagamento é no cartão, numa página segura do Asaas — o número do cartão não passa
                    pelo Flowra. A cobrança é mensal e você pode cancelar quando quiser.
                  </p>
                  {error ? <div className="set-error">{error}</div> : null}
                  <div className="set-actions">
                    <button className="btn" type="submit" disabled={busy || !selected}>
                      {busy ? "Processando…" : "Assinar e ir para o pagamento"}
                    </button>
                  </div>
                </div>
              ) : null}
            </form>
          ) : null}

          {error && active ? <div className="set-error">{error}</div> : null}
        </div>
      )}
    </AppShell>
  );
}
