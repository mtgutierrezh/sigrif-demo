import { useId, useMemo } from "react";

import type { HistoryPoint } from "../features/zones/types";
import { formatScore, formatShortTime } from "../lib/format";
import { riskColor } from "../lib/risk";

interface RiskHistoryProps {
  points: HistoryPoint[];
  loading?: boolean;
}

export function RiskHistory({ points, loading = false }: RiskHistoryProps) {
  const gradientId = useId().replace(/:/g, "");
  const series = useMemo(
    () =>
      [...points]
        .filter((point) => point.risk_score !== null)
        .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()),
    [points],
  );

  if (loading) {
    return (
      <div className="mt-5">
        <div className="skeleton h-[120px] w-full" />
      </div>
    );
  }

  if (series.length === 0) {
    return (
      <p className="mt-5 border-t border-iron pt-4 font-mono text-[12px] text-ash">
        Aún no hay historial de riesgo para esta zona.
      </p>
    );
  }

  const width = 320;
  const height = 120;
  const padding = 10;
  const maxPoints = Math.max(series.length - 1, 1);
  const x = (index: number) => padding + (index / maxPoints) * (width - padding * 2);
  const y = (score: number) => height - padding - score * (height - padding * 2);
  const line = series.map((point, index) => `${x(index)},${y(point.risk_score ?? 0)}`).join(" ");
  const area = `${x(0)},${height - padding} ${line} ${x(series.length - 1)},${height - padding}`;
  const first = series[0];
  const last = series[series.length - 1];
  const delta = (last.risk_score ?? 0) - (first.risk_score ?? 0);

  return (
    <section className="mt-5 border-t border-iron pt-4" aria-labelledby="historial-titulo">
      <div className="flex items-center justify-between">
        <h3 id="historial-titulo" className="font-mono text-[12px] uppercase tracking-[0.08em] text-bone">
          Historial de riesgo
        </h3>
        <span className="font-mono text-[11px] text-ash">
          {delta >= 0 ? "+" : ""}
          {formatScore(delta)}
        </span>
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="mt-3 h-[120px] w-full"
        role="img"
        aria-label={`Historial de ${series.length} lecturas, desde ${formatShortTime(first.created_at)} hasta ${formatShortTime(last.created_at)}`}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#ebfc72" stopOpacity="0.28" />
            <stop offset="1" stopColor="#ebfc72" stopOpacity="0" />
          </linearGradient>
        </defs>
        <line x1={padding} y1={y(0.4)} x2={width - padding} y2={y(0.4)} stroke="#404040" strokeDasharray="2 4" />
        <line x1={padding} y1={y(0.7)} x2={width - padding} y2={y(0.7)} stroke="#404040" strokeDasharray="2 4" />
        <polygon points={area} fill={`url(#${gradientId})`} />
        <polyline points={line} fill="none" stroke="#f4f3e8" strokeWidth="1.5" />
        {series.map((point, index) => (
          <circle
            key={`${point.created_at}-${index}`}
            cx={x(index)}
            cy={y(point.risk_score ?? 0)}
            r="2.5"
            fill={riskColor(point.risk_level)}
            stroke="#13140e"
            strokeWidth="1"
          >
            <title>
              {formatShortTime(point.created_at)} · {point.risk_level ?? "Sin dato"} ·{" "}
              {formatScore(point.risk_score)}
            </title>
          </circle>
        ))}
      </svg>

      <div className="flex justify-between font-mono text-[10px] text-ash">
        <span>{formatShortTime(first.created_at)}</span>
        <span>{formatShortTime(last.created_at)}</span>
      </div>

      <table className="sr-only">
        <caption>Historial de riesgo</caption>
        <thead>
          <tr>
            <th scope="col">Hora</th>
            <th scope="col">Nivel</th>
            <th scope="col">Score</th>
          </tr>
        </thead>
        <tbody>
          {series.map((point, index) => (
            <tr key={`${point.created_at}-fila-${index}`}>
              <td>{formatShortTime(point.created_at)}</td>
              <td>{point.risk_level ?? "Sin dato"}</td>
              <td>{formatScore(point.risk_score)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
