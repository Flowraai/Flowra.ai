import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { RiskBadge } from "../components/RiskBadge";
import { ThemeToggle } from "../components/ThemeToggle";
import { ChatPanel } from "../components/ChatPanel";
import { MedicationCard } from "../components/MedicationCard";
import { AppointmentsCard } from "../components/AppointmentsCard";
import { ExamsCard } from "../components/ExamsCard";
import { PrescriptionsCard } from "../components/PrescriptionsCard";
import { EditPatientModal } from "../components/EditPatientModal";
import { IconAlertTri, IconChart, IconSpark } from "../components/icons";
import { useAsync } from "../lib/useAsync";
import { ApiError } from "../api/client";
import { patients, alerts as alertsApi } from "../api/endpoints";
import { avatarGradient, initials, num, RISK_LABEL, shortDay } from "../lib/format";
import type { Alert, CheckIn, RiskLevel } from "../api/types";
import "./PatientDetail.css";

function age(birth: string | null): string | null {
  if (!birth) return null;
  const b = new Date(birth);
  const now = new Date();
  let a = now.getFullYear() - b.getFullYear();
  if (now.getMonth() < b.getMonth() || (now.getMonth() === b.getMonth() && now.getDate() < b.getDate())) a--;
  return a >= 0 && a < 130 ? `${a} anos` : null;
}

function sleepLabel(ci: CheckIn): string {
  const s = ci.structured_responses["slept_well"];
  if (s === "sim") return "bom";
  if (s === "nao" || s === "não") return "ruim";
  const h = num(ci.structured_responses["sleep_hours"]);
  return h != null ? `${h}h` : "—";
}

