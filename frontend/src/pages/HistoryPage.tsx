import { AlertTriangle, History, RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";

import { PageLoader } from "../components/PageLoader";
import { RiskBadge } from "../components/RiskBadge";
import { useSession } from "../components/session";
import type { RiskLevel } from "../features/zones/types";
import { useEvaluations } from "../features/zones/useEvaluations";
import { useZones } from "../features/zones/useZones";
import { actorLabel } from "../lib/actor";
import { formatDateTime, formatScore } from "../lib/format";
import { zoneLabel } from "../lib/names";

const LEVELS: Array<RiskLevel | "todos"> = ["todos", "Bajo", "Medio", "Alto"];

export default function HistoryPage() {
  const { canSimulate } = useSession();
  const [zoneId, setZoneId] = useState<number | null>(null);
  const [level, setLevel] = useState<RiskLevel | "todos">("todos");
  const zones = useZones();
  const evaluations = useEvaluations({
    zoneId,
    riskLevel: level === "todos" ? null : level,
  });

  const zoneById = useMemo(
    () => new Map((zones.data ?? []).map((zone) => [zone.id, zone])),
    [zones.data],
  );

  if (!canSimulate) {
    return (
      <div className="mx-auto flex min-h-[60dvh] max-w-[800px] flex-col justify-center px-5 py-16 md:px-8">
        <AlertTriangle size={28} strokeWidth={1.5} className="text-ember" aria-hidden="true" />
        <h1 className="mt-4 text-[34px] leading-tight tracking-[-0.03em]">
          Historial reservado para operadores.
        </h1>
        <p className="mt-3 max-w-lg text-bone-muted">
          Inicia sesión con una cuenta del grupo <span className="font-mono">operadores</span> para
          revisar las evaluaciones registradas, su modelo y el usuario que las generó.
        </p>
      </div>
    );
  }

  if (evaluations.isLoading) return <PageLoader />;

  if (evaluations.isError) {
    return (
      <div className="mx-auto flex min-h-[60dvh] max-w-[800px] flex-col justify-center px-5 py-16 md:px-8">
        <AlertTriangle size={28} strokeWidth={1.5} className="text-ember" aria-hidden="true" />
        <h1 className="mt-4 text-[34px] leading-tight tracking-[-0.03em]">
          No pudimos cargar el historial.
        </h1>
        <p className="mt-3 text-bone-muted">Revisa la conexión con la API y vuelve a intentar.</p>
        <button
          type="button"
          className="btn btn-primary mt-6 w-fit"
          onClick={() => void evaluations.refetch()}
        >
          <RefreshCw size={16} strokeWidth={1.5} aria-hidden="true" /> Reintentar
        </button>
      </div>
    );
  }

  const rows = evaluations.data ?? [];

  return (
    <div className="mx-auto max-w-[1200px] px-5 py-12 md:px-8 md:py-16">
      <p className="font-mono text-[12px] uppercase tracking-[0.14em] text-surveyor">
        Trazabilidad del modelo
      </p>
      <div className="mt-3 flex flex-wrap items-end justify-between gap-5">
        <div>
          <h1 className="text-[40px] leading-none tracking-[-0.03em] md:text-[56px]">
            Historial de evaluaciones
          </h1>
          <p className="mt-4 max-w-2xl text-bone-muted">
            Últimas 200 evaluaciones con fecha, zona, comuna, nivel, P(Alto), modelo y usuario.
            Esta vista está reservada al grupo operadores.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => void evaluations.refetch()}
          aria-label="Actualizar el historial de evaluaciones"
        >
          <RefreshCw size={16} strokeWidth={1.5} aria-hidden="true" /> Actualizar
        </button>
      </div>

      <div className="mt-10 grid gap-5 md:grid-cols-2">
        <label className="flex flex-col gap-1">
          <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">
            Filtrar por zona
          </span>
          <select
            className="input font-mono text-[12px] [color-scheme:dark]"
            value={zoneId ?? ""}
            onChange={(event) =>
              setZoneId(event.target.value ? Number(event.target.value) : null)
            }
          >
            <option value="">Todas las zonas</option>
            {(zones.data ?? []).map((zone) => (
              <option key={zone.id} value={zone.id}>
                {zoneLabel(zone.name, zone.display_name)} · {zone.comuna}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">
            Filtrar por nivel
          </span>
          <select
            className="input font-mono text-[12px] [color-scheme:dark]"
            value={level}
            onChange={(event) => setLevel(event.target.value as RiskLevel | "todos")}
          >
            {LEVELS.map((option) => (
              <option key={option} value={option}>
                {option === "todos" ? "Todos los niveles" : option}
              </option>
            ))}
          </select>
        </label>
      </div>

      <p className="mt-4 font-mono text-[11px] text-ash" role="status" aria-live="polite">
        {rows.length} evaluaciones en la vista actual.
      </p>

      <section className="mt-6 border border-iron p-5" aria-labelledby="tabla-historial">
        <div className="flex items-center gap-2">
          <History size={16} strokeWidth={1.5} className="text-surveyor" aria-hidden="true" />
          <h2 id="tabla-historial" className="text-[22px] tracking-[-0.03em]">
            Evaluaciones registradas
          </h2>
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[900px] text-left font-mono text-[11px]">
            <caption className="sr-only">
              Historial de evaluaciones filtrado por zona y nivel de riesgo
            </caption>
            <thead className="text-ash">
              <tr>
                <th className="pb-2 font-normal">Fecha</th>
                <th className="pb-2 font-normal">Zona</th>
                <th className="pb-2 font-normal">Comuna</th>
                <th className="pb-2 font-normal">Nivel</th>
                <th className="pb-2 font-normal">P(Alto)</th>
                <th className="pb-2 font-normal">Modelo</th>
                <th className="pb-2 font-normal">Usuario</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((evaluation) => {
                const zone = zoneById.get(evaluation.zone_id);
                return (
                  <tr key={evaluation.id} className="border-t border-iron">
                    <td className="whitespace-nowrap py-3 pr-3 text-ash">
                      {formatDateTime(evaluation.created_at)}
                    </td>
                    <td className="py-3 pr-3 text-bone">
                      {zoneLabel(
                        evaluation.zone_name || zone?.name || `Zona ${evaluation.zone_id}`,
                        zone?.display_name,
                      )}
                    </td>
                    <td className="py-3 pr-3 text-ash">
                      {evaluation.comuna || zone?.comuna || "Sin dato"}
                    </td>
                    <td className="py-3 pr-3">
                      <RiskBadge level={evaluation.risk_level} />
                    </td>
                    <td className="py-3 pr-3 text-bone">{formatScore(evaluation.risk_score)}</td>
                    <td className="py-3 pr-3 text-ash">{evaluation.model_version}</td>
                    <td className="py-3 text-ash">{actorLabel(evaluation.created_by)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {rows.length === 0 ? (
            <p className="mt-4 border border-iron p-5 font-mono text-[11px] text-ash">
              No hay evaluaciones para los filtros seleccionados.
            </p>
          ) : null}
        </div>
      </section>
    </div>
  );
}
