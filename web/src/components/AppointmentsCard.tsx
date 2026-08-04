import { useEffect, useState } from "react";
import { patients, appointments as apptApi } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { Appointment, AppointmentKind, AppointmentStatus } from "../api/types";
import { AddAppointmentModal } from "./AddAppointmentModal";
import { IconCalendar } from "./icons";
import "./AppointmentsCard.css";

const KIND: Record<AppointmentKind, string> = { consultation: "Consulta", return: "Retorno" };
const STATUS: Record<AppointmentStatus, { label: string; cls: string }> = {
  scheduled: { label: "Agendada", cls: "s-open" },
  confirmed: { label: "Confirmada", cls: "s-ok" },
  cancelled: { label: "Cancelada", cls: "s-off" },
  completed: { label: "Concluída", cls: "s-done" },
};

function fmt(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function AppointmentsCard({ patientId }: { patientId: string }) {
  const [list, setList] = useState<Appointment[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  function load() {
    setError(null);
    patients
      .appointments(patientId)
      .then(setList)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Falha ao carregar as consultas."));
  }
  useEffect(load, [patientId]);

  async function setStatus(a: Appointment, status: AppointmentStatus) {
    setBusy(a.id);
    try {
      const updated = await apptApi.update(a.id, { status });
      setList((prev) => (prev ? prev.map((x) => (x.id === a.id ? updated : x)) : prev));
    } catch {
      /* mantém */
    } finally {
      setBusy(null);
    }
  }

  const now = Date.now();
  const rows = (list ?? []).slice().sort((a, b) => b.scheduled_at.localeCompare(a.scheduled_at));

  return (
    <div className="card">
      <div className="hd">
        <IconCalendar width={16} height={16} color="var(--muted)" />
        <h4>Consultas</h4>
        <button className="btn sm" style={{ marginLeft: "auto" }} onClick={() => setShowAdd(true)}>
          + Agendar
        </button>
      </div>
      <div className="bd">
        {error ? (
          <span className="muted">{error}</span>
        ) : !list ? (
          <div className="state">
            <div className="spinner" />
          </div>
        ) : rows.length === 0 ? (
          <span className="muted" style={{ fontSize: 13 }}>Nenhuma consulta agendada.</span>
        ) : (
          <div className="appt-list">
            {rows.map((a) => {
              const open = a.status === "scheduled" || a.status === "confirmed";
              const upcoming = new Date(a.scheduled_at).getTime() >= now;
              const st = STATUS[a.status];
              return (
                <div className="appt" key={a.id}>
                  <div className={`appt-when ${open && upcoming ? "next" : ""}`}>
                    <b className="tnum">{fmt(a.scheduled_at)}</b>
                    <span>
                      {KIND[a.kind]}
                      {a.location ? ` · ${a.location}` : ""}
                    </span>
                  </div>
                  <span className={`appt-status ${st.cls}`}>{st.label}</span>
                  {open ? (
                    <div className="appt-actions">
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
        )}
      </div>

      {showAdd ? (
        <AddAppointmentModal
          patientId={patientId}
          onClose={() => setShowAdd(false)}
          onCreated={() => {
            setShowAdd(false);
            load();
          }}
        />
      ) : null}
    </div>
  );
}
