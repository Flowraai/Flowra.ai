import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { ThemeToggle } from "../components/ThemeToggle";
import { FinanceChart } from "../components/FinanceChart";
import { BatchesCard } from "../components/BatchesCard";
import { useAsync } from "../lib/useAsync";
import { charges as chargesApi } from "../api/endpoints";
import { downloadFile } from "../api/client";
import type { ChargeStatus, ConsultationCharge, PaymentMethod } from "../api/types";
import "./FinancialPanel.css";

function brl(cents: number): string {
  return (cents / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}
function when(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "2-digit" });
}

type Period = "30d" | "mes" | "3m" | "tudo";
const STATUS_LABEL: Record<string, string> = {
  pending: "A receber", billed: "Faturado", received: "Recebido", denied: "Glosado", cancelled: "Cancelado",
};
const METHODS: { v: PaymentMethod; label: string }[] = [
  { v: "pix", label: "PIX" }, { v: "dinheiro", label: "Dinheiro" },
  { v: "cartao", label: "Cartão" }, { v: "convenio", label: "Convênio" },
];

function periodRange(p: Period): { start?: string; end?: string } {
  const now = new Date();
  if (p === "tudo") return {};
  if (p === "mes") {
    const start = new Date(now.getFullYear(), now.getMonth(), 1);
    return { start: start.toISOString() };
  }
  const days = p === "30d" ? 30 : 90;
  const start = new Date(now.getTime() - days * 86400000);
  return { start: start.toISOString() };
}

