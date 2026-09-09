import { useEffect, useState } from "react";
import { patients } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { WearableSummary } from "../api/types";
import { IconSpark } from "./icons";
import "./ClinicalCard.css";

function sleepLabel(min: number | null): string {
  if (min == null) return "—";
  return `${Math.floor(min / 60)}h${String(min % 60).padStart(2, "0")}`;
}
function num(v: number | null): string {
  return v == null ? "—" : v.toLocaleString("pt-BR");
}

export function WearableCard({ patientId }: { patientId: string }) {
  const [data, setData] = useState<WearableSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    patients
      .wearable(patientId)
      .then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Falha ao carregar o dispositivo."));
  }, [patientId]);

  const latest = data?.latest;
  const metrics: { label: string; latest: string; avg: string }[] = [
    { label: "Sono", latest: sleepLabel(latest?.sleep_minutes ?? null), avg: sleepLabel(data?.avg_sleep_minutes ?? null) },
    { label: "FC repouso", latest: `${num(latest?.resting_hr ?? null)} bpm`, avg: `${num(data?.avg_resting_hr ?? null)} bpm` },
    { label: "HRV", latest: `${num(latest?.hrv_ms ?? null)} ms`, avg: `${num(data?.avg_hrv_ms ?? null)} ms` },
    { label: "Passos", latest: num(latest?.steps ?? null), avg: num(data?.avg_steps ?? null) },
  ];

  return (
    <div className="card">
      <div className="hd">
        <IconSpark width={16} height={16} color="var(--muted)" />
        <h4>Dispositivo</h4>
        {data?.connected ? <span className="badge b-ok" style={{ marginLeft: "auto" }}>conectado</span> : null}
      </div>
      <div className="bd">
        {error ? (
          <span className="muted">{error}</span>
        ) : !data ? (
          <div className="state"><div className="spinner" /></div>
        ) : !data.connected ? (
          <span className="muted" style={{ fontSize: 13 }}>
            O paciente ainda não conectou um relógio ou pulseira.
          </span>
        ) : (
          <>
            <div className="wear-grid">
              {metrics.map((m) => (
                <div className="wear-cell" key={m.label}>
                  <span className="wear-label">{m.label}</span>
                  <b>{m.latest}</b>
                  <span className="wear-avg">média 14d {m.avg}</span>
                </div>
              ))}
            </div>
            {data.last_sync_at ? (
              <p className="muted" style={{ fontSize: 11.5, margin: "10px 0 0" }}>
                Última sincronização: {new Date(data.last_sync_at).toLocaleString("pt-BR", {
                  day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
                })}
              </p>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}
