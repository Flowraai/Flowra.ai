import { useEffect, useMemo, useState } from "react";
import { charges as chargesApi, billingBatches } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { BillingBatch, ConsultationCharge } from "../api/types";
import "../pages/FinancialPanel.css";

function brl(cents: number): string {
  return (cents / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}
function when(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "2-digit" });
}

type PlanGroup = { id: string; name: string; count: number; total: number };

export function BatchesCard({ onChange }: { onChange: () => void }) {
  const [toBill, setToBill] = useState<PlanGroup[]>([]);
  const [batches, setBatches] = useState<BillingBatch[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function load() {
    setError(null);
    // Cobranças de convênio ainda pendentes (a faturar), agrupadas por convênio.
    chargesApi
      .list({ status: "pending" })
      .then((rows: ConsultationCharge[]) => {
        const g = new Map<string, PlanGroup>();
        for (const c of rows) {
          if (c.kind !== "convenio" || !c.health_plan_id) continue;
          const cur = g.get(c.health_plan_id) ?? {
            id: c.health_plan_id,
            name: c.health_plan_name ?? "Convênio",
            count: 0,
            total: 0,
          };
          cur.count += 1;
          cur.total += c.doctor_cents;
          g.set(c.health_plan_id, cur);
        }
        setToBill([...g.values()].sort((a, b) => b.total - a.total));
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Falha ao carregar."));
    billingBatches.list().then(setBatches).catch(() => setBatches([]));
  }
  useEffect(load, []);

  async function generate(planId: string) {
    setBusy(true);
    setError(null);
    try {
      const ref = new Date().toISOString().slice(0, 7); // "YYYY-MM"
      await billingBatches.create({ health_plan_id: planId, reference: ref });
      load();
      onChange();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Não foi possível gerar o lote.");
    } finally {
      setBusy(false);
    }
  }

  async function close(id: string) {
    setBusy(true);
    try {
      await billingBatches.close(id);
      load();
    } finally {
      setBusy(false);
    }
  }

  const openBatches = useMemo(() => (batches ?? []).filter((b) => b.status === "open"), [batches]);
  const closedBatches = useMemo(() => (batches ?? []).filter((b) => b.status === "closed"), [batches]);

  return (
    <div className="card">
      <div className="hd"><h4>Faturamento de convênios</h4></div>
      <div className="bd">
        {error ? <div className="set-error" style={{ marginBottom: 10 }}>{error}</div> : null}

        <div className="bt-sub">A faturar</div>
        {toBill.length === 0 ? (
          <span className="muted" style={{ fontSize: 13 }}>Nenhuma consulta de convênio pendente de faturamento.</span>
        ) : (
          <ul className="bt-list">
            {toBill.map((g) => (
              <li key={g.id} className="bt-item">
                <div>
                  <b>{g.name}</b>
                  <span className="muted"> · {g.count} consulta(s) · {brl(g.total)}</span>
                </div>
                <button className="mini primary" disabled={busy} onClick={() => generate(g.id)}>
                  Gerar lote
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="bt-sub" style={{ marginTop: 16 }}>Lotes</div>
        {batches == null ? (
          <div className="state"><div className="spinner" /></div>
        ) : batches.length === 0 ? (
          <span className="muted" style={{ fontSize: 13 }}>Nenhum lote gerado ainda.</span>
        ) : (
          <ul className="bt-list">
            {[...openBatches, ...closedBatches].map((b) => (
              <li key={b.id} className="bt-batch">
                <div className="bt-batch-top">
                  <b>{b.health_plan_name ?? "Convênio"}</b>
                  {b.reference ? <span className="muted"> · {b.reference}</span> : null}
                  <span className={`fp-st ${b.status === "open" ? "st-pending" : "st-received"}`}>
                    {b.status === "open" ? "Em aberto" : "Encerrado"}
                  </span>
                  <span className="muted bt-date">{when(b.created_at)}</span>
                </div>
                <div className="bt-batch-vals">
                  <span>{b.charge_count} consulta(s)</span>
                  <span className="warn">{brl(b.billed_cents)} aguardando</span>
                  <span className="ok">{brl(b.received_cents)} recebido</span>
                  {b.denied_cents > 0 ? <span className="glosa">{brl(b.denied_cents)} glosado</span> : null}
                  {b.status === "open" && b.billed_cents === 0 ? (
                    <button className="mini" disabled={busy} onClick={() => close(b.id)}>Encerrar</button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
        <p className="muted" style={{ fontSize: 12, marginTop: 10, marginBottom: 0 }}>
          Concilie cada consulta faturada na lista abaixo: <b>Recebi</b> ou <b>Glosar</b> (com motivo).
        </p>
      </div>
    </div>
  );
}