export function FinancialPanel() {
  const navigate = useNavigate();
  const [period, setPeriod] = useState<Period>("3m");
  const [statusFilter, setStatusFilter] = useState<"" | ChargeStatus>("");
  const [reload, setReload] = useState(0);
  const range = useMemo(() => periodRange(period), [period]);

  const summary = useAsync(() => chargesApi.summary(range), [period, reload]);
  const list = useAsync(
    () => chargesApi.list({ ...range, status: statusFilter || undefined }),
    [period, statusFilter, reload],
  );

  const s = summary.data;

  async function mark(id: string, patch: Parameters<typeof chargesApi.update>[1]) {
    try {
      await chargesApi.update(id, patch);
      setReload((k) => k + 1);
    } catch {
      /* ignore; recarrega no próximo ciclo */
    }
  }

  async function glosar(id: string) {
    const reason = window.prompt("Motivo da glosa (opcional):", "");
    if (reason === null) return; // cancelou
    await mark(id, { status: "denied", notes: reason.trim() || null });
  }

  function exportCsv() {
    const q = new URLSearchParams();
    if (range.start) q.set("start", range.start);
    if (range.end) q.set("end", range.end);
    if (statusFilter) q.set("status", statusFilter);
    const qs = q.toString();
    downloadFile(`/charges/export.csv${qs ? `?${qs}` : ""}`, "financeiro-flowra.csv").catch(() => {});
  }

  return (
    <AppShell title="Financeiro" subtitle="A receber, recebido e faturamento por período" actions={<ThemeToggle />}>
      <div className="fp-tools">
        <div className="fp-periods">
          {(["30d", "mes", "3m", "tudo"] as Period[]).map((p) => (
            <button key={p} className={period === p ? "on" : ""} onClick={() => setPeriod(p)}>
              {p === "30d" ? "30 dias" : p === "mes" ? "Este mês" : p === "3m" ? "3 meses" : "Tudo"}
            </button>
          ))}
        </div>
        <button className="fp-export" onClick={exportCsv} title="Baixar o movimento em CSV para o contador">
          ⬇ Exportar CSV
        </button>
      </div>

      {summary.loading ? (
        <div className="state"><div className="spinner" /></div>
      ) : summary.error ? (
        <div className="state"><span className="err">{summary.error}</span></div>
      ) : s ? (
        <>
          <div className="fp-kpis fp-kpis-4">
            <Kpi color="var(--fin-pending)" label="A receber" value={brl(s.to_receive_cents)} />
            <Kpi color="var(--fin-received)" label="Recebido" value={brl(s.received_cents)} />
            <Kpi color="var(--risk-red)" label="Glosado" value={brl(s.denied_cents)} note={`${s.denied_count} consulta(s)`} />
            <Kpi color="var(--accent)" label="Total" value={brl(s.to_receive_cents + s.received_cents)} />
          </div>

          <div className="fp-grid">
            <div className="card">
              <div className="hd"><h4>Faturamento por mês</h4></div>
              <div className="bd"><FinanceChart months={s.monthly} /></div>
            </div>

            <div className="card">
              <div className="hd"><h4>Por convênio × particular</h4></div>
              <div className="bd">
                {s.by_plan.length === 0 ? (
                  <span className="muted" style={{ fontSize: 13 }}>Sem lançamentos no período.</span>
                ) : (
                  <ul className="fp-plans">
                    {s.by_plan.map((b) => (
                      <li key={b.health_plan_id ?? "particular"}>
                        <div className="fp-plan-top">
                          <b>{b.name}</b>
                          <span className="muted">{b.count} consulta(s)</span>
                        </div>
                        <div className="fp-plan-vals">
                          <span className="ok">{brl(b.received_cents)} recebido</span>
                          <span className="warn">{brl(b.to_receive_cents)} a receber</span>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>
        </>
      ) : null}

      <div style={{ marginBottom: 16 }}>
        <BatchesCard onChange={() => setReload((k) => k + 1)} />
      </div>

      <div className="card fp-list-card">
        <div className="hd">
          <h4>Lançamentos</h4>
          <div className="fp-statusfilter">
            {([["", "Todos"], ["pending", "A receber"], ["billed", "Faturado"], ["received", "Recebido"], ["denied", "Glosado"], ["cancelled", "Cancelado"]] as const).map(
              ([v, label]) => (
                <button key={v} className={statusFilter === v ? "on" : ""} onClick={() => setStatusFilter(v)}>
                  {label}
                </button>
              ),
            )}
          </div>
        </div>
        <div className="bd">
          {list.loading ? (
            <div className="state"><div className="spinner" /></div>
          ) : list.error ? (
            <span className="err">{list.error}</span>
          ) : (list.data ?? []).length === 0 ? (
            <span className="muted" style={{ fontSize: 13 }}>Nenhum lançamento no período.</span>
          ) : (
            <div className="fp-table">
              <table>
                <thead>
                  <tr><th>Paciente</th><th>Data</th><th>Tipo</th><th>Repasse</th><th>Situação</th><th /></tr>
                </thead>
                <tbody>
                  {(list.data ?? []).map((c: ConsultationCharge) => (
                    <tr key={c.id}>
                      <td className="fp-name" onClick={() => navigate(`/pacientes/${c.patient_id}`)}>
                        {c.patient_name ?? "—"}
                      </td>
                      <td className="tnum">{when(c.created_at)}</td>
                      <td>{c.kind === "convenio" ? c.health_plan_name ?? "Convênio" : "Particular"}</td>
                      <td className="tnum"><b>{brl(c.doctor_cents)}</b></td>
                      <td><span className={`fp-st st-${c.status}`}>{STATUS_LABEL[c.status]}</span></td>
                      <td className="fp-actions">
                        {c.status === "pending" ? (
                          METHODS.map((m) => (
                            <button key={m.v} title={`Recebi via ${m.label}`}
                                    onClick={() => mark(c.id, { status: "received", payment_method: m.v })}>
                              {m.label}
                            </button>
                          ))
                        ) : c.status === "billed" ? (
                          <>
                            <button title="Recebido do convênio"
                                    onClick={() => mark(c.id, { status: "received", payment_method: "convenio" })}>
                              Recebi
                            </button>
                            <button title="Registrar glosa" onClick={() => glosar(c.id)}>Glosar</button>
                          </>
                        ) : c.status === "received" || c.status === "denied" ? (
                          <button onClick={() => mark(c.id, { status: "pending" })}>Reabrir</button>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}

function Kpi({ color, label, value, note }: { color: string; label: string; value: string; note?: string }) {
  return (
    <div className="fp-kpi">
      <span className="fp-kpi-stripe" style={{ background: color }} />
      <span className="fp-kpi-lab">{label}</span>
      <span className="fp-kpi-val tnum" style={{ color }}>{value}</span>
      {note ? <span className="fp-kpi-note">{note}</span> : null}
    </div>
  );
}
