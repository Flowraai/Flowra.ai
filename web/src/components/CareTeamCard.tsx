import { useEffect, useMemo, useState } from "react";
import { patients as patientsApi, clinic } from "../api/endpoints";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { CareTeamMember } from "../api/types";
import "./ClinicalCard.css";
import "./CareTeamCard.css";

export function CareTeamCard({ patientId }: { patientId: string }) {
  const { session } = useAuth();
  const [team, setTeam] = useState<CareTeamMember[] | null>(null);
  const [doctors, setDoctors] = useState<CareTeamMember[]>([]);
  const [pick, setPick] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function load() {
    setError(null);
    patientsApi
      .careTeam(patientId)
      .then(setTeam)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Falha ao carregar a equipe."));
  }
  useEffect(load, [patientId]);

  useEffect(() => {
    clinic.doctors().then(setDoctors).catch(() => setDoctors([]));
  }, []);

  const primaryId = useMemo(() => team?.find((m) => m.is_primary)?.doctor_id, [team]);
  const canManage =
    session?.role === "owner" ||
    (Boolean(session?.doctor) && session?.doctor?.id === primaryId);

  const available = useMemo(() => {
    const inTeam = new Set((team ?? []).map((m) => m.doctor_id));
    return doctors.filter((d) => !inTeam.has(d.doctor_id));
  }, [doctors, team]);

  async function add() {
    if (!pick) return;
    setBusy(true);
    setError(null);
    try {
      setTeam(await patientsApi.addCareTeam(patientId, pick));
      setPick("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Não foi possível adicionar.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(doctorId: string) {
    setBusy(true);
    setError(null);
    try {
      await patientsApi.removeCareTeam(patientId, doctorId);
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Não foi possível remover.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <div className="hd">
        <span aria-hidden>👥</span>
        <h4>Equipe de cuidado</h4>
      </div>
      <div className="bd">
        {error ? <span className="muted">{error}</span> : null}
        {team == null ? (
          <div className="state"><div className="spinner" /></div>
        ) : (
          <>
            <ul className="ct-list">
              {team.map((m) => (
                <li key={m.doctor_id} className="ct-item">
                  <span>
                    <b>{m.name}</b>
                    {m.specialty ? <span className="muted"> · {m.specialty}</span> : null}
                    {m.is_primary ? <span className="ct-primary"> responsável</span> : null}
                  </span>
                  {canManage && !m.is_primary ? (
                    <button className="mini" disabled={busy} onClick={() => remove(m.doctor_id)}>
                      Remover
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
            {canManage && available.length > 0 ? (
              <div className="ct-add">
                <select value={pick} onChange={(e) => setPick(e.target.value)}>
                  <option value="">Adicionar profissional…</option>
                  {available.map((d) => (
                    <option key={d.doctor_id} value={d.doctor_id}>
                      {d.name}{d.specialty ? ` · ${d.specialty}` : ""}
                    </option>
                  ))}
                </select>
                <button className="mini primary" disabled={busy || !pick} onClick={add}>
                  Adicionar
                </button>
              </div>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}
