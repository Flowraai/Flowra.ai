import { useId, useState } from "react";
import type { ChargeMonth } from "../api/types";
import "./FinanceChart.css";

function brl(cents: number): string {
  return (cents / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}
function brlShort(cents: number): string {
  const v = cents / 100;
  if (v >= 1000) return `R$${(v / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}k`;
  return `R$${v.toLocaleString("pt-BR", { maximumFractionDigits: 0 })}`;
}
function monthLabel(m: string): string {
  const [y, mo] = m.split("-");
  const d = new Date(Number(y), Number(mo) - 1, 1);
  return d.toLocaleDateString("pt-BR", { month: "short", year: "2-digit" }).replace(".", "");
}

// Marcas: barras empilhadas por mês (recebido embaixo, a receber em cima), com
// 2px de respiro entre os segmentos e topo arredondado. Eixo único (R$).
export function FinanceChart({ months }: { months: ChargeMonth[] }) {
  const [table, setTable] = useState(false);
  const [hover, setHover] = useState<number | null>(null);
  const clip = useId();

  if (months.length === 0) {
    return <p className="muted" style={{ fontSize: 13 }}>Sem lançamentos no período para o gráfico.</p>;
  }

  const totals = months.map((m) => m.received_cents + m.pending_cents);
  const max = Math.max(1, ...totals);
  // Escala "bonita": arredonda o topo.
  const step = Math.pow(10, Math.floor(Math.log10(max)));
  const niceMax = Math.ceil(max / step) * step;

  const W = Math.max(320, months.length * 68 + 56);
  const H = 240;
  const padL = 52;
  const padB = 34;
  const padT = 16;
  const plotW = W - padL - 16;
  const plotH = H - padT - padB;
  const bw = Math.min(40, (plotW / months.length) * 0.6);
  const gap = 2;

  const x = (i: number) => padL + (plotW / months.length) * (i + 0.5);
  const y = (c: number) => padT + plotH * (1 - c / niceMax);
  const gridVals = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(niceMax * f));

  if (table) {
    return (
      <div>
        <ChartToolbar table={table} setTable={setTable} />
        <div className="fc-tablewrap">
          <table className="fc-table">
            <thead>
              <tr><th>Mês</th><th>Recebido</th><th>A receber</th><th>Total</th></tr>
            </thead>
            <tbody>
              {months.map((m) => (
                <tr key={m.month}>
                  <td>{monthLabel(m.month)}</td>
                  <td>{brl(m.received_cents)}</td>
                  <td>{brl(m.pending_cents)}</td>
                  <td><b>{brl(m.received_cents + m.pending_cents)}</b></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  return (
    <div>
      <ChartToolbar table={table} setTable={setTable} />
      <div className="fc-legend">
        <span><i style={{ background: "var(--fin-received)" }} /> Recebido</span>
        <span><i style={{ background: "var(--fin-pending)" }} /> A receber</span>
      </div>
      <div className="fc-wrap">
        <svg viewBox={`0 0 ${W} ${H}`} className="fc-svg" role="img" aria-label="Faturamento por mês">
          <defs>
            <clipPath id={clip}><rect x={padL} y={padT} width={plotW} height={plotH} /></clipPath>
          </defs>
          {/* grade + rótulos do eixo (recessivos) */}
          {gridVals.map((v) => (
            <g key={v}>
              <line x1={padL} x2={W - 16} y1={y(v)} y2={y(v)} className="fc-grid" />
              <text x={padL - 8} y={y(v) + 3.5} className="fc-axis" textAnchor="end">{brlShort(v)}</text>
            </g>
          ))}
          {months.map((m, i) => {
            const cx = x(i);
            const recH = plotH * (m.received_cents / niceMax);
            const penH = plotH * (m.pending_cents / niceMax);
            const baseY = padT + plotH;
            const recY = baseY - recH;
            const penY = recY - penH - (recH > 0 && penH > 0 ? gap : 0);
            const on = hover === i;
            return (
              <g key={m.month} clipPath={`url(#${clip})`}
                 onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
                <rect x={cx - bw / 2 - 6} y={padT} width={bw + 12} height={plotH} fill="transparent" />
                {m.received_cents > 0 ? (
                  <rect x={cx - bw / 2} y={recY} width={bw} height={recH} rx={penH > 0 ? 0 : 4}
                        fill="var(--fin-received)" opacity={on || hover === null ? 1 : 0.5} />
                ) : null}
                {m.pending_cents > 0 ? (
                  <rect x={cx - bw / 2} y={penY} width={bw} height={penH} rx={4}
                        fill="var(--fin-pending)" opacity={on || hover === null ? 1 : 0.5} />
                ) : null}
              </g>
            );
          })}
          {/* rótulos do eixo X */}
          {months.map((m, i) => (
            <text key={m.month} x={x(i)} y={H - padB + 18} className="fc-axis" textAnchor="middle">
              {monthLabel(m.month)}
            </text>
          ))}
        </svg>
        {hover !== null ? (
          <div
            className="fc-tip"
            style={{ left: `${(x(hover) / W) * 100}%` }}
          >
            <b>{monthLabel(months[hover].month)}</b>
            <span><i style={{ background: "var(--fin-received)" }} />Recebido {brl(months[hover].received_cents)}</span>
            <span><i style={{ background: "var(--fin-pending)" }} />A receber {brl(months[hover].pending_cents)}</span>
            <span className="fc-tip-total">Total {brl(totals[hover])}</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function ChartToolbar({ table, setTable }: { table: boolean; setTable: (v: boolean) => void }) {
  return (
    <div className="fc-toolbar">
      <button className={table ? "" : "on"} onClick={() => setTable(false)}>Gráfico</button>
      <button className={table ? "on" : ""} onClick={() => setTable(true)}>Tabela</button>
    </div>
  );
}
