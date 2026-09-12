import { useEffect, useMemo, useState } from "react";
import { patients, scales as scalesApi } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { RiskLevel, ScaleDef, ScaleEntry } from "../api/types";
import { Sparkline } from "./Sparkline";
import { IconClipboard } from "./icons";
import "./ClinicalCard.css";

const LEVEL_COLOR: Record<RiskLevel, string> = {
  green: "var(--risk-green)",
  yellow: "var(--risk-yellow)",
  orange: "var(--risk-orange)",
  red: "var(--risk-red)",
};

function when(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "2-digit" });
}

export function ScalesCard({ patientId }: { patientId: string }) {
  const [catalog, setCatalog] = useState<ScaleDef[]>([]);
  const [list, setList] = useState<ScaleEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [picking, setPicking] = useState(false);
  const [busy, setBusy] = useState(false);

  function load() {
    setError(null);
    patients
      .scales(patientId)
      .then(setList)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Falha ao carregar as escalas."));
  }
  useEffect(() => {
    scalesApi.catalog().then(setCatalog).catch(() => setCatalog([]));
    load();
  }, [patientId]);

  const maxOf = useMemo(() => {
    const m = new Map<string, number>();
    catalog.forEach((s) => m.set(s.code, s.max_score));
    return m;
  }, [catalog]);

  // Agrupa por escala: histórico (done, mais antigo→recente) + pendentes.
  const groups = useMemo(() => {
    const byScale = new Map<string, ScaleEntry[]>();
    for (const e of list ?? []) {
      (byScale.get(e.scale_code) ?? byScale.set(e.scale_code, []).get(e.scale_code)!).push(e);
    }
    return [...byScale.entries()].map(([code, entries]) => {
      const done = entries
        .filter((e) => e.status === "done")
        .sort((a, b) => (a.completed_at ?? "").localeCompare(b.completed_at ?? ""));
      const pending = entries.filter((e) => e.status === "pending");
      const name = entries[0].scale_name;
      return { code, name, done, pending };
    });
  }, [list]);

  async function request(code: string) {
    setBusy(true);
    try {
      await patients.requestScale(patientId, code);
      setPicking(false);
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Não foi possível solicitar.");
    } finally {
      setBusy(false);
    }
  }

  async function cancel(entryId: string) {
    setBusy(true);
    try {
      await scalesApi.cancel(entryId);
      load();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <div className="hd">
        <IconClipboard width={16} height={16} color="var(--muted)" />
        <h4>Escalas clínicas</h4>
        <button className="btn sm" style={{ marginLeft: "auto" }} onClick={() => setPicking((v) => !v)}>
          + Solicitar
        </button>
      </div>
      <div className="bd">
        {picking ? (
          <div className="scale-pick">
            {catalog.map((s) => (
              <button key={s.code} className="scale-pick-item" disabled={busy} onClick={() => request(s.code)}>
                <b>{s.name}</b>
                <span className="muted">{s.description}</span>
              </button>
            ))}
          </div>
        ) : null}

        {error ? (
          <span className="muted">{error}</span>
        ) : !list ? (
          <div className="state"><div className="spinner" /></div>
        ) : groups.length === 0 ? (
          <span className="muted" style={{ fontSize: 13 }}>
            Nenhuma escala aplicada. Solicite PHQ-9 (depressão) ou GAD-7 (ansiedade).
          </span>
        ) : (
          <div className="scale-list">
            {groups.map((g) => {
              const last = g.done[g.done.length - 1];
              const max = maxOf.get(g.code) ?? 27;
              return (
                <div className="scale-group" key={g.code}>
                  <div className="scale-top">
                    <b>{g.name}</b>
                    {last ? (
                      <span className="scale-score" style={{ color: LEVEL_COLOR[last.level ?? "green"] }}>
                        {last.score}/{max} · {last.severity}
                        {last.flagged ? " ⚠️" : ""}
                      </span>
                    ) : (
                      <span className="muted" style={{ fontSize: 12.5 }}>aguardando 1ª resposta</span>
                    )}
                  </div>
                  {g.done.length > 1 ? (
                    <div className="scale-trend">
                      <Sparkline
                        values={g.done.map((e) => e.score ?? 0)}
                        color={LEVEL_COLOR[last?.level ?? "green"]}
                        min={0}
                        max={max}
                        width={140}
                      />
                      <span className="muted">
                        {g.done.length} respostas · {when(g.done[0].completed_at!)} → {when(last!.completed_at!)}
                      </span>
                    </div>
                  ) : null}
                  {g.pending.map((p) => (
                    <div className="scale-pending" key={p.id}>
                      <span className="chip">aguardando resposta · pedido {when(p.requested_at)}</span>
                      <button className="mini danger" disabled={busy} onClick={() => cancel(p.id)}>
                        Cancelar
                      </button>
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
