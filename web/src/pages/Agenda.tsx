import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { ThemeToggle } from "../components/ThemeToggle";
import { appointments as apptApi, patients as patientsApi } from "../api/endpoints";
import { ApiError } from "../api/client";
import { useAsync } from "../lib/useAsync";
import type { Appointment, AppointmentKind, AppointmentStatus } from "../api/types";
import "./Agenda.css";

const KIND: Record<AppointmentKind, string> = { consultation: "Consulta", return: "Retorno" };
const STATUS: Record<AppointmentStatus, { label: string; cls: string }> = {
  scheduled: { label: "Agendada", cls: "s-open" },
  confirmed: { label: "Confirmada", cls: "s-ok" },
  cancelled: { label: "Cancelada", cls: "s-off" },
  completed: { label: "Concluída", cls: "s-done" },
};

function dayKey(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("pt-BR", { weekday: "long", day: "2-digit", month: "long" });
}
function timeOf(iso: string): string {
  return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}
// Valor inicial do <input type="datetime-local"> a partir de um ISO (hora local).
function toLocalInput(iso: string): string {
  const d = new Date(iso);
  const off = d.getTimezoneOffset() * 60000;
  return new Date(d.getTime() - off).toISOString().slice(0, 16);
}

export function Agenda() {
  const navigate = useNavigate();
  const names = useAsync(() => patientsApi.list(), []);
  const [list, setList] = useState<Appointment[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [when, setWhen] = useState("");

  function load() {
    setError(null);
    apptApi
      .upcoming()
      .then(setList)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Falha ao carregar a agenda."));
  }
  useEffect(load, []);

  const nameOf = useMemo(() => {
    const m = new Map<string, string>();
    (names.data ?? []).forEach((p) => m.set(p.id, p.name));
    return (id: string) => m.get(id) ?? "Paciente";
  }, [names.data]);

  const groups = useMemo(() => {
    const rows = [...(list ?? [])].sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at));
    const map = new Map<string, Appointment[]>();
    for (const a of rows) {
      const k = dayKey(a.scheduled_at);
      (map.get(k) ?? map.set(k, []).get(k)!).push(a);
    }
    return [...map.entries()];
  }, [list]);

  function apply(updated: Appointment) {
    setList((prev) => (prev ? prev.map((x) => (x.id === updated.id ? updated : x)) : prev));
  }

  async function setStatus(a: Appointment, status: AppointmentStatus) {
    setBusy(a.id);
    try {
      const updated = await apptApi.update(a.id, { status });
      // Concluída/cancelada saem da lista de "próximas" no próximo load; aqui só reflete.
      if (status === "completed" || status === "cancelled") {
        setList((prev) => (prev ? prev.filter((x) => x.id !== a.id) : prev));
      } else {
        apply(updated);
      }
    } catch {
      /* mantém */
    } finally {
      setBusy(null);
    }
  }

  function startEdit(a: Appointment) {
    setEditing(a.id);
    setWhen(toLocalInput(a.scheduled_at));
  }

  async function saveReschedule(a: Appointment) {
    if (!when) return;
    setBusy(a.id);
    try {
      const iso = new Date(when).toISOString();
      const updated = await apptApi.update(a.id, { scheduled_at: iso });
      apply(updated);
      setEditing(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Não foi possível remarcar.");
    } finally {
      setBusy(null);
    }
  }

  const pending = (list ?? []).filter((a) => a.reschedule_requested_at).length;

  return (
    <AppShell
      title="Agenda"
      subtitle={`${(list ?? []).length} consulta(s) à frente`}
      actions={<ThemeToggle />}
    >
      <div className="panel">
        <div className="panel-head">
          <h3>Próximas consultas</h3>
          <span className="hint">
            {pending > 0
              ? `${pending} pedido(s) de remarcação aguardando`
              : "lembretes automáticos são enviados 24h antes"}
          </span>
        </div>

        {error ? (
          <div className="state">
            <span className="err">{error}</span>
          </div>
        ) : !list ? (
          <div className="state">
            <div className="spinner" />
          </div>
        ) : groups.length === 0 ? (
          <div className="state">Nenhuma consulta agendada. Marque uma na ficha do paciente.</div>
        ) : (
          <div className="agenda">
            {groups.map(([day, rows]) => (
              <div className="agenda-day" key={day}>
                <div className="agenda-daylabel">{day}</div>
                {rows.map((a) => {
                  const st = STATUS[a.status];
                  const wantsReschedule = Boolean(a.reschedule_requested_at);
                  return (
                    <div className={`agenda-row ${wantsReschedule ? "flagged" : ""}`} key={a.id}>
                      <span className="agenda-time tnum">{timeOf(a.scheduled_at)}</span>
                      <div className="agenda-main">
                        <div className="agenda-top">
                          <button className="pt-link" onClick={() => navigate(`/pacientes/${a.patient_id}`)}>
                            {nameOf(a.patient_id)}
                          </button>
                          <span className="agenda-kind">{KIND[a.kind]}</span>
                          <span className={`appt-status ${st.cls}`}>{st.label}</span>
                          {wantsReschedule ? <span className="chip alert">quer remarcar</span> : null}
                        </div>
                        {a.location ? <div className="agenda-loc">📍 {a.location}</div> : null}
                        {a.reschedule_note ? (
                          <div className="agenda-note">"{a.reschedule_note}"</div>
                        ) : null}

                        {editing === a.id ? (
                          <div className="agenda-edit">
                            <input
                              type="datetime-local"
                              value={when}
                              onChange={(e) => setWhen(e.target.value)}
                            />
                            <button className="btn sm" disabled={busy === a.id} onClick={() => saveReschedule(a)}>
                              Salvar novo horário
                            </button>
                            <button className="btn ghost sm" onClick={() => setEditing(null)}>
                              Cancelar
                            </button>
                          </div>
                        ) : null}
                      </div>

                      {editing !== a.id ? (
                        <div className="agenda-actions">
                          <button className="mini" disabled={busy === a.id} onClick={() => startEdit(a)}>
                            Remarcar
                          </button>
                          {a.status !== "confirmed" ? (
                            <button className="mini" disabled={busy === a.id} onClick={() => setStatus(a, "confirmed")}>
                              Confirmar
                            </button>
                          ) : null}
                          <button className="mini" disabled={busy === a.id} onClick={() => setStatus(a, "completed")}>
                            Concluir
                          </button>
                          <button className="mini danger" disabled={busy === a.id} onClick={() => setStatus(a, "cancelled")}>
                            Cancelar
                          </button>
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
