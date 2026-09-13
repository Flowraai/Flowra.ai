import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { patients } from "../api/endpoints";
import { RISK_LABEL } from "../lib/format";
import type {
  Appointment, CheckIn, ClinicalNote, MedicationAdherence, MedicationPlan,
  Patient, PatientSummary, ScaleEntry,
} from "../api/types";
import "./PatientReport.css";

function age(birth: string | null): string | null {
  if (!birth) return null;
  const b = new Date(birth);
  const now = new Date();
  let a = now.getFullYear() - b.getFullYear();
  if (now.getMonth() < b.getMonth() || (now.getMonth() === b.getMonth() && now.getDate() < b.getDate())) a--;
  return a >= 0 && a < 130 ? `${a} anos` : null;
}
function toNum(v: unknown): number | null {
  if (typeof v === "number") return v;
  if (typeof v === "string") {
    const n = Number(v.replace(",", "."));
    return Number.isFinite(n) ? n : null;
  }
  return null;
}
function avg(xs: number[]): string {
  return xs.length ? (xs.reduce((a, b) => a + b, 0) / xs.length).toFixed(1) : "—";
}
function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
}
function fmtDT(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit" });
}

const KIND_LABEL: Record<string, string> = { note: "Anotação", diagnosis: "Diagnóstico", other: "Outro" };

