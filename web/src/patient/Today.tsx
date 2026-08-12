import { useEffect, useState } from "react";
import { patientApi, PatientApiError, type Appointment, type PatientToday } from "./api";

function firstName(name: string): string {
  return name.trim().split(/\s+/)[0] ?? name;
}

function longDate(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", {
    weekday: "short",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function Today({
  today,
  onStartCheckin,
}: {
  today: PatientToday;
  onStartCheckin: () => void;
}) {
  const [appointments, setAppointments] = useState<Appointment[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function loadAppointments() {
    try {
      setAppointments(await patientApi.appointments());
    } catch (e) {
      setError(e instanceof PatientApiError ? e.message : null);
    }
  }

  useEffect(() => {
    loadAppointments();
  }, []);

  async function confirm(id: string) {
    setBusy(id);
    try {
      await patientApi.confirmAppointment(id);
      await loadAppointments();
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <h1 className="pt-h1">Olá, {firstName(today.patient_name)} 👋</h1>
      <div className="pt-sub">Como você está hoje?</div>

      {today.checked_in_today ? (
        <div className="pt-card">
          <div className="pt-done">✓ Check-in de hoje concluído</div>
          <p className="pt-muted" style={{ marginTop: 10, marginBottom: 0 }}>
            Obrigado por responder. Seu médico acompanha suas respostas.
          </p>
        </div>
      ) : (
        <div className="pt-card">
          <h3>Check-in de hoje</h3>
          <p className="pt-muted" style={{ marginTop: 4, marginBottom: 12 }}>
            Leva menos de 1 minuto e ajuda seu médico a acompanhar você entre as consultas.
          </p>
          <button className="pt-btn" onClick={onStartCheckin}>
            Fazer check-in de hoje
          </button>
        </div>
      )}

      {appointments && appointments.length > 0 ? (
        <div className="pt-card">
          <h3>Próximas consultas</h3>
          {appointments.map((a) => (
            <div className="pt-dose" key={a.id}>
              <div className="pt-dose-info">
                <b>{a.kind === "return" ? "Retorno" : "Consulta"}</b>
                <div className="pt-muted">{longDate(a.scheduled_at)}</div>
                {a.location ? <div className="pt-muted">{a.location}</div> : null}
              </div>
              {a.status === "confirmed" ? (
                <span className="tag taken">✓ Confirmada</span>
              ) : (
                <button
                  className="pt-btn ghost small"
                  disabled={busy === a.id}
                  onClick={() => confirm(a.id)}
                >
                  Confirmar
                </button>
              )}
            </div>
          ))}
        </div>
      ) : null}

      {error ? <div className="pt-error">{error}</div> : null}
    </div>
  );
}
