import { AlertTriangle, ListOrdered, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";

import { PageLoader } from "../components/PageLoader";
import { RiskBadge } from "../components/RiskBadge";
import { useSession } from "../components/session";
import { usePriority } from "../features/zones/usePriority";
import type { PriorityLevel } from "../features/zones/types";
import { formatDateTime, formatNumber } from "../lib/format";
import { zoneLabel } from "../lib/names";

const PRIORITY_CLASSES: Record<PriorityLevel, string> = {
  Alta: "border border-ember text-ember",
  Media: "border border-surveyor text-surveyor",
  Baja: "border border-iron text-ash",
};

const WEIGHT_LABELS: Record<string, string> = {
  alto_probability: "P(Alto)",
  vegetation: "Vegetación",
  historical_fires: "Incendios históricos",
  slope: "Pendiente",
  population_density: "Densidad de población",
};

export default function PriorityPage() {
  const { canSimulate } = useSession();
  const priority = usePriority(20);

  if (!canSimulate) {
    return (
      <div className="mx-auto flex min-h-[60dvh] max-w-[800px] flex-col justify-center px-5 py-16 md:px-8">
        <AlertTriangle size={28} strokeWidth={1.5} className="text-ember" aria-hidden="true" />
        <h1 className="mt-4 text-[34px] leading-tight tracking-[-0.03em]">
          Priorización reservada para operadores.
        </h1>
        <p className="mt-3 max-w-lg text-bone-muted">
          Inicia sesión con una cuenta del grupo <span className="font-mono">operadores</span> para
          revisar el ranking territorial y sus componentes.
        </p>
      </div>
    );
  }

  if (priority.isLoading) return <PageLoader />;

  if (priority.isError || !priority.data) {
    return (
      <div className="mx-auto flex min-h-[60dvh] max-w-[800px] flex-col justify-center px-5 py-16 md:px-8">
        <AlertTriangle size={28} strokeWidth={1.5} className="text-ember" aria-hidden="true" />
        <h1 className="mt-4 text-[34px] leading-tight tracking-[-0.03em]">
          No pudimos calcular la prioridad.
        </h1>
        <p className="mt-3 text-bone-muted">Revisa la conexión con la API y vuelve a intentar.</p>
        <button
          type="button"
          className="btn btn-primary mt-6 w-fit"
          onClick={() => void priority.refetch()}
        >
          <RefreshCw size={16} strokeWidth={1.5} aria-hidden="true" /> Reintentar
        </button>
      </div>
    );
  }

  const data = priority.data;
  const coverage = data.population_coverage;
  const coveragePercent =
    coverage.total > 0 ? Math.round((coverage.known / coverage.total) * 100) : 0;

  return (
    <div className="mx-auto max-w-[1200px] px-5 py-12 md:px-8 md:py-16">
      <p className="font-mono text-[12px] uppercase tracking-[0.14em] text-surveyor">
        Priorización territorial
      </p>
      <div className="mt-3 flex flex-wrap items-end justify-between gap-5">
        <div>
          <h1 className="text-[40px] leading-none tracking-[-0.03em] md:text-[56px]">
            Prioridad operativa
          </h1>
          <p className="mt-4 max-w-2xl text-bone-muted">
            Ranking explicable de las zonas con mayor necesidad de revisión preventiva. Combina la
            probabilidad del modelo con vegetación, incendios históricos, pendiente y densidad de
            población.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => void priority.refetch()}
          aria-label="Actualizar el ranking de prioridad"
        >
          <RefreshCw size={16} strokeWidth={1.5} aria-hidden="true" /> Actualizar
        </button>
      </div>

      <section className="mt-10 grid gap-px bg-iron sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["Zonas evaluadas", String(data.total_zones), "Base del ranking"],
          [
            "Cobertura de población",
            `${coverage.known} / ${coverage.total}`,
            `${coveragePercent} % con dato municipal`,
          ],
          ["P95 incendios", formatNumber(data.fires_p95, 1), "Normalización histórica"],
          [
            "P95 densidad",
            `${formatNumber(data.density_p95_log, 2)} log`,
            "Normalización de densidad",
          ],
        ].map(([label, value, hint]) => (
          <div key={label} className="bg-obsidian px-4 py-5">
            <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">{label}</p>
            <p className="mt-2 font-mono text-[24px] leading-none text-bone">{value}</p>
            <p className="mt-2 font-mono text-[10px] text-ash">{hint}</p>
          </div>
        ))}
      </section>

      <section className="mt-8 border border-iron p-5" aria-labelledby="ranking-prioridad">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex items-center gap-2">
            <ListOrdered size={16} strokeWidth={1.5} className="text-surveyor" aria-hidden="true" />
            <h2 id="ranking-prioridad" className="text-[22px] tracking-[-0.03em]">
              Top {data.items.length} zonas por prioridad
            </h2>
          </div>
          <p className="font-mono text-[10px] text-ash">
            Calculado {formatDateTime(data.generated_at)}
          </p>
        </div>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[980px] text-left font-mono text-[11px]">
            <caption className="sr-only">
              Ranking de prioridad operativa con score, nivel de riesgo, probabilidad de riesgo
              alto, población y densidad por zona
            </caption>
            <thead className="text-ash">
              <tr>
                <th className="pb-2 font-normal">#</th>
                <th className="pb-2 font-normal">Zona</th>
                <th className="pb-2 font-normal">Comuna</th>
                <th className="pb-2 font-normal">Nivel</th>
                <th className="pb-2 font-normal">Score</th>
                <th className="pb-2 font-normal">Prioridad</th>
                <th className="pb-2 font-normal">P(Alto)</th>
                <th className="pb-2 font-normal">Población</th>
                <th className="pb-2 font-normal">Densidad</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item) => (
                <tr key={item.zone_id} className="border-t border-iron">
                  <td className="py-3 pr-3 text-ash">{item.position}</td>
                  <td className="py-3 pr-3">
                    <Link
                      to={`/mapa?zona=${item.zone_id}`}
                      className="text-bone hover:text-surveyor"
                    >
                      {zoneLabel(item.zone_name)}
                    </Link>
                  </td>
                  <td className="py-3 pr-3 text-ash">{item.comuna}</td>
                  <td className="py-3 pr-3">
                    <RiskBadge level={item.risk_level} />
                  </td>
                  <td className="py-3 pr-3">
                    <div className="flex min-w-[130px] items-center gap-2">
                      <span className="h-1 flex-1 bg-iron" aria-hidden="true">
                        <span
                          className="block h-full bg-surveyor"
                          style={{ width: `${Math.min(100, item.score)}%` }}
                        />
                      </span>
                      <span className="w-10 text-right text-bone">
                        {formatNumber(item.score, 1)}
                      </span>
                    </div>
                  </td>
                  <td className="py-3 pr-3">
                    <span className={`badge ${PRIORITY_CLASSES[item.priority_level]}`}>
                      {item.priority_level}
                    </span>
                  </td>
                  <td className="py-3 pr-3 text-bone">
                    {formatNumber(item.alto_probability * 100, 0)} %
                  </td>
                  <td className="py-3 pr-3 text-bone">
                    {item.population_available && item.population !== null
                      ? formatNumber(item.population, 0)
                      : "Sin dato"}
                  </td>
                  <td className="py-3 text-ash">
                    {item.density_available && item.population_density !== null
                      ? `${formatNumber(item.population_density, 1)} hab/ha`
                      : "Sin dato"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.items.length === 0 ? (
            <p className="mt-4 border border-iron p-5 font-mono text-[11px] text-ash">
              No hay zonas disponibles para calcular la prioridad.
            </p>
          ) : null}
        </div>

        <div className="mt-6 grid gap-4 border-t border-iron pt-5 lg:grid-cols-[1.2fr_0.8fr]">
          <div>
            <h3 className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">
              Lectura del índice
            </h3>
            <p className="mt-2 text-[14px] text-bone-muted">{data.methodology_note}</p>
            <p className="mt-3 font-mono text-[10px] text-ash">
              Nivel de prioridad: alta ≥ {data.thresholds.alta} · media ≥ {data.thresholds.media}.
            </p>
          </div>
          <div>
            <h3 className="font-mono text-[10px] uppercase tracking-[0.1em] text-ash">
              Pesos base
            </h3>
            <ul className="mt-2 space-y-1 font-mono text-[11px]">
              {Object.entries(data.weights).map(([key, weight]) => (
                <li key={key} className="flex justify-between gap-3">
                  <span className="text-bone">{WEIGHT_LABELS[key] ?? key}</span>
                  <span className="text-ash">{formatNumber(weight * 100, 0)} %</span>
                </li>
              ))}
            </ul>
            <p className="mt-2 font-mono text-[10px] text-ash">
              Si falta población o área válida, el peso restante se renormaliza.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