export function PatientReport() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const { doctor } = useAuth();

  const [patient, setPatient] = useState<Patient | null>(null);
  const [summary, setSummary] = useState<PatientSummary | null>(null);
  const [checkins, setCheckins] = useState<CheckIn[]>([]);
  const [scales, setScales] = useState<ScaleEntry[]>([]);
  const [adherence, setAdherence] = useState<MedicationAdherence | null>(null);
  const [meds, setMeds] = useState<MedicationPlan[]>([]);
  const [appts, setAppts] = useState<Appointment[]>([]);
  const [notes, setNotes] = useState<ClinicalNote[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    (async () => {
      const [p, s, c, sc, ad, m, ap, nt] = await Promise.allSettled([
        patients.get(id),
        patients.summary(id),
        patients.checkins(id, 60),
        patients.scales(id),
        patients.adherence(id),
        patients.medications(id),
        patients.appointments(id),
        patients.notes(id),
      ]);
      if (!active) return;
      if (p.status === "fulfilled") setPatient(p.value);
      if (s.status === "fulfilled") setSummary(s.value);
      if (c.status === "fulfilled") setCheckins(c.value);
      if (sc.status === "fulfilled") setScales(sc.value);
      if (ad.status === "fulfilled") setAdherence(ad.value);
      if (m.status === "fulfilled") setMeds(m.value);
      if (ap.status === "fulfilled") setAppts(ap.value);
      if (nt.status === "fulfilled") setNotes(nt.value);
      setLoading(false);
    })();
    return () => { active = false; };
  }, [id]);

  const evo = useMemo(() => {
    const since = Date.now() - 30 * 86400000;
    const rows = checkins.filter((c) => new Date(c.created_at).getTime() >= since);
    const pick = (code: string) => rows.map((c) => toNum(c.structured_responses?.[code])).filter((v): v is number => v !== null);
    return { n: rows.length, mood: avg(pick("mood")), anx: avg(pick("anxiety")), sleep: avg(pick("sleep_hours")) };
  }, [checkins]);

  // Última pontuação por escala (done).
  const lastScales = useMemo(() => {
    const byCode = new Map<string, ScaleEntry>();
    for (const e of scales) {
      if (e.status !== "done") continue;
      const cur = byCode.get(e.scale_code);
      if (!cur || (e.completed_at ?? "") > (cur.completed_at ?? "")) byCode.set(e.scale_code, e);
    }
    return [...byCode.values()];
  }, [scales]);

  const activeMeds = meds.filter((m) => m.active);
  const upcoming = appts
    .filter((a) => (a.status === "scheduled" || a.status === "confirmed") && new Date(a.scheduled_at).getTime() >= Date.now())
    .sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at));

  if (loading) {
    return <div className="rep-loading"><div className="spinner" /> Gerando relatório…</div>;
  }
  if (!patient) {
    return <div className="rep-loading">Paciente não encontrado.</div>;
  }

  const meta = [age(patient.birth_date), patient.contact].filter(Boolean).join(" · ");
  const clinic = doctor?.clinic || doctor?.tenant_name || "Flowra Care";

  return (
    <div className="rep">
      <div className="rep-toolbar no-print">
        <button className="btn ghost" onClick={() => navigate(`/pacientes/${id}`)}>← Voltar</button>
        <button className="btn" onClick={() => window.print()}>Imprimir / Salvar em PDF</button>
      </div>

      <div className="rep-doc">
        <header className="rep-head">
          <div>
            <div className="rep-clinic">{clinic}</div>
            <div className="rep-doctor">
              {doctor?.name}{doctor?.specialty ? ` — ${doctor.specialty}` : ""}
              {doctor?.council_id ? ` · ${doctor.council_id}` : ""}
            </div>
          </div>
          <div className="rep-meta-right">
            Emitido em {new Date().toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" })}
          </div>
        </header>

        <h1 className="rep-title">Relatório de acompanhamento</h1>
        <div className="rep-patient">
          <b>{patient.name}</b>
          {meta ? <span> · {meta}</span> : null}
          <span className="rep-risk">Risco atual: {RISK_LABEL[patient.current_risk]}</span>
        </div>

        {summary ? (
          <section className="rep-sec">
            <h2>Resumo</h2>
            <p>{summary.summary}</p>
          </section>
        ) : null}

        <section className="rep-sec">
          <h2>Evolução (últimos 30 dias)</h2>
          <table className="rep-kv">
            <tbody>
              <tr><td>Check-ins respondidos</td><td>{evo.n}</td></tr>
              <tr><td>Humor médio</td><td>{evo.mood}/10</td></tr>
              <tr><td>Ansiedade média</td><td>{evo.anx}/10</td></tr>
              <tr><td>Sono médio</td><td>{evo.sleep} h/noite</td></tr>
            </tbody>
          </table>
        </section>

        {lastScales.length ? (
          <section className="rep-sec">
            <h2>Escalas clínicas</h2>
            <table className="rep-table">
              <thead><tr><th>Instrumento</th><th>Pontuação</th><th>Gravidade</th><th>Data</th></tr></thead>
              <tbody>
                {lastScales.map((e) => (
                  <tr key={e.id}>
                    <td>{e.scale_name}</td>
                    <td>{e.score}</td>
                    <td>{e.severity}{e.flagged ? " ⚠️" : ""}</td>
                    <td>{e.completed_at ? fmtDate(e.completed_at) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        ) : null}

        <section className="rep-sec">
          <h2>Medicação</h2>
          {adherence ? (
            <p>Adesão (30 dias): <b>{Math.round(adherence.adherence_rate * 100)}%</b> — {adherence.taken} tomadas, {adherence.later} adiadas, {adherence.missed} perdidas.</p>
          ) : null}
          {activeMeds.length ? (
            <ul className="rep-list">
              {activeMeds.map((m) => (
                <li key={m.id}>{m.name} {m.dose} — {m.times.join(", ")}</li>
              ))}
            </ul>
          ) : <p className="rep-muted">Sem medicação ativa cadastrada.</p>}
        </section>

        {upcoming.length ? (
          <section className="rep-sec">
            <h2>Próximas consultas</h2>
            <ul className="rep-list">
              {upcoming.slice(0, 5).map((a) => (
                <li key={a.id}>{fmtDT(a.scheduled_at)} — {a.kind === "return" ? "Retorno" : "Consulta"}{a.location ? ` · ${a.location}` : ""}</li>
              ))}
            </ul>
          </section>
        ) : null}

        {notes.length ? (
          <section className="rep-sec">
            <h2>Anotações e diagnósticos</h2>
            {notes.slice(0, 12).map((n) => (
              <div className="rep-note" key={n.id}>
                <div className="rep-note-h"><b>{KIND_LABEL[n.kind] ?? "Anotação"}</b> <span>{fmtDate(n.created_at)}</span></div>
                <p>{n.body}</p>
              </div>
            ))}
          </section>
        ) : null}

        <footer className="rep-foot">
          Documento gerado pelo Flowra Care em {new Date().toLocaleString("pt-BR")}. Uso clínico;
          contém dados sensíveis (LGPD) — trate com sigilo.
        </footer>
      </div>
    </div>
  );
}
