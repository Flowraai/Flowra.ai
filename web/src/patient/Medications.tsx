import { useEffect, useState } from "react";
import { patientApi, PatientApiError, type IntakeStatus, type MedicationDose } from "./api";

function hhmm(iso: string): string {
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

const STATUS_TAG: Record<Exclude<IntakeStatus, "pending">, string> = {
  taken: "✓ Tomei",
  later: "⏰ Depois",
  missed: "✕ Não tomei",
};

export function Medications() {
  const [doses, setDoses] = useState<MedicationDose[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function load() {
    try {
      setDoses(await patientApi.medicationsToday());
    } catch (e) {
      setError(e instanceof PatientApiError ? e.message : "Falha ao carregar os remédios.");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function respond(intakeId: string, status: IntakeStatus) {
    setBusy(intakeId);
    try {
      await patientApi.respondIntake(intakeId, status);
      setDoses((prev) =>
        prev ? prev.map((d) => (d.intake_id === intakeId ? { ...d, status } : d)) : prev,
      );
    } catch (e) {
      setError(e instanceof PatientApiError ? e.message : "Não foi possível registrar.");
    } finally {
      setBusy(null);
    }
  }

  if (error) return <div className="pt-card pt-error">{error}</div>;
  if (!doses)
    return (
      <div className="pt-center">
        <div className="pt-spinner" />
      </div>
    );

  return (
    <div>
      <h1 className="pt-h1">Meus remédios</h1>
      <div className="pt-sub">Marque conforme for tomando ao longo do dia.</div>
      {doses.length === 0 ? (
        <div className="pt-card pt-muted">Nenhum remédio programado para hoje.</div>
      ) : (
        <div className="pt-card">
          {doses.map((d) => (
            <div className="pt-dose" key={d.intake_id}>
              <div className="pt-dose-info">
                <b>{d.name}</b>
                <div className="pt-muted">
                  {d.dose} · {hhmm(d.scheduled_for)}
                </div>
              </div>
              {d.status === "pending" ? (
                <div className="pt-dose-actions">
                  <button
                    disabled={busy === d.intake_id}
                    title="Tomei"
                    onClick={() => respond(d.intake_id, "taken")}
                  >
                    ✓
                  </button>
                  <button
                    disabled={busy === d.intake_id}
                    title="Vou tomar depois"
                    onClick={() => respond(d.intake_id, "later")}
                  >
                    ⏰
                  </button>
                  <button
                    disabled={busy === d.intake_id}
                    title="Não tomei"
                    onClick={() => respond(d.intake_id, "missed")}
                  >
                    ✕
                  </button>
                </div>
              ) : (
                <span className={`tag ${d.status}`}>{STATUS_TAG[d.status]}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
