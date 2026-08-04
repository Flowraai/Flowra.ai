import { useEffect, useState } from "react";
import { patients, medications } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { MedicationAdherence, MedicationPlan } from "../api/types";
import { AddMedicationModal } from "./AddMedicationModal";
import { IconPill } from "./icons";
import "./MedicationCard.css";

export function MedicationCard({ patientId }: { patientId: string }) {
  const [plans, setPlans] = useState<MedicationPlan[] | null>(null);
  const [adherence, setAdherence] = useState<MedicationAdherence | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  function load() {
    setError(null);
    Promise.all([patients.medications(patientId), patients.adherence(patientId)])
      .then(([p, a]) => {
        setPlans(p);
        setAdherence(a);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Falha ao carregar a medicação."));
  }
  useEffect(load, [patientId]);

  async function deactivate(plan: MedicationPlan) {
    setBusy(plan.id);
    try {
      const updated = await medications.update(plan.id, { active: false });
      setPlans((prev) => (prev ? prev.map((x) => (x.id === plan.id ? updated : x)) : prev));
    } catch {
      /* mantém */
    } finally {
      setBusy(null);
    }
  }

  const responded = adherence ? adherence.taken + adherence.later + adherence.missed : 0;
  const rate = adherence ? Math.round(adherence.adherence_rate * 100) : 0;
  const active = (plans ?? []).filter((p) => p.active);

  return (
    <div className="card">
      <div className="hd">
        <IconPill width={16} height={16} color="var(--muted)" />
        <h4>Medicação</h4>
        <button className="btn sm" style={{ marginLeft: "auto" }} onClick={() => setShowAdd(true)}>
          + Adicionar
        </button>
      </div>
      <div className="bd">
        {error ? (
          <span className="muted">{error}</span>
        ) : !plans || !adherence ? (
          <div className="state">
            <div className="spinner" />
          </div>
        ) : (
          <>
            {responded > 0 ? (
              <div className="adh">
                <div className="adh-top">
                  <span className="muted">Adesão (30 dias)</span>
                  <b className="tnum">{rate}%</b>
                </div>
                <div className="adh-bar">
                  <i style={{ width: `${rate}%`, background: rate >= 80 ? "var(--risk-green)" : rate >= 50 ? "var(--risk-yellow)" : "var(--risk-red)" }} />
                </div>
                <span className="muted adh-detail">
                  {adherence.taken} tomadas · {adherence.later} adiadas · {adherence.missed} perdidas
                </span>
              </div>
            ) : (
              <span className="muted" style={{ fontSize: 13 }}>Sem respostas de medicação ainda.</span>
            )}

            {active.length > 0 ? (
              <div className="plan-list">
                {active.map((p) => (
                  <div className="plan" key={p.id}>
                    <div className="plan-main">
                      <b>{p.name}</b>
                      <span className="muted">
                        {p.dose} · {p.times.join(", ")}
                      </span>
                    </div>
                    <button className="plan-off" disabled={busy === p.id} onClick={() => deactivate(p)}>
                      Desativar
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <span className="muted" style={{ fontSize: 13 }}>Nenhum plano ativo.</span>
            )}
          </>
        )}
      </div>

      {showAdd ? (
        <AddMedicationModal
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
