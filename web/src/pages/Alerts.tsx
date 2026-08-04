import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { RiskBadge } from "../components/RiskBadge";
import { ThemeToggle } from "../components/ThemeToggle";
import { alerts as alertsApi, patients as patientsApi } from "../api/endpoints";
import { ApiError } from "../api/client";
import { useAsync } from "../lib/useAsync";
import { RISK_ORDER } from "../lib/format";
import type { Alert, AlertStatus, RiskLevel } from "../api/types";
import "./Alerts.css";

type Filter = "open" | "resolved" | "all";

const BAR: Record<RiskLevel, string> = {
  green: "var(--risk-green)",
  yellow: "var(--risk-yellow)",
  orange: "var(--risk-orange)",
  red: "var(--risk-red)",
};

function statusLabel(s: AlertStatus): string {
  return s === "resolved"
    ? "resolvido"
    : s === "acknowledged"
      ? "em acompanhamento"
      : s === "notified"
        ? "notificado"
        : "aberto";
}

export function Alerts() {
  const navigate = useNavigate();
  const names = useAsync(() => patientsApi.list(), []);
  const [list, setList] = useState<Alert[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("open");
  const [busy, setBusy] = useState<string | null>(null);

  function load() {
    setError(null);
    alertsApi
      .list()
      .then(setList)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Falha ao carregar os alertas."));
  }
  useEffect(load, []);

  const nameOf = useMemo(() => {
    const m = new Map<string, string>();
    (names.data ?? []).forEach((p) => m.set(p.id, p.name));
    return (id: string) => m.get(id) ?? "Paciente";
  }, [names.data]);

  const rows = useMemo(() => {
    let r = [...(list ?? [])];
    if (filter === "open") r = r.filter((a) => a.status !== "resolved");
    if (filter === "resolved") r = r.filter((a) => a.status === "resolved");
    return r.sort(
      (a, b) =>
        RISK_ORDER[b.level] - RISK_ORDER[a.level] || b.created_at.localeCompare(a.created_at),
    );
  }, [list, filter]);

  const openCount = (list ?? []).filter((a) => a.status !== "resolved").length;

  async function setStatus(a: Alert, status: AlertStatus) {
    setBusy(a.id);
    try {
      const updated = await alertsApi.updateStatus(a.id, status);
      setList((prev) => (prev ? prev.map((x) => (x.id === a.id ? updated : x)) : prev));
    } catch {
      /* mantém estado */
    } finally {
      setBusy(null);
    }
  }

  return (
    <AppShell title="Alertas" subtitle={`${openCount} em aberto`} alertCount={openCount} actions={<ThemeToggle />}>
      <div className="panel">
        <div className="panel-head">
          <h3>Alertas</h3>
          <span className="hint">gerados por check-ins, não-adesão e risco no chat</span>
          <div className="seg">
            <button className={filter === "open" ? "on" : ""} onClick={() => setFilter("open")}>
              Em aberto
            </button>
            <button className={filter === "resolved" ? "on" : ""} onClick={() => setFilter("resolved")}>
              Resolvidos
            </button>
            <button className={filter === "all" ? "on" : ""} onClick={() => setFilter("all")}>
              Todos
            </button>
          </div>
        </div>

        {error ? (
          <div className="state">
            <span className="err">{error}</span>
          </div>
        ) : !list ? (
          <div className="state">
            <div className="spinner" />
          </div>
        ) : rows.length === 0 ? (
          <div className="state">Nenhum alerta {filter === "open" ? "em aberto" : ""}. 🎉</div>
        ) : (
          <div className="alerts-list">
            {rows.map((a) => (
              <div className="alert-row" key={a.id}>
                <span className="sev" style={{ background: BAR[a.level] }} />
                <div className="alert-main">
                  <div className="alert-top">
                    <button className="pt-link" onClick={() => navigate(`/pacientes/${a.patient_id}`)}>
                      {nameOf(a.patient_id)}
                    </button>
                    <RiskBadge level={a.level} />
                    {a.urgency === "immediate" ? <span className="chip alert">urgente</span> : null}
                  </div>
                  <p className="alert-reason">{a.reason}</p>
                  <span className="alert-meta">
                    {statusLabel(a.status)} ·{" "}
                    {new Date(a.created_at).toLocaleString("pt-BR", {
                      day: "2-digit",
                      month: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
                <div className="alert-actions">
                  {a.status !== "acknowledged" && a.status !== "resolved" ? (
                    <button
                      className="btn ghost sm"
                      disabled={busy === a.id}
                      onClick={() => setStatus(a, "acknowledged")}
                    >
                      Reconhecer
                    </button>
                  ) : null}
                  {a.status !== "resolved" ? (
                    <button className="btn sm" disabled={busy === a.id} onClick={() => setStatus(a, "resolved")}>
                      Resolver
                    </button>
                  ) : (
                    <span className="chip">✓ resolvido</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
