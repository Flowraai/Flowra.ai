import { useEffect, useMemo, useState } from "react";
import { patients } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { CheckIn } from "../api/types";
import { IconChart } from "./icons";
import "./EvolutionCard.css";

type Pt = { t: number; v: number };
type Series = { key: string; label: string; color: string; pts: Pt[] };

function toNum(v: unknown): number | null {
  if (typeof v === "number") return v;
  if (typeof v === "string") {
    const n = Number(v.replace(",", "."));
    return Number.isFinite(n) ? n : null;
  }
  return null;
}
function fmtDate(t: number): string {
  return new Date(t).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

const WINDOWS = [
  { d: 14, label: "14 dias" },
  { d: 30, label: "30 dias" },
  { d: 60, label: "60 dias" },
];

/** Gráfico de linhas com eixo único, legenda, rótulo no último ponto e hover. */
function LineChart({
  series,
  xDomain,
  yMin,
  yMax,
  yTicks,
  unit,
  height = 150,
}: {
  series: Series[];
  xDomain: [number, number];
  yMin: number;
  yMax: number;
  yTicks: number[];
  unit: string;
  height?: number;
}) {
  const W = 560;
  const mL = 30, mR = 46, mT = 10, mB = 20;
  const iw = W - mL - mR;
  const ih = height - mT - mB;
  const [x0, x1] = xDomain;
  const xspan = Math.max(x1 - x0, 1);
  const yspan = Math.max(yMax - yMin, 1);
  const X = (t: number) => mL + ((t - x0) / xspan) * iw;
  const Y = (v: number) => mT + (1 - (v - yMin) / yspan) * ih;

  const [hoverT, setHoverT] = useState<number | null>(null);
  const allT = useMemo(
    () => Array.from(new Set(series.flatMap((s) => s.pts.map((p) => p.t)))).sort((a, b) => a - b),
    [series],
  );

  function onMove(e: React.MouseEvent<SVGRectElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * W; // coord no viewBox
    const t = x0 + ((px - mL) / iw) * xspan;
    let best: number | null = null;
    let bestD = Infinity;
    for (const tt of allT) {
      const d = Math.abs(tt - t);
      if (d < bestD) {
        bestD = d;
        best = tt;
      }
    }
    setHoverT(best);
  }

  const xTicks = [x0, x0 + xspan / 2, x1];
  const hoverVals =
    hoverT != null
      ? series.map((s) => ({ s, p: s.pts.find((p) => p.t === hoverT) })).filter((o) => o.p)
      : [];

  return (
    <div className="evo-chart">
      <svg viewBox={`0 0 ${W} ${height}`} width="100%" height={height} role="img">
        {/* grade + rótulos Y (recessivos) */}
        {yTicks.map((v) => (
          <g key={v}>
            <line x1={mL} x2={W - mR} y1={Y(v)} y2={Y(v)} stroke="var(--line)" strokeWidth="1" />
            <text x={mL - 6} y={Y(v) + 3} textAnchor="end" className="evo-axis">{v}</text>
          </g>
        ))}
        {/* rótulos X */}
        {xTicks.map((t, i) => (
          <text key={i} x={X(t)} y={height - 6} textAnchor={i === 0 ? "start" : i === 2 ? "end" : "middle"} className="evo-axis">
            {fmtDate(t)}
          </text>
        ))}
        {/* crosshair */}
        {hoverT != null ? (
          <line x1={X(hoverT)} x2={X(hoverT)} y1={mT} y2={mT + ih} stroke="var(--muted)" strokeWidth="1" strokeDasharray="3 3" />
        ) : null}
        {/* linhas */}
        {series.map((s) =>
          s.pts.length === 0 ? null : (
            <g key={s.key}>
              <polyline
                points={s.pts.map((p) => `${X(p.t)},${Y(p.v)}`).join(" ")}
                fill="none"
                style={{ stroke: s.color }}
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              {/* ponto + rótulo direto no último valor */}
              <circle cx={X(s.pts[s.pts.length - 1].t)} cy={Y(s.pts[s.pts.length - 1].v)} r="3.4" style={{ fill: s.color }} stroke="var(--surface)" strokeWidth="2" />
              <text x={W - mR + 5} y={Y(s.pts[s.pts.length - 1].v) + 3} className="evo-endlabel" style={{ fill: s.color }}>
                {s.pts[s.pts.length - 1].v}
              </text>
              {hoverT != null && s.pts.find((p) => p.t === hoverT) ? (
                <circle cx={X(hoverT)} cy={Y(s.pts.find((p) => p.t === hoverT)!.v)} r="4" style={{ fill: s.color }} stroke="var(--surface)" strokeWidth="2" />
              ) : null}
            </g>
          ),
        )}
        {/* overlay de hover */}
        <rect x={mL} y={mT} width={iw} height={ih} fill="transparent" onMouseMove={onMove} onMouseLeave={() => setHoverT(null)} />
      </svg>
      {hoverT != null && hoverVals.length ? (
        <div className="evo-tip">
          <b>{fmtDate(hoverT)}</b>
          {hoverVals.map((o) => (
            <span key={o.s.key}>
              <i style={{ background: o.s.color }} /> {o.s.label}: <b>{o.p!.v}{unit}</b>
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function EvolutionCard({ patientId }: { patientId: string }) {
  const [checkins, setCheckins] = useState<CheckIn[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);
  const [asTable, setAsTable] = useState(false);

  useEffect(() => {
    setError(null);
    patients
      .checkins(patientId, 90)
      .then(setCheckins)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Falha ao carregar a evolução."));
  }, [patientId]);

  const model = useMemo(() => {
    const since = Date.now() - days * 86400000;
    const rows = (checkins ?? [])
      .map((c) => ({ t: new Date(c.created_at).getTime(), r: c.structured_responses }))
      .filter((c) => c.t >= since)
      .sort((a, b) => a.t - b.t);
    const pick = (code: string): Pt[] =>
      rows.map((c) => ({ t: c.t, v: toNum(c.r?.[code]) })).filter((p): p is Pt => p.v !== null);
    const mood = pick("mood");
    const anx = pick("anxiety");
    const sleep = pick("sleep_hours");
    const xDomain: [number, number] = [since, Date.now()];
    return { rows, mood, anx, sleep, xDomain };
  }, [checkins, days]);

  const has = model.mood.length + model.anx.length + model.sleep.length > 0;
  const cHumor = "var(--chart-humor)";
  const cAnx = "var(--chart-anx)";
  const cSleep = "var(--chart-sleep)";
  const maxSleep = Math.max(12, ...model.sleep.map((p) => p.v));

  return (
    <div className="card">
      <div className="hd">
        <IconChart width={16} height={16} color="var(--muted)" />
        <h4>Evolução</h4>
        <div className="seg evo-seg" style={{ marginLeft: "auto" }}>
          {WINDOWS.map((w) => (
            <button key={w.d} className={days === w.d ? "on" : ""} onClick={() => setDays(w.d)}>{w.label}</button>
          ))}
        </div>
      </div>
      <div className="bd">
        {error ? (
          <span className="muted">{error}</span>
        ) : !checkins ? (
          <div className="state"><div className="spinner" /></div>
        ) : !has ? (
          <span className="muted" style={{ fontSize: 13 }}>Sem check-ins no período. Ajuste a janela.</span>
        ) : (
          <>
            <div className="evo-toolbar">
              <div className="evo-legend">
                <span><i style={{ background: cHumor }} /> Humor</span>
                <span><i style={{ background: cAnx }} /> Ansiedade</span>
              </div>
              <button className="mini" onClick={() => setAsTable((v) => !v)}>
                {asTable ? "Ver gráfico" : "Ver tabela"}
              </button>
            </div>

            {asTable ? (
              <div className="table evo-table">
                <table>
                  <thead><tr><th>Data</th><th>Humor</th><th>Ansiedade</th><th>Sono</th></tr></thead>
                  <tbody>
                    {[...model.rows].reverse().map((c) => (
                      <tr key={c.t}>
                        <td className="tnum">{fmtDate(c.t)}</td>
                        <td className="tnum">{toNum(c.r?.mood) ?? "—"}</td>
                        <td className="tnum">{toNum(c.r?.anxiety) ?? "—"}</td>
                        <td className="tnum">{toNum(c.r?.sleep_hours) ?? "—"}h</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <>
                <div className="evo-title">Humor e ansiedade <span className="muted">(0–10)</span></div>
                <LineChart
                  series={[
                    { key: "mood", label: "Humor", color: cHumor, pts: model.mood },
                    { key: "anx", label: "Ansiedade", color: cAnx, pts: model.anx },
                  ]}
                  xDomain={model.xDomain}
                  yMin={0}
                  yMax={10}
                  yTicks={[0, 5, 10]}
                  unit=""
                />
                {model.sleep.length > 0 ? (
                  <>
                    <div className="evo-title">Sono <span className="muted">(horas por noite)</span></div>
                    <LineChart
                      series={[{ key: "sleep", label: "Sono", color: cSleep, pts: model.sleep }]}
                      xDomain={model.xDomain}
                      yMin={0}
                      yMax={maxSleep}
                      yTicks={[0, Math.round(maxSleep / 2), maxSleep]}
                      unit="h"
                      height={120}
                    />
                  </>
                ) : null}
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