export function PatientDetail() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [reloadKey, setReloadKey] = useState(0);
  const patient = useAsync(() => patients.get(id), [id, reloadKey]);
  const summary = useAsync(() => patients.summary(id), [id]);
  const checkins = useAsync(() => patients.checkins(id, 7), [id]);
  const alertList = useAsync(() => alertsApi.list(), [id]);
  const [showEdit, setShowEdit] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const p = patient.data;

  async function exportData() {
    setExporting(true);
    setExportError(null);
    try {
      const data = await patients.export(id);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const slug = (p?.name ?? "paciente").normalize("NFD").replace(/[^\w]+/g, "-").toLowerCase();
      a.href = url;
      a.download = `flowra-${slug}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setExportError(e instanceof ApiError ? e.message : "Falha ao exportar.");
    } finally {
      setExporting(false);
    }
  }
  const meta = [age(p?.birth_date ?? null), p?.contact].filter(Boolean) as string[];
  const patientAlerts = (alertList.data ?? []).filter((a) => a.patient_id === id);
  const openAlerts = patientAlerts.filter((a) => a.status !== "resolved");

  return (
    <AppShell
      title={
        <>
          <span className="muted" style={{ fontWeight: 500, cursor: "pointer" }} onClick={() => navigate("/")}>
            Pacientes
          </span>
          <span className="muted">/</span> {p?.name ?? "…"}
        </>
      }
      subtitle="Protocolo psiquiátrico diário"
      actions={
        <>
          <ThemeToggle />
          {p ? (
            <button className="btn ghost" onClick={() => setShowEdit(true)}>
              Editar
            </button>
          ) : null}
          <button className="btn ghost" onClick={exportData} disabled={exporting || !p}>
            {exporting ? "Exportando…" : "Exportar dados (LGPD)"}
          </button>
        </>
      }
    >
      {patient.error ? (
        <div className="state">
          <span className="err">{patient.error}</span>
        </div>
      ) : (
        <>
          <div className="detail-head">
            <div
              className="pt-avatar"
              style={{ width: 46, height: 46, fontSize: 16, background: avatarGradient(p?.current_risk ?? "green") }}
            >
              {p ? initials(p.name) : "—"}
            </div>
            <div>
              <h3>{p?.name ?? "Carregando…"}</h3>
              <div className="meta">
                {meta.map((m) => (
                  <span key={m}>{m}</span>
                ))}
              </div>
            </div>
            {p ? (
              <div className="head-risk">
                <RiskBadge level={p.current_risk} label={`Risco: ${RISK_LABEL[p.current_risk]}`} />
              </div>
            ) : null}
          </div>

          <div className="grid2">
            <div className="col">
              <div className="card ai">
                <div className="hd">
                  <IconSpark width={16} height={16} color="var(--accent)" />
                  <h4>Resumo por IA</h4>
                  {summary.data ? (
                    <span className="tag">{summary.data.generated_by === "llm" ? "IA" : "resumo automático"}</span>
                  ) : null}
                </div>
                <div className="bd">
                  {summary.loading ? (
                    <span className="muted">Gerando resumo…</span>
                  ) : summary.error ? (
                    <span className="muted">{summary.error}</span>
                  ) : (
                    <SummaryBody text={summary.data!.summary} ctx={summary.data!.context} />
                  )}
                </div>
              </div>

              <div className="card">
                <div className="hd">
                  <IconChart width={16} height={16} color="var(--muted)" />
                  <h4>Check-ins recentes</h4>
                  <span className="muted" style={{ marginLeft: "auto", fontSize: 12 }}>
                    últimos {checkins.data?.length ?? 0}
                  </span>
                </div>
                {checkins.loading ? (
                  <div className="state">
                    <div className="spinner" />
                  </div>
                ) : checkins.data && checkins.data.length > 0 ? (
                  <div className="checkins">
                    {checkins.data.map((ci) => (
                      <CheckinRow key={ci.id} ci={ci} sleep={sleepLabel(ci)} />
                    ))}
                  </div>
                ) : (
                  <div className="state">Sem check-ins registrados ainda.</div>
                )}
              </div>

              <div className="card">
                <div className="hd">
                  <IconAlertTri width={16} height={16} color="var(--risk-orange)" />
                  <h4>Alertas</h4>
                  <span className="muted" style={{ marginLeft: "auto", fontSize: 12 }}>
                    {openAlerts.length} aberto(s) · {patientAlerts.length - openAlerts.length} resolvido(s)
                  </span>
                </div>
                {alertList.loading ? (
                  <div className="state">
                    <div className="spinner" />
                  </div>
                ) : patientAlerts.length > 0 ? (
                  <div>
                    {patientAlerts.slice(0, 6).map((a) => (
                      <AlertItem key={a.id} a={a} />
                    ))}
                  </div>
                ) : (
                  <div className="state">Nenhum alerta para este paciente.</div>
                )}
              </div>

              <ExamsCard patientId={id} />
            </div>

            <div className="col">
              <ChatPanel patientId={id} />
              <MedicationCard patientId={id} />
              <AppointmentsCard patientId={id} />
              <PrescriptionsCard patientId={id} />
            </div>
          </div>
        </>
      )}

      {exportError ? (
        <p className="muted" style={{ color: "var(--risk-red)", fontSize: 13 }}>{exportError}</p>
      ) : null}

      {showEdit && p ? (
        <EditPatientModal
          patient={p}
          onClose={() => setShowEdit(false)}
          onSaved={() => {
            setShowEdit(false);
            setReloadKey((k) => k + 1);
          }}
          onDeleted={() => navigate("/", { replace: true })}
        />
      ) : null}
    </AppShell>
  );
}

function SummaryBody({ text, ctx }: { text: string; ctx: Record<string, unknown> }) {
  const chips: string[] = [];
  const mood = num(ctx["avg_mood"]);
  const anx = num(ctx["avg_anxiety"]);
  const adh = ctx["adherence"] as Record<string, unknown> | undefined;
  const rate = adh ? num(adh["adherence_rate"]) : null;
  if (mood != null) chips.push(`humor médio ${mood}/10`);
  if (anx != null) chips.push(`ansiedade média ${anx}/10`);
  if (rate != null) chips.push(`adesão ${Math.round(rate * 100)}%`);
  const crises = num(ctx["crises_recent"]);
  if (crises) chips.push(`${crises} crise(s)`);
  return (
    <>
      <span style={{ lineHeight: 1.6 }}>{text}</span>
      {chips.length > 0 ? (
        <div className="ai-foot">
          {chips.map((c) => (
            <span className="chip" key={c}>
              {c}
            </span>
          ))}
        </div>
      ) : null}
    </>
  );
}

const EMOJI: Record<RiskLevel, string> = { green: "🟢", yellow: "🟡", orange: "🟠", red: "🔴" };
const BAR: Record<RiskLevel, string> = {
  green: "var(--risk-green)",
  yellow: "var(--risk-yellow)",
  orange: "var(--risk-orange)",
  red: "var(--risk-red)",
};

function CheckinRow({ ci, sleep }: { ci: CheckIn; sleep: string }) {
  const mood = num(ci.structured_responses["mood"]);
  const anx = num(ci.structured_responses["anxiety"]);
  return (
    <div className="ci-row">
      <span className="ci-day">{shortDay(ci.created_at)}</span>
      <div className="ci-metrics">
        <span>
          Humor <b>{mood ?? "—"}</b>/10
          {mood != null ? (
            <span className="bar">
              <i style={{ width: `${mood * 10}%`, background: BAR[ci.risk_level] }} />
            </span>
          ) : null}
        </span>
        <span>
          Ansiedade <b>{anx ?? "—"}</b>/10
        </span>
        <span>
          Sono <b>{sleep}</b>
        </span>
      </div>
      <span className={`risk ${ci.risk_level}`}>
        <span className="dot" /> {EMOJI[ci.risk_level]}
      </span>
    </div>
  );
}

function AlertItem({ a }: { a: Alert }) {
  const when = new Date(a.created_at).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
  return (
    <div className="alert-item">
      <span className="sev" style={{ background: BAR[a.level] }} />
      <div className="txt">
        <b>{a.reason}</b>
        <p>
          {a.urgency === "immediate" ? "Urgente" : "Rotina"} ·{" "}
          {a.status === "resolved" ? "resolvido" : a.status === "acknowledged" ? "em acompanhamento" : "aberto"}
        </p>
      </div>
      <span className="when">{when}</span>
    </div>
  );
}
