import { useEffect, useState } from "react";
import { patients, exams as examsApi } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { Exam } from "../api/types";
import { AddExamModal } from "./AddExamModal";
import { IconFlask } from "./icons";
import "./ClinicalCard.css";

export function ExamsCard({ patientId }: { patientId: string }) {
  const [list, setList] = useState<Exam[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  function load() {
    setError(null);
    patients
      .exams(patientId)
      .then(setList)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Falha ao carregar os exames."));
  }
  useEffect(load, [patientId]);

  async function markAvailable(ex: Exam) {
    setBusy(ex.id);
    try {
      const updated = await examsApi.update(ex.id, { status: "available" });
      setList((prev) => (prev ? prev.map((x) => (x.id === ex.id ? updated : x)) : prev));
    } catch {
      /* mantém */
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="card">
      <div className="hd">
        <IconFlask width={16} height={16} color="var(--muted)" />
        <h4>Exames</h4>
        <button className="btn sm" style={{ marginLeft: "auto" }} onClick={() => setShowAdd(true)}>
          + Solicitar
        </button>
      </div>
      <div className="bd">
        {error ? (
          <span className="muted">{error}</span>
        ) : !list ? (
          <div className="state">
            <div className="spinner" />
          </div>
        ) : list.length === 0 ? (
          <span className="muted" style={{ fontSize: 13 }}>Nenhum exame solicitado.</span>
        ) : (
          <div className="clin-list">
            {list.map((ex) => (
              <div className="clin-row" key={ex.id}>
                <div className="clin-main">
                  <b>{ex.name}</b>
                  {ex.notes ? <span>{ex.notes}</span> : null}
                </div>
                {ex.status === "available" ? (
                  <span className="badge b-ok">disponível</span>
                ) : (
                  <button className="mini" disabled={busy === ex.id} onClick={() => markAvailable(ex)}>
                    Marcar disponível
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {showAdd ? (
        <AddExamModal
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
