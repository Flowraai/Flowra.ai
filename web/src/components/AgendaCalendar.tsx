import { useEffect, useMemo, useState } from "react";
import { appointments as apptApi } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { Appointment, AppointmentStatus } from "../api/types";
import "./AgendaCalendar.css";

const WEEKDAYS = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];
const STATUS_CLS: Record<AppointmentStatus, string> = {
  scheduled: "c-open",
  confirmed: "c-ok",
  cancelled: "c-off",
  completed: "c-done",
};

function ymd(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function sameYmd(iso: string, d: Date): boolean {
  const a = new Date(iso);
  return a.getFullYear() === d.getFullYear() && a.getMonth() === d.getMonth() && a.getDate() === d.getDate();
}
function timeOf(iso: string): string {
  return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

export function AgendaCalendar({
  nameOf,
  onOpenPatient,
}: {
  nameOf: (id: string) => string;
  onOpenPatient: (id: string) => void;
}) {
  const [month, setMonth] = useState(() => {
    const n = new Date();
    return new Date(n.getFullYear(), n.getMonth(), 1);
  });
  const [list, setList] = useState<Appointment[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null); // ymd do dia clicado

  // 42 células a partir do domingo anterior ao dia 1.
  const cells = useMemo(() => {
    const first = new Date(month.getFullYear(), month.getMonth(), 1);
    const start = new Date(first);
    start.setDate(1 - first.getDay());
    return Array.from({ length: 42 }, (_, i) => {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      return d;
    });
  }, [month]);

  useEffect(() => {
    setError(null);
    setSelected(null);
    const start = cells[0];
    const end = new Date(cells[41]);
    end.setDate(end.getDate() + 1);
    apptApi
      .range(new Date(start.getFullYear(), start.getMonth(), start.getDate()).toISOString(), end.toISOString())
      .then(setList)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Falha ao carregar o calendário."));
  }, [cells]);

  const byDay = useMemo(() => {
    const m = new Map<string, Appointment[]>();
    for (const a of list ?? []) {
      const k = ymd(new Date(a.scheduled_at));
      (m.get(k) ?? m.set(k, []).get(k)!).push(a);
    }
    for (const arr of m.values()) arr.sort((x, y) => x.scheduled_at.localeCompare(y.scheduled_at));
    return m;
  }, [list]);

  const today = new Date();
  const monthLabel = month.toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
  const selectedAppts = selected ? byDay.get(selected) ?? [] : [];

  function shift(delta: number) {
    setMonth((m) => new Date(m.getFullYear(), m.getMonth() + delta, 1));
  }

  return (
    <div className="cal">
      <div className="cal-head">
        <button className="cal-nav" onClick={() => shift(-1)} aria-label="Mês anterior">‹</button>
        <b className="cal-month">{monthLabel}</b>
        <button className="cal-nav" onClick={() => shift(1)} aria-label="Próximo mês">›</button>
        <button
          className="cal-today"
          onClick={() => setMonth(new Date(today.getFullYear(), today.getMonth(), 1))}
        >
          Hoje
        </button>
      </div>

      {error ? <div className="state"><span className="err">{error}</span></div> : null}

      <div className="cal-grid">
        {WEEKDAYS.map((w) => (
          <div key={w} className="cal-wd">{w}</div>
        ))}
        {cells.map((d) => {
          const key = ymd(d);
          const appts = byDay.get(key) ?? [];
          const otherMonth = d.getMonth() !== month.getMonth();
          const isToday = sameYmd(today.toISOString(), d);
          return (
            <button
              key={key}
              className={`cal-cell ${otherMonth ? "other" : ""} ${isToday ? "today" : ""} ${selected === key ? "sel" : ""}`}
              onClick={() => setSelected(key)}
            >
              <span className="cal-day">{d.getDate()}</span>
              <div className="cal-appts">
                {appts.slice(0, 3).map((a) => (
                  <span key={a.id} className={`cal-chip ${STATUS_CLS[a.status]}`}>
                    <b>{timeOf(a.scheduled_at)}</b> {nameOf(a.patient_id)}
                  </span>
                ))}
                {appts.length > 3 ? <span className="cal-more">+{appts.length - 3}</span> : null}
              </div>
            </button>
          );
        })}
      </div>

      {selected ? (
        <div className="cal-day-detail">
          <div className="cal-day-title">
            {new Date(selected + "T12:00:00").toLocaleDateString("pt-BR", {
              weekday: "long", day: "2-digit", month: "long",
            })}
          </div>
          {selectedAppts.length === 0 ? (
            <span className="muted" style={{ fontSize: 13 }}>Nenhuma consulta neste dia.</span>
          ) : (
            selectedAppts.map((a) => (
              <button key={a.id} className="cal-day-row" onClick={() => onOpenPatient(a.patient_id)}>
                <b className="tnum">{timeOf(a.scheduled_at)}</b>
                <span className="pt-link">{nameOf(a.patient_id)}</span>
                <span className={`appt-status ${STATUS_CLS[a.status].replace("c-", "s-")}`}>
                  {a.status === "confirmed" ? "Confirmada" : a.status === "cancelled" ? "Cancelada"
                    : a.status === "completed" ? "Concluída" : "Agendada"}
                </span>
                {a.reschedule_requested_at ? <span className="chip alert">quer remarcar</span> : null}
              </button>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}
