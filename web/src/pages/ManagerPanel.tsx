import { useEffect, useState } from "react";
import { AppShell } from "../components/AppShell";
import { ThemeToggle } from "../components/ThemeToggle";
import { clinic } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { ClinicDashboard } from "../api/types";
import "./ManagerPanel.css";

function brl(cents: number): string {
  return (cents / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

const RISK = [
  { key: "red", label: "Alta", color: "var(--risk-red)" },
  { key: "orange", label: "Acompanhar", color: "var(--risk-orange)" },
  { key: "yellow", label: "Atenção", color: "var(--risk-yellow)" },
  { key: "green", label: "Estável", color: "var(--risk-green)" },
] as const;

export function ManagerPanel() {
  const [data, setData] = useState<ClinicDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    clinic
      .dashboard()
      .then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Falha ao carregar o painel."));
  }, []);

  const riskTotal = data ? data.risk.red + data.risk.orange + data.risk.yellow + data.risk.green : 0;

  return (
    <AppShell title="Gestão" subtitle="Visão da clínica no mês" actions={<ThemeToggle />}>
      {error ? (
        <div className="card"><div className="bd"><span className="muted">{error}</span></div></div>
      ) : !data ? (
        <div className="state"><div className="spinner" /></div>
      ) : (
        <>
          <div className="mg-kpis">
            <Kpi label="Pacientes ativos" value={String(data.patients_total)} note={`${data.doctors_total} médico(s)`} />
            <Kpi label="Precisam de atenção" value={String(data.attention_count)} stripe="var(--risk-orange)" />
            <Kpi label="Consultas no mês" value={String(data.appointments_completed)} note={`${data.appointments_cancelled} cancelada(s)`} />
            <Kpi label="Próximas consultas" value={String(data.appointments_upcoming)} />
            <Kpi label="Repasse médicos (recebido)" value={brl(data.received_cents)} stripe="var(--fin-received)" note={`${brl(data.to_receive_cents)} a receber`} />
            <Kpi label="Fatia da clínica (recebida)" value={brl(data.clinic_received_cents)} stripe="var(--accent)" note={`${brl(data.clinic_to_receive_cents)} a receber`} />
          </div>

          <div className="card mg-card">
            <div className="hd"><h4>Risco dos pacientes</h4></div>
            <div className="bd">
              {riskTotal === 0 ? (
                <span className="muted">Sem pacientes ativos ainda.</span>
              ) : (
                <>
                  <div className="mg-riskbar" role="img" aria-label="Distribuição de risco">
                    {RISK.map((r) => {
                      const n = data.risk[r.key];
                      return n > 0 ? (
                        <span key={r.key} style={{ width: `${(n / riskTotal) * 100}%`, background: r.color }} title={`${r.label}: ${n}`} />
                      ) : null;
                    })}
                  </div>
                  <div className="mg-risklegend">
                    {RISK.map((r) => (
                      <span key={r.key} className="mg-risk-item">
                        <span className="dot" style={{ background: r.color }} /> {r.label} <b>{data.risk[r.key]}</b>
                      </span>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>

          <div className="card mg-card">
            <div className="hd"><h4>Por médico</h4></div>
            <div className="bd mg-table">
              <table>
                <thead>
                  <tr>
                    <th>Médico</th>
                    <th className="tnum">Pacientes</th>
                    <th className="tnum">Consultas</th>
                    <th className="tnum">Repasse</th>
                    <th className="tnum">A receber</th>
                    <th className="tnum">Clínica</th>
                  </tr>
                </thead>
                <tbody>
                  {data.doctors.map((d) => (
                    <tr key={d.doctor_id}>
                      <td>{d.name}</td>
                      <td className="tnum">{d.patients}</td>
                      <td className="tnum">{d.appointments_completed}</td>
                      <td className="tnum ok">{brl(d.received_cents)}</td>
                      <td className="tnum warn">{brl(d.to_receive_cents)}</td>
                      <td className="tnum">{brl(d.clinic_cents)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </AppShell>
  );
}

function Kpi({ label, value, note, stripe }: { label: string; value: string; note?: string; stripe?: string }) {
  return (
    <div className="mg-kpi">
      {stripe ? <div className="mg-kpi-stripe" style={{ background: stripe }} /> : null}
      <span className="mg-kpi-lab">{label}</span>
      <b className="mg-kpi-val">{value}</b>
      {note ? <span className="mg-kpi-note">{note}</span> : null}
    </div>
  );
}
