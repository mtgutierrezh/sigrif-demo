import type { Status } from "../features/zones/types";
import { formatDateTime, formatNumber } from "../lib/format";

export function TelemetryStrip({ status }: { status: Status | undefined }) {
  const metrics: Array<[string, string]> = [
    ["Zonas", status ? String(status.zones) : "—"],
    ["Última ingesta", formatDateTime(status?.last_ingest)],
    ["Modelo", status?.model_version ?? "—"],
    ["p95 API", status?.p95_ms ? `${formatNumber(status.p95_ms, 0)} ms` : "—"],
  ];

  return (
    <div className="telemetry bg-obsidian">
      {metrics.map(([label, value]) => (
        <div key={label} className="border-r border-iron px-4 py-4 last:border-r-0">
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-ash">{label}</p>
          <p className="mt-1 font-mono text-[13px] text-bone">{value}</p>
        </div>
      ))}
    </div>
  );
}
