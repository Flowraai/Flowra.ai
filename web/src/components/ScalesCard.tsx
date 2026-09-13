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

// Tendência entre as duas últimas aplicações. Em PHQ-9/GAD-7, score maior = pior;
// `worse` guarda a direção clínica para não assumir nada.
function TrendBadge({ done, worse }: { done: ScaleEntry[]; worse: boolean }) {
  if (done.length < 2) return null;
  const last = done[done.length - 1].score;
  const prev = done[done.length - 2].score;
  if (last == null || prev == null) return null;
  const delta = last - prev;
  if (delta === 0) {
    return <span className="scale-trend-badge flat" title="Sem mudança vs. anterior">= estável</span>;
  }
  const worsened = delta > 0 === worse;
  return (
    <span
      className={`scale-trend-badge ${worsened ? "worse" : "better"}`}
      title={`${worsened ? "Piora" : "Melhora"} de ${Math.abs(delta)} ponto(s) vs. a aplicação anterior`}
    >
      {worsened ? "↑" : "↓"} {Math.abs(delta)} {worsened ? "piora" : "melhora"}
    </span>
  );
}

export function ScalesCard({ patientId }: { patientId: string }) {
  const [catalog, setCatalog] = useState<ScaleDef[]>([]);
  const [list, setList] = useState<ScaleEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [picking, setPicking] = useState(false);
  const [recur, setRecur] = useState(0); // 0 = uma vez
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

  const worseOf = useMemo(() => {
    const m = new Map<string, boolean>();
    catalog.forEach((s) => m.set(s.code, s.higher_is_worse));
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
      const recent = [...entries].sort((a, b) => b.requested_at.localeCompare(a.requested_at))[0];
      return { code, name, done, pending, recurring: recent.recurring_days };
    });
  }, [list]);

  async function request(code: string) {
    setBusy(true);
    try {
      await patients.requestScale(patientId, code, recur || null);
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
            <label className="scale-recur">
              Repetir:
              <select value={recur} onChange={(e) => setRecur(Number(e.target.value))}>
                <option value={0}>Uma vez</option>
                <option value={7}>A cada 7 dias</option>
                <option value={14}>A cada 14 dias</option>
                <option value={30}>A cada 30 dias</option>
              </select>
            </label>
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
                    {g.recurring ? <span className="chip">🔁 a cada {g.recurring}d</span> : null}
                    {last ? (
                      <span className="scale-score" style={{ color: LEVEL_COLOR[last.level ?? "green"] }}>
                        {last.score}/{max} · {last.severity}
                        {last.flagged ? " ⚠️" : ""}
                      </span>
                    ) : (
                      <span className="muted" style={{ fontSize: 12.5 }}>aguardando 1ª resposta</span>
                    )}
                    <TrendBadge done={g.done} worse={worseOf.get(g.code) ?? true} />
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
