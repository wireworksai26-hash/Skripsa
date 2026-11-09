import type { ChartSeries } from "@/lib/types";

const PALETTE = ["#0075de", "#f64932", "#ffb110", "#62aef0", "#02093a", "#b18164", "#e89d01"];

function fmtNum(v: number): string {
  if (Math.abs(v) >= 1000) return (v / 1000).toFixed(1).replace(/\.0$/, "") + "rb";
  return String(Math.round(v * 10) / 10);
}

export function BarChart({
  series,
  xlabel,
  ylabel,
}: {
  series: ChartSeries[];
  xlabel?: string;
  ylabel?: string;
}) {
  const W = 560;
  const H = 300;
  const padL = 44;
  const padB = 40;
  const max = Math.max(...series.map((s) => s.value), 1) * 1.15;
  const bw = (W - padL - 16) / series.length;
  const gridYs = [0, 0.25, 0.5, 0.75, 1];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Grafik batang">
      {gridYs.map((g) => {
        const y = H - padB - g * (H - padB - 20);
        return (
          <g key={g}>
            <line x1={padL} x2={W - 8} y1={y} y2={y} stroke="rgba(0,0,0,0.08)" strokeWidth={1} />
            <text x={padL - 8} y={y + 4} textAnchor="end" fontSize={10} fill="rgba(0,0,0,0.4)">
              {fmtNum(max * g)}
            </text>
          </g>
        );
      })}
      {series.map((s, i) => {
        const h = ((H - padB - 20) * s.value) / max;
        return (
          <g key={i}>
            <rect
              x={padL + i * bw + bw * 0.18}
              y={H - padB - h}
              width={bw * 0.64}
              height={h}
              rx={4}
              fill={PALETTE[i % PALETTE.length]}
            />
            <text
              x={padL + i * bw + bw * 0.5}
              y={H - padB - h - 6}
              textAnchor="middle"
              fontSize={10}
              fill="rgba(0,0,0,0.65)"
            >
              {fmtNum(s.value)}
            </text>
            <text
              x={padL + i * bw + bw * 0.5}
              y={H - padB + 14}
              textAnchor="middle"
              fontSize={10}
              fill="rgba(0,0,0,0.55)"
            >
              {s.label.length > 14 ? s.label.slice(0, 13) + "…" : s.label}
            </text>
          </g>
        );
      })}
      {ylabel && (
        <text x={8} y={16} fontSize={11} fill="rgba(0,0,0,0.5)">
          {ylabel}
        </text>
      )}
      {xlabel && (
        <text x={padL} y={H - 4} fontSize={10} fill="rgba(0,0,0,0.4)">
          {xlabel}
        </text>
      )}
    </svg>
  );
}

export function LineChart({
  series,
  xlabel,
  ylabel,
}: {
  series: ChartSeries[];
  xlabel?: string;
  ylabel?: string;
}) {
  const W = 560;
  const H = 300;
  const padL = 44;
  const padB = 40;
  const max = Math.max(...series.map((s) => s.value), 1) * 1.15;
  const step = (W - padL - 16) / Math.max(series.length - 1, 1);
  const pts = series.map((s, i) => ({
    x: padL + i * step,
    y: H - padB - ((H - padB - 20) * s.value) / max,
  }));
  const path = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Grafik garis">
      {[0, 0.5, 1].map((g) => {
        const y = H - padB - g * (H - padB - 20);
        return <line key={g} x1={padL} x2={W - 8} y1={y} y2={y} stroke="rgba(0,0,0,0.08)" />;
      })}
      <path d={path} fill="none" stroke="#0075de" strokeWidth={2.5} strokeLinejoin="round" />
      {pts.map((p, i) => (
        <g key={i}>
          <circle cx={p.x} cy={p.y} r={4} fill="#fff" stroke="#0075de" strokeWidth={2} />
          <text x={p.x} y={p.y - 9} textAnchor="middle" fontSize={10} fill="rgba(0,0,0,0.65)">
            {fmtNum(series[i].value)}
          </text>
          <text x={p.x} y={H - padB + 14} textAnchor="middle" fontSize={10} fill="rgba(0,0,0,0.55)">
            {series[i].label.length > 12 ? series[i].label.slice(0, 11) + "…" : series[i].label}
          </text>
        </g>
      ))}
      {ylabel && (
        <text x={8} y={16} fontSize={11} fill="rgba(0,0,0,0.5)">
          {ylabel}
        </text>
      )}
      {xlabel && (
        <text x={padL} y={H - 4} fontSize={10} fill="rgba(0,0,0,0.4)">
          {xlabel}
        </text>
      )}
    </svg>
  );
}

export function PieChart({ series }: { series: ChartSeries[] }) {
  const total = series.reduce((a, s) => a + s.value, 0) || 1;
  let angle = -Math.PI / 2;
  const cx = 130;
  const cy = 130;
  const R = 105;

  const slices = series.map((s, i) => {
    const frac = s.value / total;
    const end = angle + frac * Math.PI * 2;
    const large = frac > 0.5 ? 1 : 0;
    const x1 = cx + R * Math.cos(angle);
    const y1 = cy + R * Math.sin(angle);
    const x2 = cx + R * Math.cos(end);
    const y2 = cy + R * Math.sin(end);
    const d = `M${cx},${cy} L${x1.toFixed(2)},${y1.toFixed(2)} A${R},${R} 0 ${large} 1 ${x2.toFixed(2)},${y2.toFixed(2)} z`;
    angle = end;
    return { d, color: PALETTE[i % PALETTE.length], s };
  });

  return (
    <svg viewBox="0 0 480 280" className="w-full" role="img" aria-label="Grafik lingkaran">
      {slices.map((sl, i) => (
        <path key={i} d={sl.d} fill={sl.color} stroke="#fff" strokeWidth={2} />
      ))}
      {series.map((s, i) => (
        <g key={i}>
          <rect x={268} y={40 + i * 26} width={12} height={12} rx={3} fill={PALETTE[i % PALETTE.length]} />
          <text x={288} y={50 + i * 26} fontSize={12} fill="rgba(0,0,0,0.75)">
            {s.label} — {fmtNum(s.value)} ({Math.round((s.value / total) * 100)}%)
          </text>
        </g>
      ))}
    </svg>
  );
}
