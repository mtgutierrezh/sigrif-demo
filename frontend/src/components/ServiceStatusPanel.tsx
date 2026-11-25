import { AlertTriangle, RefreshCw, Server } from "lucide-react";

import type { ServicesStatus } from "../features/zones/types";
import { formatDateTime, formatNumber } from "../lib/format";

const STATUS_LABELS: Record<string, string> = {
  ok: "Operativo",
  degraded: "Degradado",
  down: "Sin conexión",
  disabled: "Deshabilitado",
  sin_datos: "Sin datos",
};

const STATUS_TEXT: Record<string, string> = {
  ok: "text-surveyor",
  degraded: "text-ember",
  down: "text-ember",
  disabled: "text-ash",
  sin_datos: "text-ash",
};

interface ServiceStatusPanelProps {
  data: ServicesStatus | undefined;
  loading: boolean;
  error: boolean;
  onRetry: () => void;
}

export function ServiceStatusPanel({ data, loading, error, onRetry }: ServiceStatusPanelProps) {
  const overall = data?.status ?? "sin_datos";
  return (
    <section className="border border-iron p-5" aria-labelledby="servicios-titulo">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Server size={16} strokeWidth={1.5} className="text-surveyor" aria-hidden="true" />
          <h2 id="servicios-titulo" className="text-[22px] tracking-[-0.03em]">
            Estado de servicios
          </h2>
        </div>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={onRetry}
          disabled={loading}
          aria-label="Actualizar el estado de los servicios"
        >
          <RefreshCw size={15} strokeWidth={1.5} aria-hidden="true" />
          {loading ? "Consultando…" : "Actualizar"}
        </button>
      </div>

      <p className="mt-3 font-mono text-[11px] text-ash" role="status" aria-live="polite">
        {error
          ? "No pudimos consultar el estado de los servicios."
          : data
            ? `Estado general: ${STATUS_LABELS[overall] ?? overall} · ${formatDateTime(data.checked_at)}`
            : "Consultando servicios…"}
      </p>

      {error ? (
        <div className="mt-4 flex items-center gap-2 border border-iron p-3 text-ember">
          <AlertTriangle size={16} strokeWidth={1.5} aria-hidden="true" />
          <span className="font-mono text-[11px]">Revisa la conexión con la API.</span>
        </div>
      ) : (
        <ul className="mt-4 grid gap-px bg-iron sm:grid-cols-2 lg:grid-cols-3">
          {(data?.services ?? []).map((service) => (
            <li key={service.key} className="bg-obsidian px-4 py-4">
              <div className="flex items-center justify-between gap-3">
                <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">
                  {service.label}
                </span>
                <span className={`font-mono text-[11px] ${STATUS_TEXT[service.status] ?? "text-ash"}`}>
                  {STATUS_LABELS[service.status] ?? service.status}
                </span>
              </div>
              <p className="mt-2 font-mono text-[11px] leading-relaxed text-bone-muted">
                {service.detail}
              </p>
            </li>
          ))}
        </ul>
      )}

      {data ? (
        <p className="mt-3 font-mono text-[10px] text-ash">
          Frescura {data.freshness_minutes === null ? "sin dato" : `${formatNumber(data.freshness_minutes, 0)} min`} ·
          cola {data.queue_depth === null ? "sin dato" : `${data.queue_depth} mensajes`} ·{" "}
          {data.stale ? "datos desactualizados" : "datos vigentes"}
        </p>
      ) : null}
    </section>
  );
}
