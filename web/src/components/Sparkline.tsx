// Mini-gráfico de tendência (ex.: humor nos últimos check-ins).

export function Sparkline({
  values,
  color,
  width = 96,
  height = 26,
  min = 0,
  max = 10,
}: {
  values: number[];
  color: string;
  width?: number;
  height?: number;
  min?: number;
  max?: number;
}) {
  if (values.length === 0) {
    return <span className="muted" style={{ fontSize: 12 }}>—</span>;
  }
  const pad = 3;
  const span = Math.max(max - min, 1);
  const step = values.length > 1 ? (width - pad * 2) / (values.length - 1) : 0;
  const y = (v: number) => height - pad - ((v - min) / span) * (height - pad * 2);
  const pts = values.map((v, i) => `${pad + i * step},${y(v).toFixed(1)}`).join(" ");
  const last = values[values.length - 1];

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} fill="none" aria-hidden>
      <polyline points={pts} stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={pad + (values.length - 1) * step} cy={y(last)} r="2.6" fill={color} />
    </svg>
  );
}
