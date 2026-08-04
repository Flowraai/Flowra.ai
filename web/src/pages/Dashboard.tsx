import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { RiskBadge } from "../components/RiskBadge";
import { ThemeToggle } from "../components/ThemeToggle";
import { NewPatientModal } from "../components/NewPatientModal";
import { IconPlus, IconSearch } from "../components/icons";
import { useAsync } from "../lib/useAsync";
import { patients } from "../api/endpoints";
import { avatarGradient, initials, relativeDate, RISK_ORDER } from "../lib/format";
import type { PatientPanelItem, RiskLevel } from "../api/types";
import "./Dashboard.css";

type Filter = "all" | "attention" | "inactive";

function isToday(iso: string | null): boolean {
  if (!iso) return false;
  const d = new Date(iso);
  const n = new Date();
  return d.getFullYear() === n.getFullYear() && d.getMonth() === n.getMonth() && d.getDate() === n.getDate();
}

export function Dashboard() {
  const navigate = useNavigate();
  const [reloadKey, setReloadKey] = useState(0);
  const { data, loading, error } = useAsync(() => patients.list(), [reloadKey]);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [showNew, setShowNew] = useState(false);

  const list = data ?? [];
  const kpis = useMemo(() => {
    const openAlerts = list.reduce((s, p) => s + p.open_alerts, 0);
    const elevated = list.filter((p) => p.current_risk === "orange" || p.current_risk === "red").length;
    const noCheckinToday = list.filter((p) => !isToday(p.last_checkin_at)).length;
    const stable = list.filter((p) => p.current_risk === "green").length;
    return { openAlerts, elevated, noCheckinToday, stable, total: list.length };
  }, [list]);

  const rows = useMemo(() => {
    let r = [...list].sort(
      (a, b) =>
        RISK_ORDER[b.current_risk] - RISK_ORDER[a.current_risk] ||
        (a.last_checkin_at ?? "").localeCompare(b.last_checkin_at ?? ""),
    );
    if (filter === "attention") r = r.filter((p) => RISK_ORDER[p.current_risk] >= 2 || p.open_alerts > 0);
    if (filter === "inactive") r = r.filter((p) => p.inactive);
    if (query.trim()) r = r.filter((p) => p.name.toLowerCase().includes(query.trim().toLowerCase()));
    return r;
  }, [list, filter, query]);

  const today = new Date().toLocaleDateString("pt-BR", { weekday: "long", day: "2-digit", month: "long" });

  return (
    <AppShell
      title="Painel"
      subtitle={`${today} · ${kpis.total} paciente(s) em acompanhamento`}
      alertCount={kpis.openAlerts}
      actions={
        <>
          <div className="search">
            <IconSearch width={15} height={15} />
            <input
              placeholder="Buscar paciente…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="Buscar paciente"
            />
          </div>
          <ThemeToggle />
          <button className="btn" onClick={() => setShowNew(true)}>
            <IconPlus width={15} height={15} /> Novo paciente
          </button>
        </>
      }
    >
      <div className="kpis">
        <Kpi color="var(--risk-red)" label="Alertas em aberto" value={kpis.openAlerts} note="somando todos os pacientes" />
        <Kpi color="var(--risk-orange)" label="Em risco elevado" value={kpis.elevated} note="🟠 laranja + 🔴 vermelho" />
        <Kpi
          color="var(--risk-yellow)"
          label="Sem check-in hoje"
          value={kpis.noCheckinToday}
          note={`de ${kpis.total} pacientes`}
        />
        <Kpi color="var(--risk-green)" label="Estáveis" value={kpis.stable} note="check-in em dia" />
      </div>

      <div className="panel">
        <div className="panel-head">
          <h3>Pacientes por prioridade</h3>
          <span className="hint">ordenado por risco, depois por check-in mais antigo</span>
          <div className="seg">
            <button className={filter === "all" ? "on" : ""} onClick={() => setFilter("all")}>
              Todos
            </button>
            <button className={filter === "attention" ? "on" : ""} onClick={() => setFilter("attention")}>
              Precisam de atenção
            </button>
            <button className={filter === "inactive" ? "on" : ""} onClick={() => setFilter("inactive")}>
              Inativos
            </button>
          </div>
        </div>

        {loading ? (
          <div className="state">
            <div className="spinner" />
            Carregando pacientes…
          </div>
        ) : error ? (
          <div className="state">
            <span className="err">{error}</span>
          </div>
        ) : rows.length === 0 ? (
          <div className="state">Nenhum paciente encontrado.</div>
        ) : (
          <div className="table">
            <table>
              <thead>
                <tr>
                  <th>Paciente</th>
                  <th>Risco</th>
                  <th>Último check-in</th>
                  <th>Alertas</th>
                  <th>Situação</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((p) => (
                  <PatientRow key={p.id} p={p} onOpen={() => navigate(`/pacientes/${p.id}`)} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showNew ? (
        <NewPatientModal onClose={() => setShowNew(false)} onCreated={() => setReloadKey((k) => k + 1)} />
      ) : null}
    </AppShell>
  );
}

function Kpi({ color, label, value, note }: { color: string; label: string; value: number; note: string }) {
  return (
    <div className="tile">
      <span className="stripe" style={{ background: color }} />
      <span className="lab">{label}</span>
      <span className="val tnum" style={{ color }}>
        {value}
      </span>
      <span className="delta">{note}</span>
    </div>
  );
}

function PatientRow({ p, onOpen }: { p: PatientPanelItem; onOpen: () => void }) {
  const stripe: Record<RiskLevel, string> = {
    green: "var(--risk-green)",
    yellow: "var(--risk-yellow)",
    orange: "var(--risk-orange)",
    red: "var(--risk-red)",
  };
  return (
    <tr onClick={onOpen}>
      <td className="patient">
        <span className="sev-stripe" style={{ background: stripe[p.current_risk] }} />
        <div className="row">
          <div className="pt-avatar" style={{ width: 34, height: 34, fontSize: 12.5, background: avatarGradient(p.current_risk) }}>
            {initials(p.name)}
          </div>
          <div className="pt-name">
            <b>{p.name}</b>
          </div>
        </div>
      </td>
      <td>
        <RiskBadge level={p.current_risk} />
      </td>
      <td className={`tnum ${p.inactive ? "warn" : ""}`}>{relativeDate(p.last_checkin_at)}</td>
      <td>{p.open_alerts > 0 ? <span className="chip alert">{p.open_alerts} aberto(s)</span> : <span className="chip">—</span>}</td>
      <td>
        {p.inactive ? (
          <span className="chip alert">
            {p.days_since_checkin != null ? `${p.days_since_checkin}d sem check-in` : "inativo"}
          </span>
        ) : (
          <span className="muted" style={{ fontSize: 12.5 }}>em dia</span>
        )}
      </td>
      <td className="muted">›</td>
    </tr>
  );
}
